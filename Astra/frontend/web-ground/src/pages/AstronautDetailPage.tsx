import { useState, type CSSProperties } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CalendarDays, CheckCircle2, ChevronDown, Circle, ClipboardCheck, ClipboardList, MessageSquare, Radiation, Radio, ShieldAlert, Sparkles } from 'lucide-react'
import type {
  Alert,
  Astronaut,
  Indicator,
  IndicatorSeries,
  Mission,
  RadiationState,
  Range,
  Role,
} from '@contracts'
import {
  AlertItem,
  apiPost,
  errorMessage,
  formatDate,
  IndicatorCard,
  relativeTime,
  StatusBadge,
  TrendChart,
  useApi,
  useDocumentTitle,
  useNow,
  useToast,
} from '@astra/shared'
import { canWrite } from '../lib/ground'
import { CommandComposer } from '../components/CommandComposer'

const RANGES: Array<{ id: Range; label: string }> = [
  { id: '24h', label: '24 hours' },
  { id: '7d', label: '7 days' },
  { id: '30d', label: '30 days' },
]

interface PlanProgress {
  astronautId: string
  weekOf?: string
  completed?: number
  total?: number
  items: Array<{ id: string; title: string; category: string; done: boolean }>
}

interface ExposureSummary {
  astronautId: string
  records: Array<{ id: string; date: string; doseMsv: number; symptoms: string[]; note?: string }>
  monitoringActive: boolean
}

interface CheckinEntry {
  id: string
  createdAt: string
  mood: number
  energy: number
  dizziness: number
  workload: number
  symptoms: string[]
  note?: string
}

interface CrewMessage {
  id: string
  createdAt: string
  reason: string
  detail?: string
  severity: 'attention' | 'urgent'
  symptoms: string[]
}

export function AstronautDetailPage({ role }: { role: Role }) {
  const { id = 'ast-zain' } = useParams()
  useDocumentTitle('Astronaut detail · Astra')
  const toast = useToast()
  const now = useNow(30_000)

  const profile = useApi<Astronaut>(`/api/astronauts/${id}`, { live: true })
  const indicators = useApi<Indicator[]>(`/api/astronauts/${id}/indicators`, { live: true, livePrefixes: ['indicator'] })
  const alerts = useApi<Alert[]>(`/api/astronauts/${id}/alerts`, { live: true, livePrefixes: ['alert'] })
  const radiation = useApi<RadiationState>(`/api/astronauts/${id}/radiation`, { live: true, livePrefixes: ['rad'] })
  const missions = useApi<Mission[]>(`/api/astronauts/${id}/missions`)
  const plan = useApi<PlanProgress>(`/api/astronauts/${id}/plan`, { live: true, livePrefixes: ['plan'] })
  const exposure = useApi<ExposureSummary>(`/api/astronauts/${id}/exposure`, { live: true, livePrefixes: ['rad', 'exposure'] })
  const checkins = useApi<CheckinEntry[]>(`/api/astronauts/${id}/checkins`, { live: true })
  const messages = useApi<CrewMessage[]>(`/api/astronauts/${id}/messages`, { live: true })

  const [selected, setSelected] = useState('heartRate')
  const [range, setRange] = useState<Range>('24h')
  const series = useApi<IndicatorSeries>(`/api/astronauts/${id}/indicators/${selected}?range=${range}`)
  const [ackBusy, setAckBusy] = useState<string | null>(null)

  const openAlerts = (alerts.data ?? []).filter((alert) => !alert.acknowledged)
  const selectedIndicator = (indicators.data ?? []).find((indicator) => indicator.key === selected) ?? null
  const writable = canWrite(role)
  const planItems = plan.data?.items ?? []
  const planTotal = plan.data?.total ?? planItems.length
  const planDone = plan.data?.completed ?? planItems.filter((item) => item.done).length

  async function acknowledge(alertId: string) {
    setAckBusy(alertId)
    try {
      await apiPost(`/api/alerts/${alertId}/ack`)
      alerts.reload()
      toast({ title: 'Alert acknowledged', message: 'Your name is attached to the audit entry.', severity: 'info' })
    } catch (err) {
      toast({ title: 'Could not acknowledge', message: errorMessage(err), severity: 'attention' })
    } finally {
      setAckBusy(null)
    }
  }

  return (
    <section className="page detail-page">
      <header className="page-head">
        <div className="page-head__title">
          <Link to="/" className="back-link"><ArrowLeft size={15} aria-hidden="true" /> Back to crew</Link>
          <span className="eyebrow">Astronaut detail</span>
          <h1>{profile.data?.name ?? 'Loading astronaut'}</h1>
          <p className="muted">{profile.data ? `${profile.data.currentMissionName} · ${profile.data.location ?? 'Crew vehicle'}` : 'Reading the crew hub.'}</p>
        </div>
        {profile.data && <StatusBadge status={profile.data.status} size="lg" label={profile.data.name} />}
      </header>

      {profile.error && <p className="auth-error" role="alert">{profile.error}</p>}

      <div className="panel detail-profile" data-status={profile.data?.status}>
        <span className="avatar avatar--lg" aria-hidden="true">{profile.data?.initials ?? '—'}</span>
        <div className="detail-profile__id">
          <span className="strong">{profile.data?.name ?? '—'}</span>
          <span className="faint tiny">Mission day {profile.data?.missionDay ?? '—'} · last sync {relativeTime(profile.data?.lastSyncAt, now)}</span>
        </div>
        <div className="kpi-row detail-kpis">
          <div className="kpi"><span className="kpi__value">{profile.data?.restingHr ?? '—'}</span><span className="kpi__label">Resting bpm</span></div>
          <div className="kpi"><span className="kpi__value">{profile.data?.sleepHours != null ? profile.data.sleepHours.toFixed(1) : '—'}</span><span className="kpi__label">Sleep hours</span></div>
          <div className="kpi"><span className="kpi__value">{openAlerts.length}</span><span className="kpi__label">Open alerts</span></div>
          <div className="kpi"><span className="kpi__value">{radiation.data ? radiation.data.cumulativeMsv.toFixed(1) : '—'}</span><span className="kpi__label">Dose mSv</span></div>
        </div>
      </div>

      <div className="panel section-head">
        <h2 className="panel-title">Current measurements</h2>
        <span className="faint tiny">Select a card to chart its trend</span>
      </div>

      {!indicators.data && !indicators.error && (
        <div className="grid grid--auto" aria-hidden="true">
          {Array.from({ length: 6 }, (_, index) => <span className="skeleton" key={index} style={{ height: 158 }} />)}
        </div>
      )}

      <div className="grid grid--auto stagger">
        {(indicators.data ?? []).map((indicator, index) => (
          <div key={indicator.key} className={`indicator-select${indicator.key === selected ? ' is-selected' : ''}`} style={{ '--i': index } as CSSProperties}>
            <IndicatorCard indicator={indicator} now={now} onOpen={setSelected} />
          </div>
        ))}
      </div>

      <div className="panel detail-row">
        <div className="panel-head">
          <div>
            <h2 className="panel-title">{selectedIndicator?.label ?? 'Trend'}</h2>
            <p className="panel-sub">Personal baseline band, never a population average.</p>
          </div>
          <div className="segmented" role="group" aria-label="Time range">
            {RANGES.map((item) => (
              <button key={item.id} type="button" aria-pressed={range === item.id} onClick={() => setRange(item.id)}>{item.label}</button>
            ))}
          </div>
        </div>
        {series.loading && !series.data && <span className="skeleton" style={{ height: 260 }} />}
        {series.error && <p className="auth-error small" role="alert">{series.error}</p>}
        {series.data && <TrendChart data={series.data.samples} baseline={series.data.baseline} unit={series.data.unit} label={series.data.label} precision={selectedIndicator?.precision ?? 0} height={260} />}
      </div>

      <div className="detail-grid detail-row">
        <details key={id} className="panel alert-band">
          <summary className="alert-band__summary">
            <h2 className="panel-title"><ShieldAlert size={17} aria-hidden="true" /> Open alerts</h2>
            <span className="badge" data-status={openAlerts.length > 0 || alerts.error ? 'attention' : 'normal'}>{alerts.error ? 'Unavailable' : alerts.data ? `${openAlerts.length} open` : 'Loading'}</span>
            <ChevronDown size={17} aria-hidden="true" className="alert-band__chevron" />
          </summary>
          <div className="alert-band__body">
            {alerts.error && <p className="auth-error small" role="alert">{alerts.error}</p>}
            {!alerts.data && !alerts.error && <p className="faint small">Loading alerts…</p>}
            {alerts.data && !alerts.error && openAlerts.length === 0 && <p className="faint small">Nothing open for this astronaut. Acknowledged alerts stay in the queue with their audit entry.</p>}
            <div className="alert-band__grid">
              {openAlerts.map((alert) => <AlertItem key={alert.id} alert={alert} now={now} canAck={writable} busy={ackBusy === alert.id} onAck={acknowledge} />)}
            </div>
            {!writable && <p className="faint tiny" style={{ marginTop: 10 }}>The viewer role can read the queue but cannot acknowledge.</p>}
          </div>
        </details>

        <div className="panel">
          <div className="panel-head">
            <h2 className="panel-title"><Radio size={17} aria-hidden="true" /> Radiation</h2>
            {radiation.data && <StatusBadge status={radiation.data.status} label="Dose" />}
          </div>
          {!radiation.data && !radiation.error && <span className="skeleton" style={{ height: 90 }} />}
          {radiation.error && <p className="auth-error small" role="alert">{radiation.error}</p>}
          {radiation.data && (
            <>
              <div className="row row--between small"><span className="faint">Live rate</span><span className="numeric strong">{radiation.data.doseRate} {radiation.data.unit}</span></div>
              <div className="row row--between small"><span className="faint">Cumulative</span><span className="numeric strong">{radiation.data.cumulativeMsv.toFixed(1)} mSv</span></div>
              <div className="meter" style={{ marginTop: 8 }} role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(radiation.data.budgetUsedPct)} aria-label="Mission radiation budget used">
                <div className={`meter__fill${radiation.data.budgetUsedPct >= 75 ? ' meter__fill--danger' : radiation.data.budgetUsedPct >= 50 ? ' meter__fill--warn' : ''}`} style={{ width: `${Math.min(100, radiation.data.budgetUsedPct)}%` }} />
              </div>
              <span className="faint tiny">{radiation.data.budgetUsedPct.toFixed(1)}% of the {radiation.data.budgetMsv} mSv mission budget</span>
            </>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2 className="panel-title"><Radiation size={17} aria-hidden="true" /> Exposure follow-up</h2>
            {exposure.data && <span className="badge" data-status={exposure.data.monitoringActive ? 'attention' : 'normal'}><span className="badge__dot" aria-hidden="true" />{exposure.data.monitoringActive ? 'Monitoring' : 'Clear'}</span>}
          </div>
          {!exposure.data && !exposure.error && <span className="skeleton" style={{ height: 90 }} />}
          {exposure.error && <p className="auth-error small" role="alert">{exposure.error}</p>}
          {exposure.data && exposure.data.records.length === 0 && <p className="faint small">No exposure records for this astronaut.</p>}
          {exposure.data && exposure.data.records.length > 0 && (
            <div className="stack" style={{ marginTop: 4 }}>
              {exposure.data.records.slice(0, 4).map((record) => (
                <div className="row row--between small" key={record.id} style={{ gap: 8 }}><span className="faint">{formatDate(record.date)}</span><span className="numeric strong">{record.doseMsv.toFixed(1)} mSv</span><span className="faint tiny">{record.symptoms.length > 0 ? record.symptoms.join(', ') : 'no symptoms'}</span></div>
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2 className="panel-title"><ClipboardList size={17} aria-hidden="true" /> Plan progress</h2>
            <span className="badge" data-status="normal">{plan.data ? `${planDone}/${planTotal}` : '—'}</span>
          </div>
          {!plan.data && !plan.error && <span className="skeleton" style={{ height: 110 }} />}
          {plan.error && <p className="auth-error small" role="alert">{plan.error}</p>}
          {plan.data && planTotal === 0 && <p className="faint small">No plan steps recorded for this week yet.</p>}
          {plan.data && planTotal > 0 && (
            <>
              <div className="meter" style={{ marginTop: 8 }} role="meter" aria-valuemin={0} aria-valuemax={planTotal} aria-valuenow={planDone} aria-label="Checklist steps completed this week">
                <div className={`meter__fill${planDone === planTotal ? '' : ' meter__fill--warn'}`} style={{ width: `${Math.round((planDone / planTotal) * 100)}%` }} />
              </div>
              <span className="faint tiny">{plan.data.weekOf ? `Week of ${formatDate(plan.data.weekOf)} · ` : ''}The crew device reports progress on each sync.</span>
              <div className="stack" style={{ marginTop: 10 }}>
                {planItems.map((item) => (
                  <div className="row row--between small" key={item.id} style={{ gap: 8 }}>{item.done ? <CheckCircle2 size={15} aria-hidden="true" style={{ color: 'var(--green)', flexShrink: 0 }} /> : <Circle size={15} aria-hidden="true" className="faint" style={{ flexShrink: 0 }} />}<span className={item.done ? 'faint' : 'strong'} style={{ flex: 1 }}>{item.title}</span><span className="faint tiny">{item.category}</span></div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2 className="panel-title"><ClipboardCheck size={17} aria-hidden="true" /> Check-ins</h2>
            <span className="badge" data-status={(checkins.data?.length ?? 0) > 0 ? 'normal' : 'attention'}>{checkins.data?.length ?? 0} synced</span>
          </div>
          {!checkins.data && !checkins.error && <span className="skeleton" style={{ height: 90 }} />}
          {checkins.error && <p className="auth-error small" role="alert">{checkins.error}</p>}
          {checkins.data && checkins.data.length === 0 && <p className="faint small">No check-ins have reached the station yet.</p>}
          <div className="stack" style={{ marginTop: 4 }}>
            {(checkins.data ?? []).slice(0, 5).map((item) => (
              <div key={item.id} className="stack" style={{ gap: 2 }}>
                <div className="row row--between small" style={{ gap: 8 }}>
                  <span className="faint">{relativeTime(item.createdAt, now)}</span>
                  <span className="strong">Mood {item.mood}/5 · Energy {item.energy}/5 · Dizzy {item.dizziness}/3 · Load {item.workload}/5</span>
                </div>
                {item.note && <p className="muted small" dir="auto">{item.note}</p>}
                {item.symptoms.length > 0 && <span className="faint tiny">{item.symptoms.join(', ')}</span>}
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2 className="panel-title"><MessageSquare size={17} aria-hidden="true" /> Medical notes</h2>
            <span className="badge" data-status={(messages.data?.length ?? 0) > 0 ? 'attention' : 'normal'}>{messages.data?.length ?? 0} notes</span>
          </div>
          {!messages.data && !messages.error && <span className="skeleton" style={{ height: 90 }} />}
          {messages.error && <p className="auth-error small" role="alert">{messages.error}</p>}
          {messages.data && messages.data.length === 0 && <p className="faint small">No companion notes for the medical team yet.</p>}
          <div className="stack" style={{ marginTop: 4 }}>
            {(messages.data ?? []).slice(0, 5).map((item) => (
              <div key={item.id} className="stack" style={{ gap: 2 }}>
                <div className="row row--between small" style={{ gap: 8 }}>
                  <span className="strong">{item.reason}</span>
                  <span className="badge" data-status={item.severity}>{item.severity}</span>
                </div>
                {item.detail && <p className="muted small" dir="auto">{item.detail}</p>}
                <span className="faint tiny">{item.symptoms.join(', ') || 'no symptoms listed'} · {relativeTime(item.createdAt, now)}</span>
              </div>
            ))}
          </div>
        </div>

        {writable ? (
          <div className="panel command-panel">
            <CommandComposer astronautId={id} astronautLabel={profile.data?.name ?? id} onCreated={() => undefined} />
          </div>
        ) : (
          <div className="panel panel--glow">
            <span className="eyebrow eyebrow--violet">Read-only role</span>
            <p className="muted small" style={{ marginTop: 8 }}>Your session can view crew health but not send commands. Ask a flight surgeon or medical officer to send plan or threshold changes.</p>
          </div>
        )}

        <div className="panel panel--glow detail-wide">
          <span className="eyebrow eyebrow--violet"><Sparkles size={13} aria-hidden="true" /> Companion context</span>
          <p className="muted small" style={{ marginTop: 8 }}>The companion sees the same measurements but not the companion transcripts unless the astronaut shares them. Consent is checked again on every sync.</p>
        </div>
      </div>

      <div className="detail-row">
        <div className="panel">
          <div className="panel-head">
            <h2 className="panel-title"><CalendarDays size={17} aria-hidden="true" /> Mission record</h2>
            <span className="faint tiny">{missions.data?.length ?? 0} missions</span>
          </div>
          {!missions.data && !missions.error && <span className="skeleton" style={{ height: 150 }} />}
          {missions.error && <p className="auth-error small" role="alert">{missions.error}</p>}
          <div className="mission-list detail-missions stagger">
            {(missions.data ?? []).map((mission, index) => (
              <article className={`mission-card${mission.endDate ? '' : ' is-current'}`} key={mission.id} style={{ '--i': index } as CSSProperties}>
                <div className="row row--between row--wrap" style={{ gap: 8 }}>
                  <span className="strong">{mission.name}</span>
                  {!mission.endDate ? <span className="badge" data-status="normal"><span className="badge__dot" aria-hidden="true" />Current</span> : <span className="faint tiny">{mission.days} days</span>}
                </div>
                <span className="faint tiny">{mission.vehicle} · {formatDate(mission.startDate)} → {mission.endDate ? formatDate(mission.endDate) : 'in progress'} · {mission.role}</span>
                <p className="muted small">{mission.highlight}</p>
                <div className="mission-stats">
                  <span><strong>{mission.stats.meanSleepHours.toFixed(1)} h</strong> sleep</span>
                  <span><strong>{mission.stats.meanHeartRate}</strong> bpm</span>
                  <span><strong>{mission.stats.radiationDoseMsv.toFixed(1)}</strong> mSv</span>
                  <span><strong>{mission.stats.incidents}</strong> incidents</span>
                </div>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
