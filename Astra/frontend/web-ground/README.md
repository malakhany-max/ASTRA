# Astra — Ground console (`web-ground`)

The local mission-control demo app. It covers the crew
overview, per-astronaut detail, mission history, the alert queue, ground commands and backup/link
state.

## Run

From the repository root:

```bash
npm run dev:ground   # http://localhost:5174
```

The packaged local app opens directly to the crew overview with no sign-in screen. It uses the
bundled simulated-data fixture and exposes the demo command controls. The Ground Station backend
retains its RBAC-protected login API for separately configured live deployments.

## Pages

| Route | What it shows |
| --- | --- |
| `/` | Crew cards sorted attention-first with four mission KPIs |
| `/crew/:id` | Profile, indicators with trend chart, open alerts, radiation, mission record, command composer |
| `/history` | Current and past missions with search, astronaut and vehicle filters |
| `/alerts` | Priority queue with priority/astronaut/state filters and acknowledgment |
| `/commands` | Command log with audit trail and a composer (hidden for viewers) |
| `/backup` | Backup batches, link state and security checks |

Commands move `pending → delivered` only when the crew device acknowledges them. The audit trail
keeps author, time and every state change.

## Mock API vs real hub

```bash
# .env.local — empty (or "mock") keeps the bundled fixtures
VITE_API_BASE=https://hub.internal
```

Requests are relative (`/api/...`); live updates switch from the in-browser event bus to
`GET /ws/events`. Changing the base requires no code changes.

## Build and offline check

```bash
npm run build:ground
npm run preview -w web-ground -- --port 4174   # http://localhost:4174
```

## Tests

```bash
npm test                                # shared Vitest + RTL suite
npx playwright test --project=ground    # one smoke test against the production preview
```

## Security boundary

Do **not** put signing or private keys in the browser. The browser only displays data and sends user
input; verification, signing and authorization are enforced by the hub.
