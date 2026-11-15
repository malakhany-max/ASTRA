/* eslint-disable */

export type HealthStatus = 'normal' | 'attention' | 'urgent' | 'unknown'
export type TrendDirection = 'up' | 'down' | 'stable'
export type AlertPriority = 'security' | 'radiation' | 'health'
export type AlertSeverity = 'urgent' | 'attention' | 'info'
export type LinkStateValue = 'connected' | 'autonomous' | 'degraded' | 'down'
export type SecurityLevel = 'ok' | 'degraded' | 'critical'
export type Role = 'flight_surgeon' | 'medical_officer' | 'viewer'
export type DemoScenario =
  | 'reset'
  | 'normal'
  | 'day60'
  | 'radiation_spike'
  | 'sensor_fault'
  | 'cut_link'
  | 'restore_link'
  | 'link_delay'
  | 'attack_forged_reading'
  | 'attack_replay'
  | 'attack_spoofed_device'
  | 'attack_fake_dosimeter'

export interface AstraDomain {
  healthStatus?: HealthStatus
  indicator?: Indicator
  indicatorSample?: IndicatorSample
  indicatorSeries?: IndicatorSeries
  organ?: Organ
  alert?: Alert
  astronaut?: Astronaut
  crewOverview?: CrewOverview
  mission?: Mission
  exposureRecord?: ExposureRecord
  exposureState?: ExposureState
  radiationEvent?: RadiationEvent
  radiationState?: RadiationState
  shelterInfo?: ShelterInfo
  securityCheck?: SecurityCheck
  securityState?: SecurityState
  linkState?: LinkState
  backupState?: BackupState
  checkin?: Checkin
  checkinRequest?: CheckinRequest
  plan?: Plan
  planItem?: PlanItem
  companionMessage?: CompanionMessage
  companionRequest?: CompanionRequest
  companionReply?: CompanionReply
  companionAction?: CompanionAction
  breathingTechnique?: BreathingTechnique
  speechResult?: SpeechResult
  authUser?: AuthUser
  loginRequest?: LoginRequest
  session?: Session
  consentState?: ConsentState
  astronautSettings?: AstronautSettings
  commandRequest?: CommandRequest
  commandRecord?: CommandRecord
  demoRequest?: DemoRequest
  demoState?: DemoState
  appEvent?: AppEvent
}
export interface Indicator {
  key: string
  label: string
  unit: string
  value: number
  secondary?: number | null
  status: HealthStatus
  reason: string
  updatedAt: string
  baseline: Baseline
  trend: TrendDirection
  precision?: number | null
}
export interface Baseline {
  low: number
  high: number
}
export interface IndicatorSample {
  t: string
  value: number
  secondary?: number | null
}
export interface IndicatorSeries {
  key: string
  label: string
  unit: string
  baseline: Baseline
  range: string
  samples: IndicatorSample[]
}
export interface Organ {
  id: 'heart' | 'brain' | 'lungs' | 'bones'
  name: string
  function: string
  status: HealthStatus
  hazards: string[]
  whatToDo: string[]
  indicatorKeys: string[]
}
export interface Alert {
  id: string
  astronautId: string
  priority: AlertPriority
  severity: AlertSeverity
  title: string
  why: string
  createdAt: string
  acknowledged: boolean
  acknowledgedBy?: string | null
  acknowledgedAt?: string | null
  source: string
  channel?: 'station' | 'astronaut'
}
export interface Astronaut {
  id: string
  name: string
  initials: string
  missionDay: number
  currentMissionId: string
  currentMissionName: string
  status: HealthStatus
  linkState: LinkStateValue
  lastSyncAt: string
  activeAlerts: number
  sleepHours?: number
  restingHr?: number
  location?: string
}
export interface CrewOverview {
  generatedAt: string
  link: LinkState
  astronauts: Astronaut[]
}
export interface LinkState {
  state: LinkStateValue
  label: string
  since: string
  delayMs: number
  lastSyncAt: string
  queue: number
}
export interface Mission {
  id: string
  astronautId: string
  name: string
  vehicle: string
  startDate: string
  endDate: string | null
  days: number
  role: string
  highlight: string
  summary: string
  stats: MissionStats
}
export interface MissionStats {
  meanSleepHours: number
  meanHeartRate: number
  radiationDoseMsv: number
  incidents: number
}
export interface ExposureRecord {
  id: string
  astronautId: string
  missionId: string
  date: string
  doseMsv: number
  symptoms: string[]
  followUpUntil: string | null
  note?: string
}
export interface ExposureState {
  astronautId: string
  records: ExposureRecord[]
  monitoringActive: boolean
  monitoringStartedAt: string | null
  monitoringUntil: string | null
  windowHours: number
}
export interface RadiationEvent {
  id: string
  type: 'routine' | 'solar_particle_event' | 'alarm' | 'dosimeter_spike'
  doseRate: number
  startedAt: string
  endedAt: string | null
  note?: string
}
export interface RadiationState {
  astronautId: string
  doseRate: number
  unit: string
  cumulativeMsv: number
  budgetMsv: number
  budgetUsedPct: number
  status: HealthStatus
  alertActive: boolean
  shelter: ShelterInfo
  latestEvent?: RadiationEvent
  events: RadiationEvent[]
}
export interface ShelterInfo {
  zone: string
  direction: 'left' | 'right' | 'forward' | 'behind' | 'up' | 'down'
  distanceM: number
  instructions: string[]
}
export interface SecurityCheck {
  id: 'confidentiality' | 'integrity' | 'secure_communication' | 'offline_backup'
  label: string
  state: SecurityLevel
  detail: string
}
export interface SecurityState {
  level: SecurityLevel
  headline: string
  checks: SecurityCheck[]
  lastEventAt: string
}
export interface BackupState {
  status: 'current' | 'syncing' | 'queued' | 'error'
  lastBackupAt: string
  pendingBatches: number
  sizeKb: number
  encrypted: boolean
}
export interface Checkin {
  id: string
  astronautId: string
  createdAt: string
  mood: number
  energy: number
  dizziness: number
  workload: number
  symptoms: string[]
  note?: string
}
export interface CheckinRequest {
  astronautId?: string
  mood: number
  energy: number
  dizziness: number
  workload: number
  symptoms: string[]
  note?: string
}
export interface Plan {
  astronautId: string
  weekOf: string
  items: PlanItem[]
}
export interface PlanItem {
  id: string
  category: 'exercise' | 'nutrition' | 'sleep' | 'wellbeing'
  title: string
  detail: string
  rationale: string
  durationMin: number
  done: boolean
}
export interface CompanionMessage {
  id: string
  role: 'astronaut' | 'companion'
  text: string
  createdAt: string
  actions?: CompanionAction[]
}
export interface CompanionAction {
  id: string
  label: string
  kind: 'breathing' | 'checkin' | 'plan' | 'shelter' | 'none'
  payload?: string | null
}
export interface CompanionRequest {
  astronautId: string
  text: string
  tone?: 'calm' | 'warm' | 'direct'
  language?: 'en' | 'ar'
}
export interface CompanionReply {
  reply: CompanionMessage
  actions: CompanionAction[]
}
export interface BreathingTechnique {
  id: string
  name: string
  description: string
  phases: BreathingPhase[]
  defaultMinutes: number
  benefits: string[]
}
export interface BreathingPhase {
  label: 'inhale' | 'hold' | 'exhale' | 'pause'
  seconds: number
}
export interface SpeechResult {
  text: string
  confidence?: number | null
}
export interface AuthUser {
  id: string
  name: string
  role: Role
  initials: string
}
export interface LoginRequest {
  email: string
  password: string
}
export interface Session {
  token: string
  user: AuthUser
  expiresAt: string
}
export interface ConsentState {
  tiers: ConsentTiers
  updatedAt: string
}
export interface ConsentTiers {
  vitals_summary: boolean
  psych_summary: boolean
  raw_audio: boolean
  exposure_records: boolean
}
export interface AstronautSettings {
  voice: boolean
  tone: 'calm' | 'warm' | 'direct'
  language: 'en' | 'ar'
  checkinTime: string
  environment: 'spacecraft' | 'station' | 'rover' | 'base'
  notifications: NotificationPrefs
}
export interface NotificationPrefs {
  alarms: boolean
  reminders: boolean
  companion: boolean
}
export interface CommandRequest {
  astronautId: string
  type: 'thresholds' | 'plan' | 'schedule'
  payload: {
    [k: string]: unknown
  }
}
export interface CommandRecord {
  id: string
  astronautId: string
  type: 'thresholds' | 'plan' | 'schedule'
  payload: {
    [k: string]: unknown
  }
  status: 'pending' | 'delivered' | 'failed'
  createdAt: string
  deliveredAt: string | null
  createdBy: string
  audit: AuditEntry[]
}
export interface AuditEntry {
  at: string
  actor: string
  action: string
}
export interface DemoRequest {
  scenario: DemoScenario
  delayMs?: number
}
export interface DemoState {
  missionDay: number
  scenario: DemoScenario
  link: LinkState
  security: SecurityState
  radiationAlertActive: boolean
}
export interface AppEvent {
  id: string
  type: string
  at: string
  severity: 'info' | 'attention' | 'urgent'
  message: string
  payload: {
    [k: string]: unknown
  }
}
