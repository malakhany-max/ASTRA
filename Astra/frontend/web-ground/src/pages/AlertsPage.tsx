import { useMemo, useState, type CSSProperties } from 'react'
import { BellRing, Clock3, ShieldAlert } from 'lucide-react'
import type { Alert, CrewOverview, Role } from '@contracts'
import { AlertItem, apiPost, errorMessage, useApi, useNow, useToast } from '@astra/shared'
import { canWrite } from '../lib/ground'

type PriorityFilter = 'all' | Alert['priority']

const PRIORITIES: Array<{ id: PriorityFilter; label: string }> = [
  { id: 'all', label: 'All priorities' },
  { id: 'security', label: 'Security' },
  { id: 'radiation', label: 'Radiation' },
  { id: 'health', label: 'Health' },
]

export function AlertsPage({ role }: { role: Role }) {
  const toast = useToast()
  const now = useNow(30_000)
  const alerts = useApi<Alert[]>('/api/alerts', { live: true, livePrefixes: ['alert', 'rad', 'indicator'] })
  const overview = useApi<CrewOverview>('/api/crew/overview')

  const [priority, setPriority] = useState<PriorityFilter>('all')
  const [astronautId, setAstronautId] = useState('all')
  const [state, setState] = useState<'all' | 'open' | 'acknowledged'>('open')
  const [busyId, setBusyId] = useState<string | null>(null)

  const names = useMemo(() => {
    const map: Record<string, string> = {}
    for (const astronaut of overview.data?.astronauts ?? []) map[astronaut.id] = astronaut.name
    return map
  }, [overview.data])

  const filtered = useMemo(() => {
    return (alerts.data ?? []).filter((alert) => {
      if (priority !== 'all' && alert.priority !== priority) return false
      if (astronautId !== 'all' && alert.astronautId !== astronautId) return false
      if (state === 'open' && alert.acknowledged) return false
      if (state === 'acknowledged' && !alert.acknowledged) return false
      return true
    })
  }, [alerts.data, priority, astronautId, state])

  const open = (alerts.data ?? []).filter((alert) => !alert.acknowledged)
  const urgent = open.filter((alert) => alert.severity === 'urgent').length
  const writable = canWrite(role)

  async function acknowledge(id: string) {
    setBusyId(id)
    try {
      await apiPost(`/api/alerts/${id}/ack`)
      alerts.reload()
      toast({ title: 'Alert acknowledged', message: 'The audit trail now shows who acknowledged it and when.', severity: 'info' })
    } catch (err) {
      toast({ title: 'Could not acknowledge', message: errorMessage(err), severity: 'attention' })
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="page alerts-page">
      <header className="page-head">
        <div className="page-head__title">
          <span className="eyebrow">Alert queue</span>
          <h1>One honest queue</h1>
          <p className="muted">Security, radiation and health alerts in priority order with the reason behind each. Acknowledging records your name in the audit trail.</p>
        </div>
        <div className="chip"><BellRing size={14} aria-hidden="true" /> {open.length} open</div>
      </header>

      <div className="kpi-row stagger">
        <div className="panel kpi" style={{ '--i': 0 } as CSSProperties}>
          <span className="kpi__value" data-status={urgent > 0 ? 'urgent' : undefined}>{urgent}</span>
          <span className="kpi__label">Urgent</span>
        </div>
        <div className="panel kpi" style={{ '--i': 1 } as CSSProperties}>
          <span className="kpi__value">{open.length - urgent}</span>
          <span className="kpi__label">Attention</span>
        </div>
        <div className="panel kpi" style={{ '--i': 2 } as CSSProperties}>
          <span className="kpi__value">{(alerts.data ?? []).length - open.length}</span>
          <span className="kpi__label">Acknowledged</span>
        </div>
        <div className="panel kpi" style={{ '--i': 3 } as CSSProperties}>
          <span className="kpi__value">{filtered.length}</span>
          <span className="kpi__label">Matching now</span>
        </div>
      </div>

      <div className="panel filter-bar" style={{ marginTop: 18 }}>
        <div className="filter-chips" role="group" aria-label="Priority">
          {PRIORITIES.map((option) => (
            <button
              key={option.id}
              type="button"
              className={`chip${priority === option.id ? ' chip--active' : ''}`}
              aria-pressed={priority === option.id}
              onClick={() => setPriority(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>

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
            <span className="field__label">State</span>
            <select className="select" value={state} onChange={(event) => setState(event.target.value as typeof state)}>
              <option value="all">Any state</option>
              <option value="open">Open only</option>
              <option value="acknowledged">Acknowledged</option>
            </select>
          </label>
        </div>
      </div>

      {alerts.error && <p className="auth-error" role="alert">{alerts.error}</p>}
      {!alerts.data && !alerts.error && <div className="stack" aria-hidden="true"><span className="skeleton" style={{ height: 120 }} /><span className="skeleton" style={{ height: 120 }} /></div>}

      <div className="stack stagger" style={{ marginTop: 18 }}>
        {filtered.map((alert, index) => (
          <div key={`${priority}-${astronautId}-${state}-${alert.id}`} style={{ '--i': index } as CSSProperties}>
            <AlertItem
              alert={alert}
              astronautName={names[alert.astronautId] ?? alert.astronautId}
              now={now}
              canAck={writable}
              busy={busyId === alert.id}
              onAck={acknowledge}
            />
          </div>
        ))}
      </div>

      {alerts.data && filtered.length === 0 && (
        <div className="empty" style={{ marginTop: 18 }}>
          <Clock3 size={18} aria-hidden="true" /> No alerts match these filters. Every filter keeps an “Any” reset.
        </div>
      )}

      {!writable && (
        <div className="banner banner--calm" style={{ marginTop: 16 }} role="status">
          <ShieldAlert className="banner__icon" size={18} aria-hidden="true" />
          <div>
            <div className="banner__title">Viewer session</div>
            <div className="banner__body">You can read the queue and every reason in it, but acknowledgement is limited to flight surgeons and medical officers.</div>
          </div>
        </div>
      )}
    </section>
  )
}
