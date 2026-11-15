import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Mic, MicOff, Send, ShieldCheck, Sparkles, Volume2, VolumeX } from 'lucide-react'
import type { AstronautSettings, CompanionAction, CompanionMessage, CompanionReply, Indicator, LinkState } from '@contracts'
import {
  USE_MOCK,
  apiGet,
  apiPost,
  errorMessage,
  formatTime,
  apiPostAudio,
  apiPostWav,
  isArabicText,
  listenOnce,
  recognitionAvailable,
  speak,
  speechSupported,
  startWavRecording,
  useApi,
  useToast,
} from '@astra/shared'
import { ASTRONAUT_ID } from '../lib/astro'
import type { ListenError, WavRecording } from '@astra/shared'

const QUICK_PROMPTS = [
  'My sleep was short last night.',
  'I feel dizzy when I stand up.',
  'I am worried about the solar storm.',
  'I feel tense and cannot settle.',
  'نومي كان قليل الليلة الماضية.',
  'بحس بدوخة لما أقف.',
  'قلقان من العاصفة الشمسية.',
  'متوتر ومش قادر أهدى.',
]

const ACTION_ROUTES: Record<CompanionAction['kind'], string | null> = {
  breathing: '/breathing',
  checkin: '/checkin',
  plan: '/plan',
  shelter: '/radiation',
  none: null,
}

const LISTEN_ERROR_MESSAGES: Partial<Record<ListenError, string>> = {
  'not-allowed': 'Microphone permission is blocked. Allow it in the browser, or type instead.',
  'service-not-allowed': 'The browser blocked voice input. Allow it in the browser, or type instead.',
  'no-speech': 'No speech was detected. Tap the mic and try again, or type instead.',
  network: 'Browser voice input needs a connection. Type instead, or stage the local speech model.',
  'audio-capture': 'No microphone was found. Connect one or type instead.',
}

export function CompanionPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const transcript = useApi<CompanionMessage[]>(`/api/companion/transcript/${ASTRONAUT_ID}`, {
    live: true,
    livePrefixes: ['companion'],
  })
  const settings = useApi<AstronautSettings>(`/api/astronauts/${ASTRONAUT_ID}/settings`)
  const indicators = useApi<Indicator[]>(`/api/astronauts/${ASTRONAUT_ID}/indicators`)
  const link = useApi<LinkState>('/api/link/state', { live: true })
  const tts = useApi<{ available: boolean; detail?: string }>('/api/companion/tts/status')

  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [listening, setListening] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [voiceOn, setVoiceOn] = useState(true)

  const streamRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const recordingRef = useRef<WavRecording | null>(null)
  const browserListenRef = useRef<(() => void) | null>(null)
  const startingRef = useRef(false)
  const sttStatusRef = useRef<Promise<boolean> | null>(null)
  const browserNoticeRef = useRef(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const audioUrlRef = useRef<string | null>(null)
  const voiceTouched = useRef(false)
  const voiceNoticeRef = useRef(false)

  function voiceUnavailable() {
    if (voiceNoticeRef.current) return false
    voiceNoticeRef.current = true
    toast({ title: 'Local voice not installed', message: 'Spoken replies fall back to the browser or stay on screen. Text replies always work.', severity: 'info' })
    return true
  }

  useEffect(() => {
    if (settings.data && !voiceTouched.current) setVoiceOn(settings.data.voice)
  }, [settings.data])

  useEffect(() => () => {
    void recordingRef.current?.cancel()
    browserListenRef.current?.()
    audioRef.current?.pause()
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current)
  }, [])

  useEffect(() => {
    const node = streamRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [transcript.data?.length, sending])

  async function send(raw?: string) {
    const value = (raw ?? text).trim()
    if (!value || sending) return
    setSending(true)
    setError(null)
    try {
      const result = await apiPost<CompanionReply>('/api/companion/message', {
        astronautId: ASTRONAUT_ID,
        text: value,
        tone: settings.data?.tone ?? 'calm',
        language: 'en' as const,
        mode: link.data?.state === 'connected' ? 'connected' : 'autonomous',
        statusSummary: (indicators.data ?? []).filter((item) => item.status !== 'normal').map((item) => ({
          astronaut_id: ASTRONAUT_ID,
          indicator: item.key,
          status: item.status,
          reasons: [item.reason],
        })),
        dizzinessReported: (indicators.data ?? []).some((item) => item.key === 'dizziness' && item.value > 0),
      })
      setText('')
      transcript.reload()
      if (voiceOn && result.reply.text) {
        if (isArabicText(result.reply.text)) {
          if (!speechSupported() || !speak(result.reply.text)) voiceUnavailable()
        } else if (tts.data?.available === false) {
          voiceUnavailable()
          if (speechSupported()) speak(result.reply.text)
        } else {
          try {
            const audio = await apiPostAudio('/api/companion/tts', { text: result.reply.text })
            if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current)
            audioUrlRef.current = URL.createObjectURL(audio)
            audioRef.current = new Audio(audioUrlRef.current)
            await audioRef.current.play()
          } catch {
            if (!speechSupported() || !speak(result.reply.text)) {
              voiceUnavailable()
            }
          }
        }
      }
    } catch (err) {
      setError(errorMessage(err))
      toast({ title: 'Message not sent', message: errorMessage(err), severity: 'attention' })
    } finally {
      setSending(false)
    }
  }

  function runAction(action: CompanionAction) {
    const route = ACTION_ROUTES[action.kind]
    if (!route) return
    const target = action.kind === 'breathing' && action.payload ? `${route}?technique=${action.payload}` : route
    navigate(target)
  }

  function localSttReady(): Promise<boolean> {
    if (USE_MOCK) return Promise.resolve(false)
    sttStatusRef.current ??= apiGet<{ available: boolean }>('/api/companion/stt/status')
      .then((status) => Boolean(status.available))
      .catch(() => false)
    return sttStatusRef.current
  }

  function startBrowserListening(): boolean {
    let heard = false
    let reported = false
    const stop = listenOnce(
      (value) => {
        heard = true
        setText(value)
        textareaRef.current?.focus()
      },
      () => {
        browserListenRef.current = null
        setListening(false)
        if (!heard && !reported) {
          toast({ title: 'No speech detected', message: 'The browser did not write any words. Tap the mic and try again, or type instead.', severity: 'attention' })
        }
      },
      {
        onInterim: (value) => {
          heard = true
          setText(value)
        },
        onError: (reason) => {
          const message = LISTEN_ERROR_MESSAGES[reason]
          if (message) {
            reported = true
            toast({ title: 'Voice input stopped', message, severity: 'attention' })
          }
        },
      },
    )
    if (!stop) return false
    browserListenRef.current = stop
    setListening(true)
    if (!browserNoticeRef.current && !USE_MOCK) {
      browserNoticeRef.current = true
      toast({ title: 'Browser voice input', message: 'The local speech model is not configured, so the browser is listening. Chrome may process speech online.', severity: 'info' })
    }
    return true
  }

  async function stopAndTranscribe(recording: WavRecording) {
    setListening(false)
    setTranscribing(true)
    try {
      const wav = await recording.stop()
      const result = await apiPostWav<{ text: string }>('/api/companion/stt', wav)
      const spoken = result.text?.trim()
      if (spoken) {
        setText(spoken)
        textareaRef.current?.focus()
      } else {
        toast({ title: 'No speech detected', message: 'Nothing was transcribed. Tap the mic and try again, or type instead.', severity: 'attention' })
        textareaRef.current?.focus()
      }
    } catch (cause) {
      if (startBrowserListening()) {
        toast({ title: 'Using browser voice input', message: `${errorMessage(cause)}. Speak again and the browser will write it for you.`, severity: 'info' })
      } else {
        toast({ title: 'Voice input unavailable', message: errorMessage(cause), severity: 'attention' })
        textareaRef.current?.focus()
      }
    } finally {
      setTranscribing(false)
    }
  }

  async function beginRecording(): Promise<boolean> {
    try {
      recordingRef.current = await startWavRecording()
      setListening(true)
      return true
    } catch {
      return false
    }
  }

  async function toggleMic() {
    if (transcribing || startingRef.current) return
    if (browserListenRef.current) {
      browserListenRef.current()
      browserListenRef.current = null
      setListening(false)
      return
    }
    if (recordingRef.current) {
      const recording = recordingRef.current
      recordingRef.current = null
      await stopAndTranscribe(recording)
      return
    }
    startingRef.current = true
    try {
      if (await localSttReady() && await beginRecording()) return
      if (startBrowserListening()) return
      if (USE_MOCK && await beginRecording()) return
      toast({
        title: 'Voice input unavailable',
        message: recognitionAvailable()
          ? 'The microphone could not start. Allow access or type instead.'
          : 'This browser does not support speech input and the local speech model is not configured, so please type instead.',
        severity: 'attention',
      })
      textareaRef.current?.focus()
    } finally {
      startingRef.current = false
    }
  }

  const messages = transcript.data ?? []
  const lastMessage = messages[messages.length - 1]

  return (
    <section className="page companion-page">
      <header className="page-head">
        <div className="page-head__title">
          <span className="eyebrow eyebrow--violet">Companion</span>
          <h1>Talk it through</h1>
          <p className="muted">Short answers, one small next step. The companion never diagnoses, and it passes a short note to the flight medical team when you describe a symptom.</p>
          {voiceOn && tts.data?.available === false && (
            <p className="faint small" role="status">Local voice model is not installed; spoken replies fall back to the browser or stay on screen.</p>
          )}
        </div>
        <button
          type="button"
          className={`btn btn--ghost${voiceOn ? ' btn--selected' : ''}`}
          onClick={() => {
            voiceTouched.current = true
            setVoiceOn((current) => !current)
            if (voiceOn) audioRef.current?.pause()
          }}
          aria-pressed={voiceOn}
          aria-label={voiceOn ? 'Turn spoken replies off' : 'Turn spoken replies on'}
        >
          {voiceOn ? <Volume2 size={16} aria-hidden="true" /> : <VolumeX size={16} aria-hidden="true" />}
          {voiceOn ? 'Voice on' : 'Voice off'}
        </button>
      </header>

      <div className="split">
        <div className="panel panel--flush companion-window">
          <div className="companion-window__head">
            <div className="row">
              <span className="companion-avatar" aria-hidden="true"><Sparkles size={16} /></span>
              <div>
                <div className="strong small">Astra companion</div>
                <div className="faint tiny">{sending ? 'Typing…' : 'Ready when you are'}</div>
              </div>
            </div>
            <span className="badge"><ShieldCheck size={12} aria-hidden="true" /> Private to your consent</span>
          </div>

          <div className="companion-stream" ref={streamRef} aria-live="polite" aria-relevant="additions">
            {!transcript.data && (
              <div className="stack">
                <span className="skeleton" style={{ height: 54, borderRadius: 18, width: '72%' }} />
                <span className="skeleton" style={{ height: 74, borderRadius: 18, width: '86%', alignSelf: 'flex-end' }} />
              </div>
            )}
            {transcript.error && <p className="auth-error small" role="alert">{transcript.error}</p>}

            {messages.map((message) => (
              <div key={message.id} className={`bubble-row bubble-row--${message.role}`}>
                <div className={`bubble bubble--${message.role}`}>
                  <p dir="auto">{message.text}</p>
                  <span className="bubble__meta">{formatTime(message.createdAt)}</span>
                </div>
                {message.role === 'companion' && message.actions && message.actions.length > 0 && (
                  <div className="bubble-actions">
                    {message.actions.map((action) => (
                      <button key={action.id} type="button" className="btn btn--calm btn--sm" onClick={() => runAction(action)}>
                        {action.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {sending && (
              <div className="bubble-row bubble-row--companion">
                <div className="bubble bubble--companion bubble--typing" aria-label="Companion is typing">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </div>
              </div>
            )}
          </div>

          {error && <p className="auth-error small" role="alert">{error}</p>}

          <div className="composer">
            <textarea
              ref={textareaRef}
              className="composer__input"
              rows={2}
              dir="auto"
              value={text}
              onChange={(event) => setText(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  void send()
                }
              }}
              placeholder={
                transcribing
                  ? 'Transcribing your voice…'
                  : listening
                    ? (browserListenRef.current ? 'Listening — speak normally…' : 'Recording — tap the mic to stop…')
                    : 'Say what feels heaviest right now…'
              }
              aria-label="Message the companion"
            />
            <div className="composer__actions">
              <button
                type="button"
                className={`btn btn--icon btn--ghost${listening || transcribing ? ' is-listening' : ''}`}
                onClick={toggleMic}
                disabled={transcribing}
                aria-pressed={listening}
                aria-busy={transcribing}
                aria-label={transcribing ? 'Transcribing voice input' : listening ? 'Stop listening' : 'Speak instead of typing'}
              >
                {listening || transcribing ? <Mic size={18} aria-hidden="true" /> : <MicOff size={18} aria-hidden="true" />}
              </button>
              <button
                type="button"
                className="btn btn--primary"
                onClick={() => void send()}
                disabled={sending || text.trim().length === 0}
              >
                <Send size={16} aria-hidden="true" /> Send
              </button>
            </div>
          </div>
        </div>

        <div className="stack">
          <div className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Openers</h2>
              <span className="faint tiny">One tap</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              {QUICK_PROMPTS.map((prompt) => (
                <button key={prompt} type="button" className="quick-prompt" onClick={() => void send(prompt)} disabled={sending}>
                  <span>{prompt}</span>
                  <Send size={14} aria-hidden="true" />
                </button>
              ))}
            </div>
          </div>

          <div className="panel panel--glow">
            <span className="eyebrow eyebrow--violet">How it helps</span>
            <ul className="mini-list muted small" style={{ marginTop: 10 }}>
              <li>Names the feeling in one line, then suggests one small action.</li>
              <li>Sends a short note to the flight medical team when you describe a symptom.</li>
              <li>{voiceOn ? 'Replies can be spoken while you keep your hands free.' : 'Replies stay on screen while spoken replies are off.'}</li>
            </ul>
            {lastMessage && lastMessage.role === 'companion' && (
              <div className="faint tiny" style={{ marginTop: 12 }}>Last reply {formatTime(lastMessage.createdAt)} · transcript kept as your consent allows</div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
