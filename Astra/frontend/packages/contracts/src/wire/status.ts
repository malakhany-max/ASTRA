export interface ASTRAStatusProducedByTheEngine {
  schema: 'astra.status.v1'
  astronaut_id: string
  indicator: string
  status: 'normal' | 'attention' | 'urgent'
  confidence: number
  reasons: string[]
  baseline_ref: string
  recommended_action: string
  decision_level: 1 | 2 | 3
  computed_ts: string
}
