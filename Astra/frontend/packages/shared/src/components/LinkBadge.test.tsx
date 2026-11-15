import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LinkBadge } from './LinkBadge'

const NOW = new Date('2026-11-13T12:00:00.000Z').getTime()
const THREE_HOURS_AGO = new Date(NOW - 3 * 3_600_000).toISOString()

describe('LinkBadge', () => {
  it('shows a calm autonomous mode to the astronaut when the link is down', () => {
    render(<LinkBadge state="down" lastSyncAt={THREE_HOURS_AGO} now={NOW} />)

    const badge = screen.getByTestId('link-badge')
    expect(badge).toHaveTextContent('Autonomous Mode')
    expect(badge).toHaveClass('link-badge--autonomous')
    expect(badge).not.toHaveClass('link-badge--down')
    expect(badge).toHaveAttribute('data-state', 'down')
  })

  it('keeps the astronaut label calm for autonomous and degraded links', () => {
    const { rerender } = render(<LinkBadge state="autonomous" now={NOW} />)
    expect(screen.getByTestId('link-badge')).toHaveTextContent('Autonomous Mode')

    rerender(<LinkBadge state="degraded" now={NOW} />)
    expect(screen.getByTestId('link-badge')).toHaveTextContent('Low link')
    expect(screen.getByTestId('link-badge')).toHaveClass('link-badge--degraded')
  })

  it('tells the ground team the truth about stale data', () => {
    render(<LinkBadge state="down" variant="ground" lastSyncAt={THREE_HOURS_AGO} now={NOW} />)

    const badge = screen.getByTestId('link-badge')
    expect(badge).toHaveTextContent('Link down')
    expect(badge).toHaveTextContent('Last known 3 h ago')
    expect(badge).toHaveClass('link-badge--down')
  })

  it('marks a connected ground link as live with its age', () => {
    render(<LinkBadge state="connected" variant="ground" lastSyncAt={THREE_HOURS_AGO} now={NOW} />)
    expect(screen.getByTestId('link-badge')).toHaveTextContent('Live · Synced 3 h ago')
  })
})
