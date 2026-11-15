export interface ASTRAExposureRecord {
  schema: 'astra.exposure_record.v1'
  event_id: string
  astronaut_id: string
  start_ts: string
  end_ts: string
  peak_dose_rate: {
    value: number
    unit: string
    [k: string]: unknown
  }
  cumulative_dose: {
    value: number
    unit: string
    [k: string]: unknown
  }
  location: string
  shielding: 'shelter_active' | 'none'
  sensor_integrity: 'trusted' | 'degraded' | 'untrusted'
  followup_window_hours: number
  symptom_checkins: {
    ts: string
    symptoms: string[]
    severity: number
    [k: string]: unknown
  }[]
  escalation_level: 1 | 2 | 3
  sig: string
}
