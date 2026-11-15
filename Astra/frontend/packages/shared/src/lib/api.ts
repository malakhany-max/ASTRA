const rawBase = ((import.meta.env.VITE_API_BASE as string | undefined) ?? '').trim()
const rawGroundBase = ((import.meta.env.VITE_GROUND_BASE as string | undefined) ?? 'http://127.0.0.1:8100').trim()
const companionBase = ((import.meta.env.VITE_COMPANION_BASE as string | undefined) ?? 'http://127.0.0.1:8200').trim()
const linkBase = ((import.meta.env.VITE_LINK_BASE as string | undefined) ?? 'http://127.0.0.1:8300').trim()
const GROUND_CLIENT = (import.meta.env.VITE_APP_KIND as string | undefined) === 'ground'
const LOCAL_PROXY = (import.meta.env.VITE_LOCAL_PROXY as string | undefined) === 'true'

export const USE_MOCK = !LOCAL_PROXY && (rawBase === '' || rawBase === 'mock')
export const API_BASE = USE_MOCK || LOCAL_PROXY ? '' : rawBase.replace(/\/+$/, '')
const GROUND_BASE = USE_MOCK || LOCAL_PROXY ? '' : rawGroundBase.replace(/\/+$/, '')

function isGroundPath(path: string): boolean {
  const pathname = path.split('?', 1)[0]
  return pathname.startsWith('/auth/') || pathname === '/api/commands' || pathname.startsWith('/api/commands/') ||
    (GROUND_CLIENT && (pathname.startsWith('/api/crew/') || pathname.startsWith('/api/astronauts/') ||
      pathname === '/api/alerts' || pathname.startsWith('/api/alerts/') || pathname === '/api/link/state' ||
      pathname === '/api/backup/state' || pathname === '/api/security/state'))
}

let localSession: Promise<string> | null = null
async function sessionToken(): Promise<string | null> {
  if (USE_MOCK) return null
  const cached = sessionStorage.getItem('astra_access_token')
  const expiresAt = Number(sessionStorage.getItem('astra_access_expires') ?? 0)
  if (cached && expiresAt > Date.now() + 60_000) return cached
  localSession ??= fetch('/__astra/local-session', { cache: 'no-store' })
    .then(async (response) => {
      if (!response.ok) throw new Error('Could not open the local ASTRA session.')
      const result = await response.json() as { access_token: string }
      sessionStorage.setItem('astra_access_token', result.access_token)
      sessionStorage.setItem('astra_access_expires', String(Date.now() + 25 * 60_000))
      return result.access_token
    }).finally(() => { localSession = null })
  return localSession
}

function backendAstronautId(id: string | undefined): string | undefined {
  if (!id) return id
  return ({ 'ast-zain': 'A-07', 'ast-maya': 'A-03', 'ast-idris': 'A-11' } as Record<string, string>)[id] ?? id
}

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, message: string, body: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData) && !(typeof Blob !== 'undefined' && init.body instanceof Blob)) {
    headers.set('content-type', 'application/json')
  }

  const token = await sessionToken()
  if (token) headers.set('authorization', `Bearer ${token}`)
  const companionPath = !USE_MOCK && path.startsWith('/api/companion/')
  const groundPath = !USE_MOCK && isGroundPath(path)
  const requestPath = companionPath && !LOCAL_PROXY ? path.replace(/^\/api/, '') : path
  const requestBase = companionPath ? (LOCAL_PROXY ? '' : companionBase.replace(/\/+$/, '')) : groundPath ? GROUND_BASE : API_BASE
  const normalizedPath = GROUND_CLIENT && groundPath ? requestPath.replace(/^(\/api\/astronauts\/)([^/?]+)/,
    (_match, prefix: string, id: string) => `${prefix}${backendAstronautId(decodeURIComponent(id))}`) : requestPath
  const res = await fetch(`${requestBase}${normalizedPath}`, { ...init, headers })

  if (!res.ok) {
    let body: unknown = null
    try {
      body = await res.json()
    } catch {
      body = await res.text().catch(() => null)
    }
    const record = body && typeof body === 'object' ? body as { error?: unknown; detail?: unknown } : null
    const detail = record && (record.error ?? record.detail)
    const message = detail != null ? String(detail) : `Request failed (${res.status})`
    throw new ApiError(res.status, message, body)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  if (!USE_MOCK && GROUND_CLIENT && path === '/api/alerts') {
    return request<Array<Record<string, unknown>>>(path, { signal }).then((items) => items.map((item) => ({
      ...item, astronautId: ({ 'A-07': 'ast-zain', 'A-03': 'ast-maya', 'A-11': 'ast-idris' } as Record<string, string>)[String(item.astronaut_id ?? item.astronautId)] ?? item.astronautId,
    })) as T)
  }
  if (!USE_MOCK && GROUND_CLIENT && path === '/api/link/state') {
    return request<{ connected: boolean; queue_size: number; delay_seconds?: number; last_sync_ts?: string | null; staleness?: Array<{ stale: boolean }> }>(path, { signal }).then((item) => ({
      state: !item.connected ? 'autonomous' : item.delay_seconds ? 'degraded' : 'connected',
      label: !item.connected ? 'Autonomous' : item.delay_seconds ? 'Delayed link' : 'Connected',
      since: item.last_sync_ts ?? '', lastSyncAt: item.last_sync_ts ?? '', queue: item.queue_size, delayMs: Math.round((item.delay_seconds ?? 0) * 1000),
    }) as T)
  }
  if (!USE_MOCK && GROUND_CLIENT && path === '/api/backup/state') {
    return request<{ available: boolean; queue_size?: number; last_backup_ts?: string | null; size_kb?: number; encrypted?: boolean }>(path, { signal }).then((item) => ({
      status: item.available ? 'current' : 'error', lastBackupAt: item.last_backup_ts ?? '',
      pendingBatches: item.queue_size ?? 0, sizeKb: item.size_kb ?? 0, encrypted: item.encrypted ?? true,
    }) as T)
  }
  if (!USE_MOCK && path === '/api/commands') {
    return request<Array<{ id: string; astronaut_id: string; type: string; payload: unknown; created_ts: string; status: string; created_by: string; delivered_ts?: string | null }>>(path, { signal })
      .then((items) => items.map((item) => ({
        id: item.id, astronautId: ({ 'A-07': 'ast-zain', 'A-03': 'ast-maya', 'A-11': 'ast-idris' } as Record<string, string>)[item.astronaut_id] ?? item.astronaut_id,
        type: item.type, payload: item.payload, createdAt: item.created_ts, status: item.status,
        createdBy: item.created_by, deliveredAt: item.delivered_ts ?? null,
        audit: [{ at: item.created_ts, actor: item.created_by, action: 'Signed and queued for downlink' }],
      })) as T)
  }
  if (!USE_MOCK && path === '/api/companion/breathing') {
    type CompanionTechnique = {
      id?: string; name?: string; purpose?: string
      cycle_seconds?: { inhale?: number; hold?: number; exhale?: number }
      duration_options_min?: number[]
    }
    return request<{ techniques: CompanionTechnique[] }>(path, { signal }).then((result) =>
      result.techniques.map((item) => {
        const cycle = item.cycle_seconds ?? {}
        const phases: Array<{ label: 'inhale' | 'hold' | 'exhale'; seconds: number }> = []
        if (cycle.inhale) phases.push({ label: 'inhale', seconds: cycle.inhale })
        if (cycle.hold) phases.push({ label: 'hold', seconds: cycle.hold })
        if (cycle.exhale) phases.push({ label: 'exhale', seconds: cycle.exhale })
        const durations = item.duration_options_min?.length ? item.duration_options_min : [3]
        return {
          id: item.id ?? '', name: item.name ?? '', description: item.purpose ?? '',
          phases, defaultMinutes: durations.includes(3) ? 3 : durations[0], benefits: [],
        }
      }) as unknown as T)
  }
  return request<T>(path, { signal })
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  if (!USE_MOCK && path === '/api/commands' && body && typeof body === 'object') {
    const value = body as { astronautId?: string; type?: string; payload?: Record<string, unknown> }
    const bundleTypes: Record<string, string> = {
      schedule: 'config_bundle', thresholds: 'thresholds_bundle', plan: 'guideline_bundle',
    }
    const commandType = value.type ?? 'schedule'
    return request<{ queued: boolean; msg_id: string; bundle: Record<string, unknown>; created_by: string }>(path, {
      method: 'POST',
      body: JSON.stringify({
        command_type: bundleTypes[commandType] ?? 'config_bundle',
        payload: { ...(value.payload ?? {}), astronaut_id: backendAstronautId(value.astronautId), ui_type: commandType },
      }),
    }).then((result) => ({
      id: result.msg_id, astronautId: value.astronautId ?? '', type: commandType,
      payload: value.payload ?? {}, createdAt: String(result.bundle.created_ts ?? new Date().toISOString()),
      status: result.queued ? 'pending' : 'failed', deliveredAt: null, createdBy: result.created_by,
      audit: [{ at: String(result.bundle.created_ts ?? new Date().toISOString()),
        actor: result.created_by, action: 'Signed and queued for downlink' }],
    } as T))
  }
  if (!USE_MOCK && path === '/api/checkin' && body && typeof body === 'object') {
    const value = body as {
      astronautId?: string; mood: number; energy: number; dizziness: number
      workload: number; symptoms: string[]; note?: string
    }
    const ts = new Date().toISOString()
    return request<{ accepted: boolean; ts: string }>(path, {
      method: 'POST',
      body: JSON.stringify({
        astronaut_id: backendAstronautId(value.astronautId), ts, mood: value.mood,
        energy: value.energy, dizziness: value.dizziness, workload: value.workload,
        symptoms: value.symptoms, notes: value.note ?? '',
      }),
    }).then(() => ({
      id: `checkin-${ts}`, astronautId: value.astronautId ?? 'A-07', createdAt: ts,
      mood: value.mood, energy: value.energy, dizziness: value.dizziness,
      workload: value.workload, symptoms: value.symptoms, note: value.note,
    } as T))
  }
  if (!USE_MOCK && path === '/api/companion/message' && body && typeof body === 'object') {
    const value = body as {
      astronautId?: string; text?: string; tone?: string; mode?: string
      statusSummary?: unknown[]; dizzinessReported?: boolean
    }
    const tones: Record<string, string> = { calm: 'neutral', warm: 'warm', direct: 'brief' }
    return request<{
      reply_text: string
      actions: Array<Record<string, unknown>>
      mode: string
    }>(path, {
      method: 'POST',
      body: JSON.stringify({
        astronaut_id: value.astronautId,
        text: value.text,
        tone: tones[value.tone ?? 'calm'] ?? 'neutral',
        mode: value.mode === 'connected' ? 'connected' : 'autonomous',
        status_summary: value.statusSummary ?? [],
        dizziness_reported: value.dizzinessReported ?? false,
      }),
    }).then((result) => {
      const actions = (result.actions ?? []).map((action, index) => {
        const type = String(action.type ?? '')
        const technique = action.technique
        const techniqueId = typeof technique === 'string' ? technique
          : technique && typeof technique === 'object' && 'id' in technique ? String((technique as { id: unknown }).id)
            : null
        const kind = type === 'breathing' || type === 'offer_breathing' ? 'breathing'
          : type === 'submit_checkin' || type === 'post_exposure_checkin' || type === 'weekly_wellbeing_questions' ? 'checkin'
            : type === 'approved_protocol_required' ? 'shelter' : 'none'
        return {
          id: `${type || 'action'}-${index}`,
          label: kind === 'breathing' ? 'Start breathing exercise'
            : kind === 'checkin' ? 'Open check-in'
              : kind === 'shelter' ? 'Open radiation guidance' : 'Continue',
          kind,
          payload: techniqueId,
        }
      })
      const text = result.reply_text ?? ''
      return {
        reply: { id: `companion-${Date.now()}`, role: 'companion', text,
          createdAt: new Date().toISOString(), actions },
        actions,
      } as T
    })
  }
  if (!USE_MOCK && path === '/demo/scenario' && body && typeof body === 'object' && 'scenario' in body) {
    const scenario = String((body as { scenario: unknown }).scenario)
    const delayMs = Number((body as { delayMs?: number }).delayMs ?? 0)
    const linkPaths: Record<string, string> = { cut_link: '/link/disconnect', restore_link: '/link/connect' }
    if (linkPaths[scenario] || scenario === 'link_delay') {
      const target = scenario === 'link_delay' ? '/link/delay' : linkPaths[scenario]
      const linkBody = scenario === 'link_delay' ? { seconds: Math.max(0, delayMs / 1000) } : {}
      return fetch(`${LOCAL_PROXY ? '' : linkBase.replace(/\/+$/, '')}${target}`, {
        method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(linkBody),
      }).then(async (response) => {
        if (!response.ok) throw new ApiError(response.status, `Link request failed (${response.status})`, await response.text())
        return request<T>('/api/demo/state')
      })
    }
    const hubScenario = scenario === 'normal' ? 'reset' : scenario
    return request<T>('/demo/scenario', { method: 'POST', body: JSON.stringify({ name: hubScenario }) })
  }
  return request<T>(path, {
    method: 'POST',
    body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
  })
}

export function apiPostWav<T>(path: string, body: Blob): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body,
    headers: { 'content-type': 'audio/wav' },
  })
}

export async function apiPostAudio(path: string, body: unknown): Promise<Blob> {
  const companionPath = !USE_MOCK && path.startsWith('/api/companion/')
  const requestPath = companionPath && !LOCAL_PROXY ? path.replace(/^\/api/, '') : path
  const requestBase = companionPath ? (LOCAL_PROXY ? '' : companionBase.replace(/\/+$/, '')) : API_BASE
  const headers = new Headers({ 'content-type': 'application/json' })
  const token = await sessionToken()
  if (token) headers.set('authorization', `Bearer ${token}`)
  const groundPath = !USE_MOCK && isGroundPath(path)
  const response = await fetch(`${groundPath ? GROUND_BASE : requestBase}${requestPath}`, {
    method: 'POST', headers, body: JSON.stringify(body),
  })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const result = await response.json() as { detail?: string; error?: string }
      message = result.error ?? result.detail ?? message
    } catch { }
    throw new ApiError(response.status, message, null)
  }
  return response.blob()
}

export function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const consentMatch = path.match(/^\/api\/consent\/([^/]+)$/)
  if (!USE_MOCK && consentMatch && body && typeof body === 'object') {
    const value = body as { tiers?: Record<string, boolean> }
    return request<T>(path, {
      method: 'PUT',
      body: JSON.stringify({
        astronaut_id: backendAstronautId(decodeURIComponent(consentMatch[1])),
        tiers: value.tiers,
        emergency_override: false,
      }),
    })
  }
  return request<T>(path, {
    method: 'PUT',
    body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
  })
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Something went wrong'
}
