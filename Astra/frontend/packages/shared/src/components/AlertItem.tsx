import { Check, HeartPulse, Radiation, ShieldAlert } from 'lucide-react'
import type { Alert } from '@contracts'
import { relativeTime } from '../lib/format'
import { StatusBadge } from './StatusBadge'

export interface AlertItemProps {
  alert: Alert
  astronautName?: string
  canAck?: boolean
  busy?: boolean
  onAck?: (id: string) => void
  now?: number
}

const priorityIcon = {
  security: ShieldAlert,
  radiation: Radiation,
  health: HeartPulse,
} as const

const severityStatus = {
  urgent: 'urgent',
  attention: 'attention',
  info: 'normal',
} as const

export function AlertItem({
  alert,
  astronautName,
  canAck = false,
  busy = false,
  onAck,
  now = Date.now(),
}: AlertItemProps) {
  const PriorityIcon = priorityIcon[alert.priority]
  const status = severityStatus[alert.severity]

  return (
    <article className="alert" data-status={status} aria-label={`${alert.priority} alert: ${alert.title}`}>
      <span className="alert__stripe" aria-hidden="true" />
      <div>
        <div className="alert__top">
          <span className={`priority-tag priority-tag--${alert.priority}`}>
            <PriorityIcon size={11} style={{ verticalAlign: -1, marginRight: 4 }} aria-hidden="true" />
            {alert.priority}
          </span>
          <span className="alert__title">{alert.title}</span>
          <StatusBadge status={status} label="Severity" />
        </div>
        <p className="alert__why">
          <strong className="strong">Why: </strong>
          {alert.why}
        </p>
        <div className="alert__meta">
          {astronautName && <span>{astronautName}</span>}
          <span>{alert.source}</span>
          <span>{relativeTime(alert.createdAt, now)}</span>
          {alert.acknowledged && (
            <span className="badge" data-status="normal">
              <Check size={12} aria-hidden="true" /> {alert.acknowledgedBy ?? 'Acknowledged'}
            </span>
          )}
        </div>
      </div>
      {canAck && !alert.acknowledged && onAck && (
        <div className="alert__actions">
          <button
            type="button"
            className="btn btn--calm"
            onClick={() => onAck(alert.id)}
            disabled={busy}
          >
            <Check size={15} aria-hidden="true" />
            Acknowledge
          </button>
        </div>
      )}
    </article>
  )
}
