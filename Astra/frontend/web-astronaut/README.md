# Astra — Astronaut app (`web-astronaut`)

The crew-facing web app. It shows Zain Hassan's smartwatch measurements, the body model, radiation
and exposure state, daily check-ins, the AI companion, breathing exercises, the ground-approved plan
and privacy settings.

## Run

From the repository root:

```bash
npm run dev:astronaut   # http://localhost:5173
```

The app boots the bundled mock hub (MSW) automatically, so it works with no backend and no network.

## Mock API vs real hub

All data goes through `apiGet` / `apiPost` / `apiPut` in `@astra/shared`. The switch is one variable:

```bash
# .env.local — leave empty (or "mock") to keep the bundled fixtures
VITE_API_BASE=https://hub.internal
```

With a real base, live updates use `GET /ws/events` instead of the in-browser event bus. No code
changes are needed; every request is relative (`/api/...`).

## Pages

| Route | What it shows |
| --- | --- |
| `/` | Greeting, indicators sorted by risk, schedule, companion prompt |
| `/body` | Organ map with four systems and linked measurements |
| `/indicators/:key` | Trend chart, personal baseline, what it means, what to do |
| `/radiation` | Dose gauge, mission budget, protection steps, shelter route |
| `/exposure` | Post-exposure monitoring window and timeline |
| `/checkin` | Mood, energy, dizziness, sleep scales and symptoms |
| `/companion` | Chat transcript, action cards, voice input/output |
| `/breathing` | Animated breathing orb with 1/3/5 minute sessions |
| `/plan` | Ground-delivered plan grouped by category |
| `/settings` | Preferences, consent tiers, security checks, backup state |

## Build and offline check

```bash
npm run build:astronaut
npm run preview -w web-astronaut -- --port 4173   # http://localhost:4173
```

Everything is bundled locally (@fontsource fonts, lucide-react icons, Recharts, MSW). The built app
never calls a CDN.

## Tests

```bash
npm test                                   # shared Vitest + RTL suite
npx playwright test --project=astronaut    # one smoke test against the production preview
```

## Security boundary

Do **not** put signing or private keys in the browser. The browser only displays data and sends user
input; signatures, integrity checks and the companion model live on the hub.
