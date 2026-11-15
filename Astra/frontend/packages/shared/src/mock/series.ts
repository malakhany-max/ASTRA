import type { Indicator, IndicatorSample, Range } from '@contracts'

const MIN = 60_000
const HOUR = 3_600_000
const DAY = 86_400_000

const RANGES: Record<Range, { span: number; step: number }> = {
  '24h': { span: 24 * HOUR, step: 15 * MIN },
  '7d': { span: 7 * DAY, step: HOUR },
  '30d': { span: 30 * DAY, step: 3 * HOUR },
}

interface Limits {
  min: number
  max: number
  precision: number
}

const LIMITS: Record<string, Limits> = {
  heartRate: { min: 42, max: 150, precision: 0 },
  spo2: { min: 91, max: 100, precision: 1 },
  bloodPressure: { min: 85, max: 165, precision: 0 },
  bloodGlucose: { min: 3, max: 11, precision: 1 },
  temperature: { min: 35.6, max: 38.2, precision: 1 },
  sleep: { min: 3.5, max: 10, precision: 1 },
  dizziness: { min: 0, max: 3, precision: 0 },
  mood: { min: 1, max: 5, precision: 0 },
  radiation: { min: 0.2, max: 1000, precision: 1 },
}

const FALLBACK: Limits = { min: 0, max: 100, precision: 1 }

const DAILY_LOG_HOUR: Record<string, number> = { sleep: 7, mood: 20, dizziness: 20 }

function hashString(value: string): number {
  let hash = 2166136261
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}

function draw(seed: number): number {
  let a = seed
  a = (a + 0x6d2b79f5) | 0
  let t = Math.imul(a ^ (a >>> 15), 1 | a)
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296
}

function noiseAt(key: string, ts: number, period: number): number {
  const position = ts / period
  const node = Math.floor(position)
  const fraction = position - node
  const start = draw(hashString(`${key}:${node}`)) - 0.5
  const end = draw(hashString(`${key}:${node + 1}`)) - 0.5
  const ease = fraction * fraction * (3 - 2 * fraction)
  return start + (end - start) * ease
}

function turbulence(key: string, ts: number): number {
  return 0.6 * noiseAt(`${key}:slow`, ts, 5 * HOUR)
    + 0.3 * noiseAt(`${key}:mid`, ts, 55 * MIN)
    + 0.1 * noiseAt(`${key}:fast`, ts, 11 * MIN)
}

function localHour(ts: number): number {
  const date = new Date(ts)
  return date.getHours() + date.getMinutes() / 60
}

function localMidnight(ts: number): number {
  const date = new Date(ts)
  date.setHours(0, 0, 0, 0)
  return date.getTime()
}

function meal(hour: number, at: number): number {
  return Math.exp(-((hour - at) ** 2) / 1.6)
}

function clamp(value: number, limits: Limits): number {
  return Math.min(limits.max, Math.max(limits.min, value))
}

function continuousValue(astronautId: string, key: string, ts: number, mean: number): number {
  const hour = localHour(ts)
  const day = noiseAt(`${astronautId}:${key}:day`, ts, DAY)
  const noise = turbulence(`${astronautId}:${key}:noise`, ts)

  switch (key) {
    case 'heartRate':
      return mean
        + 7 * Math.cos(((hour - 15) * Math.PI * 2) / 24)
        + 3.2 * meal(hour, 7.5)
        + 2.4 * meal(hour, 12.5)
        + 3 * meal(hour, 17.5)
        + 2.5 * day
        + 2.4 * noise
    case 'spo2':
      return mean + 0.3 * Math.cos(((hour - 14) * Math.PI * 2) / 24) + 0.3 * day + 0.25 * noise
    case 'bloodPressure':
      return mean
        + 5 * Math.cos(((hour - 16) * Math.PI * 2) / 24)
        + 2.5 * meal(hour, 13)
        + 3 * day
        + 2.5 * noise
    case 'bloodGlucose':
      return mean
        - 0.15
        + 1.6 * meal(hour, 8)
        + 1.9 * meal(hour, 13)
        + 1.5 * meal(hour, 19)
        + 0.25 * day
        + 0.15 * noise
    case 'temperature':
      return mean - 0.08 + 0.26 * Math.cos(((hour - 16) * Math.PI * 2) / 24) + 0.06 * day + 0.05 * noise
    case 'radiation': {
      const storm = draw(hashString(`${astronautId}:storm:${localMidnight(ts)}`)) < 1 / 21
        ? 12 * Math.exp(-((hour - 14) ** 2) / 1.5)
        : 0
      return mean + storm + 0.3 * day + 0.25 * noise
    }
    default:
      return mean + 4 * day + 3 * noise
  }
}

function diastolicValue(astronautId: string, ts: number, base: number, systolic: number, systolicMean: number): number {
  return base + 0.35 * (systolic - systolicMean) + 1.4 * turbulence(`${astronautId}:diastolic:noise`, ts)
}

function dailyValue(astronautId: string, key: string, dayStart: number, mean: number, limits: Limits): number {
  const day = noiseAt(`${astronautId}:${key}:daily`, dayStart, DAY)
  const roll = draw(hashString(`${astronautId}:${key}:roll:${dayStart}`))
  if (key === 'sleep') return clamp(mean + 2.8 * day, limits)
  if (key === 'mood') return Math.round(clamp(3.7 + 2.6 * day, limits))
  if (key === 'dizziness') return roll > 0.95 ? 2 : roll > 0.78 ? 1 : 0
  return mean
}

function round(value: number, limits: Limits, precision: number): number {
  return Number(clamp(value, limits).toFixed(precision))
}

function anchor(
  samples: IndicatorSample[],
  now: number,
  window: number,
  target: number,
  model: number,
  read: (sample: IndicatorSample) => number | null | undefined,
  write: (sample: IndicatorSample, value: number) => void,
): void {
  const delta = target - model
  if (Math.abs(delta) < 1e-9) return
  for (const sample of samples) {
    const current = read(sample)
    if (current == null) continue
    const ts = new Date(sample.t).getTime()
    const remaining = 1 - Math.max(0, now - ts) / window
    if (remaining <= 0) continue
    write(sample, current + delta * (remaining * remaining * (3 - 2 * remaining)))
  }
}

function dailySeries(
  astronautId: string,
  indicator: Indicator,
  limits: Limits,
  precision: number,
  start: number,
  now: number,
  includePrevious: boolean,
): IndicatorSample[] {
  const logHour = DAILY_LOG_HOUR[indicator.key]
  const mean = (indicator.baseline.low + indicator.baseline.high) / 2
  const entries: { ts: number; value: number }[] = []
  let previous: { ts: number; value: number } | undefined

  const cursor = new Date(start)
  cursor.setHours(0, 0, 0, 0)
  while (cursor.getTime() <= now) {
    const log = new Date(cursor)
    log.setHours(logHour, 0, 0, 0)
    const entry = {
      ts: log.getTime(),
      value: dailyValue(astronautId, indicator.key, cursor.getTime(), mean, limits),
    }
    if (log.getTime() < start) previous = entry
    else if (log.getTime() <= now) entries.push(entry)
    cursor.setDate(cursor.getDate() + 1)
  }

  if (entries.length === 0 && previous) entries.push(previous)
  if (entries.length === 0) entries.push({ ts: now, value: indicator.value })
  const updatedAt = new Date(indicator.updatedAt).getTime()
  const latest = entries[entries.length - 1]
  const closest = entries.reduce((best, entry) =>
    Math.abs(entry.ts - updatedAt) < Math.abs(best.ts - updatedAt) ? entry : best, latest)
  if (Math.abs(closest.ts - updatedAt) <= 12 * HOUR) closest.value = indicator.value
  else entries.push({ ts: now, value: indicator.value })
  if (entries.length < 2 && previous) entries.unshift(previous)
  else if (includePrevious && previous) entries.unshift(previous)
  if (entries.length < 2 && entries[0].ts < now) entries.push({ ts: now, value: entries[0].value })

  return entries.map((entry) => ({
    t: new Date(entry.ts).toISOString(),
    value: round(entry.value, limits, precision),
  }))
}

export function buildSeries(
  astronautId: string,
  indicator: Indicator,
  range: Range,
  now: number,
): IndicatorSample[] {
  const frame = RANGES[range] ?? RANGES['24h']
  const limits = LIMITS[indicator.key] ?? FALLBACK
  const precision = indicator.precision ?? limits.precision
  const mean = (indicator.baseline.low + indicator.baseline.high) / 2
  const start = now - frame.span

  if (DAILY_LOG_HOUR[indicator.key] !== undefined) {
    return dailySeries(astronautId, indicator, limits, precision, start, now, frame.span > DAY)
  }

  const points = Math.round(frame.span / frame.step)
  const samples: IndicatorSample[] = []
  for (let i = 0; i <= points; i += 1) {
    const ts = start + i * frame.step
    samples.push({ t: new Date(ts).toISOString(), value: continuousValue(astronautId, indicator.key, ts, mean) })
  }

  const window = indicator.key === 'radiation'
    ? Math.max(frame.step, 45 * MIN)
    : Math.min(6 * HOUR, Math.max(frame.step * 2, frame.span * 0.1))
  const model = continuousValue(astronautId, indicator.key, now, mean)
  anchor(samples, now, window, indicator.value, model, (sample) => sample.value, (sample, value) => {
    sample.value = value
  })

  if (indicator.key === 'bloodPressure') {
    const diastolicBase = indicator.secondary ?? mean - 38
    for (const sample of samples) {
      sample.secondary = diastolicValue(astronautId, new Date(sample.t).getTime(), diastolicBase, sample.value, mean)
    }
    if (indicator.secondary != null) {
      const diastolicModel = diastolicValue(astronautId, now, diastolicBase, model, mean)
      anchor(samples, now, window, indicator.secondary, diastolicModel, (sample) => sample.secondary, (sample, value) => {
        sample.secondary = value
      })
    }
  }

  const diastolicLimits: Limits = { min: 52, max: 105, precision: 0 }
  for (const sample of samples) {
    sample.value = round(sample.value, limits, precision)
    if (sample.secondary != null) sample.secondary = round(sample.secondary, diastolicLimits, 0)
  }

  return samples
}
