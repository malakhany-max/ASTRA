export interface ASTRAConsent {
  astronaut_id: string
  tiers: {
    vitals_summary: boolean
    psych_summary: boolean
    raw_audio: boolean
    exposure_records: boolean
  }
  emergency_override: boolean
}
