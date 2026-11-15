import type { Role } from '@contracts'

export function canWrite(role: Role): boolean {
  return role !== 'viewer'
}

export const COMMAND_TYPE_LABEL = {
  schedule: 'Schedule',
  thresholds: 'Thresholds',
  plan: 'Plan',
} as const

export const INDICATOR_OPTIONS = [
  { key: 'heartRate', label: 'Heart rate' },
  { key: 'spo2', label: 'SpO₂' },
  { key: 'bloodPressure', label: 'Blood pressure' },
  { key: 'bloodGlucose', label: 'Blood glucose' },
  { key: 'temperature', label: 'Temperature' },
  { key: 'sleep', label: 'Sleep' },
  { key: 'dizziness', label: 'Dizziness' },
  { key: 'mood', label: 'Mood' },
  { key: 'radiation', label: 'Radiation' },
] as const

export function astronautName(id: string, names: Record<string, string>): string {
  return names[id] ?? id
}
