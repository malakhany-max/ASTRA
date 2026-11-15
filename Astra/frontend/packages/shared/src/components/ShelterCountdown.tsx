import { useEffect, useRef, useState } from 'react'
import { formatClock } from '../lib/format'

export interface ShelterCountdownProps {
  seconds: number
  size?: number
  onElapsed?: () => void
}

export function ShelterCountdown({ seconds, size = 170, onElapsed }: ShelterCountdownProps) {
  const [remaining, setRemaining] = useState(seconds)
  const elapsedRef = useRef(false)
  const onElapsedRef = useRef(onElapsed)
  onElapsedRef.current = onElapsed

  useEffect(() => {
    setRemaining(seconds)
    elapsedRef.current = false
  }, [seconds])

  useEffect(() => {
    const id = window.setInterval(() => {
      setRemaining((current) => {
        if (current <= 1) {
          window.clearInterval(id)
          if (!elapsedRef.current) {
            elapsedRef.current = true
            onElapsedRef.current?.()
          }
          return 0
        }
        return current - 1
      })
    }, 1000)
    return () => window.clearInterval(id)
  }, [seconds])

  const radius = 54
  const circumference = 2 * Math.PI * radius
  const pct = seconds === 0 ? 0 : remaining / seconds

  return (
    <div
      className="shelter__countdown"
      style={{ width: size, height: size }}
      data-testid="shelter-countdown"
      role="timer"
      aria-label={
        remaining > 0
          ? `${formatClock(remaining)} until storm arrival`
          : 'Storm active. Remain in shelter.'
      }
    >
      <svg viewBox="0 0 140 140" width={size} height={size} aria-hidden="true">
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke="rgba(255, 255, 255, 0.12)"
          strokeWidth="8"
          strokeDasharray={`${circumference} ${circumference}`}
        />
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke={remaining > 0 ? 'var(--amber)' : 'var(--red)'}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${circumference * pct} ${circumference}`}
          transform="rotate(-90 70 70)"
          style={{ transition: 'stroke-dasharray 1s linear, stroke .3s ease' }}
        />
      </svg>
      <span className="shelter__countdown-value" aria-hidden="true">
        {formatClock(remaining)}
      </span>
      <span className="shelter__countdown-label" aria-hidden="true">
        {remaining > 0 ? 'Until arrival' : 'Storm active'}
      </span>
    </div>
  )
}
