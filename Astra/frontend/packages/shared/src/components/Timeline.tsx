import type { ReactNode } from 'react'
import type { HealthStatus } from '@contracts'

export interface TimelineItem {
  id: string
  time: string
  title: string
  text?: string
  status?: HealthStatus
  icon?: ReactNode
}

export function Timeline({ items }: { items: TimelineItem[] }) {
  return (
    <ol className="timeline" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
      {items.map((item) => (
        <li className="timeline__item" key={item.id} data-status={item.status ?? 'normal'}>
          <span className="timeline__dot" aria-hidden="true">
            {item.icon ?? <span style={{ width: 7, height: 7, borderRadius: 99, background: 'currentColor' }} />}
          </span>
          <div className="timeline__body">
            <span className="timeline__time">{item.time}</span>
            <span className="timeline__title">{item.title}</span>
            {item.text && <span className="timeline__text">{item.text}</span>}
          </div>
        </li>
      ))}
    </ol>
  )
}
