export interface ASTRAIntegrityResultSecuritySDK {
  classification: 'trusted' | 'suspect_fault' | 'suspect_tamper'
  reasons: string[]
  checks: {
    signature: boolean
    freshness: boolean
    plausibility: boolean
    sensor_health: boolean
    cross_sensor: boolean
  }
}
