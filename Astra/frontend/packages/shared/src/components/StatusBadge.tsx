import type { HealthStatus } from '@contracts'
import { ui } from '../lib/i18n'

export interface StatusBadgeProps {
  status: HealthStatus
  label?: string
  size?: 'sm' | 'lg'
  live?: boolean
  className?: string
}

export function StatusBadge({
  status,
  label,
  size = 'sm',
  live = false,
  className = '',
}: StatusBadgeProps) {
  const text = ui.status[status]
  return (
    <span
      className={`badge ${size === 'lg' ? 'badge--lg' : ''} ${live ? 'badge--live' : ''} ${className}`}
      data-status={status}
      aria-label={label ? `${label}: ${text}` : text}
    >
      <span className="badge__dot" aria-hidden="true" />
      {text}
    </span>
  )
}
