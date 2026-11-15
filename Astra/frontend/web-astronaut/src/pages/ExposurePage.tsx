import { Activity, CalendarClock, HeartPulse, Info, Stethoscope, Timer } from 'lucide-react'
import type { ExposureState } from '@contracts'
import { formatClock, relativeTime, StatusBadge, Timeline, useApi, useNow } from '@astra/shared'
import type { TimelineItem } from '@astra/shared'
import { ASTRONAUT_ID } from '../lib/astro'

function countdownLabel(untilIso: string | null, now: number): string {
  if (!untilIso) return '—'
  const seconds = Math.max(0, Math.floor((new Date(untilIso).getTime() - now) / 1000))
  const hours = Math.floor(seconds / 3600)
  if (hours >= 1) return `${hours} h ${Math.floor((seconds % 3600) / 60)} min`
  return formatClock(seconds)
}

export function ExposurePage() {
  const now = useNow(1000)
  const exposure = useApi<ExposureState>(`/api/astronauts/${ASTRONAUT_ID}/exposure`, { live: true, livePrefixes: ['rad', 'exposure', 'alert'] })
  const data = exposure.data

  const records: TimelineItem[] = (data?.records ?? []).slice().reverse().map((record) => ({
    id: record.id,
    time: new Date(record.date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }),
    title: `${record.doseMsv.toFixed(1)} mSv · ${record.symptoms.length > 0 ? record.symptoms.join(', ') : 'no symptoms recorded'}`,
    text: record.note,
    status: record.doseMsv >= 3 ? 'attention' : 'normal',
    icon: <Activity size={13} aria-hidden="true" />,
  }))

  const monitoringSeconds = data?.monitoringUntil ? Math.max(0, Math.floor((new Date(data.monitoringUntil).getTime() - now) / 1000)) : 0
  const totalWindowSeconds = (data?.windowHours ?? 72) * 3600
  const progress = data?.monitoringActive ? Math.min(100, Math.max(0, 100 - (monitoringSeconds / totalWindowSeconds) * 100)) : 0

  return (
    <section className="page">
      <header className="page-head">
        <div className="page-head__title">
          <span className="eyebrow">Post-exposure follow-up</span>
          <h1>Exposure timeline</h1>
          <p className="muted">An honest record of dose and symptoms, plus the monitoring window your medical team is watching.</p>
        </div>
        {data && <StatusBadge status={data.monitoringActive ? 'attention' : 'normal'} size="lg" label="Monitoring" />}
      </header>

      {!data && !exposure.error && <div className="grid grid--2"><span className="skeleton" style={{ height: 260 }} /><span className="skeleton" style={{ height: 260 }} /></div>}
      {exposure.error && <p className="muted small" role="alert">{exposure.error}</p>}

      {data && (
        <>
          <div className="grid grid--2">
            <div className="panel exposure-window" data-status={data.monitoringActive ? 'attention' : 'normal'}>
              <div className="panel-head">
                <h2 className="panel-title"><Timer size={16} aria-hidden="true" /> Monitoring window</h2>
                <span className="badge" data-status={data.monitoringActive ? 'attention' : 'normal'}><span className="badge__dot" aria-hidden="true" />{data.monitoringActive ? 'Active' : 'Not active'}</span>
              </div>
              {data.monitoringActive ? (
                <>
                  <div className="monitor-count"><span className="monitor-count__value numeric">{countdownLabel(data.monitoringUntil, now)}</span><span className="faint tiny">until the window closes</span></div>
                  <div className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress)} aria-label="Monitoring window progress"><div className="meter__fill meter__fill--warn" style={{ width: `${progress}%` }} /></div>
                  <p className="muted small">Started {relativeTime(data.monitoringStartedAt, now)}. The team checks symptoms and dose at each scheduled contact.</p>
                </>
              ) : (
                <p className="muted small">No active monitoring window. A window opens automatically after any exposure above the follow-up threshold.</p>
              )}
              <div className="monitor-meta"><CalendarClock size={15} aria-hidden="true" /><span className="faint tiny">Window length {data.windowHours} hours · follow-up is based on the recorded dose, not how you feel.</span></div>
            </div>

            <div className="panel">
              <div className="panel-head"><h2 className="panel-title"><Stethoscope size={16} aria-hidden="true" /> Who is watching</h2></div>
              <p className="muted small">Your flight surgeon and the radiation protection team monitor this window. They see the recorded dose and any symptoms you report — nothing more.</p>
              <div className="security-check" data-status="normal" style={{ marginTop: 8 }}>
                <span className="security-check__state" aria-hidden="true"><HeartPulse size={15} /></span>
                <div><div className="strong small">Symptoms you report go into the same timeline</div><div className="faint tiny">A check-in with dizziness or headache is linked to the exposure record automatically.</div></div>
              </div>
              <div className="banner banner--calm" style={{ marginTop: 14 }}>
                <Info className="banner__icon" size={18} aria-hidden="true" />
                <div><div className="banner__title">Diet cannot reverse exposure</div><div className="banner__body">No food or supplement undoes radiation dose. The only real protections are time, distance and shielding. The plan focuses on recovery and monitoring.</div></div>
              </div>
            </div>
          </div>

          <div className="split" style={{ marginTop: 20 }}>
            <div className="panel">
              <div className="panel-head"><h2 className="panel-title">Recorded exposures</h2><span className="faint tiny">{data.records.length} record{data.records.length === 1 ? '' : 's'}</span></div>
              {records.length === 0 ? <div className="empty">No exposure records yet.</div> : <Timeline items={records} />}
            </div>

            <div className="panel">
              <div className="panel-head"><h2 className="panel-title">What the numbers mean</h2></div>
              <div className="exposure-scale">
                <div className="exposure-scale__row"><span className="strong small">Routine day</span><span className="faint tiny">Around 0.5–1 mSv on a deep-space transit day.</span></div>
                <div className="exposure-scale__row"><span className="strong small">Solar event</span><span className="faint tiny">Can deliver a large dose in minutes. Shelter is the only effective response.</span></div>
                <div className="exposure-scale__row"><span className="strong small">Mission budget</span><span className="faint tiny">The planned total the mission is allowed to accumulate.</span></div>
              </div>
              <p className="faint tiny" style={{ marginTop: 12 }}>This page never predicts a health outcome from a single reading. Only the medical team interprets exposure against your history.</p>
            </div>
          </div>
        </>
      )}
    </section>
  )
}
