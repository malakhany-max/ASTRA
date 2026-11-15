import { useMemo, useState, type CSSProperties } from 'react'
import { ChevronDown, ListChecks, Send, ShieldCheck } from 'lucide-react'
import type { CommandRecord, CrewOverview } from '@contracts'
import { relativeTime, useApi, useDocumentTitle, useNow } from '@astra/shared'
import { CommandComposer } from '../components/CommandComposer'
import { COMMAND_TYPE_LABEL } from '../lib/ground'

const STATUS_META: Record<CommandRecord['status'], { label: string; status: string }> = {
  pending: { label: 'Queued', status: 'attention' },
  delivered: { label: 'Delivered', status: 'normal' },
  failed: { label: 'Failed', status: 'urgent' },
}

function payloadSummary(command: CommandRecord): string {
  if (command.type === 'schedule') {
    const time = command.payload.checkinTime
    return typeof time === 'string' ? `Check-in reminder at ${time}` : 'Check-in schedule update'
  }
  if (command.type === 'thresholds') {
    const key = String(command.payload.key ?? 'indicator')
    const low = command.payload.low
    const high = command.payload.high
    return `${key}: ${String(low ?? '—')} to ${String(high ?? '—')}`
  }
  const note = command.payload.note
  return typeof note === 'string' && note.length > 0 ? note : 'Plan update'
}

export function CommandsPage() {
  useDocumentTitle('Commands · Astra')
  const now = useNow(30_000)
  const commands = useApi<CommandRecord[]>('/api/commands', { live: true, livePrefixes: ['command', 'link'] })
  const overview = useApi<CrewOverview>('/api/crew/overview', { live: true, livePrefixes: ['link'] })

  const [astronautId, setAstronautId] = useState('ast-zain')
  const [filterAstronaut, setFilterAstronaut] = useState('all')
  const [filterStatus, setFilterStatus] = useState<'all' | CommandRecord['status']>('all')

  const names = useMemo(() => {
    const map: Record<string, string> = {}
    for (const astronaut of overview.data?.astronauts ?? []) map[astronaut.id] = astronaut.name
    return map
  }, [overview.data])

  const filtered = useMemo(() => {
    return (commands.data ?? []).filter((command) => {
      if (filterAstronaut !== 'all' && command.astronautId !== filterAstronaut) return false
      if (filterStatus !== 'all' && command.status !== filterStatus) return false
      return true
    })
  }, [commands.data, filterAstronaut, filterStatus])

  const pending = (commands.data ?? []).filter((command) => command.status === 'pending').length
  const astronautLabel = names[astronautId] ?? astronautId

  return (
    <section className="page commands-page">
      <header className="page-head">
        <div className="page-head__title">
          <span className="eyebrow">Ground commands</span>
          <h1>Change the plan, keep the trail</h1>
          <p className="muted">Every command moves from queued to delivered only when the crew device acknowledges it. Nothing reports success early.</p>
        </div>
        <div className="chip"><Send size={14} aria-hidden="true" /> {pending} queued</div>
      </header>

      <div className="split commands-split">
        <div className="panel">
          <div className="panel-head">
            <h2 className="panel-title"><ListChecks size={17} aria-hidden="true" /> Command log</h2>
            <span className="faint tiny">{filtered.length} of {(commands.data ?? []).length}</span>
          </div>

          <div className="filter-bar filter-bar--inline">
            <label className="field">
              <span className="field__label">Astronaut</span>
              <select className="select" value={filterAstronaut} onChange={(event) => setFilterAstronaut(event.target.value)}>
                <option value="all">Any astronaut</option>
                {(overview.data?.astronauts ?? []).map((astronaut) => (
                  <option key={astronaut.id} value={astronaut.id}>{astronaut.name}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">State</span>
              <select className="select" value={filterStatus} onChange={(event) => setFilterStatus(event.target.value as typeof filterStatus)}>
                <option value="all">Any state</option>
                <option value="pending">Queued</option>
                <option value="delivered">Delivered</option>
                <option value="failed">Failed</option>
              </select>
            </label>
          </div>

          {commands.error && <p className="auth-error" role="alert">{commands.error}</p>}
          {!commands.data && !commands.error && <span className="skeleton" style={{ height: 200 }} />}

          <div className="command-list stagger">
            {filtered.map((command, index) => {
              const meta = STATUS_META[command.status]
              return (
                <article className="command-card" key={command.id} data-status={meta.status} style={{ '--i': index } as CSSProperties}>
                  <div className="command-card__head">
                    <span className="command-card__type">{COMMAND_TYPE_LABEL[command.type]}</span>
                    <span className="strong small">{names[command.astronautId] ?? command.astronautId}</span>
                    <span className="command-card__status" data-status={meta.status}>
                      <span className="badge__dot" aria-hidden="true" /> {meta.label}
                    </span>
                  </div>
                  <p className="command-card__summary">{payloadSummary(command)}</p>
                  <div className="command-card__meta faint tiny">
                    <span>By {command.createdBy}</span>
                    <span>{relativeTime(command.createdAt, now)}</span>
                    {command.deliveredAt && <span>Delivered {relativeTime(command.deliveredAt, now)}</span>}
                  </div>
                  <details className="command-audit">
                    <summary><ChevronDown size={13} aria-hidden="true" /> Audit trail · {command.audit.length} entries</summary>
                    <ol>
                      {command.audit.map((entry) => (
                        <li key={`${command.id}-${entry.at}-${entry.action}`}>
                          <span className="faint tiny">{new Date(entry.at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                          <span className="small">{entry.action}</span>
                          <span className="faint tiny">{entry.actor}</span>
                        </li>
                      ))}
                    </ol>
                  </details>
                </article>
              )
            })}
          </div>

          {commands.data && filtered.length === 0 && <div className="empty">No commands match these filters.</div>}
        </div>

        <div className="stack">
          <div className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Recipient</h2>
              <span className="faint tiny">Commands are addressed to one crew device</span>
            </div>
            <label className="field">
              <span className="field__label">Astronaut</span>
              <select className="select" value={astronautId} onChange={(event) => setAstronautId(event.target.value)}>
                {(overview.data?.astronauts ?? []).map((astronaut) => (
                  <option key={astronaut.id} value={astronaut.id}>{astronaut.name}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="panel">
            <CommandComposer
              astronautId={astronautId}
              astronautLabel={astronautLabel}
              onCreated={() => commands.reload()}
            />
          </div>

          <div className="panel panel--glow">
            <span className="eyebrow eyebrow--violet"><ShieldCheck size={13} aria-hidden="true" /> Why it is slow on purpose</span>
            <p className="muted small" style={{ marginTop: 8 }}>A command is queued while the link is down and delivered only after the crew device confirms it. The audit trail keeps the author, the time and every state change.</p>
          </div>
        </div>
      </div>
    </section>
  )
}
