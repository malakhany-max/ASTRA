import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CircleStop, HeartPulse, Pause, Play, RotateCcw, Volume2, VolumeX, Wind } from 'lucide-react'
import type { AstronautSettings, BreathingPhase, BreathingTechnique, Indicator } from '@contracts'
import {
  apiGet,
  formatClock,
  speak,
  stopSpeaking,
  useApi,
  useToast,
} from '@astra/shared'
import { ASTRONAUT_ID } from '../lib/astro'
import { BREATHING_FALLBACK } from '../lib/breathing'

const PHASE_WORD: Record<BreathingPhase['label'], string> = {
  inhale: 'Breathe in',
  hold: 'Hold',
  exhale: 'Breathe out',
  pause: 'Rest',
}

const LENGTHS = [1, 3, 5]

interface PhaseNow {
  phase: BreathingPhase
  index: number
  remaining: number
}

function phaseAt(phases: BreathingPhase[], elapsed: number): PhaseNow {
  if (phases.length === 0) {
    return { phase: { label: 'pause', seconds: 1 }, index: -1, remaining: 0 }
  }
  const cycle = phases.reduce((sum, phase) => sum + phase.seconds, 0)
  const position = cycle > 0 ? elapsed % cycle : 0
  let cursor = 0
  for (let index = 0; index < phases.length; index += 1) {
    const phase = phases[index]
    if (position < cursor + phase.seconds) {
      return { phase, index, remaining: Math.max(0, phase.seconds - (position - cursor)) }
    }
    cursor += phase.seconds
  }
  const last = phases[phases.length - 1]
  return { phase: last, index: phases.length - 1, remaining: last.seconds }
}

export function BreathingPage() {
  const toast = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const techniques = useApi<BreathingTechnique[]>('/api/companion/breathing')
  const settings = useApi<AstronautSettings>(`/api/astronauts/${ASTRONAUT_ID}/settings`)

  const available = techniques.data?.length ? techniques.data : techniques.error ? BREATHING_FALLBACK : []
  const selectedId = searchParams.get('technique') ?? available[0]?.id ?? ''
  const technique = available.find((item) => item.id === selectedId) ?? available[0] ?? null

  const [minutes, setMinutes] = useState(3)
  const [running, setRunning] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [finished, setFinished] = useState(false)
  const [beforeHr, setBeforeHr] = useState<number | null>(null)
  const [afterHr, setAfterHr] = useState<number | null>(null)
  const [voiceOn, setVoiceOn] = useState(true)
  const voiceTouched = useRef(false)
  const phaseRef = useRef(-1)

  useEffect(() => {
    if (settings.data && !voiceTouched.current) setVoiceOn(settings.data.voice)
  }, [settings.data])

  useEffect(() => {
    if (technique) setMinutes((current) => (LENGTHS.includes(current) ? current : technique.defaultMinutes))
  }, [technique?.id])

  useEffect(() => () => stopSpeaking(), [])

  const duration = minutes * 60
  const phases = technique?.phases ?? []
  const now = useMemo(() => phaseAt(phases, elapsed), [phases, elapsed])

  useEffect(() => {
    if (!running) return
    const id = window.setInterval(() => {
      setElapsed((value) => Math.min(duration, value + 0.25))
    }, 250)
    return () => window.clearInterval(id)
  }, [running, duration])

  useEffect(() => {
    if (!running) return
    if (elapsed < duration) return
    setRunning(false)
    setFinished(true)
    void captureHeartRate(setAfterHr)
    if (voiceOn) speak('Session complete. Notice how your body feels now.')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [elapsed, running, duration])

  useEffect(() => {
    if (!running || !technique) return
    if (now.index === phaseRef.current) return
    phaseRef.current = now.index
    if (voiceOn) speak(PHASE_WORD[now.phase.label])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [now.index, running, voiceOn])

  async function captureHeartRate(setter: (value: number | null) => void) {
    try {
      const list = await apiGet<Indicator[]>(`/api/astronauts/${ASTRONAUT_ID}/indicators`)
      const heartRate = list.find((indicator) => indicator.key === 'heartRate')
      setter(heartRate ? Math.round(heartRate.value) : null)
    } catch {
      setter(null)
    }
  }

  function start() {
    if (elapsed >= duration) setElapsed(0)
    setFinished(false)
    setAfterHr(null)
    if (beforeHr === null) void captureHeartRate(setBeforeHr)
    setRunning(true)
    toast({ title: 'Session started', message: 'Follow the circle. Pause any time — the timer waits for you.', severity: 'info' })
  }

  function stop() {
    setRunning(false)
    setElapsed(0)
    setFinished(false)
    setAfterHr(null)
    phaseRef.current = -1
    stopSpeaking()
  }

  function choose(id: string) {
    stop()
    setSearchParams({ technique: id })
    setElapsed(0)
    phaseRef.current = -1
  }

  const unpaced = phases.length === 0
  const scale = !running || unpaced
    ? 0.82
    : now.phase.label === 'inhale' || now.phase.label === 'hold'
      ? 1
      : 0.58
  const orbStyle = {
    transform: `scale(${scale})`,
    transitionDuration: `${Math.max(0.3, now.phase.seconds)}s`,
  } as CSSProperties
  const progress = duration > 0 ? Math.min(100, (elapsed / duration) * 100) : 0

  return (
    <section className="page breathing-page">
      <header className="page-head">
        <div className="page-head__title">
          <span className="eyebrow">Breathing</span>
          <h1>Slow the room down</h1>
          <p className="muted">The circle grows as you breathe in and settles as you breathe out. Follow it, or just sit with it.</p>
        </div>
        <button
          type="button"
          className={`btn btn--ghost${voiceOn ? ' btn--selected' : ''}`}
          onClick={() => {
            voiceTouched.current = true
            setVoiceOn((current) => !current)
            if (voiceOn) stopSpeaking()
          }}
          aria-pressed={voiceOn}
        >
          {voiceOn ? <Volume2 size={16} aria-hidden="true" /> : <VolumeX size={16} aria-hidden="true" />}
          {voiceOn ? 'Voice on' : 'Voice off'}
        </button>
      </header>

      <div className="split">
        <div className="panel breathing-stage">
          {!technique && !techniques.error && <span className="skeleton" style={{ height: 360 }} />}
          {techniques.error && available.length > 0 && (
            <p className="muted tiny" role="status">The companion service is offline. These built-in techniques work without it.</p>
          )}

          {technique && (
            <>
              <div className="breathing-orb-wrap">
                <div className="breathing-orb-halo" aria-hidden="true" />
                <div className="breathing-orb" style={orbStyle} aria-hidden="true">
                  <div className="breathing-orb__core" />
                </div>
                <div className="breathing-center">
                  <span className="breathing-phase" aria-live="polite">{running ? (unpaced ? 'Breathe naturally' : PHASE_WORD[now.phase.label]) : finished ? 'Done' : 'Ready'}</span>
                  <span className="breathing-count numeric">{running ? Math.ceil(unpaced ? duration - elapsed : now.remaining) : formatClock(duration)}</span>
                  <span className="faint tiny">{technique.name}</span>
                </div>
              </div>

              <div className="meter" aria-hidden="true">
                <span style={{ width: `${progress}%` }} />
              </div>

              <div className="row row--between row--wrap">
                <div className="row row--wrap">
                  {!running ? (
                    <button type="button" className="btn btn--primary btn--lg" onClick={start}>
                      <Play size={17} aria-hidden="true" /> {elapsed > 0 && elapsed < duration ? 'Resume' : 'Start'}
                    </button>
                  ) : (
                    <button type="button" className="btn btn--calm btn--lg" onClick={() => setRunning(false)}>
                      <Pause size={17} aria-hidden="true" /> Pause
                    </button>
                  )}
                  <button type="button" className="btn btn--ghost" onClick={stop} disabled={elapsed === 0 && !running}>
                    <CircleStop size={16} aria-hidden="true" /> Stop
                  </button>
                  <button type="button" className="btn btn--ghost" onClick={() => { stop(); setElapsed(0) }}>
                    <RotateCcw size={16} aria-hidden="true" /> Reset
                  </button>
                </div>
                <div className="segmented" role="group" aria-label="Session length">
                  {LENGTHS.map((length) => (
                    <button
                      key={length}
                      type="button"
                      aria-pressed={minutes === length}
                      onClick={() => {
                        stop()
                        setMinutes(length)
                      }}
                    >
                      {length} min
                    </button>
                  ))}
                </div>
              </div>

              {finished && (
                <div className="breathing-result" role="status">
                  <HeartPulse size={18} aria-hidden="true" />
                  <div>
                    <div className="strong small">How your body responded</div>
                    {beforeHr !== null && afterHr !== null ? (
                      <div className="faint small">
                        Heart rate {beforeHr} → {afterHr} bpm. {afterHr < beforeHr
                          ? `That is ${beforeHr - afterHr} bpm lower in this session — one reading, not a promise.`
                          : 'Roughly unchanged, or a little higher. That happens too; the calm usually lands before the number moves.'}
                      </div>
                    ) : (
                      <div className="faint small">Heart-rate readings were not available for this session. How do you feel right now is the honest measure.</div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="stack">
          <div className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Techniques</h2>
              <span className="faint tiny">{available.length} available</span>
            </div>
            <div className="stack stagger" style={{ gap: 10 }}>
              {available.map((item, index) => (
                <button
                  key={item.id}
                  type="button"
                  className={`technique-card${item.id === technique?.id ? ' is-selected' : ''}`}
                  aria-pressed={item.id === technique?.id}
                  onClick={() => choose(item.id)}
                  style={{ '--i': index } as CSSProperties}
                >
                  <div className="row row--between">
                    <span className="strong small">{item.name}</span>
                    <span className="badge"><Wind size={12} aria-hidden="true" /> {item.defaultMinutes} min</span>
                  </div>
                  <span className="faint tiny">{item.description}</span>
                  <span className="technique-card__phases">
                    {item.phases.map((phase, index) => (
                      <span key={`${item.id}-${index}`} className="phase-pill">{phase.label} {phase.seconds}s</span>
                    ))}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="panel panel--glow">
            <span className="eyebrow eyebrow--violet">Why it works here</span>
            <ul className="mini-list muted small" style={{ marginTop: 10 }}>
              <li>A longer exhale nudges the pulse down without equipment.</li>
              <li>No screen staring required — the voice keeps the count for you.</li>
              <li>Works with the harness on, in a seat, or inside the shelter.</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  )
}
