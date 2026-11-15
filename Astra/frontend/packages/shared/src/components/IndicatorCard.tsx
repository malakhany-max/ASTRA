import { ChevronRight, Minus, TrendingDown, TrendingUp } from 'lucide-react'
import type { Indicator } from '@contracts'
import { formatNumber, relativeTime } from '../lib/format'
import { StatusBadge } from './StatusBadge'

export interface IndicatorCardProps {
  indicator: Indicator
  now?: number
  onOpen?: (key: string) => void
}

const trendMeta = {
  up: { Icon: TrendingUp, label: 'Trending up' },
  down: { Icon: TrendingDown, label: 'Trending down' },
  stable: { Icon: Minus, label: 'Stable' },
} as const

export function IndicatorCard({ indicator, now = Date.now(), onOpen }: IndicatorCardProps) {
  const { Icon, label: trendLabel } = trendMeta[indicator.trend]
  const value = `${formatNumber(indicator.value, indicator.precision ?? 0)}${
    indicator.secondary != null ? `/${formatNumber(indicator.secondary, 0)}` : ''
  }`

  const content = (
    <>
      <div className="indicator-card__top">
        <span className="indicator-card__label">{indicator.label}</span>
        <StatusBadge status={indicator.status} label={indicator.label} />
      </div>
      <div className="indicator-card__value" key={indicator.updatedAt}>
        {value}
        <span className="indicator-card__unit">{indicator.unit}</span>
      </div>
      <p className="indicator-card__reason">{indicator.reason}</p>
      <div className="indicator-card__foot">
        <span>{relativeTime(indicator.updatedAt, now)}</span>
        <span className={`trend trend--${indicator.trend}`}>
          <Icon size={13} aria-hidden="true" />
          <span className="sr-only">{trendLabel}</span>
          {indicator.trend}
        </span>
      </div>
    </>
  )

  if (!onOpen) {
    return (
      <article
        className="indicator-card"
        data-status={indicator.status}
        aria-label={`${indicator.label}: ${value} ${indicator.unit}, ${indicator.status}`}
      >
        {content}
      </article>
    )
  }

  return (
    <button
      type="button"
      className="indicator-card"
      data-status={indicator.status}
      onClick={() => onOpen(indicator.key)}
      aria-label={`Open ${indicator.label}: ${value} ${indicator.unit}, ${indicator.status}`}
    >
      {content}
      <ChevronRight
        size={16}
        aria-hidden="true"
        style={{ position: 'absolute', right: 14, bottom: 14, opacity: 0.35 }}
      />
    </button>
  )
}
