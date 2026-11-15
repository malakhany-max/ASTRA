import type { HealthStatus } from '@contracts'
import { clamp, formatNumber } from '../lib/format'

export interface GaugeProps {
  value: number
  max: number
  unit: string
  label?: string
  status?: HealthStatus
  size?: number
  precision?: number
}

export function Gauge({
  value,
  max,
  unit,
  label,
  status = 'normal',
  size = 190,
  precision = 1,
}: GaugeProps) {
  const radius = 54
  const circumference = 2 * Math.PI * radius
  const sweep = 0.75
  const pct = clamp(max === 0 ? 0 : value / max, 0, 1)

  return (
    <div
      className="gauge"
      data-status={status}
      role="img"
      aria-label={`${label ?? 'Gauge'}: ${formatNumber(value, precision)} ${unit} of ${formatNumber(max, precision)} ${unit}`}
      style={{ width: size, height: size }}
    >
      <svg viewBox="0 0 140 140" width={size} height={size} aria-hidden="true">
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke="rgba(126, 166, 255, 0.12)"
          strokeWidth="11"
          strokeLinecap="round"
          strokeDasharray={`${circumference * sweep} ${circumference}`}
          transform="rotate(135 70 70)"
        />
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke="var(--status)"
          strokeWidth="11"
          strokeLinecap="round"
          strokeDasharray={`${circumference * sweep * pct} ${circumference}`}
          transform="rotate(135 70 70)"
          style={{ filter: 'drop-shadow(0 0 8px var(--status))', transition: 'stroke-dasharray .8s ease' }}
        />
      </svg>
      <div className="gauge__center">
        <span className="gauge__value">{formatNumber(value, precision)}</span>
        <span className="gauge__unit">{unit}</span>
        {label && <span className="faint tiny">{label}</span>}
      </div>
    </div>
  )
}
