"""Onboard Hub API. All service traffic is loopback-only and state is local."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(os.environ.get("ASTRA_PROJECT") or (ROOT.parent if (ROOT.parent / "security").is_dir() else ROOT))
for package_path in ("", "engine", "link", "attack_sim", "simulators"):
    path = str(ROOT / package_path)
    if path not in sys.path:
        sys.path.insert(0, path)
for package_path in ("security", "ai-companion"):
    path = str(PROJECT / package_path)
    if path not in sys.path:
        sys.path.insert(0, path)

from astra_engine import evaluate, make_weekly_plan
from astra_engine.config import load_engine_config
from astra_link import LinkQueue
from . import security_adapter as sec
from .content import load_plan_content
from .store import HubStore
from .view_models import (INDICATORS, alert_views, backend_id, indicator_views, reading_anchors,
                          series_view, ui_id)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# A summary is sent once the sensor burst settles, and at least this often.
SUMMARY_QUIET_SECONDS = float(os.environ.get("ASTRA_SUMMARY_QUIET_SECONDS", "2"))
SUMMARY_MAX_SECONDS = float(os.environ.get("ASTRA_SUMMARY_SECONDS", "30"))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Reading(StrictModel):
    schema_: Literal["astra.reading.v1"] = Field(alias="schema")
    device_id: str = Field(min_length=1)
    astronaut_id: str = Field(min_length=1)
    metric: Literal["heart_rate", "hrv_rmssd", "spo2", "skin_temp", "sleep_duration", "activity_level", "bp_systolic", "bp_diastolic", "blood_glucose", "dizziness_self_report", "mood", "dose_rate", "cumulative_dose", "neutron_dose_rate"]
    value: float
    unit: str
    ts: str
    seq: int = Field(ge=0)
    nonce: str = Field(pattern=r"^[0-9a-f]{32}$")
    source: Literal["wearable", "clinical_device", "manual", "dosimeter", "area_monitor", "self_report"]
    quality: float = Field(ge=0, le=1)
    sig: str = Field(min_length=1)


class ManualReading(StrictModel):
    astronaut_id: str
    metric: Literal["bp_systolic", "bp_diastolic", "blood_glucose"]
    value: float
    unit: str
    quality: float = Field(default=1.0, ge=0, le=1)


class Checkin(StrictModel):
    astronaut_id: str
    ts: str
    mood: int = Field(ge=1, le=5)
    energy: int = Field(ge=1, le=5)
    dizziness: int = Field(ge=0, le=3)
    workload: int = Field(ge=1, le=5)
    symptoms: list[str] = Field(default_factory=list)
    notes: str = ""


class Consent(StrictModel):
    astronaut_id: str
    tiers: dict[str, bool]
    emergency_override: bool

    @field_validator("tiers")
    @classmethod
    def validate_tiers(cls, tiers):
        required = {"vitals_summary", "psych_summary", "raw_audio", "exposure_records"}
        if set(tiers) != required or tiers["raw_audio"]:
            raise ValueError("consent tiers must match the contract; raw_audio must remain false")
        return tiers


class AstronautSettingsRequest(BaseModel):
    voice: bool = True
    tone: Literal["calm", "warm", "direct"] = "calm"
    language: Literal["en", "ar"] = "en"
    checkinTime: str = "19:30"
    environment: Literal["spacecraft", "station", "rover", "base"] = "spacecraft"
    notifications: dict[str, bool] = Field(default_factory=lambda: {
        "alarms": True, "reminders": True, "companion": True,
    })


class DemoScenario(StrictModel):
    name: str


class Downlink(StrictModel):
    bundle: dict


class PlanItemState(StrictModel):
    done: bool


def _week_start() -> str:
    today = datetime.now(timezone.utc).date()
    return (today - timedelta(days=today.weekday())).isoformat()


class EventHub:
    def __init__(self): self.clients: set[asyncio.Queue] = set()
    async def publish(self, event_type: str, data: dict):
        item = {"type": event_type, "data": data}
        for client in tuple(self.clients):
            try: client.put_nowait(item)
            except asyncio.QueueFull:
                try: client.get_nowait(); client.put_nowait(item)
                except (asyncio.QueueEmpty, asyncio.QueueFull): pass


def create_app(store: HubStore | None = None, queue: LinkQueue | None = None) -> FastAPI:
    store = store or HubStore()
    queue = queue or LinkQueue()
    sec.set_event_uplink_sink(queue.enqueue)
    events = EventHub()
    config = load_engine_config()
    app = FastAPI(title="ASTRA Onboard Hub", version="1.0.0",
                  description="Offline-first astronaut health hub. Deterministic rules provide decision support, not diagnosis.")
    app.add_middleware(CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:4173", "http://127.0.0.1:4174",
                       "http://localhost:5173", "http://localhost:5174", "http://localhost:4173", "http://localhost:4174"],
        allow_credentials=False, allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"])
    app.state.store, app.state.link_queue, app.state.events, app.state.config = store, queue, events, config
    from simulators.crew import seed_hub_store
    seed_hub_store(store)
    if not store.backup_path.exists():
        store.create_backup()

    def _enqueue(kind: str, payload: dict, priority: int, direction="uplink", node_id="hub-01"):
        envelope = sec.make_envelope(kind, payload, direction=direction, priority=priority, node_id=node_id)
        signed = sec.sign_envelope(envelope)
        queue.enqueue(signed)
        return signed

    def _should_alert(aid: str, indicator: str, level: str) -> bool:
        key = f"alert_notify:{aid}:{indicator}"
        last = store.get_kv(key) or {}
        stamp = datetime.now(timezone.utc).timestamp()
        if last.get("status") == level and stamp - float(last.get("stamp", 0)) < 900:
            return False
        store.set_kv(key, {"status": level, "stamp": stamp})
        return True

    summary_generation: dict[str, int] = {}

    def _summary_payload(aid: str, anchors: dict | None = None) -> dict | None:
        latest = store.latest_readings(aid, 1)
        if not latest:
            return None
        reading = latest[0]
        consent = store.get_consent(aid) or sec.default_consent(aid)
        snapshot = _measurement_snapshot(aid, consent, anchors)
        recent = {}
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for item in store.statuses(aid):
            if str(item.get("computed_ts", "")) >= cutoff:
                recent[item.get("indicator")] = item
        latest_statuses = list(recent.values())
        psych_shared = sec.consent_allows(consent, "psych_summary")
        psych_metric = str(reading.get("metric", "")).startswith(("mood", "dizziness", "wellbeing"))
        if psych_metric and psych_shared:
            content = {"psych_summary": {
                "reading": {"metric": reading["metric"], "value": reading["value"],
                            "unit": reading.get("unit", ""), "ts": reading.get("ts", "")},
                **{key: value for key, value in snapshot.items() if key != "readings"}}}
            psych_readings = store.psych_readings(aid)
            if psych_readings:
                content["psych_summary"]["readings"] = [
                    {"metric": item["metric"], "value": item["value"], "unit": item.get("unit", ""), "ts": item.get("ts", "")}
                    for item in psych_readings[-30:]]
        else:
            compact_baselines = {
                metric: {"mean": float(values.get("mean", 0)), "scale": float(values.get("scale", 0))}
                for phase_values in store.get_state(aid).get("baselines", {}).values()
                for metric, values in phase_values.items()
                if isinstance(values, dict) and isinstance(values.get("mean"), (int, float))
            }
            vitals = {"statuses": [item for item in latest_statuses
                                   if not str(item.get("indicator", "")).startswith(("mood", "wellbeing"))],
                      "baselines": compact_baselines, **snapshot}
            if not psych_metric:
                vitals["reading"] = {"metric": reading["metric"], "value": reading["value"],
                                     "unit": reading.get("unit", ""), "ts": reading.get("ts", "")}
            content = {"vitals_summary": vitals}
        return sec.filter_for_uplink(content, consent) or None

    def _send_summary(aid: str) -> None:
        anchors = reading_anchors(store.latest_readings(aid, 2))
        payload = _summary_payload(aid, anchors)
        store.set_kv(f"summary_sent:{aid}", datetime.now(timezone.utc).timestamp())
        store.set_kv(f"measurement_anchors:{aid}", anchors)
        if payload:
            _enqueue("summary", {"astronaut_id": aid, **payload}, 4)

    async def _deliver_summary(aid: str, generation: int, delay: float) -> None:
        if delay:
            await asyncio.sleep(delay)
        if summary_generation.get(aid) == generation:
            _send_summary(aid)

    async def _process_reading(message: dict, extra_context: dict | None = None) -> dict:
        result = sec.verify_and_classify(message)
        classification = result.get("classification", "suspect_tamper")
        aid = str(message.get("astronaut_id", "unknown"))
        ts = str(message.get("ts", _utc_now()))
        await events.publish("security" if classification == "suspect_tamper" else "alert", {
            "classification": classification, "astronaut_id": aid, "reasons": result.get("reasons", [])})
        if classification == "trusted":
            store.save_reading(message)
            if message.get("source") == "area_monitor":
                await events.publish("radiation", {"astronaut_id": aid, "source": "area_monitor",
                                                     "metric": message.get("metric"), "ts": ts})
                store.create_backup()
                return {"classification": classification, "reasons": result.get("reasons", [])}
            if message.get("source") == "dosimeter":
                store.set_kv(f"dosimeter_trusted:{aid}", True)
            profile = next((p for p in store.profiles() if p.get("astronaut_id") == aid), {"astronaut_id": aid})
            state = store.get_state(aid)
            prior_context = {"phase": app.state.link_queue.get_meta("mission_phase", "transit"),
                             "mission_day": app.state.link_queue.get_meta("mission_day", 90),
                             "gravity_transition": app.state.store.get_kv("gravity_transition", False),
                             "dosimeter_trusted": store.get_kv(f"dosimeter_trusted:{aid}", True)}
            prior_context.update(extra_context or {})
            prior_context["area_monitor_dose_rates"] = [
                float(item["value"]) for item in store.readings(aid, "dose_rate", 100)
                if item.get("source") == "area_monitor"][-2:]
            statuses, new_state = evaluate(profile, state, [message], prior_context, app.state.config)
            store.set_state(aid, new_state)
            for status in statuses:
                store.save_status(status)
                if status["indicator"] in ("radiation_dose_rate", "radiation_cumulative"):
                    await events.publish("radiation", status)
                elif status["status"] != "normal":
                    await events.publish("alert", status)
                if status["status"] != "normal" and _should_alert(aid, str(status["indicator"]), status["status"]):
                    emergency = status["decision_level"] == 3
                    tier = "psych_summary" if str(status["indicator"]).startswith(("mood", "dizziness", "wellbeing")) else "vitals_summary"
                    content = {tier: {"indicator": status["indicator"], "status": status["status"], "reasons": status["reasons"]},
                               "emergency": emergency}
                    consent = store.get_consent(aid) or sec.default_consent(aid)
                    filtered = sec.filter_for_uplink(content, consent)
                    if filtered:
                        _enqueue("alert", {"astronaut_id": aid, **filtered}, 1 if emergency else 3)

            exposure = new_state.get("post_exposure", {}).get("exposure_record")
            if exposure:
                signed_record = sec.sign_exposure_record(exposure)
                store.save_exposure(signed_record)
                consent = store.get_consent(aid) or sec.default_consent(aid)
                filtered = sec.filter_for_uplink({"exposure_records": signed_record, "emergency": signed_record.get("escalation_level") == 3}, consent)
                if filtered:
                    _enqueue("exposure_record", filtered["exposure_records"], 2)

            consent = store.get_consent(aid) or sec.default_consent(aid)
            psych_metric = str(message.get("metric", "")).startswith(("mood", "dizziness", "wellbeing"))
            force = psych_metric or any(item.get("status") != "normal" for item in statuses)
            may_share = sec.consent_allows(consent, "vitals_summary") or \
                (psych_metric and sec.consent_allows(consent, "psych_summary"))
            if may_share:
                generation = summary_generation.get(aid, 0) + 1
                summary_generation[aid] = generation
                last_sent = float(store.get_kv(f"summary_sent:{aid}", 0) or 0)
                due = force or datetime.now(timezone.utc).timestamp() - last_sent >= SUMMARY_MAX_SECONDS
                if due:
                    await _deliver_summary(aid, generation, 0)
                else:
                    asyncio.create_task(_deliver_summary(aid, generation, SUMMARY_QUIET_SECONDS))
            await events.publish("status", {"astronaut_id": aid, "statuses": statuses})
        elif classification == "suspect_fault":
            store.add_anomaly(aid, "sensor_fault", {"device_id": message.get("device_id"), "metric": message.get("metric"), "reasons": result.get("reasons", [])}, ts)
            if message.get("source") == "dosimeter":
                store.set_kv(f"dosimeter_trusted:{aid}", False)
                profile = next((p for p in store.profiles() if p.get("astronaut_id") == aid), {"astronaut_id": aid})
                state = store.get_state(aid)
                statuses, state = evaluate(profile, state, [], {"dosimeter_trusted": False}, app.state.config)
                store.set_state(aid, state)
                for status in statuses:
                    store.save_status(status)
                    await events.publish("radiation", status)
            await events.publish("alert", {"astronaut_id": aid, "classification": classification, "reasons": result.get("reasons", [])})
        else:
            store.add_anomaly(aid, "tamper", {"device_id": message.get("device_id"), "reasons": result.get("reasons", [])}, ts)
            if message.get("source") == "dosimeter":
                store.set_kv(f"dosimeter_trusted:{aid}", False)
        store.create_backup()
        return {"classification": classification, "reasons": result.get("reasons", [])}

    @app.post("/ingest", status_code=202)
    async def ingest(message: Reading):
        return await _process_reading(message.model_dump(by_alias=True))

    @app.post("/api/checkin", status_code=202)
    async def checkin(item: Checkin, request: Request):
        _authorize(request, item.astronaut_id, "write_self")
        value = item.model_dump()
        store.save_checkin(value)
        for metric, field, unit in (("mood", "mood", "scale_1_5"), ("dizziness_self_report", "dizziness", "scale_0_3")):
            raw = {"schema": "astra.reading.v1", "astronaut_id": value["astronaut_id"], "metric": metric,
                   "value": value[field], "unit": unit, "source": "self_report", "quality": 1.0,
                   "ts": value["ts"]}
            signed = sec.sign_reading(raw, f"self-{value['astronaut_id']}")
            extra = {"symptoms": value["symptoms"],
                "symptom_severity": max(value["dizziness"], 1 if value["symptoms"] else 0),
                "significant_symptom": value["dizziness"] >= 3,
                "force_checkin": True, "trend_change": True} if metric == "mood" else None
            await _process_reading(signed, extra)
        await events.publish("checkin", {"astronaut_id": value["astronaut_id"], "ts": value["ts"]})
        _enqueue("checkin", {"astronaut_id": value["astronaut_id"], "checkin": {
            "ts": value["ts"], "mood": value["mood"], "energy": value["energy"],
            "dizziness": value["dizziness"], "workload": value["workload"],
            "symptoms": value["symptoms"], "notes": value.get("notes", "")}}, 2)
        store.create_backup(force=True)
        return {"accepted": True, "ts": value["ts"]}

    @app.post("/api/manual-reading", status_code=202)
    async def manual_reading(item: ManualReading, principal: dict = Depends(sec.rbac.require_permission("write_self"))):
        if not sec.rbac.can_access_astronaut(principal, item.astronaut_id):
            raise HTTPException(403, "astronaut access denied")
        reading = {"schema": "astra.reading.v1", **item.model_dump(), "device_id": f"manual-{item.astronaut_id}",
                   "source": "manual", "ts": _utc_now()}
        signed = sec.sign_reading(reading, reading["device_id"])
        return await _process_reading(signed)

    def _ui_astronaut_id(astronaut_id: str) -> str:
        return backend_id(astronaut_id)

    def _authorize(request: Request, astronaut_id: str, permission: str = "read_self") -> dict:
        aid = _ui_astronaut_id(astronaut_id)
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            try:
                principal = sec.rbac.decode_session(authorization.split(" ", 1)[1].strip())
            except Exception as exc:
                raise HTTPException(401, "invalid or expired session") from exc
        else:
            if aid != "A-07":
                raise HTTPException(401, "a valid Ground Station session is required")
            principal = {"username": "astronaut-demo", "role": "astronaut", "astronaut_id": aid}
        if not sec.rbac.has_permission(principal.get("role", ""), permission):
            raise HTTPException(403, f"role lacks {permission}")
        if not sec.rbac.can_access_astronaut(principal, aid):
            raise HTTPException(403, "astronaut access denied")
        return principal

    def _profile(astronaut_id: str) -> dict:
        aid = _ui_astronaut_id(astronaut_id)
        profile = next((item for item in store.profiles() if item.get("astronaut_id") == aid), None)
        if profile is None:
            raise HTTPException(404, "astronaut profile not found")
        return profile

    def _baseline_overrides(aid: str) -> dict:
        return store.get_kv(f"baseline_overrides:{aid}") or {}

    def _ui_indicators(astronaut_id: str):
        aid = _ui_astronaut_id(astronaut_id)
        return indicator_views(store.latest_readings(aid, 2), store.statuses(aid), store.get_state(aid),
                               _baseline_overrides(aid))

    def _measurement_snapshot(aid: str, consent: dict, anchors: dict | None = None) -> dict:
        psych_shared = sec.consent_allows(consent, "psych_summary")
        return {
            "captured_at": _utc_now(),
            "anchors": anchors if anchors is not None else reading_anchors(store.latest_readings(aid, 2)),
            "indicators": [item for item in _ui_indicators(aid)
                           if psych_shared or item["key"] not in {"mood", "dizziness"}],
            "readings": [item for item in store.latest_readings(aid, 2)
                         if psych_shared or not str(item.get("metric", "")).startswith(("mood", "dizziness", "wellbeing"))],
            "overrides": _baseline_overrides(aid),
            "radiation": _radiation_view(aid),
        }

    def _radiation_view(aid: str) -> dict:
        dose_rates = store.readings(aid, "dose_rate", 400)
        cumulative = store.readings(aid, "cumulative_dose", 400)
        personal_rates = [item for item in dose_rates if item.get("source") == "dosimeter"]
        personal_cumulative = [item for item in cumulative if item.get("source") == "dosimeter"]
        statuses = store.statuses(aid)
        status_by_name = {}
        for item in sorted(statuses, key=lambda entry: str(entry.get("computed_ts", ""))):
            status_by_name[item.get("indicator")] = item
        rate_status = status_by_name.get("radiation_dose_rate", {})
        cumulative_status = status_by_name.get("radiation_cumulative", {})
        latest_rate = personal_rates[-1] if personal_rates else (dose_rates[-1] if dose_rates else None)
        latest_cumulative = personal_cumulative[-1] if personal_cumulative else (cumulative[-1] if cumulative else None)
        dose_rate = float(latest_rate["value"]) if latest_rate else 0.0
        dose_msv = float(latest_cumulative["value"]) / 1000 if latest_cumulative else 0.0
        radiation_config = app.state.config.get("status_thresholds", {}).get("radiation", {})
        budget = float(radiation_config.get("cumulative_attention_uSv", 500000)) / 1000
        radiation_status = rate_status.get("status", cumulative_status.get("status", "unknown"))
        events = []
        seen_events = set()
        for item in (personal_rates or dose_rates)[-20:]:
            value = float(item.get("value", 0))
            hourly = str(item.get("ts", ""))[:13]
            if hourly in seen_events:
                continue
            seen_events.add(hourly)
            events.append({"id": f"{item.get('device_id', 'dose')}:{item.get('ts', '')}",
                           "type": "dosimeter_spike" if value >= float(radiation_config.get("urgent_uSv_per_h", 500)) else "routine",
                           "doseRate": value, "startedAt": item.get("ts", ""), "endedAt": item.get("ts", ""),
                           "note": "Personal dosimeter reading." if personal_rates else "Area monitor reading."})
        shelter = {"zone": "Cabin shielded sleep station", "direction": "behind",
                   "distanceM": 4,
                   "instructions": ["Move to the shielded sleep station and close the stowage cover.",
                                    "Take the personal dosimeter with you and re-read it there.",
                                    "Tell your crewmate and stay on the link until the reading settles."]}
        return {"astronautId": ui_id(aid), "doseRate": dose_rate, "unit": "µSv/h",
                "cumulativeMsv": dose_msv, "budgetMsv": budget,
                "budgetUsedPct": min(100.0, dose_msv / budget * 100) if budget else 0.0,
                "status": radiation_status,
                "alertActive": radiation_status == "urgent",
                "personalDosimeterAvailable": bool(personal_rates),
                "shelter": shelter,
                "latestEvent": events[-1] if events else None, "events": events}

    def _plan_items(aid: str) -> list[dict]:
        plan = store.get_plan(aid) or make_weekly_plan(
            aid, int(queue.get_meta("mission_day", 90)) // 7, store.statuses(aid), load_plan_content())
        progress = store.plan_progress(aid, _week_start())
        items = []
        rationales = plan.get("rationale_by_category", {})
        for category in ("exercise", "nutrition", "sleep", "wellbeing"):
            for index, item in enumerate(plan.get(category, [])):
                item_id = f"{category}-{index}"
                items.append({"id": item_id, "category": category,
                              "title": item.get("title", category.title()), "detail": item.get("notes", ""),
                              "rationale": rationales.get(category, plan.get("rationale", "Personal trend review.")),
                              "durationMin": int(item.get("duration_min", 0)),
                              "done": progress.get(item_id, False)})
        return items

    def _plan_payload(aid: str, items: list[dict] | None = None) -> dict:
        items = items if items is not None else _plan_items(aid)
        note = store.get_kv(f"plan_note:{aid}")
        payload = {"astronautId": ui_id(aid), "weekOf": _week_start(), "items": items}
        if note:
            payload["groundNote"] = note
        return payload

    def _send_plan_progress(aid: str, items: list[dict]) -> None:
        completed = sum(1 for item in items if item["done"])
        _enqueue("plan_progress", {"astronaut_id": aid, "week": _week_start(),
                                   "completed": completed, "total": len(items), "items": items}, 4)
        store.set_kv(f"plan_progress_sent:{aid}:{_week_start()}", True)

    @app.get("/api/crew/overview")
    async def crew_overview(request: Request):
        authorization = request.headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Ground Station session required")
        try:
            principal = sec.rbac.decode_session(authorization.split(" ", 1)[1].strip())
        except Exception as exc:
            raise HTTPException(401, "invalid or expired session") from exc
        if not sec.rbac.has_permission(principal.get("role", ""), "read_crew"):
            raise HTTPException(403, "crew-wide access denied")
        astronauts = [await astronaut_view(ui_id(profile["astronaut_id"]), request) for profile in store.profiles()]
        connected = bool(queue.get_meta("connected", True))
        delay = float(queue.get_meta("delay_seconds", 0) or 0)
        synced = queue.get_meta("last_sync_ts", "") or ""
        link_value = "autonomous" if not connected else "degraded" if delay else "connected"
        return {"generatedAt": _utc_now(), "astronauts": astronauts,
                "link": {"state": link_value,
                         "label": "Autonomous Mode" if not connected else "Delayed link" if delay else "Connected",
                         "since": synced, "delayMs": int(delay * 1000), "lastSyncAt": synced,
                         "queue": queue.size()}}

    @app.get("/api/astronauts/{astronaut_id}")
    async def astronaut_view(astronaut_id: str, request: Request):
        _authorize(request, astronaut_id)
        profile = _profile(astronaut_id)
        aid = profile["astronaut_id"]
        readings = store.latest_readings(aid, 1)
        statuses = store.statuses(aid)
        link_connected = bool(queue.get_meta("connected", True))
        delay = float(queue.get_meta("delay_seconds", 0) or 0)
        link_state_value = "autonomous" if not link_connected else "degraded" if delay else "connected"
        latest = {}
        for reading in readings:
            latest[reading.get("metric")] = reading
        astronaut_status = max(statuses, key=lambda item: {"normal": 0, "attention": 1, "urgent": 2}.get(item.get("status"), 0), default={}).get("status", "unknown")
        sync = max([item.get("ts", "") for item in readings] + [item.get("computed_ts", "") for item in statuses], default="")
        ui_key = ui_id(aid)
        return {
            "id": ui_key, "name": profile.get("name", ui_key),
            "initials": "".join(part[0] for part in str(profile.get("name", ui_key)).split()[:2]).upper(),
            "missionDay": int(queue.get_meta("mission_day", 90)),
            "currentMissionId": f"current-{aid}", "currentMissionName": "Current mission",
            "status": astronaut_status, "linkState": link_state_value, "lastSyncAt": sync,
            "activeAlerts": sum(item.get("status") != "normal" for item in statuses),
            "sleepHours": latest.get("sleep_duration", {}).get("value"),
            "restingHr": latest.get("heart_rate", {}).get("value"), "location": "Onboard vehicle",
        }

    @app.get("/api/astronauts/{astronaut_id}/indicators")
    async def astronaut_indicators(astronaut_id: str, request: Request):
        _authorize(request, astronaut_id)
        _profile(astronaut_id)
        return _ui_indicators(astronaut_id)

    @app.get("/api/astronauts/{astronaut_id}/missions")
    async def astronaut_missions(astronaut_id: str, request: Request):
        _authorize(request, astronaut_id)
        profile = _profile(astronaut_id)
        aid = ui_id(profile["astronaut_id"])
        history = profile.get("mission_history", [])
        sleep = float((store.latest_reading(profile["astronaut_id"], "sleep_duration") or {}).get("value", 0.0))
        heart = float((store.latest_reading(profile["astronaut_id"], "heart_rate") or {}).get("value", 0.0))
        result = [{
            "id": f"current-{aid}", "astronautId": aid, "name": "Astra Demo Mission",
            "vehicle": "Orion", "startDate": "2026-01-01", "endDate": None,
            "days": int(queue.get_meta("mission_day", 90)), "role": "Mission specialist",
            "highlight": "Current mission", "summary": "Live readings from the onboard hub.",
            "stats": {"meanSleepHours": round(sleep, 1), "meanHeartRate": round(heart),
                      "radiationDoseMsv": 0.0, "incidents": 0},
        }]
        for index, mission in enumerate(history):
            result.append({
                "id": str(mission.get("mission_id", f"MISSION-{index + 1}")), "astronautId": aid,
                "name": mission.get("name", f"Prior mission {index + 1}"),
                "vehicle": mission.get("vehicle", "Orion"),
                "startDate": mission.get("start", "2024-01-01"),
                "endDate": mission.get("end", "2024-06-01"),
                "days": int(mission.get("days", 0)),
                "role": mission.get("role", "Mission specialist"),
                "highlight": mission.get("summary", "Completed mission"),
                "summary": mission.get("summary", ""),
                "stats": mission.get("stats", {"meanSleepHours": 7.2, "meanHeartRate": 61,
                                               "radiationDoseMsv": 12.0, "incidents": 0}),
            })
        return result

    @app.get("/api/astronauts/{astronaut_id}/indicators/{key}")
    async def astronaut_indicator_series(astronaut_id: str, key: str, request: Request, range: str = "24h"):
        _authorize(request, astronaut_id)
        _profile(astronaut_id)
        if key not in {"heartRate", "spo2", "bloodPressure", "bloodGlucose", "temperature", "sleep", "dizziness", "mood", "radiation"}:
            raise HTTPException(404, "unknown indicator")
        if range not in {"24h", "7d", "30d"}:
            raise HTTPException(400, "range must be 24h, 7d or 30d")
        aid = _ui_astronaut_id(astronaut_id)
        metric = INDICATORS[key][0]
        readings = store.readings(aid, metric, 400)
        if key == "bloodPressure":
            readings = sorted(readings + store.readings(aid, "bp_diastolic", 400), key=lambda item: item.get("ts", ""))
        return series_view(key, readings, store.statuses(aid), store.get_state(aid),
                           range, _baseline_overrides(aid), aid,
                           anchors=store.get_kv(f"measurement_anchors:{aid}") or {})

    @app.get("/api/astronauts/{astronaut_id}/organs")
    async def astronaut_organs(astronaut_id: str, request: Request):
        _authorize(request, astronaut_id)
        _profile(astronaut_id)
        indicators = {item["key"]: item for item in _ui_indicators(astronaut_id)}
        definitions = [
            ("heart", "Heart & circulation", "Circulates blood; heart-rate and pressure trends are monitored.", ["Microgravity adaptation"], ["Re-measure after resting.", "Tell the crew if symptoms feel urgent."], ["heartRate", "bloodPressure"]),
            ("brain", "Brain & sleep", "Sleep, mood and balance are checked against personal trends.", ["Sleep disruption", "Fluid shifts"], ["Use the check-in to report changes.", "Stop if you feel unsteady."], ["sleep", "dizziness", "mood"]),
            ("lungs", "Lungs & oxygen", "Oxygen saturation is monitored from the available sensor readings.", ["Cabin environment"], ["Repeat a reading if it seems unusual.", "Report breathing discomfort to the crew."], ["spo2"]),
            ("bones", "Bones & movement", "Movement and dose trends are shown for crew review.", ["Reduced loading", "Radiation exposure"], ["Follow the approved mission exercise plan."], ["radiation"]),
        ]
        result = []
        for organ_id, name, function, hazards, what_to_do, keys in definitions:
            relevant = [indicators[key]["status"] for key in keys if key in indicators]
            result.append({"id": organ_id, "name": name, "function": function,
                           "status": max(relevant, key=lambda level: {"normal": 0, "attention": 1, "urgent": 2}.get(level, 0), default="unknown"),
                           "hazards": hazards, "whatToDo": what_to_do, "indicatorKeys": keys})
        return result

    @app.get("/api/astronauts/{astronaut_id}/alerts")
    async def astronaut_alerts(astronaut_id: str, request: Request):
        _authorize(request, astronaut_id)
        _profile(astronaut_id)
        aid = _ui_astronaut_id(astronaut_id)
        return alert_views(store.statuses(aid), store.acknowledged_alerts())

    @app.get("/api/astronauts/{astronaut_id}/radiation")
    async def astronaut_radiation(astronaut_id: str, request: Request):
        _authorize(request, astronaut_id)
        profile = _profile(astronaut_id)
        return _radiation_view(profile["astronaut_id"])

    @app.get("/api/astronauts/{astronaut_id}/exposure")
    async def astronaut_exposure(astronaut_id: str, request: Request):
        _authorize(request, astronaut_id)
        profile = _profile(astronaut_id)
        aid = profile["astronaut_id"]
        state = store.get_state(aid).get("post_exposure", {})
        records = []
        for item in store.exposures(aid):
            cumulative_value = item.get("cumulative_dose", {}).get("value", 0)
            start_ts = item.get("start_ts", "")
            hours = int(item.get("followup_window_hours", 72))
            try:
                start_time = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
                until = (start_time + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                until = None
            symptoms = [symptom for checkin in item.get("symptom_checkins", []) for symptom in checkin.get("symptoms", [])]
            records.append({"id": item.get("event_id", "exposure"), "astronautId": ui_id(aid),
                            "missionId": f"current-{aid}", "date": start_ts[:10],
                            "doseMsv": float(cumulative_value) / 1000,
                            "symptoms": symptoms or ["No symptoms reported"], "followUpUntil": until,
                            "note": "Health changes and later symptoms are co-occurring; this record does not infer a cause."})
        return {"astronautId": ui_id(aid), "records": records,
                "monitoringActive": bool(state.get("active")), "monitoringStartedAt": state.get("start_ts"),
                "monitoringUntil": records[-1].get("followUpUntil") if records else None,
                "windowHours": int(state.get("followup_window_hours", 72))}

    @app.get("/api/astronauts/{astronaut_id}/checkins")
    async def astronaut_checkins(astronaut_id: str, request: Request):
        _authorize(request, astronaut_id)
        profile = _profile(astronaut_id)
        aid = profile["astronaut_id"]
        return [{"id": f"checkin-{item.get('ts', '')}", "astronautId": ui_id(aid),
                 "createdAt": item.get("ts", ""), "mood": item.get("mood", 3),
                 "energy": item.get("energy", 3), "dizziness": item.get("dizziness", 0),
                 "workload": item.get("workload", 3), "symptoms": item.get("symptoms", []),
                 "note": item.get("notes", "")} for item in reversed(store.checkins(aid))]

    @app.get("/api/astronauts/{astronaut_id}/plan")
    async def astronaut_plan(astronaut_id: str, request: Request):
        _authorize(request, astronaut_id)
        profile = _profile(astronaut_id)
        aid = profile["astronaut_id"]
        items = _plan_items(aid)
        if not store.get_kv(f"plan_progress_sent:{aid}:{_week_start()}"):
            _send_plan_progress(aid, items)
        return _plan_payload(aid, items)

    @app.post("/api/astronauts/{astronaut_id}/plan/{item_id}")
    async def set_plan_item(astronaut_id: str, item_id: str, item: PlanItemState, request: Request):
        _authorize(request, astronaut_id, "write_self")
        profile = _profile(astronaut_id)
        aid = profile["astronaut_id"]
        items = _plan_items(aid)
        if item_id not in {entry["id"] for entry in items}:
            raise HTTPException(404, "plan item not found")
        store.set_plan_item(aid, _week_start(), item_id, item.done, _utc_now())
        store.create_backup(force=True)
        sec.audit_log("astronaut", "plan_item", f"{aid}:{item_id}", {"done": item.done})
        updated = _plan_items(aid)
        _send_plan_progress(aid, updated)
        await events.publish("plan", {"astronaut_id": aid, "item_id": item_id, "done": item.done})
        return _plan_payload(aid, updated)

    @app.get("/api/astronauts/{astronaut_id}/settings")
    async def astronaut_settings(astronaut_id: str, request: Request):
        _authorize(request, astronaut_id)
        profile = _profile(astronaut_id)
        return store.get_settings(profile["astronaut_id"]) or AstronautSettingsRequest().model_dump()

    @app.put("/api/astronauts/{astronaut_id}/settings")
    async def save_astronaut_settings(astronaut_id: str, item: AstronautSettingsRequest, request: Request):
        _authorize(request, astronaut_id, "write_self")
        profile = _profile(astronaut_id)
        value = item.model_dump()
        store.set_settings(profile["astronaut_id"], value)
        store.create_backup(force=True)
        await events.publish("settings", {"astronaut_id": profile["astronaut_id"]})
        return value

    @app.get("/api/status/{astronaut_id}")
    async def get_status(astronaut_id: str):
        return store.statuses(astronaut_id)

    @app.get("/api/readings/{astronaut_id}")
    async def get_readings(astronaut_id: str, metric: str | None = None, limit: int = 500):
        return store.readings(astronaut_id, metric, min(max(limit, 1), 1000))

    @app.get("/api/alerts")
    async def get_alerts(request: Request, astronaut_id: str | None = None):
        authorization = request.headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Ground Station session required")
        try:
            principal = sec.rbac.decode_session(authorization.split(" ", 1)[1].strip())
        except Exception as exc:
            raise HTTPException(401, "invalid or expired session") from exc
        if not sec.rbac.has_permission(principal.get("role", ""), "read_crew"):
            raise HTTPException(403, "crew-wide access denied")
        statuses = [s for profile in store.profiles() for s in store.statuses(profile["astronaut_id"])]
        alerts = alert_views(statuses, store.acknowledged_alerts())
        if astronaut_id:
            target = ui_id(_ui_astronaut_id(astronaut_id))
            alerts = [a for a in alerts if a["astronautId"] == target]
        return alerts

    @app.post("/api/alerts/{alert_id}/ack")
    async def acknowledge_hub_alert(alert_id: str, request: Request):
        target_aid = alert_id.split(":", 1)[0]
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            try:
                principal = sec.rbac.decode_session(authorization.split(" ", 1)[1].strip())
            except Exception as exc:
                raise HTTPException(401, "invalid or expired session") from exc
            astronaut_self = principal.get("role") == "astronaut" and principal.get("astronaut_id") == target_aid
            if not astronaut_self and not sec.rbac.has_permission(principal.get("role", ""), "ack_alert"):
                raise HTTPException(403, "alert acknowledgement denied")
            actor = str(principal.get("username", "unknown"))
        else:
            if target_aid != "A-07":
                raise HTTPException(401, "a valid session is required")
            actor = "astronaut-demo"
        available = {item["id"] for item in alert_views(
            [status for profile in store.profiles() for status in store.statuses(profile["astronaut_id"])],
            store.acknowledged_alerts())}
        if alert_id not in available:
            raise HTTPException(404, "alert not found")
        store.acknowledge_alert(alert_id, actor, _utc_now())
        store.create_backup(force=True)
        sec.audit_log(actor, "alert_acknowledge", alert_id, {})
        await events.publish("alert", {"id": alert_id, "acknowledged": True})
        return {"alert_id": alert_id, "acknowledged": True}

    @app.get("/api/plan/{astronaut_id}")
    async def get_plan(astronaut_id: str, week: int = 12):
        plan = store.get_plan(astronaut_id)
        if plan is None:
            plan = make_weekly_plan(astronaut_id, week, store.statuses(astronaut_id), load_plan_content())
            store.save_plan(plan)
            store.create_backup()
        return plan

    @app.get("/api/radiation/current")
    async def radiation_current(astronaut_id: str = "A-07"):
        readings = store.readings(astronaut_id, "dose_rate", 500)
        personal = [item for item in readings if item.get("source") == "dosimeter"]
        statuses = store.statuses(astronaut_id)
        radiation = [s for s in statuses if s["indicator"] in ("radiation_dose_rate", "radiation_cumulative", "post_exposure_followup")]
        if not personal:
            profile = next((p for p in store.profiles() if p["astronaut_id"] == astronaut_id), {"astronaut_id": astronaut_id})
            area_rates = [float(item["value"]) for item in readings if item.get("source") == "area_monitor"][-2:]
            fresh, _ = evaluate(profile, store.get_state(astronaut_id), [],
                {"dosimeter_trusted": False, "area_monitor_dose_rates": area_rates}, app.state.config)
            radiation = [item for item in radiation if item["indicator"] != "radiation_dose_rate"] + fresh
        return {"astronaut_id": astronaut_id, "statuses": radiation[-20:],
                "last_update_ts": personal[-1].get("ts") if personal else None,
                "personal_dosimeter_available": bool(personal)}

    @app.get("/api/exposure-records/{astronaut_id}")
    async def exposure_records(astronaut_id: str): return store.exposures(astronaut_id)

    @app.get("/api/link/state")
    async def link_state():
        connected = bool(queue.get_meta("connected", True))
        delay = float(queue.get_meta("delay_seconds", 0) or 0)
        synced = queue.get_meta("last_sync_ts", "") or ""
        return {"connected": connected, "mode": "connected" if connected else "autonomous",
                "last_sync_ts": synced, "queue_size": queue.size(),
                "state": "autonomous" if not connected else "degraded" if delay else "connected",
                "label": "Autonomous Mode" if not connected else "Delayed link" if delay else "Connected",
                "since": synced, "delayMs": int(delay * 1000), "lastSyncAt": synced,
                "queue": queue.size()}

    @app.get("/api/backup/state")
    async def backup_state():
        state = store.backup_state()
        return {"status": "current" if state["available"] else "error",
                "lastBackupAt": state["last_backup_ts"] or "", "pendingBatches": queue.size(),
                "sizeKb": state["size_kb"], "encrypted": state["encrypted"]}

    @app.get("/api/security/state")
    async def security_state():
        latest = sec.list_events(1)
        shield = sec.shield_state()
        level = "critical" if shield == "alert" else shield
        last_event = (latest[0].get("time_end") or latest[0].get("created_ts")) if latest else ""
        return {"shield": shield, "last_event_ts": last_event, "level": level,
                "headline": "Security checks need review" if level != "ok" else "Security checks are operating normally",
                "lastEventAt": last_event,
                "checks": [{"id": "integrity", "label": "Reading integrity", "state": level,
                            "detail": "Signed readings are checked before analysis."}]}

    @app.get("/api/consent/{astronaut_id}")
    async def get_consent(astronaut_id: str, request: Request):
        _authorize(request, astronaut_id)
        aid = _ui_astronaut_id(astronaut_id)
        value = store.get_consent(aid) or sec.default_consent(aid)
        return {**value, "updatedAt": value.get("updated_ts", "")}

    @app.put("/api/consent/{astronaut_id}")
    async def put_consent(astronaut_id: str, item: Consent, request: Request):
        _authorize(request, astronaut_id, "write_self")
        aid = _ui_astronaut_id(astronaut_id)
        if item.astronaut_id != aid:
            raise HTTPException(403, "consent astronaut id does not match the route")
        value = item.model_dump()
        value["updated_ts"] = _utc_now()
        store.set_consent(aid, value)
        store.create_backup(force=True)
        sec.audit_log("astronaut", "consent_change", aid, {"tiers": value["tiers"]})
        await events.publish("security", {"type": "consent_changed", "astronaut_id": aid})
        return {**value, "updatedAt": value["updated_ts"]}

    @app.websocket("/ws/events")
    async def websocket_events(websocket: WebSocket):
        await websocket.accept(); mailbox: asyncio.Queue = asyncio.Queue(maxsize=100); events.clients.add(mailbox)
        try:
            while True: await websocket.send_json(await mailbox.get())
        except WebSocketDisconnect:
            pass
        finally:
            events.clients.discard(mailbox)

    @app.post("/internal/downlink", status_code=202)
    async def receive_downlink(item: dict):
        if item.get("direction") == "downlink":
            if not sec.verify_envelope(item):
                raise HTTPException(400, "downlink envelope signature invalid")
            bundle = item.get("payload", {}).get("bundle", {})
        else:
            bundle = item.get("bundle", item)
        if not sec.verify_bundle(bundle): raise HTTPException(400, "bundle signature invalid")
        kind = bundle.get("type")
        ack_aid = ""
        if kind == "revocation_list":
            sec.apply_revocation_bundle(bundle, actor="hub")
        elif kind in {"config_bundle", "thresholds_bundle", "guideline_bundle"}:
            payload = bundle.get("payload", {}) or {}
            aid = backend_id(str(payload.get("astronaut_id") or ""))
            ack_aid = aid
            ui_type = str(payload.get("ui_type") or {
                "config_bundle": "schedule", "thresholds_bundle": "thresholds",
                "guideline_bundle": "plan"}.get(kind, ""))
            replacement = payload.get("thresholds")
            if replacement:
                app.state.config["status_thresholds"] = replacement
            if aid and ui_type == "schedule" and payload.get("checkinTime"):
                settings = store.get_settings(aid) or AstronautSettingsRequest().model_dump()
                store.set_settings(aid, {**settings, "checkinTime": str(payload["checkinTime"])})
                await events.publish("settings", {"astronaut_id": aid})
            elif aid and ui_type == "thresholds":
                metric = INDICATORS.get(str(payload.get("key")), (None,))[0]
                if metric and payload.get("low") is not None and payload.get("high") is not None:
                    overrides = store.get_kv(f"baseline_overrides:{aid}") or {}
                    overrides[metric] = {"low": float(payload["low"]), "high": float(payload["high"])}
                    store.set_kv(f"baseline_overrides:{aid}", overrides)
                    await events.publish("indicator", {"astronaut_id": aid})
            elif aid and ui_type == "plan":
                note = str(payload.get("note") or "").strip()
                if note:
                    store.set_kv(f"plan_note:{aid}", {"note": note, "ts": _utc_now()})
                    await events.publish("plan", {"astronaut_id": aid})
        store.save_bundle(bundle)
        sec.audit_log("ground-01", "apply_downlink_bundle", str(kind), {"bundle_type": kind})
        await events.publish("status", {"type": "downlink_applied", "bundle_type": kind})
        if ack_aid:
            _enqueue("command_ack", {"astronaut_id": ack_aid, "msg_id": str(item.get("msg_id", "")),
                                     "bundle_type": str(kind), "applied_ts": _utc_now()}, 3)
        return {"accepted": True, "type": kind}

    @app.post("/internal/companion-notify", status_code=202)
    async def companion_notify(item: dict):
        aid = backend_id(str(item.get("astronaut_id") or ""))
        if not aid:
            raise HTTPException(422, "astronaut_id is required")
        message = {
            "reason": str(item.get("reason", "crew report"))[:120],
            "detail": str(item.get("detail", ""))[:400],
            "severity": "urgent" if item.get("severity") == "urgent" else "attention",
            "symptoms": [str(symptom)[:80] for symptom in list(item.get("symptoms", []))[:8]],
            "created_ts": _utc_now(),
        }
        _enqueue("crew_message", {"astronaut_id": aid, "crew_message": message}, 1)
        sec.audit_log(aid, "companion_notify", aid, {"reason": message["reason"]})
        return {"accepted": True, "ts": message["created_ts"]}

    @app.post("/demo/scenario")
    async def demo_scenario(item: DemoScenario):
        name = item.name
        if name.startswith("attack_"):
            try:
                import attack_sim
                result = attack_sim.trigger_scenario(name)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            await events.publish("security", {"scenario": name, "detected": result["detected"], "classification": result["classification"]})
            return result
        from simulators.scenario_runner import build_scenario_readings
        if name in {"reset", "normal"}:
            store.reset_demo()
            store.create_backup(force=True)
            queue.set_meta("connected", True)
            queue.set_meta("delay_seconds", 0)
            queue.set_meta("mission_day", 90)
            queue.set_meta("demo_scenario", name)
            await events.publish("status", {"type": "demo_reset"})
            return {"accepted": True, "scenario": name}
        if name == "day60":
            queue.set_meta("mission_day", 60)
            name_to_generate = "sleep_degradation"
        else:
            name_to_generate = name
        if name_to_generate not in {"sleep_degradation", "radiation_spike", "sensor_fault", "link_cut", "link_restore"}:
            raise HTTPException(400, "unknown demo scenario")
        queue.set_meta("demo_scenario", name)
        if name_to_generate == "link_cut":
            queue.set_meta("connected", False); await events.publish("link", {"connected": False, "mode": "autonomous"})
            return {"accepted": True, "scenario": name}
        if name_to_generate == "link_restore":
            queue.set_meta("connected", True); await events.publish("link", {"connected": True, "mode": "connected"})
            return {"accepted": True, "scenario": name}
        readings = build_scenario_readings(name_to_generate, "A-07")
        results = [await _process_reading(reading) for reading in readings]
        return {"accepted": True, "scenario": name, "results": results}

    @app.get("/api/demo/state")
    async def get_demo_state():
        connected = bool(queue.get_meta("connected", True))
        delay = float(queue.get_meta("delay_seconds", 0) or 0)
        synced = queue.get_meta("last_sync_ts", "") or ""
        shield = sec.shield_state()
        level = "critical" if shield == "alert" else shield
        events_latest = sec.list_events(1)
        last_event = (events_latest[0].get("time_end") or events_latest[0].get("created_ts")) if events_latest else ""
        latest_radiation = store.statuses("A-07")
        radiation_active = any(item.get("indicator", "").startswith("radiation") and item.get("status") == "urgent"
                               for item in latest_radiation)
        return {"missionDay": int(queue.get_meta("mission_day", 90)),
                "scenario": queue.get_meta("demo_scenario", "normal"),
                "link": {"state": "autonomous" if not connected else "degraded" if delay else "connected",
                         "label": "Autonomous Mode" if not connected else "Delayed link" if delay else "Connected",
                         "since": synced, "delayMs": int(delay * 1000), "lastSyncAt": synced, "queue": queue.size()},
                "security": {"level": level, "headline": "Security checks need review" if level != "ok" else "Security checks are operating normally",
                             "lastEventAt": last_event,
                             "checks": [{"id": "integrity", "label": "Reading integrity", "state": level,
                                         "detail": "Signed readings are checked before analysis."}]},
                "radiationAlertActive": radiation_active}

    @app.get("/health")
    async def health(): return {"status": "ok", "mode": "offline-first"}

    return app


app = create_app()
