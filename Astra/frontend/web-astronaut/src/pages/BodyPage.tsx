import { useState } from 'react'
import type { CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Bone, Brain, ChevronRight, HeartPulse, Wind } from 'lucide-react'
import type { Indicator, Organ, OrganId } from '@contracts'
import { StatusBadge, useApi } from '@astra/shared'
import { ASTRONAUT_ID } from '../lib/astro'

const ORGAN_META: Record<OrganId, { icon: typeof HeartPulse; top: string; left: string; label: string }> = {
  brain: { icon: Brain, top: '8%', left: '50%', label: 'Brain & sleep' },
  heart: { icon: HeartPulse, top: '33%', left: 'calc(50% - 18px)', label: 'Heart' },
  lungs: { icon: Wind, top: '27%', left: 'calc(50% + 22px)', label: 'Lungs' },
  bones: { icon: Bone, top: '73%', left: 'calc(50% - 12px)', label: 'Bones & muscles' },
}

export function BodyPage() {
  const navigate = useNavigate()
  const [selected, setSelected] = useState<OrganId>('heart')
  const organs = useApi<Organ[]>(`/api/astronauts/${ASTRONAUT_ID}/organs`, { live: true, livePrefixes: ['indicator', 'rad'] })
  const indicators = useApi<Indicator[]>(`/api/astronauts/${ASTRONAUT_ID}/indicators`, { live: true, livePrefixes: ['indicator'] })

  const organ = organs.data?.find((item) => item.id === selected) ?? null
  const related = (indicators.data ?? []).filter((indicator) => organ?.indicatorKeys.includes(indicator.key))

  return (
    <section className="page">
      <header className="page-head">
        <div className="page-head__title">
          <span className="eyebrow">Your body in microgravity</span>
          <h1>Your body model</h1>
          <p className="muted">Four systems carry most of the spaceflight risk. Tap one to see what is happening and what to do today.</p>
        </div>
      </header>

      <div className="split body-split">
        <div className="panel organ-panel">
          <div className="organ-map">
            <div className="organ-map__glow" aria-hidden="true" />
            <svg viewBox="0 0 220 420" className="body-figure" role="img" aria-label="Holographic human body with four glowing system markers">
              <defs>
                <linearGradient id="body-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#cfeeff" stopOpacity="0.78" />
                  <stop offset="35%" stopColor="#7fd3ff" stopOpacity="0.62" />
                  <stop offset="68%" stopColor="#3f95ff" stopOpacity="0.46" />
                  <stop offset="100%" stopColor="#1d4fb8" stopOpacity="0.3" />
                </linearGradient>
                <linearGradient id="body-sheen" x1="0" y1="0" x2="1" y2="0.2">
                  <stop offset="0%" stopColor="#ffffff" stopOpacity="0.08" />
                  <stop offset="34%" stopColor="#ffffff" stopOpacity="0.28" />
                  <stop offset="55%" stopColor="#ffffff" stopOpacity="0" />
                  <stop offset="100%" stopColor="#02132e" stopOpacity="0.32" />
                </linearGradient>
                <radialGradient id="body-volume" cx="40%" cy="28%" r="78%">
                  <stop offset="0%" stopColor="#ffffff" stopOpacity="0.34" />
                  <stop offset="42%" stopColor="#9fe0ff" stopOpacity="0.14" />
                  <stop offset="100%" stopColor="#2c6fe0" stopOpacity="0" />
                </radialGradient>
                <radialGradient id="body-beam" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#9fe8ff" stopOpacity="0.32" />
                  <stop offset="55%" stopColor="#5cc8ff" stopOpacity="0.13" />
                  <stop offset="100%" stopColor="#3f7bff" stopOpacity="0" />
                </radialGradient>
                <radialGradient id="body-floor" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#8fe6ff" stopOpacity="0.5" />
                  <stop offset="100%" stopColor="#3f7bff" stopOpacity="0" />
                </radialGradient>
                <linearGradient id="body-edge" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#e6faff" stopOpacity="0.98" />
                  <stop offset="50%" stopColor="#8fe4ff" stopOpacity="0.78" />
                  <stop offset="100%" stopColor="#3f7bff" stopOpacity="0.38" />
                </linearGradient>
                <filter id="body-bloom" x="-30%" y="-20%" width="160%" height="140%">
                  <feGaussianBlur stdDeviation="3.6" />
                </filter>
                <filter id="body-soft" x="-60%" y="-60%" width="220%" height="220%">
                  <feGaussianBlur stdDeviation="7" />
                </filter>
                <path id="body-path" d="M 110 14 C 99 14 90 23 90 37 C 90 50 97 59 104 63 L 104 78 C 94 82 70 85 54 92 C 47 103 42 138 38 170 C 35 194 32 222 30 250 C 29 266 28 278 29 290 C 30 300 36 307 42 304 C 46 299 47 291 45 283 C 43 269 45 247 47 225 C 49 197 52 167 54 145 C 55 133 57 126 60 121 C 63 127 67 137 70 150 C 73 162 80 174 83 184 C 83 196 79 212 76 226 C 73 248 75 280 77 308 C 79 336 81 362 83 382 C 84 390 84 396 85 400 C 85 405 92 409 99 407 C 102 406 103 402 101 399 C 100 395 100 392 100 388 C 96 362 95 338 96 312 C 99 288 102 262 105 246 L 110 236 L 115 246 C 118 262 121 288 124 312 C 125 338 124 362 120 388 C 120 392 120 395 119 399 C 117 402 118 406 121 407 C 128 409 135 405 135 400 C 136 396 136 390 137 382 C 139 362 141 336 143 308 C 145 280 147 248 144 226 C 141 212 137 196 137 184 C 140 174 147 162 150 150 C 153 137 157 127 160 121 C 163 126 165 133 166 145 C 168 167 171 197 173 225 C 175 247 177 269 175 283 C 173 291 174 299 178 304 C 184 307 190 300 191 290 C 192 278 191 266 190 250 C 188 222 185 194 182 170 C 178 138 173 103 166 92 C 150 85 126 82 116 78 L 116 63 C 123 59 130 50 130 37 C 130 23 121 14 110 14 Z" />
                <clipPath id="body-clip"><use href="#body-path" /></clipPath>
              </defs>
              <ellipse className="body-figure__floor" cx="110" cy="411" rx="52" ry="7" />
              <ellipse className="body-figure__beam" cx="110" cy="200" rx="26" ry="170" />
              <use className="body-figure__shell" href="#body-path" />
              <g clipPath="url(#body-clip)">
                <rect x="0" y="0" width="220" height="420" fill="url(#body-sheen)" />
                <use href="#body-path" fill="none" stroke="#03132f" strokeWidth="9" opacity="0.3" />
                <use href="#body-path" fill="none" stroke="#0a2a66" strokeWidth="4" opacity="0.3" />
                <ellipse cx="90" cy="160" rx="34" ry="120" fill="#ffffff" opacity="0.1" filter="url(#body-soft)" />
                <ellipse cx="96" cy="150" rx="80" ry="150" fill="url(#body-volume)" />
                <ellipse cx="79" cy="128" rx="17" ry="12" fill="#ffffff" opacity="0.2" filter="url(#body-soft)" />
                <ellipse cx="141" cy="130" rx="17" ry="12" fill="#ffffff" opacity="0.14" filter="url(#body-soft)" />
                <ellipse cx="96" cy="196" rx="12" ry="26" fill="#0a1c46" opacity="0.28" filter="url(#body-soft)" />
                <ellipse cx="126" cy="300" rx="12" ry="40" fill="#ffffff" opacity="0.1" filter="url(#body-soft)" />
                <ellipse cx="110" cy="38" rx="12" ry="18" fill="url(#body-volume)" opacity="0.7" />
                <path className="body-figure__details" d="M85 96 C93 104 102 105 108 99" />
                <path className="body-figure__details" d="M135 96 C127 104 118 105 112 99" />
                <path className="body-figure__details" d="M80 118 C86 133 100 139 108 130" />
                <path className="body-figure__details" d="M140 118 C134 133 120 139 112 130" />
                <path className="body-figure__details" d="M96 156 C102 159 118 159 124 156" />
                <path className="body-figure__faint" d="M97 171 C103 174 117 174 123 171" />
                <path className="body-figure__faint" d="M99 186 C105 189 115 189 121 186" />
                <path className="body-figure__faint" d="M110 104 L110 210" />
                <path className="body-figure__faint" d="M83 140 C87 152 87 164 85 174" />
                <path className="body-figure__faint" d="M137 140 C133 152 133 164 135 174" />
                <path className="body-figure__faint" d="M80 206 C90 214 130 214 140 206" />
                <path className="body-figure__faint" d="M94 296 C102 301 118 301 126 296" />
                <path className="body-figure__faint" d="M32 260 C35 270 37 278 36 286" />
                <path className="body-figure__faint" d="M188 260 C185 270 183 278 184 286" />
                <path className="body-figure__faint" d="M87 403 C93 406 99 406 103 402" />
                <path className="body-figure__faint" d="M133 403 C127 406 121 406 117 402" />
              </g>
              <use className="body-figure__glow" href="#body-path" />
              <use className="body-figure__edge" href="#body-path" />
            </svg>

            {(organs.data ?? []).map((item) => {
              const meta = ORGAN_META[item.id]
              const Icon = meta.icon
              const active = item.id === selected
              return (
                <button key={item.id} type="button" className="organ-hotspot" data-status={item.status} data-active={active} aria-pressed={active} aria-label={`${meta.label}: ${item.status}. Show details`} title={meta.label} onClick={() => setSelected(item.id)} style={{ top: meta.top, left: meta.left } as CSSProperties}>
                  <Icon size={17} aria-hidden="true" />
                  <span className="organ-hotspot__label">{meta.label}</span>
                </button>
              )
            })}
          </div>
          <p className="faint tiny organ-panel__hint">Markers glow with the current status. Hover or focus one to read its name.</p>
        </div>

        <div className="stack">
          <div className="panel organ-detail" data-status={organ?.status}>
            {!organ && <span className="skeleton" style={{ height: 220 }} />}
            {organ && (
              <div className="organ-detail__body" key={organ.id}>
                <div className="panel-head">
                  <div>
                    <span className="eyebrow">System detail</span>
                    <h2 className="organ-detail__title">{organ.name}</h2>
                  </div>
                  <StatusBadge status={organ.status} size="lg" label={organ.name} />
                </div>
                <p className="muted small organ-detail__function">{organ.function}</p>

                <div className="organ-detail__block">
                  <span className="field__label">What microgravity is doing</span>
                  <div className="chip-row">
                    {organ.hazards.map((hazard) => (
                      <span className="chip" key={hazard}>{hazard}</span>
                    ))}
                  </div>
                </div>

                <div className="organ-detail__block">
                  <span className="field__label">What to do now</span>
                  <ol className="organ-steps">
                    {organ.whatToDo.map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ol>
                </div>
              </div>
            )}
          </div>

          <div className="panel">
            <div className="panel-head">
              <h3 className="panel-title">Linked measurements</h3>
            </div>
            {related.length === 0 && <p className="faint small">No linked reading for this system right now.</p>}
            <div className="linked-list">
              {related.map((indicator) => (
                <button type="button" key={indicator.key} className="linked-row" data-status={indicator.status} onClick={() => navigate(`/indicators/${indicator.key}`)}>
                  <span className="linked-row__name">{indicator.label}</span>
                  <span className="linked-row__value numeric">{indicator.value}{indicator.secondary != null ? `/${indicator.secondary}` : ''} <span className="faint tiny">{indicator.unit}</span></span>
                  <StatusBadge status={indicator.status} label={indicator.label} />
                  <ChevronRight size={16} aria-hidden="true" />
                </button>
              ))}
            </div>
            <button type="button" className="btn btn--ghost" style={{ marginTop: 12 }} onClick={() => navigate('/radiation')}>
              Open radiation & shelter <ArrowRight size={14} aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
