import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, ShieldAlert, ShieldCheck, ShieldX, TriangleAlert } from 'lucide-react'
import type { SecurityCheck, SecurityLevel } from '@contracts'
import { relativeTime } from '../lib/format'
import { ui } from '../lib/i18n'

export interface ShieldIconProps {
  level: SecurityLevel
  checks?: SecurityCheck[]
  headline?: string
  lastEventAt?: string
}

const icons = {
  ok: ShieldCheck,
  degraded: ShieldAlert,
  critical: ShieldX,
} as const

const checkIcons = {
  ok: CheckCircle2,
  degraded: TriangleAlert,
  critical: ShieldX,
} as const

export function ShieldIcon({ level, checks = [], headline, lastEventAt }: ShieldIconProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const Icon = icons[level]

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false)
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div ref={ref} style={{ position: 'relative' }} data-status={level}>
      <button
        type="button"
        className="shield"
        aria-label={`Security: ${ui.security[level]}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        title={`Security: ${ui.security[level]}`}
        onClick={() => setOpen((value) => !value)}
        data-testid="shield-icon"
      >
        <Icon size={19} aria-hidden="true" />
      </button>
      {open && (
        <div className="popover" role="dialog" aria-label="Security status">
          <div className="row row--between" style={{ marginBottom: 8 }}>
            <strong className="small">{headline ?? `Security: ${ui.security[level]}`}</strong>
            <span className="badge" data-status={level}>
              <span className="badge__dot" aria-hidden="true" />
              {ui.security[level]}
            </span>
          </div>
          {checks.map((check) => {
            const CheckIcon = checkIcons[check.state]
            return (
              <div className="security-check" key={check.id} data-status={check.state}>
                <span className="security-check__state" aria-hidden="true">
                  <CheckIcon size={15} />
                </span>
                <div>
                  <div className="strong">{check.label}</div>
                  <div className="faint tiny">{check.detail}</div>
                </div>
              </div>
            )
          })}
          {lastEventAt && (
            <p className="faint tiny" style={{ marginTop: 10 }}>
              Last security event {relativeTime(lastEventAt)}
            </p>
          )}
          <p className="faint tiny" style={{ marginTop: 10 }}>
            Only cleared medical staff can read crew vitals. Data stays encrypted end to end.
          </p>
        </div>
      )}
    </div>
  )
}
