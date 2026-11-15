import { useMemo, useState, type CSSProperties } from 'react'
import { CalendarRange, Search, X } from 'lucide-react'
import type { Astronaut, CrewOverview, Mission } from '@contracts'
import { formatDate, StatusBadge, useApi } from '@astra/shared'

const VEHICLES = ['Orion', 'Gateway', 'ISS']

function CrewHistory({
  astronaut,
  query,
  vehicle,
}: {
  astronaut: Astronaut
  query: string
  vehicle: string
}) {
  const missions = useApi<Mission[]>(`/api/astronauts/${astronaut.id}/missions`)

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase()
    return (missions.data ?? []).filter((mission) => {
      if (vehicle !== 'all' && mission.vehicle !== vehicle) return false
      if (!term) return true
      return [mission.name, mission.vehicle, mission.role, mission.highlight, mission.summary]
        .join(' ')
        .toLowerCase()
        .includes(term)
    })
  }, [missions.data, query, vehicle])

  if (missions.data && filtered.length === 0) return null

  return (
    <section className="history-crew">
      <div className="history-crew__head">
        <span className="avatar" aria-hidden="true">{astronaut.initials}</span>
        <div>
          <h2 className="panel-title">{astronaut.name}</h2>
          <span className="faint tiny">{astronaut.currentMissionName} · {filtered.length} of {missions.data?.length ?? 0} missions</span>
        </div>
        <StatusBadge status={astronaut.status} label={astronaut.name} />
      </div>

      {!missions.data && !missions.error && <span className="skeleton" style={{ height: 150 }} />}
      {missions.error && <p className="auth-error small" role="alert">{missions.error}</p>}

      <div className="mission-timeline stagger">
        {filtered.map((mission, index) => (
          <article className={`mission-card mission-card--timeline${mission.endDate ? '' : ' is-current'}`} key={mission.id} style={{ '--i': index } as CSSProperties}>
            <span className="mission-timeline__dot" aria-hidden="true" />
            <div className="row row--between row--wrap" style={{ gap: 8 }}>
              <span className="strong">{mission.name}</span>
              {!mission.endDate ? (
                <span className="badge" data-status="normal"><span className="badge__dot" aria-hidden="true" />Current</span>
              ) : (
                <span className="faint tiny">{mission.days} days</span>
              )}
            </div>
            <span className="faint tiny">
              {mission.vehicle} · {formatDate(mission.startDate)} → {mission.endDate ? formatDate(mission.endDate) : 'in progress'} · {mission.role}
            </span>
            <p className="muted small mission-card__highlight">{mission.highlight}</p>
            <p className="faint tiny">{mission.summary}</p>
            <div className="mission-stats">
              <span><strong>{mission.stats.meanSleepHours.toFixed(1)} h</strong> mean sleep</span>
              <span><strong>{mission.stats.meanHeartRate}</strong> bpm mean</span>
              <span><strong>{mission.stats.radiationDoseMsv.toFixed(1)}</strong> mSv dose</span>
              <span><strong>{mission.stats.incidents}</strong> incidents</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

export function HistoryPage() {
  const overview = useApi<CrewOverview>('/api/crew/overview', { live: true, livePrefixes: ['link'] })
  const [query, setQuery] = useState('')
  const [astronautId, setAstronautId] = useState('all')
  const [vehicle, setVehicle] = useState('all')

  const crew = (overview.data?.astronauts ?? []).filter((astronaut) => astronautId === 'all' || astronaut.id === astronautId)

  return (
    <section className="page history-page">
      <header className="page-head">
        <div className="page-head__title">
          <span className="eyebrow">Mission history</span>
          <h1>Astronaut records</h1>
          <p className="muted">Current and past missions with sleep, heart-rate and dose summaries. Every filter has its own reset so nothing hides silently.</p>
        </div>
        <div className="chip"><CalendarRange size={14} aria-hidden="true" /> {crew.length} crew member{crew.length === 1 ? '' : 's'} shown</div>
      </header>

      <div className="panel filter-bar">
        <label className="field filter-search">
          <span className="field__label">Search</span>
          <span className="filter-search__wrap">
            <Search size={15} aria-hidden="true" />
            <input
              className="input"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Mission, role or highlight"
              aria-label="Search mission history"
            />
            {query && (
              <button type="button" className="filter-search__clear" onClick={() => setQuery('')} aria-label="Clear search">
                <X size={14} aria-hidden="true" />
              </button>
            )}
          </span>
        </label>

        <div className="filter-group">
          <label className="field">
            <span className="field__label">Astronaut</span>
            <select className="select" value={astronautId} onChange={(event) => setAstronautId(event.target.value)}>
              <option value="all">Any astronaut</option>
              {(overview.data?.astronauts ?? []).map((astronaut) => (
                <option key={astronaut.id} value={astronaut.id}>{astronaut.name}</option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="field__label">Vehicle</span>
            <select className="select" value={vehicle} onChange={(event) => setVehicle(event.target.value)}>
              <option value="all">Any vehicle</option>
              {VEHICLES.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </label>
        </div>
      </div>

      {overview.error && <p className="auth-error" role="alert">{overview.error}</p>}
      {!overview.data && !overview.error && <span className="skeleton" style={{ height: 220 }} />}

      <div className="stack" style={{ marginTop: 18 }}>
        {crew.map((astronaut) => (
          <CrewHistory key={astronaut.id} astronaut={astronaut} query={query} vehicle={vehicle} />
        ))}
      </div>

      {overview.data && (
        <p className="faint tiny" style={{ marginTop: 16 }}>Search {query ? `“${query}”` : 'is empty'} · vehicle {vehicle === 'all' ? 'any' : vehicle} · astronaut {astronautId === 'all' ? 'any' : crew[0]?.name ?? 'any'}.</p>
      )}
    </section>
  )
}
