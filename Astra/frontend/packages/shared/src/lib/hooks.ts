import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, apiGet, errorMessage } from './api'
import { connectEvents } from './events'
import { USE_MOCK } from './api'

export interface ApiState<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => void
}

export function useApi<T>(
  path: string | null,
  options: { live?: boolean; livePrefixes?: string[] } = {},
): ApiState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(Boolean(path))
  const [version, setVersion] = useState(0)
  const livePrefixesRef = useRef(options.livePrefixes)

  const reload = useCallback(() => setVersion((v) => v + 1), [])

  useEffect(() => {
    if (!path) return
    let alive = true
    let attempt = 0
    let retry: number | undefined
    const controller = new AbortController()
    setLoading(true)
    const load = () => {
      apiGet<T>(path, controller.signal)
        .then((result) => {
          if (!alive) return
          setData(result)
          setError(null)
          setLoading(false)
        })
        .catch((err) => {
          if (!alive || controller.signal.aborted) return
          const transient = err instanceof TypeError || (err instanceof ApiError && err.status >= 500)
          if (transient && attempt < 15) {
            attempt += 1
            retry = window.setTimeout(load, 900)
            return
          }
          setError(errorMessage(err))
          setLoading(false)
        })
    }
    load()
    return () => {
      alive = false
      window.clearTimeout(retry)
      controller.abort()
    }
  }, [path, version])

  useEffect(() => {
    if (!options.live) return
    const groundClient = (import.meta.env.VITE_APP_KIND as string | undefined) === 'ground'
    const poll = !USE_MOCK && groundClient ? window.setInterval(reload, 4000) : undefined
    let timer: number | undefined
    const unsubscribe = connectEvents((event) => {
      const prefixes = livePrefixesRef.current
      if (prefixes && prefixes.length > 0 && !prefixes.some((p) => event.type.startsWith(p))) {
        return
      }
      window.clearTimeout(timer)
      timer = window.setTimeout(reload, 220)
    })
    return () => {
      window.clearTimeout(timer)
      if (poll !== undefined) window.clearInterval(poll)
      unsubscribe()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, options.live])

  return { data, error, loading, reload }
}

export function useNow(intervalMs = 30_000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs)
    return () => window.clearInterval(id)
  }, [intervalMs])
  return now
}

export function useDocumentTitle(title: string): void {
  useEffect(() => {
    document.title = title
  }, [title])
}
