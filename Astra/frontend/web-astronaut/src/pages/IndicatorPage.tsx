import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Info, Ruler, ScanLine } from 'lucide-react'
import type { Indicator, IndicatorSeries, Range } from '@contracts'
import { relativeTime, StatusBadge, TrendChart, useApi, useNow } from '@astra/shared'
import { ASTRONAUT_ID, INDICATOR_GUIDE } from '../lib/astro'

const RANGES: { id: Range; label: string }[] = [
  { id: '24h', label: '24 hours' },
  { id: '7d', label: '7 days' },
  { id: '30d', label: '30 days' },
]

export function IndicatorPage() {
  const { key = '' } = useParams()
  const [range, setRange] = useState<Range>('24h')
  const now = useNow(30_000)
  const indicators = useApi<Indicator[]>(`/api/astronauts/${ASTRONAUT_ID}/indicators`, { live: true })
  const series = useApi<IndicatorSeries>(`/api/astronauts/${ASTRONAUT_ID}/indicators/${key}?range=${range}`)

  const indicator = indicators.data?.find((item) => item.key === key) ?? null
  const guide = INDICATOR_GUIDE[key]

  const stats = useMemo(() => {
    const samples = series.data?.samples ?? []
    if (samples.length === 0) return null
    const values = samples.map((sample) => sample.value)
    return {
      min: Math.min(...values),
      max: Math.max(...values),
      mean: values.reduce((total, value) => total + value, 0) / values.length,
      last: samples.slice(-6).reverse(),
    }
  }, [series.data])

  const precision = indicator?.precision ?? (key === 'bloodGlucose' ? 1 : 0)

  return (
    <section className="page">
      <header className="page-head">
        <div className="page-head__title">
          <Link to="/" className="back-link"><ArrowLeft size={15} aria-hidden="true" /> All measurements</Link>
          <span className="eyebrow">Indicator detail</span>
          <h1>{indicator?.label ?? key}</h1>
          <p className="muted">{indicator ? indicator.reason : 'Loading the latest reading and trend.'}</p>
        </div>
        {indicator && (
          <div className="detail-headline" data-status={indicator.status}>
            <span className="detail-headline__value numeric">{indicator.value}{indicator.secondary != null ? <span className="detail-headline__secondary">/{indicator.secondary}</span> : null}</span>
            <span className="detail-headline__unit">{indicator.unit}</span>
            <StatusBadge status={indicator.status} size="lg" label={indicator.label} />
            <span className="faint tiny">Updated {relativeTime(indicator.updatedAt, now)}</span>
          </div>
        )}
      </header>

      {indicators.error && <p className="muted small" role="alert">{indicators.error}</p>}

      <div className="split">
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2 className="panel-title">Trend</h2>
              <p className="panel-sub">The shaded band is your personal baseline, not a population average.</p>
            </div>
            <div className="segmented" role="group" aria-label="Time range">
              {RANGES.map((item) => (
                <button key={item.id} type="button" aria-pressed={range === item.id} onClick={() => setRange(item.id)}>{item.label}</button>
              ))}
            </div>
          </div>

          {series.loading && !series.data && <span className="skeleton" style={{ height: 280 }} />}
          {series.error && <p className="muted small" role="alert">{series.error}</p>}
          {series.data && <TrendChart data={series.data.samples} baseline={series.data.baseline} unit={series.data.unit} label={series.data.label} precision={precision} height={280} />}

          {stats && (
            <div className="kpi-row" style={{ marginTop: 18 }}>
              <div className="kpi"><span className="kpi__value numeric">{stats.mean.toFixed(precision)}</span><span className="kpi__label">Average</span></div>
              <div className="kpi"><span className="kpi__value numeric">{stats.min.toFixed(precision)}</span><span className="kpi__label">Lowest</span></div>
              <div className="kpi"><span className="kpi__value numeric">{stats.max.toFixed(precision)}</span><span className="kpi__label">Highest</span></div>
              <div className="kpi"><span className="kpi__value numeric">{series.data?.samples.length ?? 0}</span><span className="kpi__label">Samples</span></div>
            </div>
          )}
        </div>

        <div className="stack">
          {guide && (
            <>
              <div className="panel guide-card">
                <span className="guide-card__icon" aria-hidden="true"><Info size={17} /></span>
                <div>
                  <h3 className="panel-title">Why we measure this</h3>
                  <p className="muted small">{guide.why}</p>
                </div>
              </div>
              <div className="panel guide-card">
                <span className="guide-card__icon" aria-hidden="true"><Ruler size={17} /></span>
                <div>
                  <h3 className="panel-title">How to measure</h3>
                  <p className="muted small">{guide.how}</p>
                </div>
              </div>
            </>
          )}

          <div className="panel">
            <div className="panel-head">
              <h3 className="panel-title"><ScanLine size={15} aria-hidden="true" /> Latest samples</h3>
            </div>
            {!stats && <p className="faint small">No samples in this range yet.</p>}
            <div className="sample-list">
              {stats?.last.map((sample) => (
                <div className="sample-row" key={sample.t}>
                  <span className="faint tiny">{new Date(sample.t).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                  <span className="numeric strong">{sample.value.toFixed(precision)} {series.data?.unit}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
