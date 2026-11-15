import { CloudOff, Radio, Satellite, TriangleAlert } from 'lucide-react'
import type { LinkStateValue } from '@contracts'
import { relativeTime } from '../lib/format'
import { ui } from '../lib/i18n'

export interface LinkBadgeProps {
  state: LinkStateValue
  lastSyncAt?: string
  now?: number
  variant?: 'astronaut' | 'ground'
  className?: string
}

export function LinkBadge({
  state,
  lastSyncAt,
  now = Date.now(),
  variant = 'astronaut',
  className = '',
}: LinkBadgeProps) {
  const age = relativeTime(lastSyncAt, now)

  let tone: 'connected' | 'autonomous' | 'degraded' | 'down' = state
  let text = ''
  let Icon = Satellite

  if (variant === 'astronaut') {
    if (state === 'connected') {
      text = ui.link.connected
      Icon = Satellite
    } else if (state === 'degraded') {
      text = ui.link.degraded
      tone = 'degraded'
      Icon = Radio
    } else {
      text = ui.link.autonomous
      tone = 'autonomous'
      Icon = CloudOff
    }
  } else if (state === 'connected') {
    text = `${ui.common.live} · ${ui.common.synced} ${age}`
    Icon = Satellite
  } else if (state === 'degraded') {
    text = `${ui.link.degraded} · ${ui.common.lastKnown} ${age}`
    tone = 'degraded'
    Icon = TriangleAlert
  } else if (state === 'autonomous') {
    text = `${ui.link.autonomous} · ${ui.common.lastKnown} ${age}`
    tone = 'autonomous'
    Icon = CloudOff
  } else {
    text = `${ui.link.down} · ${ui.common.lastKnown} ${age}`
    tone = 'down'
    Icon = CloudOff
  }

  return (
    <span
      className={`link-badge link-badge--${tone} ${className}`}
      data-testid="link-badge"
      data-state={state}
      aria-label={text}
      title={text}
    >
      <Icon size={14} aria-hidden="true" />
      {text}
    </span>
  )
}
