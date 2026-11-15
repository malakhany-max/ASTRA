# ASTRA Backend, Analytics, and Simulator Modules

Start the local Hub, Ground Station, Companion, and Link Simulator from the repository root:

```powershell
python -m simulators.run_demo
```

The Hub runs on port 8000, Ground Station Backend on 8100, Companion on 8200,
and Link Simulator on 8300. Each app serves Swagger UI at `/docs` and OpenAPI
at `/openapi.json`.
The demo runner binds only to the loopback host from `config/ports.yaml`; no
service calls leave the local machine. The Hub and Ground Station use local
SQLite databases, and the shared Link queue is `ASTRA_LINK_DB` (defaults to
`hub/data/link.db` for the one-command runner).

Set a Ground Station user before login:

```powershell
$env:ASTRA_GROUND_ADMIN_USER = 'flight'
$env:ASTRA_GROUND_ADMIN_PASSWORD = 'choose-a-local-password'
python ground-backend/seed_users.py
```

Run a full demo sequence:

```powershell
python -m simulators.seed
python -m simulators.run_demo
```

From another local terminal, the Hub accepts signed readings at
`http://127.0.0.1:8000/ingest`. The demo endpoint is
`POST /demo/scenario`; supported cases include `sleep_degradation`,
`radiation_spike`, `sensor_fault`, `link_cut`, `link_restore`, and the shared
attack names. Ground Station login is `POST /auth/login`; use its bearer token
for crew and command routes.

Generate synthetic scenario metrics as CSV and Markdown:

```powershell
python engine/evaluation/run_scenarios.py
```

The files are written to `engine/evaluation/results/` by default. From Python,
`ScenarioRunner(time_scale=0.1).play("sleep_degradation")` sends paced signed
readings to the local Hub.

Regenerate the editable composite OpenAPI draft with:

```powershell
python ground-backend/generate_openapi.py
```

It is written to `ground-backend/openapi.yaml`; the generator documents the
runtime routes of Hub, Ground Station, Companion, and Link Simulator while
leaving the shared root `contracts/` files untouched.

All trends and example readings are synthetic. Decision thresholds are read
from `config/thresholds.yaml`; that shared file remains read-only. Weekly plan
content is read from `companion/content/library.yaml`; items requiring an
approved mission or medical reference remain explicit placeholders there.
