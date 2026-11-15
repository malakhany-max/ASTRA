import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('shows the status as text, not color alone', () => {
    render(<StatusBadge status="urgent" label="Heart rate" />)

    expect(screen.getByText('Urgent')).toBeInTheDocument()
    expect(screen.getByLabelText('Heart rate: Urgent')).toHaveAttribute('data-status', 'urgent')
  })

  it('renders every status with its own text and tone', () => {
    const { rerender } = render(<StatusBadge status="normal" />)
    expect(screen.getByLabelText('Normal')).toHaveAttribute('data-status', 'normal')

    rerender(<StatusBadge status="attention" />)
    expect(screen.getByLabelText('Attention')).toHaveAttribute('data-status', 'attention')

    rerender(<StatusBadge status="unknown" />)
    expect(screen.getByLabelText('No reading')).toHaveAttribute('data-status', 'unknown')
  })

  it('supports the large touch size', () => {
    render(<StatusBadge status="normal" size="lg" />)
    expect(screen.getByLabelText('Normal')).toHaveClass('badge--lg')
  })
})
