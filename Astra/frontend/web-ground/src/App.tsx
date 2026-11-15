import { lazy, Suspense } from 'react'
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import {
  Bell,
  DatabaseBackup,
  History,
  LayoutDashboard,
  TerminalSquare,
} from 'lucide-react'
import {
  ASTRA_LOGO,
  LinkBadge,
  ShieldIcon,
  Starfield,
  ToastProvider,
  useApi,
  useDocumentTitle,
} from '@astra/shared'
import type { AuthUser, LinkState, SecurityState } from '@contracts'
import { CrewPage } from './pages/CrewPage'

const AstronautDetailPage = lazy(() => import('./pages/AstronautDetailPage').then((page) => ({ default: page.AstronautDetailPage })))
const HistoryPage = lazy(() => import('./pages/HistoryPage').then((page) => ({ default: page.HistoryPage })))
const AlertsPage = lazy(() => import('./pages/AlertsPage').then((page) => ({ default: page.AlertsPage })))
const CommandsPage = lazy(() => import('./pages/CommandsPage').then((page) => ({ default: page.CommandsPage })))
const BackupPage = lazy(() => import('./pages/BackupPage').then((page) => ({ default: page.BackupPage })))

const OPERATOR: AuthUser = {
  id: 'local-ground',
  name: 'Ground Station',
  role: 'flight_surgeon',
  initials: 'GS',
}

interface PageDef {
  path: string
  label: string
  icon: LucideIcon
  end?: boolean
}

const PAGES: PageDef[] = [
  { path: '/', label: 'Crew', icon: LayoutDashboard, end: true },
  { path: '/history', label: 'History', icon: History },
  { path: '/alerts', label: 'Alerts', icon: Bell },
  { path: '/commands', label: 'Commands', icon: TerminalSquare },
  { path: '/backup', label: 'Backup & link', icon: DatabaseBackup },
]

function GroundConsole({ operator }: { operator: AuthUser }) {
  const location = useLocation()
  const link = useApi<LinkState>('/api/link/state', { live: true })
  const security = useApi<SecurityState>('/api/security/state', { live: true })
  const pages = PAGES.filter((page) => page.path !== '/commands' || operator.role === 'flight_surgeon')

  return (
    <div className="shell">
      <Starfield />
      <a className="skip-link" href="#main">Skip to content</a>

      <aside className="rail">
        <div className="rail__brand">
          <span className="brand__mark">
            <img className="brand__logo" src={ASTRA_LOGO} alt="" aria-hidden="true" />
            <span className="brand__orbit" aria-hidden="true" />
          </span>
          <div>
            <div className="brand__name">Astra</div>
            <div className="brand__sub">Ground</div>
          </div>
        </div>

        <nav className="nav" aria-label="Ground sections">
          <span className="nav__label">Mission control</span>
          {pages.map((page) => {
            const Icon = page.icon
            return (
              <NavLink key={page.path} to={page.path} end={page.end} className={({ isActive }) => `nav-item${isActive ? ' is-active' : ''}`}>
                <Icon size={18} aria-hidden="true" />
                {page.label}
              </NavLink>
            )
          })}
        </nav>

        <div className="rail__footer">
          <div>
            <div className="small strong">{operator.name}</div>
            <div className="tiny faint">Local demo access</div>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar__id">
              <span className="avatar">{operator.initials}</span>
            <div>
              <span className="topbar__name">Ground Station</span>
              <div className="topbar__meta">Local demo · simulated data</div>
            </div>
          </div>

          <span className="topbar__spacer" />

          {link.data ? (
            <LinkBadge state={link.data.state} lastSyncAt={link.data.lastSyncAt} variant="ground" />
          ) : (
            <span className="skeleton" style={{ width: 150, height: 30, borderRadius: 99 }} />
          )}

          {security.data ? (
            <ShieldIcon level={security.data.level} checks={security.data.checks} headline={security.data.headline} lastEventAt={security.data.lastEventAt} />
          ) : (
            <span className="skeleton" style={{ width: 40, height: 40, borderRadius: '50%' }} />
          )}
        </header>

        <main id="main" className="main-content">
          <div className="route-enter" key={location.pathname}>
            <Suspense fallback={<span className="skeleton" style={{ height: 320, display: 'block' }} />}>
              <Routes>
              <Route path="/" element={<CrewPage />} />
              <Route path="/crew/:id" element={<AstronautDetailPage role={operator.role} />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/alerts" element={<AlertsPage role={operator.role} />} />
              {operator.role === 'flight_surgeon' && <Route path="/commands" element={<CommandsPage />} />}
              <Route path="/backup" element={<BackupPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  )
}

export function App() {
  useDocumentTitle('Astra · Ground')
  return (
    <ToastProvider>
      <GroundConsole operator={OPERATOR} />
    </ToastProvider>
  )
}
