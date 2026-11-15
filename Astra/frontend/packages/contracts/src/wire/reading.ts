export interface ASTRAReading {
  schema: 'astra.reading.v1'
  device_id: string
  astronaut_id: string
  metric:
    | 'heart_rate'
    | 'hrv_rmssd'
    | 'spo2'
    | 'skin_temp'
    | 'sleep_duration'
    | 'activity_level'
    | 'bp_systolic'
    | 'bp_diastolic'
    | 'blood_glucose'
    | 'dizziness_self_report'
    | 'mood'
    | 'dose_rate'
    | 'cumulative_dose'
    | 'neutron_dose_rate'
  value: number
  unit: string
  ts: string
  seq: number
  nonce: string
  source: 'wearable' | 'clinical_device' | 'manual' | 'dosimeter' | 'area_monitor' | 'self_report'
  quality: number
  sig: string
}
