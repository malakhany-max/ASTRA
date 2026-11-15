import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { X } from 'lucide-react'

export interface ToastInput {
  title: string
  message?: string
  severity?: 'info' | 'attention' | 'urgent'
}

interface ToastItem extends ToastInput {
  id: number
  severity: 'info' | 'attention' | 'urgent'
}

type PushToast = (toast: ToastInput) => void

const ToastContext = createContext<PushToast>(() => {})

export function useToast(): PushToast {
  return useContext(ToastContext)
}

const statusOf = { info: 'normal', attention: 'attention', urgent: 'urgent' } as const

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const serial = useRef(0)
  const timers = useRef<number[]>([])

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((item) => item.id !== id))
  }, [])

  const push = useCallback(
    (toast: ToastInput) => {
      serial.current += 1
      const id = serial.current
      const severity = toast.severity ?? 'info'
      setItems((current) => [...current.slice(-3), { ...toast, severity, id }])
      const timer = window.setTimeout(() => dismiss(id), severity === 'urgent' ? 10_000 : 6500)
      timers.current.push(timer)
    },
    [dismiss],
  )

  useEffect(() => () => timers.current.forEach((timer) => window.clearTimeout(timer)), [])

  const value = useMemo(() => push, [push])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toaster" aria-live="polite" aria-atomic="false">
        {items.map((item) => (
          <div
            className="toast"
            key={item.id}
            data-status={statusOf[item.severity]}
            role={item.severity === 'urgent' ? 'alert' : 'status'}
          >
            <span className="toast__bar" aria-hidden="true" />
            <div>
              <div className="toast__title">{item.title}</div>
              {item.message && <div className="toast__msg">{item.message}</div>}
            </div>
            <button
              type="button"
              className="toast__close"
              onClick={() => dismiss(item.id)}
              aria-label="Dismiss notification"
            >
              <X size={14} aria-hidden="true" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
