import { useMemo, type CSSProperties } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, CalendarCheck, MessagesSquare, SmilePlus, Sparkles, Wind } from 'lucide-react'
import type { Alert, Astronaut, Indicator, Plan } from '@contracts'
import { AlertItem, IndicatorCard, rankOf, relativeTime, StatusBadge, useApi, useNow } from '@astra/shared'
import { ASTRONAUT_ID, ASTRONAUT_FIRST_NAME, greeting } from '../lib/astro'

const QUICK_ACTIONS = [
  { to: '/checkin', label: 'Quick check-in', icon: SmilePlus },
  { to: '/companion', label: 'Talk it through', icon: MessagesSquare },
  { to: '/breathing', label: 'Breathe for 3 min', icon: Wind },
  { to: '/plan', label: "Today's plan", icon: CalendarCheck },
]

export function HomePage() {
  const navigate = useNavigate()
  const now = useNow(30_000)
  const indicators = useApi<Indicator[]>(`/api/astronauts/${ASTRONAUT_ID}/indicators`, { live: true, livePrefixes: ['indicator', 'checkin'] })
  const alerts = useApi<Alert[]>(`/api/astronauts/${ASTRONAUT_ID}/alerts`, { live: true, livePrefixes: ['alert'] })
  const profile = useApi<Astronaut>(`/api/astronauts/${ASTRONAUT_ID}`, { live: true })
  const plan = useApi<Plan>(`/api/astronauts/${ASTRONAUT_ID}/plan`, { live: true })

  const sorted = useMemo(() => {
    const list = indicators.data ?? []
    return list.slice().sort((a, b) => rankOf(b.status) - rankOf(a.status))
  }, [indicators.data])

  const urgent = sorted.filter((indicator) => indicator.status === 'urgent').length
  const attention = sorted.filter((indicator) => indicator.status === 'attention').length
  const unacknowledged = (alerts.data ?? []).filter((alert) => !alert.acknowledged).slice(0, 2)
  const nextPlan = (plan.data?.items ?? []).filter((item) => !item.done).slice(0, 3)

  const summary = urgent > 0
    ? `${urgent} reading${urgent === 1 ? '' : 's'} ${urgent === 1 ? 'needs' : 'need'} attention now. The steps are below.`
    : attention > 0
      ? `${attention} value${attention === 1 ? ' is' : 's are'} outside your usual range. Nothing is dangerous right now.`
      : 'All measured values are inside your personal range. Your body is holding steady today.'

  const updated = profile.data?.lastSyncAt ?? indicators.data?.[0]?.updatedAt

  return (
    <section className="page home-page">
      <div className="hero panel panel--glow">
        <div className="hero__copy">
          <span className="eyebrow">Astronaut console · Mission day {profile.data?.missionDay ?? '—'}</span>
          <h1 className="hero__title">{greeting(new Date(now).getHours())}, {ASTRONAUT_FIRST_NAME}.</h1>
          <p className="hero__sub">{summary}</p>
          <div className="chip-row hero__actions">
            {QUICK_ACTIONS.map((action) => {
              const Icon = action.icon
              return (
                <Link key={action.to} to={action.to} className="btn btn--calm">
                  <Icon size={16} aria-hidden="true" />
                  {action.label}
                </Link>
              )
            })}
          </div>
          <div className="hero__meta faint tiny">
            {updated ? `Last sync ${relativeTime(updated, now)} · everything is measured before it is shown` : 'Waiting for the first sync'}
          </div>
        </div>

        <div className="hero__visual" aria-hidden="true">
          <div className="orbit">
            <span className="orbit__planet" />
            <span className="orbit__ring orbit__ring--a" />
            <span className="orbit__ring orbit__ring--b" />
            <span className="orbit__dot" />
            <span className="orbit__dot orbit__dot--b" />
          </div>
          <div className="hero__status">
            <StatusBadge status={urgent > 0 ? 'urgent' : attention > 0 ? 'attention' : 'normal'} size="lg" live />
            <span className="faint tiny">{urgent > 0 ? 'Act on the highlighted steps' : attention > 0 ? 'Watch the amber values' : 'Steady baseline'}</span>
          </div>
        </div>
      </div>

      {unacknowledged.length > 0 && (
        <div className="home-section">
          <div className="panel-head">
            <h2 className="panel-title">Worth a look</h2>
            <span className="faint tiny">{unacknowledged.length} open {unacknowledged.length === 1 ? 'note' : 'notes'}</span>
          </div>
          <div className="stack">
            {unacknowledged.map((alert) => (
              <AlertItem key={alert.id} alert={alert} now={now} />
            ))}
          </div>
        </div>
      )}

      <div className="home-section">
        <div className="panel-head">
          <h2 className="panel-title">Your measurements</h2>
          <span className="faint tiny">Anything needing attention is first</span>
        </div>

        {indicators.error && <p className="muted small" role="alert">{indicators.error}</p>}

        {!indicators.data && !indicators.error && (
          <div className="grid grid--auto">
            {Array.from({ length: 6 }, (_, index) => (
              <span className="skeleton" key={index} style={{ height: 158 }} />
            ))}
          </div>
        )}

        <div className="grid grid--auto stagger">
          {sorted.map((indicator, index) => (
            <div key={indicator.key} style={{ '--i': index } as CSSProperties}>
              <IndicatorCard indicator={indicator} now={now} onOpen={(key) => navigate(`/indicators/${key}`)} />
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid--2 home-section">
        <div className="panel">
          <div className="panel-head">
            <h2 className="panel-title">Next up today</h2>
            <Link to="/plan" className="btn btn--ghost">Open plan <ArrowRight size={14} aria-hidden="true" /></Link>
          </div>
          {nextPlan.length === 0 && <p className="faint small">No plan items are waiting. The ground team will send the next block.</p>}
          <ul className="focus-list">
            {nextPlan.map((item) => (
              <li className="focus-item" key={item.id}>
                <span className="focus-item__dot" aria-hidden="true" />
                <div>
                  <div className="strong small">{item.title}</div>
                  <div className="faint tiny">{item.rationale}</div>
                </div>
                <span className="badge">{item.durationMin > 0 ? `${item.durationMin} min` : item.category}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="panel panel--glow companion-brief">
          <span className="eyebrow eyebrow--violet">Companion</span>
          <h2 className="panel-title" style={{ marginTop: 8 }}>A minute to talk?</h2>
          <p className="muted small">Short sleep and a heavy schedule can make a small symptom feel bigger. Say what feels heaviest and pick one small next step.</p>
          <div className="row row--wrap" style={{ marginTop: 16 }}>
            <Link to="/companion" className="btn btn--primary"><MessagesSquare size={16} aria-hidden="true" /> Start a chat</Link>
            <button type="button" className="btn btn--ghost" onClick={() => navigate('/breathing?technique=box')}><Sparkles size={16} aria-hidden="true" /> Box breathing</button>
          </div>
        </div>
      </div>
    </section>
  )
}
