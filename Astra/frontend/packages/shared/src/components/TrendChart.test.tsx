import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { IndicatorSample } from '@contracts'
import { TrendChart } from './TrendChart'

const samples: IndicatorSample[] = [
  { t: '2026-11-13T08:00:00.000Z', value: 64 },
  { t: '2026-11-13T09:00:00.000Z', value: 71 },
  { t: '2026-11-13T10:00:00.000Z', value: 90 },
]

describe('TrendChart', () => {
  it('describes the latest value and the personal baseline for screen readers', () => {
    render(
      <TrendChart
        data={samples}
        baseline={{ low: 60, high: 80 }}
        unit="bpm"
        label="Heart rate"
        precision={0}
      />,
    )

    const chart = screen.getByTestId('trend-chart')
    expect(chart).toHaveAttribute(
      'aria-label',
      'Heart rate trend chart. Latest 90 bpm. Personal baseline 60 to 80 bpm.',
    )
  })

  it('always shows the baseline band in the legend', () => {
    render(
      <TrendChart
        data={samples}
        baseline={{ low: 60, high: 80 }}
        unit="bpm"
        label="Heart rate"
        precision={0}
      />,
    )
    expect(screen.getByText(/Personal baseline · 60–80 bpm/)).toBeInTheDocument()
  })

  it('explains an empty chart instead of drawing a flat line', () => {
    render(<TrendChart data={[]} baseline={{ low: 60, high: 80 }} unit="bpm" />)

    expect(screen.getByText('No data yet')).toBeInTheDocument()
    expect(screen.getByText('The next sync will fill this chart.')).toBeInTheDocument()
    expect(screen.queryByTestId('trend-chart')).not.toBeInTheDocument()
  })
})
