export interface ASTRASecurityEvent {
  schema: 'astra.security_event.v1'
  event_id: string
  event_type:
    | 'forged_signature'
    | 'replay'
    | 'unpaired_device'
    | 'implausible_value'
    | 'sensor_fault_suspected'
    | 'dosimeter_mismatch'
    | 'clock_anomaly'
    | 'tampered_message'
  device_id: string
  astronaut_id: string
  time_window: [string, string]
  severity: 'low' | 'medium' | 'high' | 'critical'
  evidence_hash: string
  count: number
  sig: string
}
