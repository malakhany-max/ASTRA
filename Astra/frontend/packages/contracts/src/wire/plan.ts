export interface ASTRAPersonalizedPlan {
  schema: 'astra.plan.v1'
  astronaut_id: string
  week: number
  exercise: PlanItem[]
  nutrition: PlanItem[]
  sleep: PlanItem[]
  wellbeing: PlanItem[]
  rationale: string
}
export interface PlanItem {
  title: string
  duration_min?: number
  frequency_per_week?: number
  notes: string
  [k: string]: unknown
}
