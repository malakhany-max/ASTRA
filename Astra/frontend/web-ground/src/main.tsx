import { Component, StrictMode, type ErrorInfo, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '@astra/shared/styles'
import { USE_MOCK, installFlareButtons } from '@astra/shared'
import { App } from './App'
import './app.css'

async function bootstrap() {
  installFlareButtons()
  const container = document.getElementById('root')
  if (!container) throw new Error('Root container is missing')

  if (USE_MOCK) {
    try {
      const { startMockApi } = await import('@astra/shared/mock')
      await startMockApi()
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      const safeDetail = detail.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
      container.innerHTML = `<main class="fatal-error"><h1>Ground Station could not start</h1><p>${safeDetail}</p><p>Close ASTRA and reopen GroundStation.exe. If it continues, check the launcher log in %LOCALAPPDATA%\\ASTRA Companion.</p></main>`
      return
    }
  }

  createRoot(container).render(
    <StrictMode>
      <BrowserRouter>
        <GroundErrorBoundary>
          <App />
        </GroundErrorBoundary>
      </BrowserRouter>
    </StrictMode>,
  )
}

class GroundErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, _info: ErrorInfo) {
    console.error('Ground Station render failed', error)
  }

  render() {
    if (this.state.error) {
      return <main className="fatal-error" role="alert">
        <h1>Ground Station hit a display error</h1>
        <p>{this.state.error.message}</p>
        <p>Close ASTRA and reopen GroundStation.exe. If it continues, check the launcher log in %LOCALAPPDATA%\ASTRA Companion.</p>
      </main>
    }
    return this.props.children
  }
}

void bootstrap().catch((error: unknown) => {
  const root = document.getElementById('root')
  if (!root) return
  const detail = error instanceof Error ? error.message : String(error)
  const message = document.createElement('p')
  message.textContent = detail
  const panel = document.createElement('main')
  panel.className = 'fatal-error'
  panel.innerHTML = '<h1>Ground Station could not start</h1>'
  panel.append(message)
  root.replaceChildren(panel)
})
