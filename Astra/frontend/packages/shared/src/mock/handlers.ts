import { http, HttpResponse } from 'msw'
import type {
  AstronautSettings,
  CheckinRequest,
  CommandRequest,
  CompanionRequest,
  ConsentTiers,
  DemoRequest,
  Range,
} from '@contracts'
import {
  acknowledgeAlert,
  applyScenario,
  companionReply,
  createCheckin,
  createCommand,
  crewOverview,
  db,
  demoState,
  getAlerts,
  getAstronaut,
  getBreathingTechniques,
  getCommands,
  getCompanion,
  getConsent,
  getExposure,
  getIndicators,
  getMissions,
  getOrgans,
  getPlan,
  getRadiation,
  getSeries,
  getSettings,
  setPlanItem,
  updateConsent,
  updateSettings,
} from './db'

const RANGES: Range[] = ['24h', '7d', '30d']
const ACTOR = 'Dr. Lena Ortiz'

const notFound = () => HttpResponse.json({ error: 'Not found' }, { status: 404 })

export const handlers = [
  http.get('*/api/health', () => HttpResponse.json({ ok: true, mock: true })),

  http.post('*/auth/login', async ({ request }) => {
    const body = (await request.json()) as { username?: string; password?: string }
    if (!body.username?.trim() || !body.password) {
      return HttpResponse.json({ error: 'Username and password are required' }, { status: 401 })
    }
    const username = body.username.toLowerCase()
    const role = username.includes('viewer') ? 'viewer'
      : username.includes('medical') ? 'medical_officer' : 'flight_surgeon'
    return HttpResponse.json({ access_token: `mock-${body.username.trim()}`, token_type: 'bearer', role })
  }),
  http.post('*/auth/logout', () => HttpResponse.json({ logged_out: true })),

  http.get('*/api/crew/overview', () => HttpResponse.json(crewOverview())),

  http.get('*/api/astronauts', () => HttpResponse.json(crewOverview().astronauts)),

  http.get('*/api/astronauts/:id/indicators', ({ params }) => {
    const indicators = getIndicators(String(params.id))
    if (!indicators) return notFound()
    return HttpResponse.json(indicators)
  }),

  http.get('*/api/astronauts/:id/indicators/:key', ({ params, request }) => {
    const url = new URL(request.url)
    const range = (url.searchParams.get('range') ?? '24h') as Range
    if (!RANGES.includes(range)) {
      return HttpResponse.json({ error: 'Range must be 24h, 7d or 30d' }, { status: 400 })
    }
    const series = getSeries(String(params.id), String(params.key), range)
    if (!series) return notFound()
    return HttpResponse.json(series)
  }),

  http.get('*/api/astronauts/:id/organs', ({ params }) => {
    const organs = getOrgans(String(params.id))
    if (!organs) return notFound()
    return HttpResponse.json(organs)
  }),

  http.get('*/api/astronauts/:id/radiation', ({ params }) => {
    const radiation = getRadiation(String(params.id))
    if (!radiation) return notFound()
    return HttpResponse.json(radiation)
  }),

  http.get('*/api/astronauts/:id/exposure', ({ params }) => {
    const exposure = getExposure(String(params.id))
    if (!exposure) return notFound()
    return HttpResponse.json(exposure)
  }),

  http.get('*/api/astronauts/:id/plan', ({ params }) => {
    const plan = getPlan(String(params.id))
    if (!plan) return notFound()
    return HttpResponse.json(plan)
  }),

  http.post('*/api/astronauts/:id/plan/:itemId', async ({ params, request }) => {
    const body = (await request.json()) as { done?: boolean }
    if (typeof body.done !== 'boolean') {
      return HttpResponse.json({ error: 'done must be a boolean' }, { status: 400 })
    }
    const plan = setPlanItem(String(params.id), String(params.itemId), body.done)
    if (!plan) return notFound()
    return HttpResponse.json(plan)
  }),

  http.get('*/api/astronauts/:id/missions', ({ params }) => {
    const missions = getMissions(String(params.id))
    if (!missions) return notFound()
    return HttpResponse.json(missions)
  }),

  http.get('*/api/astronauts/:id/settings', ({ params }) => {
    const settings = getSettings(String(params.id))
    if (!settings) return notFound()
    return HttpResponse.json(settings)
  }),

  http.put('*/api/astronauts/:id/settings', async ({ params, request }) => {
    const body = (await request.json()) as AstronautSettings
    const settings = updateSettings(String(params.id), body)
    if (!settings) return notFound()
    return HttpResponse.json(settings)
  }),

  http.get('*/api/astronauts/:id/alerts', ({ params }) => {
    if (!getAstronaut(String(params.id))) return notFound()
    return HttpResponse.json(getAlerts({ astronautId: String(params.id) }))
  }),

  http.get('*/api/astronauts/:id/checkins', ({ params }) => {
    if (!getAstronaut(String(params.id))) return notFound()
    return HttpResponse.json(db().checkins[String(params.id)] ?? [])
  }),

  http.get('*/api/astronauts/:id', ({ params }) => {
    const astronaut = getAstronaut(String(params.id))
    if (!astronaut) return notFound()
    return HttpResponse.json(astronaut)
  }),

  http.get('*/api/alerts', ({ request }) => {
    const url = new URL(request.url)
    return HttpResponse.json(
      getAlerts({
        astronautId: url.searchParams.get('astronautId') ?? undefined,
        priority: url.searchParams.get('priority') ?? undefined,
        acknowledged: url.searchParams.get('acknowledged') ?? undefined,
      }),
    )
  }),

  http.post('*/api/alerts/:id/ack', ({ params, request }) => {
    const alert = acknowledgeAlert(String(params.id), ACTOR)
    if (!alert) return notFound()
    return HttpResponse.json(alert)
  }),

  http.get('*/api/security/state', () => HttpResponse.json(db().security)),

  http.get('*/api/link/state', () => HttpResponse.json(db().link)),

  http.get('*/api/backup/state', () => HttpResponse.json(db().backup)),

  http.get('*/api/consent/:id', ({ params }) => {
    const consent = getConsent(String(params.id))
    if (!consent) return notFound()
    return HttpResponse.json(consent)
  }),

  http.put('*/api/consent/:id', async ({ params, request }) => {
    const body = (await request.json()) as ConsentTiers | { tiers: ConsentTiers }
    const tiers = 'tiers' in body ? body.tiers : body
    const consent = updateConsent(String(params.id), tiers)
    if (!consent) return notFound()
    return HttpResponse.json(consent)
  }),

  http.post('*/api/checkin', async ({ request }) => {
    const body = (await request.json()) as CheckinRequest
    if (
      typeof body.mood !== 'number' ||
      typeof body.energy !== 'number' ||
      typeof body.dizziness !== 'number' ||
      typeof body.workload !== 'number' ||
      !Array.isArray(body.symptoms)
    ) {
      return HttpResponse.json({ error: 'Incomplete check-in payload' }, { status: 400 })
    }
    return HttpResponse.json(createCheckin(body), { status: 201 })
  }),

  http.get('*/api/companion/breathing', () => HttpResponse.json(getBreathingTechniques())),

  http.get('*/api/companion/transcript/:id', ({ params }) => {
    const transcript = getCompanion(String(params.id))
    if (!transcript) return notFound()
    return HttpResponse.json(transcript)
  }),

  http.post('*/api/companion/stt', async ({ request }) => {
    await request.arrayBuffer()
    return HttpResponse.json({ text: 'I feel tense and my sleep was short.', confidence: 0.84 })
  }),

  http.post('*/api/companion/tts', () => {
    const sampleRate = 16_000
    const samples = sampleRate / 10
    const wav = new ArrayBuffer(44 + samples * 2)
    const view = new DataView(wav)
    const write = (offset: number, value: string) => {
      for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index))
    }
    write(0, 'RIFF'); view.setUint32(4, 36 + samples * 2, true); write(8, 'WAVE')
    write(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true)
    view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true)
    view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true)
    view.setUint16(34, 16, true); write(36, 'data'); view.setUint32(40, samples * 2, true)
    return new HttpResponse(wav, { headers: { 'content-type': 'audio/wav' } })
  }),

  http.post('*/api/companion/message', async ({ request }) => {
    const body = (await request.json()) as CompanionRequest
    if (!body.astronautId || typeof body.text !== 'string' || body.text.trim().length === 0) {
      return HttpResponse.json({ error: 'Message text is required' }, { status: 400 })
    }
    return HttpResponse.json(companionReply(body))
  }),

  http.get('*/api/commands', ({ request }) => {
    const url = new URL(request.url)
    return HttpResponse.json(getCommands(url.searchParams.get('astronautId') ?? undefined))
  }),

  http.post('*/api/commands', async ({ request }) => {
    const body = (await request.json()) as CommandRequest
    if (!body.astronautId || !body.type) {
      return HttpResponse.json({ error: 'astronautId and type are required' }, { status: 400 })
    }
    const command = createCommand(
      { astronautId: body.astronautId, type: body.type, payload: body.payload ?? {} },
      ACTOR,
    )
    if (!command) return notFound()
    return HttpResponse.json(command, { status: 201 })
  }),

  http.get('*/api/demo/state', () => HttpResponse.json(demoState())),

  http.post('*/demo/scenario', async ({ request }) => {
    const body = (await request.json()) as DemoRequest
    if (!body.scenario) {
      return HttpResponse.json({ error: 'scenario is required' }, { status: 400 })
    }
    return HttpResponse.json(applyScenario(body.scenario, body.delayMs))
  }),
]
