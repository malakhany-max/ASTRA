// @vitest-environment node
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { setupServer } from 'msw/node'
import type {
  Alert,
  Astronaut,
  BackupState,
  Checkin,
  CommandRecord,
  CompanionReply,
  ConsentState,
  Indicator,
  IndicatorSeries,
  LinkState,
  RadiationState,
  SecurityState,
} from '@contracts'
import { handlers } from './handlers'
import { resetDb } from './db'

const server = setupServer(...handlers)
const ORIGIN = 'http://localhost'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
beforeEach(() => {
  resetDb()
})

async function getJson<T>(path: string): Promise<{ status: number; body: T }> {
  const response = await fetch(`${ORIGIN}${path}`)
  return { status: response.status, body: (await response.json()) as T }
}

async function postJson<T>(path: string, body: unknown): Promise<{ status: number; body: T }> {
  const response = await fetch(`${ORIGIN}${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
  return { status: response.status, body: (await response.json()) as T }
}

describe('mock crew API', () => {
  it('serves a normal day for a crew of three', async () => {
    const overview = await getJson<{ astronauts: Astronaut[]; link: LinkState }>('/api/crew/overview')
    expect(overview.status).toBe(200)
    expect(overview.body.astronauts).toHaveLength(3)
    expect(overview.body.link.state).toBe('connected')
    expect(overview.body.astronauts.every((astronaut) => astronaut.status === 'normal')).toBe(true)
  })

  it('serves nine indicators and a series with the personal baseline', async () => {
    const indicators = await getJson<Indicator[]>('/api/astronauts/ast-zain/indicators')
    expect(indicators.body).toHaveLength(9)
    expect(indicators.body.map((indicator) => indicator.key)).toContain('radiation')

    const series = await getJson<IndicatorSeries>(
      '/api/astronauts/ast-zain/indicators/heartRate?range=7d',
    )
    expect(series.status).toBe(200)
    expect(series.body.samples.length).toBe(169)
    expect(series.body.baseline.high).toBeGreaterThan(series.body.baseline.low)
    expect(series.body.range).toBe('7d')
  })

  it('rejects an unsupported chart range', async () => {
    const series = await getJson<{ error: string }>(
      '/api/astronauts/ast-zain/indicators/heartRate?range=1y',
    )
    expect(series.status).toBe(400)
  })

  it('raises the radiation shelter state and starts post-exposure monitoring', async () => {
    await postJson('/demo/scenario', { scenario: 'radiation_spike' })

    const radiation = await getJson<RadiationState>('/api/astronauts/ast-zain/radiation')
    expect(radiation.body.alertActive).toBe(true)
    expect(radiation.body.status).toBe('urgent')
    expect(radiation.body.shelter.direction).toBe('right')
    expect(radiation.body.latestEvent?.type).toBe('solar_particle_event')

    const exposure = await getJson<{ monitoringActive: boolean; records: unknown[] }>(
      '/api/astronauts/ast-zain/exposure',
    )
    expect(exposure.body.monitoringActive).toBe(true)
    expect(exposure.body.records.length).toBeGreaterThan(1)

    const alerts = await getJson<Alert[]>('/api/alerts?priority=radiation')
    expect(alerts.body[0].severity).toBe('urgent')
  })

  it('keeps the crew app in autonomous mode and queues commands while the link is down', async () => {
    await postJson('/demo/scenario', { scenario: 'cut_link' })

    const overview = await getJson<{ link: LinkState; astronauts: Astronaut[] }>('/api/crew/overview')
    expect(overview.body.link.state).toBe('autonomous')
    expect(overview.body.astronauts[0].linkState).toBe('autonomous')
    expect(new Date(overview.body.link.lastSyncAt).getTime()).toBeLessThan(Date.now() - 2 * 3_600_000)

    const backup = await getJson<BackupState>('/api/backup/state')
    expect(backup.body.status).toBe('queued')

    const command = await postJson<CommandRecord>('/api/commands', {
      astronautId: 'ast-zain',
      type: 'thresholds',
      payload: { heartRateHigh: 85 },
    })
    expect(command.body.status).toBe('pending')

    await postJson('/demo/scenario', { scenario: 'restore_link' })
    const commands = await getJson<CommandRecord[]>('/api/commands')
    expect(commands.body.find((item) => item.id === command.body.id)?.status).toBe('delivered')
  })

  it('marks a failed sensor reading as unknown instead of guessing', async () => {
    await postJson('/demo/scenario', { scenario: 'sensor_fault' })
    const indicators = await getJson<Indicator[]>('/api/astronauts/ast-zain/indicators')
    const heartRate = indicators.body.find((indicator) => indicator.key === 'heartRate')
    expect(heartRate?.status).toBe('unknown')
    expect(heartRate?.reason).toContain('sensor')
  })

  it('degrades security for each simulated attack and never raises a fake radiation alarm', async () => {
    const cases = [
      { scenario: 'attack_forged_reading', level: 'degraded', check: 'integrity' },
      { scenario: 'attack_replay', level: 'degraded', check: 'secure_communication' },
      { scenario: 'attack_spoofed_device', level: 'critical', check: 'confidentiality' },
      { scenario: 'attack_fake_dosimeter', level: 'degraded', check: 'integrity' },
    ] as const

    for (const testCase of cases) {
      resetDb()
      await postJson('/demo/scenario', { scenario: testCase.scenario })
      const security = await getJson<SecurityState>('/api/security/state')
      expect(security.body.level).toBe(testCase.level)
      const check = security.body.checks.find((item) => item.id === testCase.check)
      expect(check?.state).toBe('degraded')

      if (testCase.scenario === 'attack_fake_dosimeter') {
        const radiation = await getJson<RadiationState>('/api/astronauts/ast-zain/radiation')
        expect(radiation.body.alertActive).toBe(false)
        expect(radiation.body.latestEvent?.type).toBe('dosimeter_spike')
      }
    }
  })

  it('stores a check-in and updates the mood and dizziness indicators', async () => {
    const checkin = await postJson<Checkin>('/api/checkin', {
      astronautId: 'ast-zain',
      mood: 2,
      energy: 2,
      dizziness: 2,
      workload: 5,
      symptoms: ['light-headed'],
      note: 'Felt light-headed after exercise.',
    })
    expect(checkin.status).toBe(201)
    expect(checkin.body.id).toMatch(/^chk-/)

    const indicators = await getJson<Indicator[]>('/api/astronauts/ast-zain/indicators')
    const mood = indicators.body.find((indicator) => indicator.key === 'mood')
    const dizziness = indicators.body.find((indicator) => indicator.key === 'dizziness')
    expect(mood?.value).toBe(2)
    expect(mood?.status).toBe('attention')
    expect(dizziness?.value).toBe(2)
    expect(dizziness?.status).toBe('attention')
  })

  it('saves consent tiers and answers the companion with suggested actions', async () => {
    const consent = await fetch(`${ORIGIN}/api/consent/ast-zain`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        vitals_summary: true,
        psych_summary: true,
        raw_audio: false,
        exposure_records: false,
      }),
    })
    const saved = (await consent.json()) as ConsentState
    expect(saved.tiers.exposure_records).toBe(false)

    const reply = await postJson<CompanionReply>('/api/companion/message', {
      astronautId: 'ast-zain',
      text: 'I feel light headed and a bit anxious.',
      tone: 'calm',
      language: 'en',
    })
    expect(reply.body.reply.role).toBe('companion')
    expect(reply.body.actions.some((action) => action.kind === 'breathing')).toBe(true)
  })
})
