import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

export const worker = setupWorker(...handlers)

export async function startMockApi(): Promise<void> {
  if (typeof window === 'undefined') return
  if (window.location.protocol === 'file:') return
  try {
    await worker.start({
      serviceWorker: { url: '/mockServiceWorker.js' },
      onUnhandledRequest: 'bypass',
    })
  } catch (error) {
    console.warn(
      'Astra mock API could not start. Run `npx msw init public --save` inside the app.',
      error,
    )
  }
}
