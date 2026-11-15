# ASTRA Companion — project documentation

ASTRA is a NASA Space Apps Challenge prototype for astronaut health support on long-duration missions. It is **decision support, not diagnosis**. All values in this demonstration are **simulated data**. The Earth-side interface is the **Ground Station**.

## Project overview

ASTRA combines signed wearable and dosimeter readings, personal-baseline trend analysis, calm check-ins, and store-and-forward communication. The Astronaut App remains useful in Autonomous Mode when the Earth link is unavailable. The Ground Station shows received data with its last update time.

Radiation is measured directly by dosimeters. Health changes and later symptoms are described as co-occurring, not as caused by radiation. Thresholds and shelter guidance remain demo content pending approved mission references.

## Services and apps

| Component | Path | Local port | Role |
|---|---|---:|---|
| Hub | `backend/hub/` | 8000 | Ingest, verify, store, evaluate and publish local events |
| Ground Station backend | `backend/ground-backend/` | 8100 | RBAC, crew history, alerts, commands and encrypted backup |
| Companion | `ai-companion/companion/` | 8200 | Deterministic dialogue, check-in and optional local voice |
| Link Simulator | `backend/link/` | 8300 | Delay, disconnect and store-and-forward traffic |
| Astronaut App | `frontend/web-astronaut/` | 5173 | Crew health and companion interface |
| Ground Station Dashboard | `frontend/web-ground/` | 5174 | Crew, alerts, history and command interface |

Start backend services with `python -m backend.simulators.run_demo`. Start web workspaces with `npm run dev:astronaut` or `npm run dev:ground` after `npm ci`. To use live local APIs, copy each app's `.env.example` to `.env.local`; otherwise clients default to MSW fixtures. Provision the Ground admin account once with `backend/ground-backend/seed_users.py` and the `ASTRA_GROUND_ADMIN_USER` / `ASTRA_GROUND_ADMIN_PASSWORD` environment variables.

## Companion behavior

The service exposes deterministic check-in, alert-explanation, breathing, radiation follow-up, STT and TTS routes. Crisis escalation is rule-based; it does not involve an LLM. Breathing has no holds, and dizziness or an urgent status switches to a non-paced grounding alternative. Raw audio is processed in memory and is never stored or logged. Vosk and Piper models must be staged locally; the service does not fetch them.

Run its tests with `python -m unittest discover -s ai-companion/companion/tests -t ai-companion -v`.

## Evaluation and demo

Run `python backend/engine/evaluation/run_scenarios.py` to produce the synthetic scenario CSV and Markdown under `backend/engine/evaluation/results/`. The Zain, Day 90 demo run-of-show is in `docs/demo-script.md`.

## Current integration limits

- The web clients map their UI view models to the Hub, Ground, Companion, and Link service routes. Automated browser tests use fixture mode; a live pass on the packaged apps was verified on 2026-11-15, and backend endpoint and RBAC tests cover the real service wiring.
- Verified on 2026-11-15: 96 Python and Companion tests, 21 shared UI tests, typechecking, both production builds, and both Playwright smoke tests pass. The packaged live apps were also exercised end to end: check-in and companion notes reach the Ground Station, and Arabic companion replies work through the launcher proxy.
- `backend/contracts/openapi.yaml` and `backend/ground-backend/openapi.yaml` are generated with `python backend/ground-backend/generate_openapi.py`; review against shared JSON schemas whenever wire contracts change.
- Local voice models and approved NASA/medical shelter wording are not included. This prototype does not claim clinical or mission validation.
