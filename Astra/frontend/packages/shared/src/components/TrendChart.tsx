import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Baseline, IndicatorSample } from '@contracts'
import { formatNumber } from '../lib/format'
import { ui } from '../lib/i18n'

export interface TrendChartProps {
  data: IndicatorSample[]
  baseline: Baseline
  unit: string
  label?: string
  color?: string
  height?: number
  precision?: number
}

export function TrendChart({
  data,
  baseline,
  unit,
  label = 'Indicator',
  color = 'var(--cyan)',
  height = 260,
  precision = 1,
}: TrendChartProps) {
  const points = data.map((sample) => ({ ...sample, ts: new Date(sample.t).getTime() }))

  if (points.length === 0) {
    return (
      <div className="empty" style={{ minHeight: height }}>
        <span>{ui.common.noData}</span>
        <span className="tiny">The next sync will fill this chart.</span>
      </div>
    )
  }

  const values = points.map((p) => p.value)
  const low = Math.min(baseline.low, ...values)
  const high = Math.max(baseline.high, ...values)
  const pad = Math.max((high - low) * 0.15, 0.5)
  const span = points[points.length - 1].ts - points[0].ts

  const tick = (ts: number) =>
    span > 40 * 3_600_000
      ? new Date(ts).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
      : new Date(ts).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })

  const latest = points[points.length - 1]
  const reduceMotion =
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  return (
    <div>
      <div
        className="chart-wrap"
        role="img"
        aria-label={`${label} trend chart. Latest ${formatNumber(latest.value, precision)} ${unit}. Personal baseline ${baseline.low} to ${baseline.high} ${unit}.`}
        data-testid="trend-chart"
        style={{ height }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 6" vertical={false} />
            <ReferenceArea
              y1={baseline.low}
              y2={baseline.high}
              fill="rgba(84, 230, 255, 0.09)"
              stroke="rgba(84, 230, 255, 0.28)"
              strokeDasharray="4 4"
            />
            <XAxis
              dataKey="ts"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={tick}
              tickLine={false}
              axisLine={false}
              minTickGap={46}
              tick={{ fontSize: 13 }}
            />
            <YAxis
              domain={[low - pad, high + pad]}
              tickLine={false}
              axisLine={false}
              width={46}
              tick={{ fontSize: 13 }}
              tickFormatter={(value: number) => formatNumber(value, precision)}
            />
            <Tooltip
              contentStyle={{
                background: 'rgba(6, 12, 26, 0.96)',
                border: '1px solid rgba(126, 196, 255, 0.32)',
                borderRadius: 10,
                fontSize: 13,
              }}
              labelFormatter={(ts) => new Date(Number(ts)).toLocaleString('en-GB')}
              formatter={(value) => [`${formatNumber(Number(value), precision)} ${unit}`, label]}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={2.4}
              dot={false}
              activeDot={{ r: 4, fill: color, stroke: '#041018', strokeWidth: 2 }}
              isAnimationActive={!reduceMotion}
              animationDuration={900}
              animationEasing="ease-out"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="chart-legend" style={{ marginTop: 8 }}>
        <span>
          <span
            className="chart-legend__swatch"
            style={{ background: 'linear-gradient(90deg, var(--cyan), var(--violet))' }}
            aria-hidden="true"
          />
          {label}
        </span>
        <span>
          <span
            className="chart-legend__swatch"
            style={{ background: 'rgba(84, 230, 255, 0.18)', border: '1px dashed rgba(84,230,255,0.5)' }}
            aria-hidden="true"
          />
          {ui.common.baseline} · {baseline.low}–{baseline.high} {unit}
        </span>
      </div>
    </div>
  )
}
