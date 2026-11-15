export interface ASTRALinkEnvelopeUsedForALLSpacecraftGroundTraffic {
  schema: 'astra.envelope.v1'
  msg_id: string
  direction: 'uplink' | 'downlink'
  type:
    'summary' | 'alert' | 'security_event' | 'exposure_record' | 'config_bundle' | 'history_bundle'
  priority: number
  created_ts: string
  payload: {
    [k: string]: unknown
  }
  node_id: 'hub-01' | 'ground-01'
  sig: string
}
