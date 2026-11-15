import { useMemo, type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Moon, Radio, ShieldAlert } from 'lucide-react'
import type { CrewOverview } from '@contracts'
import { rankOf, relativeTime, StatusBadge, useApi, useNow } from '@astra/shared'

export function CrewPage() {
  const navigate = useNavigate()
  const now = useNow(30_000)
  const overview = useApi<CrewOverview>('/api/crew/overview', { live: true, livePrefixes: ['alert', 'indicator', 'link', 'rad'] })

  const crew = useMemo(() => {
    return (overview.data?.astronauts ?? [])
      .slice()
      .sort((a, b) => rankOf(b.status) - rankOf(a.status))
  }, [overview.data])

  const attention = crew.filter((astronaut) => astronaut.status !== 'normal').length
  const alerts = crew.reduce((total, astronaut) => total + astronaut.activeAlerts, 0)
  const linked = overview.data?.link.state === 'connected'

  return (
    <section className="page crew-page">
      <header className="page-head">
        <div className="page-head__title">
          <span className="eyebrow">Ground console</span>
          <h1>Crew overview</h1>
          <p className="muted">Every astronaut with the reason behind their status, attention first. Open a card to see the full picture and the audit-ready actions.</p>
        </div>
        <div className="chip">
          <Radio size={14} aria-hidden="true" />
          {overview.data ? (linked ? 'Live telemetry' : 'Delayed — showing last known') : 'Connecting'}
        </div>
      </header>

      <div className="kpi-row crew-kpis">
        <div className="panel kpi">
          <span className="kpi__value">{overview.data ? crew.length : '—'}</span>
          <span className="kpi__label">Crew aboard</span>
        </div>
        <div className="panel kpi">
          <span className="kpi__value">{overview.data ? attention : '—'}</span>
          <span className="kpi__label">Need attention</span>
        </div>
        <div className="panel kpi">
          <span className="kpi__value">{overview.data ? alerts : '—'}</span>
          <span className="kpi__label">Active alerts</span>
        </div>
        <div className="panel kpi">
          <span className="kpi__value">{overview.data ? (linked ? 'Live' : 'Delayed') : '—'}</span>
          <span className="kpi__label">Ground link</span>
        </div>
      </div>

      {overview.error && <p className="auth-error" role="alert">{overview.error}</p>}

      {!overview.data && !overview.error && (
        <div className="grid grid--3" aria-hidden="true">
          <span className="skeleton" style={{ height: 210, borderRadius: 18 }} />
          <span className="skeleton" style={{ height: 210, borderRadius: 18 }} />
          <span className="skeleton" style={{ height: 210, borderRadius: 18 }} />
        </div>
      )}

      <div className="crew-grid stagger">
        {crew.map((astronaut, index) => (
          <button
            key={astronaut.id}
            type="button"
            className="panel crew-card"
            data-status={astronaut.status}
            style={{ '--i': index } as CSSProperties}
            onClick={() => navigate(`/crew/${astronaut.id}`)}
            aria-label={`Open ${astronaut.name}: ${astronaut.status}, ${astronaut.activeAlerts} active alerts`}
          >
            <div className="crew-card__head">
              <span className="avatar avatar--lg" aria-hidden="true">{astronaut.initials}</span>
              <div className="crew-card__id">
                <span className="crew-card__name">{astronaut.name}</span>
                <span className="faint tiny">{astronaut.location ?? astronaut.currentMissionName}</span>
              </div>
              <StatusBadge status={astronaut.status} label={astronaut.name} />
            </div>

            <div className="crew-card__vitals">
              <div className="crew-vital">
                <span className="crew-vital__label">Mission day</span>
                <span className="crew-vital__value numeric">{astronaut.missionDay}</span>
              </div>
              <div className="crew-vital">
                <span className="crew-vital__label"><Moon size={12} aria-hidden="true" /> Sleep</span>
                <span className="crew-vital__value numeric">{astronaut.sleepHours != null ? `${astronaut.sleepHours.toFixed(1)} h` : '—'}</span>
              </div>
              <div className="crew-vital">
                <span className="crew-vital__label">Resting HR</span>
                <span className="crew-vital__value numeric">{astronaut.restingHr != null ? `${astronaut.restingHr} bpm` : '—'}</span>
              </div>
            </div>

            <div className="crew-card__foot">
              <span className="faint tiny">Synced {relativeTime(astronaut.lastSyncAt, now)}</span>
              <span className={`crew-card__alerts${astronaut.activeAlerts > 0 ? ' is-hot' : ''}`}>
                <ShieldAlert size={13} aria-hidden="true" />
                {astronaut.activeAlerts} alert{astronaut.activeAlerts === 1 ? '' : 's'}
              </span>
              <span className="crew-card__open">Open <ArrowRight size={14} aria-hidden="true" /></span>
            </div>
          </button>
        ))}
      </div>

      {overview.data && !linked && (
        <div className="banner banner--calm" style={{ marginTop: 18 }} role="status">
          <Radio className="banner__icon" size={18} aria-hidden="true" />
          <div>
            <div className="banner__title">Showing last known values</div>
            <div className="banner__body">The crew link is {overview.data.link.state}. Values are labelled with their age and will refresh on reconnect. No value is invented in the meantime.</div>
          </div>
        </div>
      )}
    </section>
  )
}
