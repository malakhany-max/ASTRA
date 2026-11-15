import { useState, type CSSProperties } from 'react'
import { CalendarCheck, CheckCircle2, MessageSquareText, Send } from 'lucide-react'
import type { Checkin, CheckinRequest } from '@contracts'
import { apiPost, errorMessage, relativeTime, useApi, useNow, useToast } from '@astra/shared'
import { ASTRONAUT_ID } from '../lib/astro'

const SYMPTOMS = ['poor sleep', 'headache', 'dizziness', 'nausea', 'fatigue', 'muscle ache', 'anxiety', 'poor appetite']

interface ScaleProps {
  label: string
  hint: string
  value: number
  min: number
  max: number
  low: string
  high: string
  onChange: (value: number) => void
}

function Scale({ label, hint, value, min, max, low, high, onChange }: ScaleProps) {
  return (
    <div className="scale">
      <div className="row row--between">
        <div>
          <span className="field__label">{label}</span>
          <div className="field__hint">{hint}</div>
        </div>
        <span className="scale__value numeric" aria-hidden="true">{value}</span>
      </div>
      <input className="scale__range" type="range" min={min} max={max} step={1} value={value} onChange={(event) => onChange(Number(event.target.value))} aria-label={label} aria-valuetext={`${value} of ${max}`} />
      <div className="row row--between faint tiny"><span>{low}</span><span>{high}</span></div>
    </div>
  )
}

export function CheckinPage() {
  const toast = useToast()
  const now = useNow(30_000)
  const checkins = useApi<Checkin[]>(`/api/astronauts/${ASTRONAUT_ID}/checkins`, { live: true, livePrefixes: ['checkin'] })
  const [mood, setMood] = useState(4)
  const [energy, setEnergy] = useState(3)
  const [dizziness, setDizziness] = useState(0)
  const [workload, setWorkload] = useState(3)
  const [symptoms, setSymptoms] = useState<string[]>([])
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<Checkin | null>(null)

  function toggleSymptom(symptom: string) {
    setSymptoms((current) => (current.includes(symptom) ? current.filter((item) => item !== symptom) : [...current, symptom]))
  }

  async function submit() {
    setBusy(true)
    setError(null)
    const payload: CheckinRequest = { astronautId: ASTRONAUT_ID, mood, energy, dizziness, workload, symptoms, note: note.trim() || undefined }
    try {
      const savedCheckin = await apiPost<Checkin>('/api/checkin', payload)
      setSaved(savedCheckin)
      setNote('')
      checkins.reload()
      toast({ title: 'Check-in saved', message: 'The ground medical team can see it now.', severity: 'info' })
    } catch (err) {
      setError(errorMessage(err))
      toast({ title: 'Check-in not saved', message: errorMessage(err), severity: 'attention' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="page">
      <header className="page-head">
        <div className="page-head__title">
          <span className="eyebrow">Daily check-in</span>
          <h1>How are you doing?</h1>
          <p className="muted">One tap per question. Nothing is sent until the hub confirms it was saved.</p>
        </div>
        <div className="chip"><CalendarCheck size={15} aria-hidden="true" /> {new Date(now).toLocaleDateString('en-GB', { weekday: 'long', day: '2-digit', month: 'short' })}</div>
      </header>

      <div className="split">
        <div className="panel checkin-form">
          <div className="checkin-scales">
            <Scale label="Mood" hint="How your head feels right now" value={mood} min={1} max={5} low="Low" high="Good" onChange={setMood} />
            <Scale label="Energy" hint="What you have left in the tank" value={energy} min={1} max={5} low="Empty" high="Full" onChange={setEnergy} />
            <Scale label="Dizziness" hint="Light-headed or unsteady on your feet" value={dizziness} min={0} max={3} low="None" high="Severe" onChange={setDizziness} />
            <Scale label="Workload" hint="How heavy today feels" value={workload} min={1} max={5} low="Light" high="Heavy" onChange={setWorkload} />
          </div>

          <div className="organ-detail__block">
            <span className="field__label">Anything else?</span>
            <div className="chip-row">
              {SYMPTOMS.map((symptom) => (
                <button key={symptom} type="button" className={`chip${symptoms.includes(symptom) ? ' chip--active' : ''}`} aria-pressed={symptoms.includes(symptom)} onClick={() => toggleSymptom(symptom)}>{symptom}</button>
              ))}
            </div>
          </div>

          <label className="field">
            <span className="field__label"><MessageSquareText size={13} aria-hidden="true" /> A note (optional)</span>
            <textarea className="textarea" dir="auto" value={note} onChange={(event) => setNote(event.target.value)} placeholder="One sentence about what felt different today." />
          </label>

          {error && <p className="auth-error small" role="alert">{error}</p>}

          <div className="row row--wrap" style={{ justifyContent: 'flex-end' }}>
            <span className="faint tiny">Saved to the hub, readable only as your consent allows.</span>
            <button type="button" className="btn btn--primary btn--lg" onClick={submit} disabled={busy}><Send size={17} aria-hidden="true" /> {busy ? 'Saving…' : 'Send check-in'}</button>
          </div>

          {saved && (
            <div className="saved-checkin" role="status">
              <CheckCircle2 size={20} aria-hidden="true" />
              <div>
                <div className="strong">Saved {relativeTime(saved.createdAt)}</div>
                <div className="faint tiny">Mood {saved.mood}/5 · Energy {saved.energy}/5 · Dizziness {saved.dizziness}/3 · Workload {saved.workload}/5{saved.symptoms.length > 0 ? ` · ${saved.symptoms.join(', ')}` : ''}</div>
              </div>
            </div>
          )}
        </div>

        <div className="stack">
          <div className="panel">
            <div className="panel-head"><h2 className="panel-title">Recent check-ins</h2><span className="faint tiny">{(checkins.data ?? []).length} saved</span></div>
            {!checkins.data && <span className="skeleton" style={{ height: 120 }} />}
            {checkins.data?.length === 0 && <p className="faint small">No check-ins yet. This first one sets the tone.</p>}
            <div className="checkin-list stagger">
              {(checkins.data ?? []).slice(0, 5).map((checkin, index) => (
                <div className="checkin-row" key={checkin.id} style={{ '--i': index } as CSSProperties}>
                  <span className="checkin-row__mood numeric">{checkin.mood}<span className="faint tiny">/5</span></span>
                  <div>
                    <div className="small"><span className="strong">Mood {checkin.mood}</span> · Energy {checkin.energy} · Dizziness {checkin.dizziness}</div>
                    <div className="faint tiny">{relativeTime(checkin.createdAt, now)}{checkin.symptoms.length > 0 ? ` · ${checkin.symptoms.join(', ')}` : ''}</div>
                    {checkin.note && <div className="faint tiny" dir="auto">{checkin.note}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel panel--glow">
            <span className="eyebrow eyebrow--violet">Why one tap matters</span>
            <p className="muted small" style={{ marginTop: 8 }}>A small change reported early is easier to act on than a big change reported late. The ground team sees the trend, not just one number.</p>
          </div>
        </div>
      </div>
    </section>
  )
}
