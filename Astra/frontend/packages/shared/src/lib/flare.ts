const TARGETS = 'button, a.btn, a.nav-item, [role="button"]'

export function installFlareButtons() {
  if (typeof window === 'undefined') return
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

  let frame = 0
  let move: { x: number; y: number; target: EventTarget | null } | null = null

  const paint = () => {
    frame = 0
    if (!move) return
    const { x, y, target } = move
    move = null
    const button = (target instanceof Element ? target.closest<HTMLElement>(TARGETS) : null)
    if (!button || button.matches(':disabled')) return
    const rect = button.getBoundingClientRect()
    button.style.setProperty('--flare-x', `${x - rect.left}px`)
    button.style.setProperty('--flare-y', `${y - rect.top}px`)
  }

  const track = (event: PointerEvent) => {
    move = { x: event.clientX, y: event.clientY, target: event.target }
    if (!frame) frame = requestAnimationFrame(paint)
  }

  document.addEventListener('pointermove', track, { passive: true })
  document.addEventListener('pointerover', track, { passive: true })
}
