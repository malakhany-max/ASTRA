import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { CircleCheck, Clock3, Crosshair, Radiation as RadiationIcon, ShieldCheck, TriangleAlert, X } from 'lucide-react'
import type { Alert, RadiationState } from '@contracts'
import { apiPost, errorMessage, Gauge, relativeTime, ShelterCountdown, StatusBadge, Timeline, useApi, useNow, useToast } from '@astra/shared'
import type { TimelineItem } from '@astra/shared'
import { ASTRONAUT_ID } from '../lib/astro'

const DIRECTION_ARROW: Record<RadiationState['shelter']['direction'], string> = {
  left: '←',
  right: '→',
  up: '↑',
  down: '↓',
  forward: '↑',
  behind: '↓',
}

const EVENT_LABEL: Record<string, string> = {
  routine: 'Routine cabin measurement',
  solar_particle_event: 'Solar particle event',
  alarm: 'Dosimeter alarm',
  dosimeter_spike: 'Dosimeter spike',
}

function ShelterView({ radiation, onClose, onConfirm, busy, confirmed }: { radiation: RadiationState; onClose: () => void; onConfirm: () => void; busy: boolean; confirmed: boolean }) {
  const dialogRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const dialog = dialogRef.current
    dialog?.focus({ preventScroll: true })
    if (dialog) dialog.scrollTop = 0
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previous
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [onClose])

  return createPortal(
    <div ref={dialogRef} tabIndex={-1} className="shelter" role="dialog" aria-modal="true" aria-labelledby="shelter-title">
      <div className="shelter__scroll">
        <div className="shelter__inner">
          <span className="shelter__eyebrow"><RadiationIcon size={15} aria-hidden="true" /> Solar particle event</span>
          <h1 className="shelter__title" id="shelter-title">Shelter now</h1>
          <p className="shelter__sub">
            Move to {radiation.shelter.zone}. It is {radiation.shelter.distanceM} metres away. Keep your dosimeter clipped on and stay until the ground team or the companion confirms the storm has passed.
          </p>

          <div className="shelter__hero">
            <div className="shelter__direction">
              <span className="arrow" aria-hidden="true">{DIRECTION_ARROW[radiation.shelter.direction]}</span>
              <span className="faint small">{radiation.shelter.direction} · {radiation.shelter.distanceM} m</span>
            </div>
            <ShelterCountdown seconds={0} size={190} />
          </div>

          <div className="shelter__grid">
            {radiation.shelter.instructions.map((step, index) => (
              <div className="shelter__step" key={step}>
                <span className="shelter__step-num">STEP {String(index + 1).padStart(2, '0')}</span>
                <span className="small">{step}</span>
              </div>
            ))}
          </div>

          <div className="shelter__actions">
            {confirmed ? (
              <span className="badge" data-status="normal"><ShieldCheck size={14} aria-hidden="true" /> Ground team told you are in shelter</span>
            ) : (
              <button type="button" className="btn btn--lg shelter__ack" onClick={onConfirm} disabled={busy}><CircleCheck size={18} aria-hidden="true" /> {busy ? 'Telling the ground team…' : 'I am in shelter'}</button>
            )}
            <button type="button" className="btn btn--ghost" onClick={onClose}><X size={16} aria-hidden="true" /> Review later</button>
          </div>
          <p className="faint tiny">This view closes only by your choice. The event stays active until the hub clears it.</p>
        </div>
      </div>
    </div>,
    document.body,
  )
}

export function RadiationPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const now = useNow(30_000)
  const radiation = useApi<RadiationState>(`/api/astronauts/${ASTRONAUT_ID}/radiation`, { live: true, livePrefixes: ['rad', 'indicator', 'alert'] })
  const alerts = useApi<Alert[]>(`/api/astronauts/${ASTRONAUT_ID}/alerts`, { live: true, livePrefixes: ['alert', 'rad'] })
  const [open, setOpen] = useState(false)
  const [openedOnce, setOpenedOnce] = useState(false)
  const [busy, setBusy] = useState(false)
  const [confirmed, setConfirmed] = useState(false)

  const data = radiation.data
  const active = Boolean(data?.alertActive)

  useEffect(() => {
    if (active && !openedOnce) {
      setOpen(true)
      setOpenedOnce(true)
    }
  }, [active, openedOnce])

  async function confirmShelter() {
    const target = (alerts.data ?? []).find((alert) => !alert.acknowledged && (alert.priority === 'radiation' || alert.severity === 'urgent'))
    if (!target) {
      toast({ title: 'No open radiation alert', message: 'The hub has nothing open to acknowledge right now.', severity: 'info' })
      return
    }
    setBusy(true)
    try {
      await apiPost(`/api/alerts/${target.id}/ack`)
      setConfirmed(true)
      alerts.reload()
      toast({ title: 'Ground team told', message: 'They know you are in the shelter. Stay until the all-clear.', severity: 'info' })
    } catch (error) {
      toast({ title: 'Could not reach the hub', message: errorMessage(error), severity: 'attention' })
    } finally {
      setBusy(false)
    }
  }

  const events: TimelineItem[] = (data?.events ?? []).slice().reverse().map((event) => ({
    id: event.id,
    time: new Date(event.startedAt).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }),
    title: EVENT_LABEL[event.type] ?? event.type,
    text: event.note ?? `${event.doseRate} µSv/h · ${event.endedAt ? 'ended' : 'ongoing'}`,
    status: event.type === 'solar_particle_event' ? 'urgent' : event.type === 'routine' ? 'normal' : 'attention',
  }))

  const gaugeMax = data ? Math.max(5, Math.ceil(data.doseRate * 1.6)) : 5
  const budgetPct = data?.budgetUsedPct ?? 0

  return (
    <section className="page">
      <header className="page-head">
        <div className="page-head__title">
          <span className="eyebrow">Radiation & shelter</span>
          <h1>Dose and protection</h1>
          <p className="muted">Your live dose rate, the mission budget, and the shelter route if a solar particle event starts.</p>
        </div>
        {data && <div className="chip-row"><StatusBadge status={data.status} size="lg" live={active} /><button type="button" className="btn btn--calm" onClick={() => setOpen(true)}><Crosshair size={15} aria-hidden="true" /> Open shelter view</button></div>}
      </header>

      {active && <div className="banner banner--danger" style={{ marginBottom: 20 }} role="alert"><RadiationIcon className="banner__icon" size={20} aria-hidden="true" /><div><div className="banner__title">Solar particle event active</div><div className="banner__body">{`Shelter guidance is open on your device. Move to ${data?.shelter.zone} now and confirm when you are inside.`}</div></div></div>}

      {!data && !radiation.error && <div className="grid grid--2"><span className="skeleton" style={{ height: 280 }} /><span className="skeleton" style={{ height: 280 }} /></div>}
      {radiation.error && <p className="muted small" role="alert">{radiation.error}</p>}

      {data && (
        <>
          <div className="grid grid--2">
            <div className="panel radiation-gauge">
              <div className="panel-head"><h2 className="panel-title">Live dose rate</h2><span className="faint tiny">latest event {relativeTime(data.events[data.events.length - 1]?.startedAt, now)}</span></div>
              <div className="radiation-gauge__body">
                <Gauge value={data.doseRate} max={gaugeMax} unit={data.unit} label="Dose rate" status={data.status} size={210} />
                <div className="stack" style={{ gap: 10 }}>
                  <div className="metric">
                    <span className="metric__label">Cumulative dose</span>
                    <span className="metric__value numeric">{data.cumulativeMsv.toFixed(1)} <span className="faint tiny">mSv</span></span>
                  </div>
                  <div className="metric">
                    <span className="metric__label">Mission budget</span>
                    <span className="metric__value numeric">{data.budgetMsv} <span className="faint tiny">mSv</span></span>
                  </div>
                  <div className="metric">
                    <span className="metric__label">Budget used</span>
                    <span className="metric__value numeric">{budgetPct.toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-head"><h2 className="panel-title">Mission budget</h2><span className="badge" data-status={budgetPct >= 75 ? 'urgent' : budgetPct >= 50 ? 'attention' : 'normal'}><span className="badge__dot" aria-hidden="true" />{budgetPct >= 75 ? 'High' : budgetPct >= 50 ? 'Watch' : 'Within plan'}</span></div>
              <p className="muted small">The budget keeps the total dose for the whole mission in view, not just today’s rate.</p>
              <div className="budget" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Number(budgetPct.toFixed(1))} aria-label="Radiation budget used">
                <div className="budget__labels"><span className="numeric strong">{data.cumulativeMsv.toFixed(1)} mSv</span><span className="faint small">of {data.budgetMsv} mSv</span></div>
                <div className="meter"><div className={`meter__fill${budgetPct >= 75 ? ' meter__fill--danger' : budgetPct >= 50 ? ' meter__fill--warn' : ''}`} style={{ width: `${Math.min(100, budgetPct)}%` }} /></div>
                <div className="budget__ticks"><span>0%</span><span>50%</span><span>100%</span></div>
              </div>
              <div className="grid grid--3 protection-grid">
                <div className="protection"><Clock3 size={16} aria-hidden="true" /><span className="strong small">Time</span><span className="faint tiny">Spend as little time as possible in the highest-rate module.</span></div>
                <div className="protection"><Crosshair size={16} aria-hidden="true" /><span className="strong small">Distance</span><span className="faint tiny">Put mass and structure between you and the outer wall.</span></div>
                <div className="protection"><ShieldCheck size={16} aria-hidden="true" /><span className="strong small">Shielding</span><span className="faint tiny">The storm shelter uses the water tanks as shielding.</span></div>
              </div>
            </div>
          </div>

          <div className="split" style={{ marginTop: 20 }}>
            <div className="panel">
              <div className="panel-head"><h2 className="panel-title">Shelter route</h2><span className="faint tiny">{data.shelter.zone}</span></div>
              <div className="shelter-route">
                <div className="shelter-route__arrow" aria-hidden="true">{DIRECTION_ARROW[data.shelter.direction]}</div>
                <div>
                  <div className="strong">{data.shelter.distanceM} metres {data.shelter.direction}</div>
                  <div className="faint tiny">Follow the Node 3 handrail. Keep the dosimeter clipped on.</div>
                </div>
              </div>
              <ol className="organ-steps">
                {data.shelter.instructions.map((step) => <li key={step}>{step}</li>)}
              </ol>
              <button type="button" className="btn btn--primary" onClick={() => setOpen(true)}><TriangleAlert size={16} aria-hidden="true" /> Practice the shelter view</button>
            </div>

            <div className="panel">
              <div className="panel-head"><h2 className="panel-title">Recent events</h2><span className="faint tiny">{data.events.length} recorded</span></div>
              <Timeline items={events} />
              <button type="button" className="btn btn--ghost" style={{ marginTop: 14 }} onClick={() => navigate('/exposure')}>See post-exposure follow-up</button>
            </div>
          </div>
        </>
      )}

      {data && open && <ShelterView radiation={data} onClose={() => setOpen(false)} onConfirm={confirmShelter} busy={busy} confirmed={confirmed} />}
    </section>
  )
}
