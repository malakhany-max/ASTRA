import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '@astra/shared/styles'
import { USE_MOCK, installFlareButtons } from '@astra/shared'
import { App } from './App'
import './app.css'

async function bootstrap() {
  installFlareButtons()
  if (USE_MOCK) {
    const { startMockApi } = await import('@astra/shared/mock')
    await startMockApi()
  }

  const container = document.getElementById('root')
  if (!container) throw new Error('Root container is missing')

  createRoot(container).render(
    <StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </StrictMode>,
  )
}

void bootstrap()
