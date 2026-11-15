import { lazy, Suspense } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import {
  CalendarCheck,
  LayoutDashboard,
  MessagesSquare,
  PersonStanding,
  Radiation,
  Settings,
  SmilePlus,
  Timer,
  Wind,
} from 'lucide-react'
import type { Astronaut, LinkState, SecurityState } from '@contracts'
import { ASTRA_LOGO, LinkBadge, ShieldIcon, Starfield, ToastProvider, useApi, useDocumentTitle } from '@astra/shared'
import { HomePage } from './pages/HomePage'

const BodyPage = lazy(() => import('./pages/BodyPage').then((page) => ({ default: page.BodyPage })))
const IndicatorPage = lazy(() => import('./pages/IndicatorPage').then((page) => ({ default: page.IndicatorPage })))
const RadiationPage = lazy(() => import('./pages/RadiationPage').then((page) => ({ default: page.RadiationPage })))
const ExposurePage = lazy(() => import('./pages/ExposurePage').then((page) => ({ default: page.ExposurePage })))
const CheckinPage = lazy(() => import('./pages/CheckinPage').then((page) => ({ default: page.CheckinPage })))
const CompanionPage = lazy(() => import('./pages/CompanionPage').then((page) => ({ default: page.CompanionPage })))
const BreathingPage = lazy(() => import('./pages/BreathingPage').then((page) => ({ default: page.BreathingPage })))
const PlanPage = lazy(() => import('./pages/PlanPage').then((page) => ({ default: page.PlanPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((page) => ({ default: page.SettingsPage })))

interface PageDef {
  path: string
  label: string
  icon: LucideIcon
  end?: boolean
}

const PAGES: PageDef[] = [
  { path: '/', label: 'Home', icon: LayoutDashboard, end: true },
  { path: '/body', label: 'Body', icon: PersonStanding },
  { path: '/checkin', label: 'Check-in', icon: SmilePlus },
  { path: '/companion', label: 'Companion', icon: MessagesSquare },
  { path: '/breathing', label: 'Breathing', icon: Wind },
  { path: '/radiation', label: 'Radiation', icon: Radiation },
  { path: '/exposure', label: 'Exposure', icon: Timer },
  { path: '/plan', label: 'Plan', icon: CalendarCheck },
  { path: '/settings', label: 'Settings', icon: Settings },
]

function AppShell() {
  useDocumentTitle('Astra · Astronaut')
  const location = useLocation()

  const profile = useApi<Astronaut>('/api/astronauts/ast-zain', { live: true })
  const link = useApi<LinkState>('/api/link/state', { live: true })
  const security = useApi<SecurityState>('/api/security/state', { live: true })

  return (
    <div className="shell">
      <Starfield />
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <aside className="rail">
        <div className="rail__brand">
          <span className="brand__mark">
            <img className="brand__logo" src={ASTRA_LOGO} alt="" aria-hidden="true" />
            <span className="brand__orbit" aria-hidden="true" />
          </span>
          <div>
            <div className="brand__name">Astra</div>
            <div className="brand__sub">Astronaut</div>
          </div>
        </div>

        <nav className="nav" aria-label="Astronaut sections">
          <span className="nav__label">Health first</span>
          {PAGES.map((page) => (
            <NavLink
              key={page.path}
              to={page.path}
              end={page.end}
              className={({ isActive }) => `nav-item${isActive ? ' is-active' : ''}`}
            >
              <page.icon size={18} aria-hidden="true" />
              {page.label}
            </NavLink>
          ))}
        </nav>

        <div className="rail__footer">
          <div className="small strong">Zain Hassan</div>
          <div className="tiny faint">Mission Specialist · Gateway</div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar__id">
            <span className="avatar">ZH</span>
            <div className="astro-topbar__mission">
              <span className="topbar__name">{profile.data?.name ?? 'Zain Hassan'}</span>
              <span className="topbar__meta">
                {profile.data
                  ? `Mission day ${profile.data.missionDay} · ${profile.data.currentMissionName}`
                  : 'Loading mission day'}
              </span>
            </div>
          </div>

          <span className="topbar__spacer" />

          {link.data ? (
            <LinkBadge
              state={link.data.state}
              lastSyncAt={link.data.lastSyncAt}
              variant="astronaut"
            />
          ) : (
            <span className="skeleton" style={{ width: 140, height: 30, borderRadius: 99 }} />
          )}

          {security.data ? (
            <ShieldIcon
              level={security.data.level}
              checks={security.data.checks}
              headline={security.data.headline}
              lastEventAt={security.data.lastEventAt}
            />
          ) : (
            <span className="skeleton" style={{ width: 40, height: 40, borderRadius: '50%' }} />
          )}
        </header>

        <main id="main" className="main-content">
          <div className="route-enter" key={location.pathname}>
            <Suspense fallback={<span className="skeleton" style={{ height: 320, display: 'block' }} />}>
              <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/body" element={<BodyPage />} />
              <Route path="/radiation" element={<RadiationPage />} />
              <Route path="/exposure" element={<ExposurePage />} />
              <Route path="/checkin" element={<CheckinPage />} />
              <Route path="/companion" element={<CompanionPage />} />
              <Route path="/breathing" element={<BreathingPage />} />
              <Route path="/plan" element={<PlanPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/indicators/:key" element={<IndicatorPage />} />
              <Route path="*" element={<HomePage />} />
            </Routes>
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  )
}

export function App() {
  return (
    <ToastProvider>
      <AppShell />
    </ToastProvider>
  )
}
