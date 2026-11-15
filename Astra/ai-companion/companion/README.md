# ASTRA Companion (Member 4 module)

An offline-first, deterministic Companion service for the ASTRA demo. It is decision support and supportive conversation, **not diagnosis or therapy**. The module uses the shared route names and receives only `status_summary` objects; it does not ingest raw health readings. No cloud calls, analytics, telemetry, LLM, or internet access are used at runtime.

## Short implementation plan

1. Implement the deterministic conversation/safety logic and content library.
2. Expose the shared FastAPI routes, with local-only voice adapters.
3. Run unit tests and a local HTTP smoke test; integrate against shared contracts when the team supplies them.

## Run

This source targets Python 3.11 and is compatible with the sandbox's Python 3.12.3. FastAPI and Uvicorn are pinned in `requirements.txt`. For a fully offline install, first place the pinned wheels and their transitive dependencies in the project `wheels/` folder, then from the project root run:

```sh
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --no-index --find-links wheels/ -r companion/requirements.txt
uvicorn companion.main:app --host 127.0.0.1 --port 8200
```

No wheelhouse or shared `contracts/`/`config/` files were present in the supplied workspace, so this module does not claim to have validated their contents. It follows the pasted shared contract. Install assets from a trusted, pre-staged local package/model bundle; do not download at runtime.

## Test

Tests use the standard library and make no network requests:

```sh
python -m unittest discover -s companion/tests -v
```

HTTP smoke checks (while the server is running):

```sh
curl -fsS http://127.0.0.1:8200/health
curl -fsS http://127.0.0.1:8200/companion/checkin/next
curl -fsS http://127.0.0.1:8200/companion/breathing
curl -sS -X POST http://127.0.0.1:8200/companion/message \
  -H 'Content-Type: application/json' \
  -d '{"astronaut_id":"A-07","text":"explain this","mode":"autonomous","status_summary":[{"indicator":"resting_heart_rate","status":"attention","reasons":["resting heart rate is above this astronaut's baseline"]}]}'
```

A sample dialogue request for the check-in uses `intent: "daily_checkin"`, followed by one user response per prompt. The final response has an action `{ "type": "submit_checkin", "checkin": ... }`; the Hub should assign the authoritative UTC timestamp before POSTing the shared check-in contract. Sleep and free-text answers are retained as short text in `notes`. Check-in state is process memory only and is lost on restart.

## Routes

- `POST /companion/message` -> `{reply_text, actions, mode}`. Deterministic intents include daily/weekly check-in, breathing, alert explanation, radiation follow-up and a placeholder shelter prompt. Mode may be `connected` or `autonomous`; autonomous replies use the required store-and-forward wording.
- `GET /companion/stt/status` -> `{available, detail}`. Reports whether local transcription can run before the crew app records anything.
- `POST /companion/stt` -> `{text}` from raw WAV request bytes. Requires optional Vosk package and a pre-staged model path in `VOSK_MODEL_PATH`. Bytes are handled in memory and never logged or saved. The model is loaded once and reused.
- `POST /companion/tts` -> `audio/wav`. Requires local Piper executable and local voice `.onnx` files. Configure `PIPER_VOICES_DIR`, `PIPER_DEFAULT_VOICE`, and optionally `PIPER_BIN`. Supports a speaking-rate multiplier from 0.7 to 1.5. Generated audio is temporary and removed after response bytes are read.
- `GET /companion/breathing` and `GET /companion/breathing/{technique_id}`
- `GET /companion/checkin/next`

Each response carries `X-Response-Time-Ms`; request method, route, status and elapsed time are logged. Text, raw audio, and health data are not logged. Voice latency depends on the pre-staged model/hardware and is not asserted until measured on the target laptop.

## Safety and integration notes

- Crisis keywords and repeated self-reported low mood trigger a fixed local supportive script and `{ "type": "escalate", "target": "flight_psychologist" }`; no LLM participates. Confirm escalation transport and thresholds with the team's clinical/safety owner before operational use.
- Breathing has no breath holds. Dizziness or an urgent status / non-normal SpO2 status disables paced breathing and offers gentle grounding. Stop instructions are included in the content.
- Radiation shelter text is deliberately `[TO BE FILLED FROM NASA/MEDICAL REFERENCE]`. No shelter protocol, medical limits, medication advice or radiation-removal claims have been invented.
- The weekly questions are original and marked non-validated; no questionnaire is reproduced verbatim.
- `validate_input(text)` is exposed in `guards.py`; voice commands are intent-whitelisted, and arbitrary text is never run as a command.
- This app does not perform signature/integrity verification. It trusts that upstream systems pass only trusted status summaries; integration must preserve that security boundary.
- `companion/content/library.yaml` is JSON-compatible YAML so it can be parsed with the Python standard library. Each content section/item includes a source field.

## Local voice assets

The service deliberately does not download models or voices. Without the optional local Vosk/Piper dependencies and assets, voice routes return a clear `503`; text flows continue to work. Do not store or uplink raw audio. The service accepts WAV only, with a local size cap and in-memory processing.
