import type {
  Alert,
  Astronaut,
  AstronautSettings,
  BackupState,
  Baseline,
  Checkin,
  CheckinRequest,
  CommandRecord,
  CompanionAction,
  CompanionMessage,
  CompanionReply,
  CompanionRequest,
  ConsentState,
  ConsentTiers,
  DemoScenario,
  DemoState,
  ExposureRecord,
  ExposureState,
  Indicator,
  IndicatorKey,
  IndicatorSeries,
  LinkState,
  Mission,
  Organ,
  Plan,
  RadiationEvent,
  RadiationState,
  Range,
  SecurityCheck,
  SecurityState,
} from '@contracts'
import { worstStatus } from '../lib/format'
import { emitEvent } from './bus'
import { buildSeries } from './series'
import {
  BREATHING_TECHNIQUES,
  CREW,
  DEFAULT_SETTINGS,
  ORGANS,
  PAST_MISSIONS,
  PLAN_TEMPLATE,
  SECURITY_CHECKS,
  SHELTER,
  type CrewSeed,
  type VitalSeed,
} from './seed'

const MIN = 60_000
const HOUR = 3_600_000
const DAY = 86_400_000

const iso = (time: number): string => new Date(time).toISOString()

const round1 = (value: number): number => Math.round(value * 10) / 10

interface IndicatorOptions {
  secondary?: number | null
  status?: Indicator['status']
  trend?: Indicator['trend']
  precision?: number
}

function makeIndicator(
  key: IndicatorKey,
  label: string,
  unit: string,
  value: number,
  baseline: Baseline,
  reason: string,
  updatedAt: string,
  options: IndicatorOptions = {},
): Indicator {
  return {
    key,
    label,
    unit,
    value,
    baseline,
    reason,
    updatedAt,
    status: options.status ?? 'normal',
    trend: options.trend ?? 'stable',
    secondary: options.secondary ?? null,
    precision: options.precision ?? 0,
  }
}

function baseIndicators(vitals: VitalSeed, now: number): Indicator[] {
  return [
    makeIndicator('heartRate', 'Heart rate', 'bpm', vitals.hr, { low: 52, high: 78 }, 'Within your personal baseline.', iso(now - MIN), { precision: 0 }),
    makeIndicator('spo2', 'Blood oxygen', '%', vitals.spo2, { low: 95, high: 100 }, 'Within your personal baseline.', iso(now - 2 * MIN), { precision: 0 }),
    makeIndicator('bloodPressure', 'Blood pressure', 'mmHg', vitals.systolic, { low: 105, high: 130 }, 'Within your personal baseline.', iso(now - 3 * MIN), { secondary: vitals.diastolic, precision: 0 }),
    makeIndicator('bloodGlucose', 'Blood glucose', 'mmol/L', vitals.glucose, { low: 4, high: 6.2 }, 'Within your personal baseline.', iso(now - 4 * HOUR), { precision: 1 }),
    makeIndicator('temperature', 'Core temperature', '°C', vitals.temperature, { low: 36.2, high: 37.3 }, 'Within your personal baseline.', iso(now - 5 * MIN), { precision: 1 }),
    makeIndicator('sleep', 'Sleep last night', 'h', vitals.sleep, { low: 7, high: 9 }, 'Within your personal baseline.', iso(now - 7 * HOUR), { precision: 1 }),
    makeIndicator('dizziness', 'Dizziness', 'score', vitals.dizziness, { low: 0, high: 1 }, 'No dizziness reported.', iso(now - 30 * MIN), { precision: 0 }),
    makeIndicator('mood', 'Mood', '/5', vitals.mood, { low: 3, high: 5 }, 'Mood steady.', iso(now - 30 * MIN), { precision: 0 }),
    makeIndicator('radiation', 'Radiation dose rate', 'µSv/h', vitals.radiation, { low: 0, high: 2 }, 'Background rate for this module.', iso(now - 2 * MIN), { precision: 1 }),
  ]
}

function baseRadiation(astronautId: string, now: number, cumulative: number): RadiationState {
  const event: RadiationEvent = {
    id: `rad-${astronautId}-routine`,
    type: 'routine',
    doseRate: 0.8,
    startedAt: iso(now - 6 * HOUR),
    endedAt: iso(now - 5 * HOUR),
    note: 'Routine cabin measurement.',
  }
  return {
    astronautId,
    doseRate: 0.9,
    unit: 'µSv/h',
    cumulativeMsv: cumulative,
    budgetMsv: 150,
    budgetUsedPct: round1((cumulative / 150) * 100),
    status: 'normal',
    alertActive: false,
    shelter: SHELTER,
    latestEvent: event,
    events: [event],
  }
}

function baseExposure(astronautId: string, missionId: string, doseMsv: number, symptoms: string[], note: string): ExposureState {
  const record: ExposureRecord = {
    id: `exp-${astronautId}-past`,
    astronautId,
    missionId,
    date: '2024-05-10',
    doseMsv,
    symptoms,
    followUpUntil: null,
    note,
  }
  return {
    astronautId,
    records: [record],
    monitoringActive: false,
    monitoringStartedAt: null,
    monitoringUntil: null,
    windowHours: 72,
  }
}

function baseSecurity(now: number): SecurityState {
  return {
    level: 'ok',
    headline: 'All protections active',
    checks: SECURITY_CHECKS.map((check) => ({ ...check })),
    lastEventAt: iso(now - 5 * HOUR),
  }
}

function baseLink(now: number): LinkState {
  return {
    state: 'connected',
    label: 'Connected',
    since: iso(now - 6 * HOUR),
    delayMs: 800,
    lastSyncAt: iso(now - 2 * MIN),
    queue: 0,
  }
}

function baseBackup(now: number): BackupState {
  return {
    status: 'current',
    lastBackupAt: iso(now - 10 * MIN),
    pendingBatches: 0,
    sizeKb: 2841.6,
    encrypted: true,
  }
}

function baseCheckins(now: number): Record<string, Checkin[]> {
  return {
    'ast-zain': [
      {
        id: 'chk-zain-1',
        astronautId: 'ast-zain',
        createdAt: iso(now - DAY),
        mood: 3,
        energy: 3,
        dizziness: 1,
        workload: 4,
        symptoms: ['poor sleep'],
        note: 'Long EVA preparation block.',
      },
      {
        id: 'chk-zain-2',
        astronautId: 'ast-zain',
        createdAt: iso(now - 2 * DAY),
        mood: 4,
        energy: 4,
        dizziness: 0,
        workload: 3,
        symptoms: [],
        note: 'Good day, exercise felt easier.',
      },
    ],
    'ast-maya': [
      {
        id: 'chk-maya-1',
        astronautId: 'ast-maya',
        createdAt: iso(now - DAY),
        mood: 4,
        energy: 4,
        dizziness: 0,
        workload: 3,
        symptoms: [],
        note: 'Steady day.',
      },
    ],
    'ast-idris': [
      {
        id: 'chk-idris-1',
        astronautId: 'ast-idris',
        createdAt: iso(now - DAY),
        mood: 3,
        energy: 3,
        dizziness: 0,
        workload: 4,
        symptoms: ['shoulder stiffness'],
        note: 'Busy scheduling day.',
      },
    ],
  }
}

function baseCompanion(now: number): Record<string, CompanionMessage[]> {
  return {
    'ast-zain': [
      {
        id: 'msg-zain-1',
        role: 'companion',
        text: "I'm here. How are you feeling right now?",
        createdAt: iso(now - 40 * MIN),
      },
      {
        id: 'msg-zain-2',
        role: 'astronaut',
        text: 'A bit tired. Sleep was short and my head feels light.',
        createdAt: iso(now - 39 * MIN),
      },
      {
        id: 'msg-zain-3',
        role: 'companion',
        text: 'Thanks for telling me. Short sleep can make light-headedness feel stronger. Would a three-minute breathing session help before you re-measure?',
        createdAt: iso(now - 38 * MIN),
        actions: [
          { id: 'act-zain-breath', label: 'Start breathing exercise', kind: 'breathing', payload: 'box' },
          { id: 'act-zain-checkin', label: 'Update my check-in', kind: 'checkin', payload: null },
        ],
      },
    ],
    'ast-maya': [],
    'ast-idris': [],
  }
}

function baseAlerts(now: number): Alert[] {
  return [
    {
      id: 'al-maya-radiation',
      astronautId: 'ast-maya',
      priority: 'health',
      severity: 'info',
      title: 'Scheduled radiation check due today',
      why: 'Monthly dosimetry review is due. No action needed until the evening slot.',
      createdAt: iso(now - 3 * HOUR),
      acknowledged: false,
      source: 'crew hub',
      channel: 'station',
    },
    {
      id: 'al-idris-sleep',
      astronautId: 'ast-idris',
      priority: 'health',
      severity: 'attention',
      title: 'Sleep debt resolved after plan change',
      why: 'Three nights below 6.5 h. The adjusted lights-down plan brought mean sleep back to 7.1 h.',
      createdAt: iso(now - DAY),
      acknowledged: true,
      acknowledgedBy: 'Dr. Samir Adel',
      acknowledgedAt: iso(now - 20 * HOUR),
      source: 'crew hub',
      channel: 'station',
    },
    {
      id: 'al-zain-backup',
      astronautId: 'ast-zain',
      priority: 'security',
      severity: 'info',
      title: 'Encrypted backup verified',
      why: 'Last backup passed the integrity check. Nothing to do.',
      createdAt: iso(now - 10 * HOUR),
      acknowledged: true,
      acknowledgedBy: 'Dr. Lena Ortiz',
      acknowledgedAt: iso(now - 9 * HOUR),
      source: 'security monitor',
      channel: 'station',
    },
  ]
}

function baseCommands(now: number): CommandRecord[] {
  return [
    {
      id: 'cmd-seed-1',
      astronautId: 'ast-zain',
      type: 'schedule',
      payload: { checkinTime: '19:30' },
      status: 'delivered',
      createdAt: iso(now - 2 * DAY),
      deliveredAt: iso(now - 2 * DAY + 4 * MIN),
      createdBy: 'Dr. Lena Ortiz',
      audit: [
        { at: iso(now - 2 * DAY), actor: 'Dr. Lena Ortiz', action: 'Created schedule command' },
        { at: iso(now - 2 * DAY + 4 * MIN), actor: 'crew hub', action: 'Delivered to crew device' },
      ],
    },
  ]
}

export interface MockDb {
  baseTime: number
  missionDay: number
  scenario: DemoScenario
  indicators: Record<string, Indicator[]>
  radiation: Record<string, RadiationState>
  exposure: Record<string, ExposureState>
  security: SecurityState
  link: LinkState
  backup: BackupState
  checkins: Record<string, Checkin[]>
  plans: Record<string, Plan>
  settings: Record<string, AstronautSettings>
  consent: Record<string, ConsentState>
  companion: Record<string, CompanionMessage[]>
  alerts: Alert[]
  commands: CommandRecord[]
}

function buildState(): MockDb {
  const now = Date.now()
  const weekOf = new Date(now).toISOString().slice(0, 10)

  const indicators: Record<string, Indicator[]> = {}
  const radiation: Record<string, RadiationState> = {}
  const exposure: Record<string, ExposureState> = {}
  const plans: Record<string, Plan> = {}
  const settings: Record<string, AstronautSettings> = {}
  const consent: Record<string, ConsentState> = {}

  const exposureSeed: Record<string, { missionId: string; dose: number; symptoms: string[]; note: string }> = {
    'ast-zain': { missionId: 'mis-zain-orion-6', dose: 1.8, symptoms: ['mild headache'], note: 'Routine solar event, no follow-up required.' },
    'ast-maya': { missionId: 'mis-maya-orion-5', dose: 2.6, symptoms: [], note: 'Deep-space transit dose, within budget.' },
    'ast-idris': { missionId: 'mis-idris-orion-4', dose: 3.4, symptoms: ['fatigue'], note: 'Solar event during EVA prep, recovered.' },
  }

  for (const member of CREW) {
    indicators[member.id] = baseIndicators(member.vitals, now)
    radiation[member.id] = baseRadiation(member.id, now, member.id === 'ast-zain' ? 12.4 : 18.2)
    const seed = exposureSeed[member.id]
    exposure[member.id] = baseExposure(member.id, seed.missionId, seed.dose, seed.symptoms, seed.note)
    plans[member.id] = {
      astronautId: member.id,
      weekOf,
      items: PLAN_TEMPLATE.map((item, index) => ({
        ...item,
        id: `plan-${member.id}-${index + 1}`,
        done: member.id === 'ast-maya' ? index < 3 : index === 0,
      })),
    }
    settings[member.id] = {
      ...DEFAULT_SETTINGS,
      notifications: { ...DEFAULT_SETTINGS.notifications },
    }
    consent[member.id] = {
      tiers: {
        vitals_summary: true,
        psych_summary: true,
        raw_audio: false,
        exposure_records: true,
      },
      updatedAt: iso(now - DAY),
    }
  }

  return {
    baseTime: now,
    missionDay: 12,
    scenario: 'normal',
    indicators,
    radiation,
    exposure,
    security: baseSecurity(now),
    link: baseLink(now),
    backup: baseBackup(now),
    checkins: baseCheckins(now),
    plans,
    settings,
    consent,
    companion: baseCompanion(now),
    alerts: baseAlerts(now),
    commands: baseCommands(now),
  }
}

let state: MockDb = buildState()

export function db(): MockDb {
  return state
}

export function resetDb(): MockDb {
  state = buildState()
  return state
}

function crewSeed(astronautId: string): CrewSeed | undefined {
  return CREW.find((member) => member.id === astronautId)
}

function memberIndicators(astronautId: string): Indicator[] {
  return state.indicators[astronautId] ?? []
}

function findIndicator(astronautId: string, key: string): Indicator | undefined {
  return memberIndicators(astronautId).find((indicator) => indicator.key === key)
}

function patchIndicator(astronautId: string, key: string, patch: Partial<Indicator>): void {
  const indicator = findIndicator(astronautId, key)
  if (indicator) Object.assign(indicator, patch)
}

export function listAstronauts(): Astronaut[] {
  return CREW.map((member) => {
    const indicators = memberIndicators(member.id)
    const sleep = indicators.find((indicator) => indicator.key === 'sleep')
    const heart = indicators.find((indicator) => indicator.key === 'heartRate')
    return {
      id: member.id,
      name: member.name,
      initials: member.initials,
      missionDay: state.missionDay,
      currentMissionId: `mis-${member.id}-current`,
      currentMissionName: member.missionName,
      status: worstStatus(indicators.map((indicator) => indicator.status)),
      linkState: state.link.state,
      lastSyncAt: state.link.lastSyncAt,
      activeAlerts: state.alerts.filter((alert) => alert.astronautId === member.id && !alert.acknowledged).length,
      sleepHours: sleep?.value ?? 0,
      restingHr: heart?.value ?? 0,
      location: member.location,
    }
  })
}

export function getAstronaut(astronautId: string): Astronaut | null {
  return listAstronauts().find((astronaut) => astronaut.id === astronautId) ?? null
}

export function getIndicators(astronautId: string): Indicator[] | null {
  return crewSeed(astronautId) ? memberIndicators(astronautId) : null
}

export function getIndicator(astronautId: string, key: string): Indicator | null {
  return findIndicator(astronautId, key) ?? null
}

export function getSeries(astronautId: string, key: string, range: Range): IndicatorSeries | null {
  const indicator = findIndicator(astronautId, key)
  if (!indicator) return null
  return {
    key: indicator.key,
    label: indicator.label,
    unit: indicator.unit,
    baseline: indicator.baseline,
    range,
    samples: buildSeries(astronautId, indicator, range, Date.now()),
  }
}

export function getOrgans(astronautId: string): Organ[] | null {
  const indicators = getIndicators(astronautId)
  if (!indicators) return null
  const radiation = state.radiation[astronautId]
  return ORGANS.map((organ) => {
    const statuses = organ.indicatorKeys.map(
      (key) => indicators.find((indicator) => indicator.key === key)?.status ?? 'unknown',
    )
    let status = worstStatus(statuses)
    if (organ.id === 'bones' && status === 'normal' && (radiation?.budgetUsedPct ?? 0) >= 25) {
      status = 'attention'
    }
    return { ...organ, status }
  })
}

export function getMissions(astronautId: string): Mission[] | null {
  const member = crewSeed(astronautId)
  if (!member) return null
  const indicators = memberIndicators(astronautId)
  const sleep = indicators.find((indicator) => indicator.key === 'sleep')?.value ?? 7
  const heart = indicators.find((indicator) => indicator.key === 'heartRate')?.value ?? 70
  const dose = state.radiation[astronautId]?.cumulativeMsv ?? 0

  const current: Mission = {
    id: `mis-${astronautId}-current`,
    astronautId,
    name: member.missionName,
    vehicle: member.vehicle,
    startDate: iso(state.baseTime - state.missionDay * DAY),
    endDate: null,
    days: state.missionDay,
    role: member.missionRole,
    highlight:
      state.missionDay >= 60
        ? 'Past the halfway point with a clean monitoring window.'
        : 'Current mission in progress.',
    summary: `Day ${state.missionDay} of ${member.missionName}. Measurements continue in the background and sync when the link is available.`,
    stats: {
      meanSleepHours: round1(sleep),
      meanHeartRate: Math.round(heart),
      radiationDoseMsv: round1(dose),
      incidents: state.alerts.filter((alert) => alert.astronautId === astronautId).length,
    },
  }

  return [current, ...(PAST_MISSIONS[astronautId] ?? []).map((mission) => ({ ...mission, astronautId }))]
}

export function getRadiation(astronautId: string): RadiationState | null {
  return state.radiation[astronautId] ?? null
}

export function getExposure(astronautId: string): ExposureState | null {
  return state.exposure[astronautId] ?? null
}

export function getPlan(astronautId: string): Plan | null {
  return state.plans[astronautId] ?? null
}

export function setPlanItem(astronautId: string, itemId: string, done: boolean): Plan | null {
  const plan = state.plans[astronautId]
  const item = plan?.items.find((entry) => entry.id === itemId)
  if (!plan || !item) return null
  item.done = done
  emitEvent('plan.updated', `${item.title} marked ${done ? 'done' : 'open'}.`, 'info', { astronautId, itemId, done })
  return plan
}

export function getSettings(astronautId: string): AstronautSettings | null {
  return state.settings[astronautId] ?? null
}

export function getConsent(astronautId: string): ConsentState | null {
  return state.consent[astronautId] ?? null
}

export function getCompanion(astronautId: string): CompanionMessage[] | null {
  return astronautId in state.companion ? state.companion[astronautId] : null
}

const PRIORITY_RANK: Record<Alert['priority'], number> = { security: 0, radiation: 1, health: 2 }
const SEVERITY_RANK: Record<Alert['severity'], number> = { urgent: 3, attention: 2, info: 1 }

export function getAlerts(filter: { astronautId?: string; priority?: string; acknowledged?: string } = {}): Alert[] {
  return state.alerts
    .filter((alert) => (filter.astronautId ? alert.astronautId === filter.astronautId : true))
    .filter((alert) => (filter.priority ? alert.priority === filter.priority : true))
    .filter((alert) =>
      filter.acknowledged === undefined
        ? true
        : alert.acknowledged === (filter.acknowledged === 'true'),
    )
    .slice()
    .sort((a, b) => {
      const priority = PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority]
      if (priority !== 0) return priority
      const severity = SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity]
      if (severity !== 0) return severity
      return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    })
}

export function getCommands(astronautId?: string): CommandRecord[] {
  return state.commands
    .filter((command) => (astronautId ? command.astronautId === astronautId : true))
    .slice()
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
}

export function getBreathingTechniques() {
  return BREATHING_TECHNIQUES
}

export function crewOverview() {
  return {
    generatedAt: iso(Date.now()),
    link: state.link,
    astronauts: listAstronauts(),
  }
}

export function updateSettings(astronautId: string, settings: AstronautSettings): AstronautSettings | null {
  if (!crewSeed(astronautId)) return null
  state.settings[astronautId] = settings
  emitEvent('settings.updated', `Settings updated for ${crewSeed(astronautId)?.name}.`, 'info', {
    astronautId,
  })
  return settings
}

export function updateConsent(astronautId: string, tiers: ConsentTiers): ConsentState | null {
  if (tiers.raw_audio !== false) return null
  if (!crewSeed(astronautId)) return null
  const next: ConsentState = { tiers, updatedAt: iso(Date.now()) }
  state.consent[astronautId] = next
  emitEvent('consent.updated', 'Consent choices updated.', 'info', { astronautId })
  return next
}

export function createCheckin(request: CheckinRequest): Checkin {
  const astronautId = request.astronautId ?? 'ast-zain'
  const checkin: Checkin = {
    id: `chk-${Date.now()}`,
    astronautId,
    createdAt: iso(Date.now()),
    mood: request.mood,
    energy: request.energy,
    dizziness: request.dizziness,
    workload: request.workload,
    symptoms: request.symptoms,
    note: request.note,
  }
  const list = state.checkins[astronautId] ?? []
  state.checkins[astronautId] = [checkin, ...list]

  patchIndicator(astronautId, 'mood', {
    value: request.mood,
    status: request.mood >= 3 ? 'normal' : 'attention',
    trend: request.mood >= 3 ? 'stable' : 'down',
    reason: request.mood >= 3 ? 'Mood reported steady.' : 'Mood reported low today — reaching out early.',
    updatedAt: checkin.createdAt,
  })
  patchIndicator(astronautId, 'dizziness', {
    value: request.dizziness,
    status: request.dizziness <= 1 ? 'normal' : request.dizziness === 2 ? 'attention' : 'urgent',
    trend: request.dizziness === 0 ? 'stable' : 'up',
    reason:
      request.dizziness === 0
        ? 'No dizziness reported.'
        : `Dizziness score ${request.dizziness} of 3 reported in this check-in.`,
    updatedAt: checkin.createdAt,
  })

  emitEvent('checkin.created', 'Check-in received.', 'info', { astronautId, checkinId: checkin.id })
  return checkin
}

export function acknowledgeAlert(alertId: string, by: string): Alert | null {
  const alert = state.alerts.find((item) => item.id === alertId)
  if (!alert) return null
  alert.acknowledged = true
  alert.acknowledgedBy = by
  alert.acknowledgedAt = iso(Date.now())
  emitEvent('alert.acknowledged', `Alert acknowledged: ${alert.title}`, 'info', { alertId, by })
  return alert
}

export function createCommand(
  request: { astronautId: string; type: CommandRecord['type']; payload: Record<string, unknown> },
  createdBy: string,
): CommandRecord | null {
  if (!crewSeed(request.astronautId)) return null
  const now = Date.now()
  const delivered = state.link.state === 'connected'
  const command: CommandRecord = {
    id: `cmd-${now}`,
    astronautId: request.astronautId,
    type: request.type,
    payload: request.payload,
    status: delivered ? 'delivered' : 'pending',
    createdAt: iso(now),
    deliveredAt: delivered ? iso(now) : null,
    createdBy,
    audit: [
      { at: iso(now), actor: createdBy, action: `Created ${request.type} command` },
      ...(delivered
        ? [{ at: iso(now), actor: 'crew hub', action: 'Delivered to crew device' }]
        : [{ at: iso(now), actor: 'crew hub', action: 'Queued until the link is available' }]),
    ],
  }
  state.commands.unshift(command)

  if (request.type === 'schedule' && typeof request.payload.checkinTime === 'string') {
    const settings = state.settings[request.astronautId]
    if (settings) settings.checkinTime = request.payload.checkinTime
  }

  emitEvent(
    'command.created',
    delivered
      ? 'Command delivered to the crew device.'
      : 'Command queued — the link is not available yet.',
    delivered ? 'info' : 'attention',
    { commandId: command.id },
  )
  return command
}

function deliverPendingCommands(now: number): void {
  for (const command of state.commands) {
    if (command.status !== 'pending') continue
    command.status = 'delivered'
    command.deliveredAt = iso(now)
    command.audit.push({
      at: iso(now),
      actor: 'crew hub',
      action: 'Delivered to crew device after link restored',
    })
  }
}

function companionActions(text: string): CompanionAction[] {
  const lower = text.toLowerCase()
  if (/dizz|light|head|faint/.test(lower)) {
    return [
      { id: 'act-breath', label: 'Start breathing exercise', kind: 'breathing', payload: 'box' },
      { id: 'act-checkin', label: 'Log dizziness in a check-in', kind: 'checkin', payload: null },
    ]
  }
  if (/sleep|tired|exhaust|night/.test(lower)) {
    return [
      { id: 'act-478', label: 'Try 4-7-8 breathing', kind: 'breathing', payload: 'four-seven-eight' },
      { id: 'act-plan', label: 'Open my weekly plan', kind: 'plan', payload: null },
    ]
  }
  if (/radiation|shelter|storm/.test(lower)) {
    return [{ id: 'act-shelter', label: 'Open shelter instructions', kind: 'shelter', payload: null }]
  }
  if (/stress|anx|worr|nerv|pressure/.test(lower)) {
    return [
      { id: 'act-coherent', label: 'Start coherent breathing', kind: 'breathing', payload: 'coherent' },
      { id: 'act-checkin', label: 'Tell the ground team how I feel', kind: 'checkin', payload: null },
    ]
  }
  return [
    { id: 'act-checkin', label: 'Do a one-tap check-in', kind: 'checkin', payload: null },
    { id: 'act-breath', label: 'Take a three-minute breathing break', kind: 'breathing', payload: 'box' },
  ]
}

function companionText(request: CompanionRequest): string {
  const lower = request.text.toLowerCase()
  const opener =
    request.tone === 'direct'
      ? 'Understood.'
      : request.tone === 'warm'
        ? "I'm right here with you."
        : 'Thank you for telling me.'

  if (/dizz|light|head|faint/.test(lower)) {
    return `${opener} Light-headedness is worth taking seriously in microgravity. Sit down, keep your head still for a minute, and re-measure when it passes. If it gets worse, tell the medical team now.`
  }
  if (/sleep|tired|exhaust|night/.test(lower)) {
    return `${opener} Short sleep explains a lot of what you are feeling. A slow 4-7-8 session and dimming the lights 30 minutes before bed would help tonight.`
  }
  if (/radiation|shelter|storm/.test(lower)) {
    return `${opener} The shelter is 18 metres to your right in Node 3. Take the dosimeter with you and stay until the all-clear. I will keep the instructions on screen.`
  }
  if (/stress|anx|worr|nerv|pressure/.test(lower)) {
    return `${opener} That sounds heavy. You do not have to carry it alone. Would a short breathing session help, or do you want to send a note to the ground team?`
  }
  return `${opener} I'm listening. Say what feels heaviest right now, and we can pick one small thing to do next.`
}

export function companionReply(request: CompanionRequest): CompanionReply {
  const now = Date.now()
  const astronautId = request.astronautId
  const actions = companionActions(request.text)
  const text = companionText(request)

  const astronautMessage: CompanionMessage = {
    id: `msg-${now}-a`,
    role: 'astronaut',
    text: request.text,
    createdAt: iso(now),
  }
  const reply: CompanionMessage = {
    id: `msg-${now}-c`,
    role: 'companion',
    text,
    createdAt: iso(now + 1),
    actions,
  }

  const list = state.companion[astronautId] ?? []
  state.companion[astronautId] = [...list, astronautMessage, reply]
  emitEvent('companion.reply', 'Companion replied.', 'info', { astronautId })
  return { reply, actions }
}

function setSecurity(
  level: SecurityState['level'],
  headline: string,
  checkId: SecurityCheck['id'],
  checkState: SecurityCheck['state'],
  detail: string,
): void {
  state.security.level = level
  state.security.headline = headline
  state.security.lastEventAt = iso(Date.now())
  const check = state.security.checks.find((item) => item.id === checkId)
  if (check) {
    check.state = checkState
    check.detail = detail
  }
}

function pushAlert(
  astronautId: string,
  priority: Alert['priority'],
  severity: Alert['severity'],
  title: string,
  why: string,
): Alert {
  const alert: Alert = {
    id: `scn-al-${Date.now()}-${state.alerts.length}`,
    astronautId,
    priority,
    severity,
    title,
    why,
    createdAt: iso(Date.now()),
    acknowledged: false,
    source: 'demo scenario',
    channel: 'station',
  }
  state.alerts.unshift(alert)
  return alert
}

function clearScenarioAlerts(): void {
  state.alerts = state.alerts.filter((alert) => alert.source !== 'demo scenario')
}

export function demoState(): DemoState {
  return {
    missionDay: state.missionDay,
    scenario: state.scenario,
    link: state.link,
    security: state.security,
    radiationAlertActive: state.radiation['ast-zain']?.alertActive ?? false,
  }
}

const SCENARIO_MESSAGES: Record<Exclude<DemoScenario, 'reset'>, { message: string; severity: 'info' | 'attention' | 'urgent' }> = {
  normal: { message: 'Normal mission day loaded.', severity: 'info' },
  day60: { message: 'Fast-forwarded to day 60.', severity: 'info' },
  radiation_spike: {
    message: 'Solar particle event: shelter the crew now.',
    severity: 'urgent',
  },
  sensor_fault: {
    message: 'Heart-rate sensor fault — the reading is marked unknown.',
    severity: 'attention',
  },
  cut_link: { message: 'Ground link lost. The crew device is running autonomously.', severity: 'info' },
  restore_link: { message: 'Ground link restored.', severity: 'info' },
  link_delay: { message: 'Link delay applied. Data is arriving late.', severity: 'attention' },
  attack_forged_reading: {
    message: 'Forged reading rejected by the integrity check.',
    severity: 'attention',
  },
  attack_replay: { message: 'Replayed packet rejected.', severity: 'attention' },
  attack_spoofed_device: {
    message: 'Unknown device blocked before it could pair.',
    severity: 'urgent',
  },
  attack_fake_dosimeter: {
    message: 'Fake dosimeter spike rejected.',
    severity: 'attention',
  },
}

export function applyScenario(scenario: DemoScenario, delayMs?: number): DemoState {
  const now = Date.now()

  if (scenario === 'reset' || scenario === 'normal') {
    state = buildState()
    state.scenario = scenario
    emitEvent(
      'demo.scenario',
      scenario === 'reset' ? 'Demo reset to a normal mission day.' : 'Normal mission day loaded.',
      'info',
      { scenario },
    )
    return demoState()
  }

  state.scenario = scenario
  state.baseTime = now
  clearScenarioAlerts()

  switch (scenario) {
    case 'day60': {
      state.missionDay = 60
      const radiation = state.radiation['ast-zain']
      if (radiation) {
        radiation.cumulativeMsv = 46.2
        radiation.budgetUsedPct = round1((46.2 / radiation.budgetMsv) * 100)
        radiation.status = 'attention'
      }
      patchIndicator('ast-zain', 'sleep', {
        value: 6.1,
        status: 'attention',
        trend: 'down',
        reason: 'Average sleep 6.1 h over three nights — below your 7–9 h baseline.',
        updatedAt: iso(now - 7 * HOUR),
      })
      patchIndicator('ast-zain', 'dizziness', {
        value: 2,
        status: 'attention',
        trend: 'up',
        reason: 'Two light-headed episodes reported during exercise.',
        updatedAt: iso(now - 40 * MIN),
      })
      patchIndicator('ast-zain', 'mood', {
        value: 2,
        status: 'attention',
        trend: 'down',
        reason: 'Mood score 2 for three days — flagging early, not a diagnosis.',
        updatedAt: iso(now - 40 * MIN),
      })
      patchIndicator('ast-zain', 'radiation', {
        value: 1.4,
        status: 'attention',
        trend: 'up',
        reason: 'Cumulative dose is 31% of the mission budget — routine monitoring.',
        updatedAt: iso(now - 3 * MIN),
      })
      pushAlert(
        'ast-zain',
        'health',
        'attention',
        'Bone density watch — day 60',
        'Cumulative dose is 31% of budget and loading exercise dropped 18% this week.',
      )
      break
    }

    case 'radiation_spike': {
      const radiation = state.radiation['ast-zain']
      const event: RadiationEvent = {
        id: `scn-rad-${now}`,
        type: 'solar_particle_event',
        doseRate: 380,
        startedAt: iso(now - 3 * MIN),
        endedAt: null,
        note: 'Solar particle event detected by the station dosimeter.',
      }
      if (radiation) {
        radiation.doseRate = 380
        radiation.status = 'urgent'
        radiation.alertActive = true
        radiation.cumulativeMsv = round1(radiation.cumulativeMsv + 3.2)
        radiation.budgetUsedPct = round1((radiation.cumulativeMsv / radiation.budgetMsv) * 100)
        radiation.latestEvent = event
        radiation.events = [event, ...radiation.events]
      }
      patchIndicator('ast-zain', 'radiation', {
        value: 380,
        status: 'urgent',
        trend: 'up',
        reason: 'Solar particle event: 380 µSv/h. Move to the shelter now.',
        updatedAt: iso(now - 2 * MIN),
      })
      const exposure = state.exposure['ast-zain']
      if (exposure) {
        const record: ExposureRecord = {
          id: `scn-exp-${now}`,
          astronautId: 'ast-zain',
          missionId: 'mis-ast-zain-current',
          date: iso(now).slice(0, 10),
          doseMsv: 3.2,
          symptoms: ['none reported'],
          followUpUntil: iso(now + 72 * HOUR),
          note: 'Solar particle event — shelter protocol active.',
        }
        exposure.records = [record, ...exposure.records]
        exposure.monitoringActive = true
        exposure.monitoringStartedAt = iso(now)
        exposure.monitoringUntil = iso(now + 72 * HOUR)
      }
      state.backup.status = 'syncing'
      state.backup.pendingBatches = 4
      pushAlert(
        'ast-zain',
        'radiation',
        'urgent',
        'Solar particle event — shelter now',
        'Dose rate 380 µSv/h and rising. Shelter in Node 3; the dose budget is still within limits.',
      )
      emitEvent('radiation.alert', 'Shelter now: solar particle event.', 'urgent', {
        doseRate: 380,
      })
      break
    }

    case 'sensor_fault': {
      patchIndicator('ast-zain', 'heartRate', {
        status: 'unknown',
        trend: 'stable',
        reason: 'Wrist sensor lost contact 4 min ago — showing the last good reading.',
        updatedAt: iso(now - 4 * MIN),
      })
      pushAlert(
        'ast-zain',
        'health',
        'attention',
        'Heart-rate sensor fault',
        'No signal from the wrist sensor for 4 minutes. The last good reading is still shown and clearly marked.',
      )
      break
    }

    case 'cut_link': {
      state.link = {
        state: 'autonomous',
        label: 'Autonomous Mode',
        since: iso(now),
        delayMs: 0,
        lastSyncAt: iso(now - 3 * HOUR),
        queue: 18,
      }
      state.backup.status = 'queued'
      state.backup.pendingBatches = 6
      state.backup.lastBackupAt = iso(now - 3 * HOUR)
      emitEvent('link.state', 'Ground link lost. 18 packets queued locally.', 'info', {
        queue: 18,
      })
      break
    }

    case 'restore_link': {
      state.link = {
        state: 'connected',
        label: 'Connected',
        since: iso(now),
        delayMs: 800,
        lastSyncAt: iso(now),
        queue: 0,
      }
      state.backup.status = 'current'
      state.backup.pendingBatches = 0
      state.backup.lastBackupAt = iso(now)
      deliverPendingCommands(now)
      emitEvent('link.state', 'Ground link restored. Queued data is syncing.', 'info', { queue: 0 })
      break
    }

    case 'link_delay': {
      state.link = {
        state: 'degraded',
        label: 'Low link',
        since: iso(now),
        delayMs: delayMs ?? 45_000,
        lastSyncAt: iso(now - 20 * MIN),
        queue: 5,
      }
      emitEvent('link.state', 'Link delay applied. Data is arriving late.', 'attention', {
        delayMs: delayMs ?? 45_000,
      })
      break
    }

    case 'attack_forged_reading': {
      setSecurity(
        'degraded',
        'One forged reading was rejected. Your data is unaffected.',
        'integrity',
        'degraded',
        'A heart-rate packet failed the signature check and was dropped.',
      )
      pushAlert(
        'ast-zain',
        'security',
        'attention',
        'Forged heart-rate reading rejected',
        'The packet signature did not match your device key. It was dropped before display.',
      )
      break
    }

    case 'attack_replay': {
      setSecurity(
        'degraded',
        'A replayed packet was rejected. Your data is unaffected.',
        'secure_communication',
        'degraded',
        'A replayed telemetry packet was rejected because its nonce had been used.',
      )
      pushAlert(
        'ast-zain',
        'security',
        'attention',
        'Replayed telemetry rejected',
        'An old packet was re-sent to the hub. The nonce check blocked it.',
      )
      break
    }

    case 'attack_spoofed_device': {
      setSecurity(
        'critical',
        'Unknown device blocked. The medical team has been notified.',
        'confidentiality',
        'degraded',
        'An unknown device tried to pair as Zain’s wrist sensor and was refused.',
      )
      pushAlert(
        'ast-zain',
        'security',
        'urgent',
        'Spoofed device blocked',
        'An unpaired device attempted to send vitals under Zain’s identity. The hub refused the connection.',
      )
      break
    }

    case 'attack_fake_dosimeter': {
      setSecurity(
        'degraded',
        'A fake dosimeter spike was rejected. Radiation risk is unchanged.',
        'integrity',
        'degraded',
        'A dosimeter packet claiming a 900 µSv/h spike failed integrity verification.',
      )
      const radiation = state.radiation['ast-zain']
      if (radiation) {
        const event: RadiationEvent = {
          id: `scn-rad-fake-${now}`,
          type: 'dosimeter_spike',
          doseRate: 900,
          startedAt: iso(now - 1 * MIN),
          endedAt: iso(now),
          note: 'Rejected: signature mismatch on the dosimeter packet.',
        }
        radiation.latestEvent = event
        radiation.events = [event, ...radiation.events]
        radiation.alertActive = false
      }
      pushAlert(
        'ast-zain',
        'security',
        'attention',
        'Fake dosimeter spike rejected',
        'The packet failed the signature check, so no radiation alarm was raised.',
      )
      break
    }

    default:
      break
  }

  const meta = SCENARIO_MESSAGES[scenario]
  emitEvent('demo.scenario', meta.message, meta.severity, { scenario })
  return demoState()
}
