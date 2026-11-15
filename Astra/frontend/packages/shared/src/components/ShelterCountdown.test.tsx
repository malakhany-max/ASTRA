import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ShelterCountdown } from './ShelterCountdown'

describe('ShelterCountdown', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('counts down and stops honestly at zero', () => {
    const onElapsed = vi.fn()
    render(<ShelterCountdown seconds={2} onElapsed={onElapsed} />)

    expect(screen.getByRole('timer')).toHaveAccessibleName('00:02 until storm arrival')

    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(screen.getByRole('timer')).toHaveAccessibleName('00:01 until storm arrival')
    expect(onElapsed).not.toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(screen.getByRole('timer')).toHaveAccessibleName('Storm active. Remain in shelter.')
    expect(screen.getByText('00:00')).toBeInTheDocument()
    expect(onElapsed).toHaveBeenCalledTimes(1)

    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(screen.getByRole('timer')).toHaveAccessibleName('Storm active. Remain in shelter.')
    expect(onElapsed).toHaveBeenCalledTimes(1)
  })

  it('restarts when the countdown length changes', () => {
    const { rerender } = render(<ShelterCountdown seconds={2} />)
    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(screen.getByRole('timer')).toHaveAccessibleName('00:01 until storm arrival')

    rerender(<ShelterCountdown seconds={30} />)
    expect(screen.getByRole('timer')).toHaveAccessibleName('00:30 until storm arrival')
  })
})
