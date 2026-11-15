export function relativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return 'unknown'
  const diff = Math.max(0, now - new Date(iso).getTime())
  const min = Math.floor(diff / 60_000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min} min ago`
  const hours = Math.floor(min / 60)
  if (hours < 48) return `${hours} h ago`
  const days = Math.floor(hours / 24)
  return `${days} d ago`
}

export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds))
  const m = Math.floor(s / 60)
  const rest = s % 60
  return `${String(m).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export function formatNumber(value: number, precision = 0): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  })
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function rankOf(status: string): number {
  return status === 'urgent' ? 3 : status === 'attention' ? 2 : status === 'unknown' ? 1 : 0
}

export function worstStatus(statuses: string[]): 'normal' | 'attention' | 'urgent' | 'unknown' {
  let worst: 'normal' | 'attention' | 'urgent' | 'unknown' = 'normal'
  for (const s of statuses) {
    if (rankOf(s) > rankOf(worst)) worst = s as typeof worst
  }
  return worst
}
