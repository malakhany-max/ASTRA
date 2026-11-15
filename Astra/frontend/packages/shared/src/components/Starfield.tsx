import { useMemo } from 'react'

function mulberry32(seed: number) {
  let a = seed
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function stars(count: number, seed: number, maxSize: number) {
  const random = mulberry32(seed)
  return Array.from({ length: count }, (_, index) => ({
    id: index,
    left: random() * 100,
    top: random() * 100,
    size: 0.8 + random() * maxSize,
    opacity: 0.35 + random() * 0.6,
    delay: random() * 7,
    duration: 3 + random() * 6,
  }))
}

export function Starfield() {
  const layers = useMemo(
    () => [
      { key: 'a', stars: stars(70, 11, 1.3) },
      { key: 'b', stars: stars(34, 47, 1.9) },
    ],
    [],
  )

  return (
    <div className="app-bg" aria-hidden="true">
      <div className="aurora aurora--a" />
      <div className="aurora aurora--b" />
      <div className="starfield">
        {layers.map((layer) => (
          <div className="starfield__layer" key={layer.key}>
            {layer.stars.map((star) => (
              <span
                key={star.id}
                className="starfield__star"
                style={{
                  left: `${star.left}%`,
                  top: `${star.top}%`,
                  width: star.size,
                  height: star.size,
                  opacity: star.opacity,
                  animationDelay: `${star.delay}s`,
                  animationDuration: `${star.duration}s`,
                }}
              />
            ))}
          </div>
        ))}
        <span className="starfield__shoot" />
        <span className="starfield__shoot starfield__shoot--b" />
      </div>
    </div>
  )
}
