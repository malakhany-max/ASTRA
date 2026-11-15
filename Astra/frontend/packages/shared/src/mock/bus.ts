import type { AppEvent } from '@contracts'

type Listener = (event: AppEvent) => void

const listeners = new Set<Listener>()
const history: AppEvent[] = []
let serial = 0

export function emitEvent(
  type: string,
  message: string,
  severity: AppEvent['severity'] = 'info',
  payload: Record<string, unknown> = {},
): AppEvent {
  serial += 1
  const event: AppEvent = {
    id: `evt-${Date.now()}-${serial}`,
    type,
    at: new Date().toISOString(),
    severity,
    message,
    payload,
  }
  history.push(event)
  if (history.length > 60) history.shift()
  for (const listener of listeners) listener(event)
  return event
}

export function subscribeBus(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function recentEvents(): AppEvent[] {
  return [...history]
}
