import type { AppEvent } from '@contracts'
import { USE_MOCK } from './api'
import { subscribeBus } from '../mock/bus'

export type EventListener = (event: AppEvent) => void

function wsUrl(): string {
  const explicit = ((import.meta.env.VITE_WS_URL as string | undefined) ?? '').trim()
  if (explicit) return explicit

  const base = (import.meta.env.VITE_API_BASE as string | undefined)?.trim()
  try {
    const url = new URL(base && base !== 'mock' ? base : window.location.origin)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    url.pathname = '/ws/events'
    url.search = ''
    return url.toString()
  } catch {
    return 'ws://localhost:4000/ws/events'
  }
}

export function connectEvents(listener: EventListener): () => void {
  if (USE_MOCK) return subscribeBus(listener)

  let socket: WebSocket | null = null
  let closed = false
  let retry = 1000

  const open = () => {
    if (closed) return
    socket = new WebSocket(wsUrl())
    socket.onopen = () => {
      retry = 1000
    }
    socket.onmessage = (message) => {
      try {
        listener(JSON.parse(String(message.data)) as AppEvent)
      } catch {
      }
    }
    socket.onclose = () => {
      if (closed) return
      window.setTimeout(open, retry)
      retry = Math.min(retry * 1.7, 15000)
    }
  }

  open()
  return () => {
    closed = true
    socket?.close()
  }
}
