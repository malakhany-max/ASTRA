export * from './types'
export * as WireContracts from './canonical'

export type IndicatorKey =
  | 'heartRate'
  | 'spo2'
  | 'bloodPressure'
  | 'bloodGlucose'
  | 'temperature'
  | 'sleep'
  | 'dizziness'
  | 'mood'
  | 'radiation'

export type Range = '24h' | '7d' | '30d'

export type OrganId = 'heart' | 'brain' | 'lungs' | 'bones'

export type DemoScenarioName =
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
