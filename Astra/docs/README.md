# ASTRA Companion

ASTRA is an offline-first NASA Space Apps Challenge prototype for astronaut health monitoring and supportive check-ins during long-duration missions. It provides **decision support, not diagnosis**. All crew measurements and scenarios in this prototype are **simulated data**. The Earth-side interface is the **Ground Station**.

## System pieces

- `backend/hub/`, `backend/engine/`, `backend/simulators/`, and `backend/ground-backend/` implement local ingestion, deterministic trend analysis, synthetic devices, and the Ground Station API.
- `security/`, `backend/link/`, and `backend/attack_sim/` verify signed data, queue messages, simulate outages, and exercise attack scenarios.
- `ai-companion/companion/` provides local deterministic dialogue and optional Vosk/Piper adapters. The service does not save raw audio.
- `frontend/web-astronaut/` and `frontend/web-ground/` are the crew app and Ground Station dashboard.

All service ports come from `backend/config/ports.yaml`: Hub 8000, Ground Station 8100, Companion 8200, Link Simulator 8300, and web apps 5173–5174. Services bind to loopback.

## Start the backend services

From the repository root:

```powershell
python -m backend.simulators.run_demo
```

The services expose local Swagger UI at `/docs`. Stage the pinned dependencies and any voice models locally before use; runtime downloads are not used. If Vosk or Piper assets are unavailable, voice routes report that local capability is unavailable while text-based companion flows remain available. The crew app checks `/companion/stt/status` first: with a staged model it records and transcribes locally, otherwise it uses the browser's speech recognition (Chrome may process that audio online) and tells the crew member when neither path can write the message.

## Start the web apps

Install the exact dependencies from the checked-in `package-lock.json` with `npm ci`, then run:

```powershell
npm run dev:astronaut
npm run dev:ground
```

The default `VITE_API_BASE` is empty and selects the bundled MSW fixtures. The packaged Ground Station demo opens without a sign-in screen. For separately configured live services, copy the relevant app `.env.example` to `.env.local` before starting the Vite app; Ground Station login and command history use port 8100, crew/status/scenario APIs use the Hub on port 8000, and Companion and Link use ports 8200 and 8300. The live Ground Station backend keeps RBAC authentication enabled.

## Build the desktop apps

Install PyInstaller once, then run the build script from the repository root:

```powershell
.\.venv\Scripts\pip.exe install pyinstaller
.\build-exe.ps1
```

It produces `release\Astronaut.exe` and `release\GroundStation.exe`. Start `Astronaut.exe` first: it launches the local services (8000/8100/8200/8300) and its app window. `GroundStation.exe` reuses those services, so commands from the station reach the crew app and crew updates reach the station. Microsoft Edge must be installed. Set `ASTRA_BUILD_WORK` and `ASTRA_BUILD_DIST` to a directory on another drive when the system drive is low on space.

## Verify

```powershell
.venv\Scripts\python.exe -m pytest security\tests backend\link\tests backend\attack_sim\tests backend\engine\tests backend\hub\tests backend\ground-backend\tests backend\simulators\tests -q
.venv\Scripts\python.exe -m unittest discover -s ai-companion\companion\tests -t ai-companion -v
python backend\engine\evaluation\run_scenarios.py
npm test
npm run typecheck
npm run build
npm run e2e
```

Verified in the current workspace: 96 Python and Companion tests pass; the synthetic scenario evaluation completes; 21 shared UI tests pass; TypeScript typechecking and both production builds pass; all Playwright smoke tests pass. Pages and charts load on demand so the first screen stays small.

## Safety and limits

- The engine and companion present trends as decision support and do not diagnose.
- Radiation is read from dosimeters. Later symptoms or health changes are described as co-occurring, not caused by radiation.
- Threshold values are demo-only until reviewed against approved mission references.
- Shelter protocol text remains a placeholder until approved source wording is supplied.
- Local STT/TTS model files are optional and are never fetched by the service.
- `backend/contracts/openapi.yaml` and `backend/ground-backend/openapi.yaml` are generated from the four FastAPI services by `python backend/ground-backend/generate_openapi.py`. The team should review route and payload parity when backend contracts change.
