import { useMemo, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { Apple, CalendarCheck, CheckCircle2, Circle, Dumbbell, HeartHandshake, MoonStar, ShieldCheck } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Plan, PlanItem } from '@contracts'
import { apiPost, errorMessage, formatDate, useApi, useDocumentTitle, useToast } from '@astra/shared'
import { ASTRONAUT_ID } from '../lib/astro'

type Category = PlanItem['category']

const CATEGORY_META: Record<Category, { label: string; blurb: string; icon: LucideIcon }> = {
  exercise: { label: 'Exercise', blurb: 'Load the body so bone and muscle keep their work.', icon: Dumbbell },
  nutrition: { label: 'Nutrition', blurb: 'Fuel the repair that exercise starts.', icon: Apple },
  sleep: { label: 'Sleep', blurb: 'Protect the night; recovery happens there.', icon: MoonStar },
  wellbeing: { label: 'Wellbeing', blurb: 'Keep the mind as cared for as the body.', icon: HeartHandshake },
}

const ORDER: Category[] = ['exercise', 'nutrition', 'sleep', 'wellbeing']

export function PlanPage() {
  useDocumentTitle('Plan · Astra')
  const toast = useToast()
  const plan = useApi<Plan & { groundNote?: { note: string; ts: string } }>(
    `/api/astronauts/${ASTRONAUT_ID}/plan`,
    { live: true, livePrefixes: ['plan'] },
  )
  const [savingId, setSavingId] = useState<string | null>(null)

  const grouped = useMemo(() => {
    const items = plan.data?.items ?? []
    return ORDER.map((category) => ({
      category,
      items: items.filter((item) => item.category === category),
    })).filter((group) => group.items.length > 0)
  }, [plan.data])

  const items = plan.data?.items ?? []
  const done = items.filter((item) => item.done).length
  const totalMinutes = items.reduce((sum, item) => sum + item.durationMin, 0)
  const remainingMinutes = items.filter((item) => !item.done).reduce((sum, item) => sum + item.durationMin, 0)
  const progress = items.length > 0 ? Math.round((done / items.length) * 100) : 0

  async function toggle(item: PlanItem) {
    if (savingId) return
    const next = !item.done
    setSavingId(item.id)
    try {
      await apiPost(`/api/astronauts/${ASTRONAUT_ID}/plan/${encodeURIComponent(item.id)}`, { done: next })
      plan.reload()
    } catch (err) {
      toast({ title: 'Step not saved', message: errorMessage(err), severity: 'attention' })
    } finally {
      setSavingId(null)
    }
  }

  return (
    <section className="page plan-page">
      <header className="page-head">
        <div className="page-head__title">
          <span className="eyebrow">Weekly plan</span>
          <h1>This week, gently</h1>
          <p className="muted">Exercise, nutrition, sleep and wellbeing — each with the reason behind it. You follow it; the ground team writes it.</p>
        </div>
        {plan.data && (
          <div className="chip"><CalendarCheck size={15} aria-hidden="true" /> Week of {formatDate(plan.data.weekOf)}</div>
        )}
      </header>

      {plan.error && <p className="auth-error" role="alert">{plan.error}</p>}
      {!plan.data && !plan.error && <span className="skeleton" style={{ height: 220 }} />}

      {plan.data && (
        <>
          <div className="panel plan-summary">
            <div className="plan-summary__ring" style={{ '--pct': progress } as CSSProperties}>
              <div className="plan-summary__ring-inner">
                <span className="numeric plan-summary__pct">{progress}%</span>
                <span className="faint tiny">done</span>
              </div>
            </div>
            <div className="plan-summary__copy">
              <h2 className="panel-title">{done} of {items.length} steps complete</h2>
              <p className="muted small">{done === items.length && items.length > 0
                ? 'Every step this week is done. Rest is part of the plan too.'
                : remainingMinutes > 0
                  ? `About ${remainingMinutes} active minutes left this week. ${totalMinutes} minutes in the full plan.`
                  : `${items.length - done} of ${items.length} steps left this week.`}</p>
              <div className="row row--wrap" style={{ marginTop: 12 }}>
                <span className="badge"><ShieldCheck size={12} aria-hidden="true" /> Delivered by the ground medical team</span>
                <span className="faint tiny">Tap a step to mark it done. The ground team sees the progress on the next sync.</span>
              </div>
            </div>
          </div>

          {plan.data.groundNote && (
            <div className="panel panel--glow plan-ground-note">
              <span className="eyebrow eyebrow--violet">Note from the ground team · {formatDate(plan.data.groundNote.ts)}</span>
              <p className="muted small" style={{ marginTop: 8 }}>{plan.data.groundNote.note}</p>
            </div>
          )}

          <div className="plan-grid">
            {grouped.map((group, groupIndex) => {
              const meta = CATEGORY_META[group.category]
              const Icon = meta.icon
              const groupDone = group.items.filter((item) => item.done).length
              return (
                <div className="panel plan-group stagger" key={group.category} style={{ '--i': groupIndex } as CSSProperties}>
                  <div className="plan-group__head">
                    <span className="plan-group__icon" aria-hidden="true"><Icon size={18} /></span>
                    <div>
                      <h2 className="panel-title">{meta.label}</h2>
                      <span className="faint tiny">{meta.blurb}</span>
                    </div>
                    <span className="badge">{groupDone}/{group.items.length}</span>
                  </div>
                  <ul className="plan-list">
                    {group.items.map((item) => (
                      <li className={`plan-item${item.done ? ' is-done' : ''}`} key={item.id}>
                        <button
                          type="button"
                          className="plan-item__toggle"
                          aria-pressed={item.done}
                          disabled={savingId === item.id}
                          onClick={() => void toggle(item)}
                          aria-label={`${item.done ? 'Mark not done' : 'Mark done'}: ${item.title}`}
                        >
                          <span className="plan-item__check" aria-hidden="true">
                            {item.done ? <CheckCircle2 size={18} /> : <Circle size={18} />}
                          </span>
                          <span className="plan-item__body">
                            <span className="row row--between row--wrap" style={{ gap: 8 }}>
                              <span className="strong small">{item.title}</span>
                              {item.durationMin > 0 && <span className="badge">{item.durationMin} min</span>}
                            </span>
                            <span className="muted tiny">{item.detail}</span>
                            <span className="plan-item__why"><strong>Why:</strong> {item.rationale}</span>
                          </span>
                          <span className="sr-only">{item.done ? 'Completed' : 'Not completed yet'}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )
            })}
          </div>

          <div className="panel panel--glow plan-footnote">
            <span className="eyebrow eyebrow--violet">A note on pressure</span>
            <p className="muted small" style={{ marginTop: 8 }}>A missed item is information, not a failure. Say so in the daily check-in and the plan is adjusted — that is how it is meant to work.</p>
            <div className="row row--wrap" style={{ marginTop: 14 }}>
              <Link to="/checkin" className="btn btn--calm">Open today’s check-in</Link>
              <Link to="/breathing" className="btn btn--ghost">Take a breathing break</Link>
            </div>
          </div>
        </>
      )}
    </section>
  )
}
