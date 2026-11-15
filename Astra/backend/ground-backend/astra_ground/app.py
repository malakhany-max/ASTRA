"""Ground Station API: authentication, signed uplinks, crew history, commands."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[2]
PROJECT = Path(os.environ.get("ASTRA_PROJECT") or (ROOT.parent if (ROOT.parent / "security").is_dir() else ROOT))
for package_path in ("", "link", "simulators"):
    path = str(ROOT / package_path)
    if path not in sys.path: sys.path.insert(0, path)
for package_path in ("security", "ai-companion"):
    path = str(PROJECT / package_path)
    if path not in sys.path: sys.path.insert(0, path)

from astra_link import LinkQueue
from hub import security_adapter as sec
from simulators.crew import synthetic_profiles
from .store import GroundStore
from hub.view_models import (INDICATORS, indicator_views, reading_anchors, series_view,
                             backend_id, ui_id, metric_label)


class Login( BaseModel):
    username: str
    password: str


class Command(BaseModel):
    command_type: str | None = None
    astronautId: str | None = None
    astronaut_id: str | None = None
    type: str | None = None
    payload: dict


COMMAND_BUNDLES = {"schedule": "config_bundle", "thresholds": "thresholds_bundle", "plan": "guideline_bundle"}

CURRENT_MISSION = {"name": "Orion lunar transit", "vehicle": "Orion", "role": "Crew", "day": 90}
SERIES_WINDOW = 1200


def _current_start() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=CURRENT_MISSION["day"] - 1)).strftime("%Y-%m-%d")


class Ack(BaseModel):
    note: str = ""


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _monitoring_until(records: list[dict]) -> str | None:
    latest = [ts for ts in (_parse_ts(item.get("followUpUntil")) for item in records) if ts]
    return max(latest).isoformat().replace("+00:00", "Z") if latest else None


def _monitoring_active(records: list[dict]) -> bool:
    until = _monitoring_until(records)
    parsed = _parse_ts(until)
    return bool(parsed and parsed > datetime.now(timezone.utc))


def create_app(store: GroundStore | None = None, queue: LinkQueue | None = None) -> FastAPI:
    store = store or GroundStore()
    queue = queue or LinkQueue()
    store.seed_profiles(synthetic_profiles())
    if not store.backup_path.exists():
        store.create_backup()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sent = queue.sent_ids()
    store.mark_delivered([row["msg_id"] for row in store.pending_commands()
                          if row["created_ts"] < cutoff and row["msg_id"] in sent])
    app = FastAPI(title="ASTRA Ground Station Backend", version="1.0.0",
                  description="Offline Ground Station API; data reflects last received uplinks.")
    app.add_middleware(CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:4173", "http://127.0.0.1:4174",
                       "http://localhost:5173", "http://localhost:5174", "http://localhost:4173", "http://localhost:4174"],
        allow_credentials=False, allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"])
    app.state.store, app.state.link_queue = store, queue
    stale_after = float(os.environ.get("ASTRA_STALE_AFTER_SECONDS", "3600"))

    @app.post("/auth/login")
    async def login(item: Login):
        try:
            principal = sec.rbac.authenticate(item.username, item.password)
        except Exception as exc:
            raise HTTPException(401, "invalid credentials") from exc
        return {"access_token": sec.rbac.create_session(principal), "token_type": "bearer",
                "expires_in_seconds": 1800, "role": principal["role"]}

    @app.post("/auth/logout")
    async def logout(principal: dict = Depends(sec.rbac.require_permission("read_self"))):
        sec.rbac.logout(principal["username"])
        return {"logged_out": True}

    @app.post("/uplink", status_code=202)
    async def receive_uplink(envelope: dict):
        if envelope.get("direction") != "uplink" or not sec.verify_envelope(envelope):
            raise HTTPException(400, "uplink envelope signature or direction invalid")
        payload = envelope.get("payload", {})
        if envelope.get("type") in {"exposure_record", "history_bundle"}:
            try: payload = sec.decrypt_envelope_payload(envelope)
            except Exception as exc: raise HTTPException(400, "sensitive payload verification failed") from exc
        astronaut_id = store.save_uplink(envelope, payload)
        return {"accepted": True, "msg_id": envelope["msg_id"], "astronaut_id": astronaut_id}

    @app.get("/api/crew")
    async def crew(principal: dict = Depends(sec.rbac.require_permission("read_crew"))):
        sec.audit_log(principal["username"], "crew_list_access", "crew", {})
        return store.crew()

    def _crew_views():
        link_connected = bool(queue.get_meta("connected", True))
        link = {"state": "connected" if link_connected else "autonomous",
                "label": "Connected" if link_connected else "Autonomous",
                "since": queue.get_meta("last_sync_ts") or "", "delayMs": int(float(queue.get_meta("delay_seconds", 0) or 0) * 1000),
                "lastSyncAt": queue.get_meta("last_sync_ts") or "", "queue": queue.size()}
        astronauts = []
        for profile in store.crew():
            aid = profile["astronaut_id"]
            uplinks = store.uplinks(aid)
            indicators = _indicator_cards(aid, uplinks)
            levels = {"normal": 0, "unknown": 0, "attention": 1, "urgent": 2}
            worst = max((item["status"] for item in indicators), key=lambda value: levels.get(value, 0), default="unknown")
            heart = next((x["value"] for x in indicators if x["key"] == "heartRate"), None)
            sleep = next((x["value"] for x in indicators if x["key"] == "sleep"), None)
            astronauts.append({"id": ui_id(aid), "name": profile.get("name", aid),
                "initials": "".join(part[0] for part in profile.get("name", aid).split()[:2]).upper(),
                "missionDay": CURRENT_MISSION["day"], "currentMissionId": f"current-{aid}", "currentMissionName": CURRENT_MISSION["name"],
                "status": worst, "linkState": link["state"],
                "lastSyncAt": store.get_kv(f"last_update:{aid}") or "", "activeAlerts": sum(1 for a in _alerts(aid) if not a["acknowledged"]),
                "sleepHours": sleep, "restingHr": heart, "location": "Crew vehicle"})
        return {"generatedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                "link": link, "astronauts": astronauts}

    def _snapshot(uplinks):
        """Newest measurement snapshot rendered by the onboard hub."""
        best, best_key = None, None
        for record in uplinks:
            payload = record["payload"] if isinstance(record["payload"], dict) else {}
            for tier in ("vitals_summary", "psych_summary"):
                summary = payload.get(tier) or {}
                if not isinstance(summary, dict) or not summary.get("indicators"):
                    continue
                key = (str(summary.get("captured_at") or record.get("ts") or ""), len(summary["indicators"]))
                if best_key is None or key >= best_key:
                    best, best_key = summary, key
        return best

    def _indicator_cards(aid, uplinks):
        snapshot = _snapshot(uplinks)
        if snapshot:
            return snapshot["indicators"]
        readings, statuses = _collect(aid, uplinks)
        return indicator_views(readings, statuses, _baselines(uplinks))

    def _collect(aid, uplinks):
        readings, statuses = [], []
        for record in uplinks:
            payload = record["payload"]
            summary = payload.get("vitals_summary", {}) if isinstance(payload, dict) else {}
            reading = summary.get("reading")
            if reading and reading.get("metric"):
                readings.append(reading)
            readings.extend(summary.get("readings", []))
            psych = payload.get("psych_summary", {}) if isinstance(payload, dict) else {}
            psych_reading = psych.get("reading")
            if psych_reading and psych_reading.get("metric"):
                readings.append(psych_reading)
            readings.extend(psych.get("readings", []))
            status_items = summary.get("statuses", [])
            if status_items:
                statuses.extend(status_items)
            if record["type"] == "alert":
                alert_summary = summary or (payload.get("psych_summary", {}) if isinstance(payload, dict) else {})
                status = alert_summary.get("status")
                indicator = alert_summary.get("indicator")
                if status and indicator:
                    statuses.append({"astronaut_id": aid, "indicator": indicator, "status": status,
                                     "reasons": alert_summary.get("reasons", []), "computed_ts": record["ts"]})
        unique = {(item.get("metric"), item.get("ts")): item for item in readings}
        return sorted(unique.values(), key=lambda item: item.get("ts", "")), statuses

    def _baselines(uplinks):
        baselines = {}
        for record in uplinks:
            values = record["payload"].get("vitals_summary", {}).get("baselines", {})
            baselines.update(values)
        return {"baselines": {"transit": baselines}}

    def _recent_per_metric(readings, limit):
        grouped: dict[str, list[dict]] = {}
        for item in readings:
            grouped.setdefault(str(item.get("metric")), []).append(item)
        return sorted((item for items in grouped.values() for item in items[-limit:]),
                      key=lambda item: str(item.get("ts", "")))

    def _profile_view(aid):
        profile = store.get_crew(aid)
        if not profile: return None
        overview = _crew_views()
        astronaut = next((item for item in overview["astronauts"] if item["id"] == ui_id(aid)), None)
        return astronaut

    def _mission_views(aid):
        profile = store.get_crew(aid)
        if not profile: return None
        uplinks = store.uplinks(aid)
        cards = {item["key"]: item for item in _indicator_cards(aid, uplinks)}
        heart = float((cards.get("heartRate") or {}).get("value") or 0.0)
        sleep = float((cards.get("sleep") or {}).get("value") or 0.0)
        current = {"id": f"current-{aid}", "astronautId": ui_id(aid), "name": CURRENT_MISSION["name"],
                   "vehicle": CURRENT_MISSION["vehicle"], "startDate": _current_start(), "endDate": None,
                   "days": CURRENT_MISSION["day"], "role": CURRENT_MISSION["role"], "highlight": "Current mission",
                   "summary": "Live readings received from the onboard hub.",
                   "stats": {"meanSleepHours": round(sleep, 1), "meanHeartRate": round(heart),
                             "radiationDoseMsv": 0, "incidents": 0}}
        history = [{"id": mission.get("mission_id", f"MISSION-{index + 1}"), "astronautId": ui_id(aid),
                    "name": mission.get("name", f"Prior mission {index + 1}"),
                    "vehicle": mission.get("vehicle", "Orion"),
                    "startDate": mission.get("start", "2024-01-01"),
                    "endDate": mission.get("end", "2024-06-01"),
                    "days": int(mission.get("days", 0)),
                    "role": mission.get("role", "Mission specialist"),
                    "highlight": mission.get("summary", "Completed mission"),
                    "summary": mission.get("summary", ""),
                    "stats": mission.get("stats", {"meanSleepHours": 7.2, "meanHeartRate": 61,
                                                   "radiationDoseMsv": 12.0, "incidents": 0})}
                   for index, mission in enumerate(profile.get("mission_history", []))]
        return [current, *history]

    @app.get("/api/crew/overview")
    async def crew_overview(principal: dict = Depends(sec.rbac.require_permission("read_crew"))):
        return _crew_views()

    @app.get("/api/astronauts/{astronaut_id}")
    async def astronaut_detail(astronaut_id: str, principal: dict = Depends(sec.rbac.require_permission("read_self"))):
        aid = backend_id(astronaut_id)
        if not sec.rbac.can_access_astronaut(principal, aid): raise HTTPException(403, "crew access denied")
        result = _profile_view(aid)
        if result is None: raise HTTPException(404, "crew member not found")
        return result

    @app.get("/api/astronauts/{astronaut_id}/indicators")
    async def astronaut_indicators(astronaut_id: str, principal: dict = Depends(sec.rbac.require_permission("read_self"))):
        aid = backend_id(astronaut_id)
        if not sec.rbac.can_access_astronaut(principal, aid): raise HTTPException(403, "crew access denied")
        return _indicator_cards(aid, store.uplinks(aid))

    @app.get("/api/astronauts/{astronaut_id}/indicators/{key}")
    async def astronaut_series(astronaut_id: str, key: str, range: str = "24h", principal: dict = Depends(sec.rbac.require_permission("read_self"))):
        aid = backend_id(astronaut_id)
        if not sec.rbac.can_access_astronaut(principal, aid): raise HTTPException(403, "crew access denied")
        if key not in {"heartRate", "spo2", "bloodPressure", "bloodGlucose", "temperature", "sleep", "dizziness", "mood", "radiation"}: raise HTTPException(404, "indicator not found")
        uplinks = store.uplinks(aid, SERIES_WINDOW)
        readings, statuses = _collect(aid, uplinks)
        metric = INDICATORS[key][0]
        allowed = {metric, "bp_diastolic"} if key == "bloodPressure" else {metric}
        readings = _recent_per_metric([item for item in readings if item.get("metric") in allowed], 400)
        snapshot = _snapshot(uplinks) or {}
        overrides = dict(snapshot.get("overrides") or {})
        card = next((item for item in snapshot.get("indicators", []) if item.get("key") == key), None)
        if card and isinstance(card.get("baseline"), dict):
            overrides[metric] = card["baseline"]
        return series_view(key, readings, statuses, _baselines(uplinks), range,
                           overrides=overrides or None, astronaut_id=aid,
                           anchors=snapshot.get("anchors") or reading_anchors(snapshot.get("readings") or []))

    @app.get("/api/astronauts/{astronaut_id}/checkins")
    async def astronaut_checkins(astronaut_id: str, principal: dict = Depends(sec.rbac.require_permission("read_self"))):
        aid = backend_id(astronaut_id)
        if not sec.rbac.can_access_astronaut(principal, aid): raise HTTPException(403, "crew access denied")
        return [{"id": f"checkin-{item.get('ts', '')}", "astronautId": ui_id(aid),
                 "createdAt": item.get("ts", ""), "mood": item.get("mood", 3),
                 "energy": item.get("energy", 3), "dizziness": item.get("dizziness", 0),
                 "workload": item.get("workload", 3), "symptoms": item.get("symptoms", []),
                 "note": item.get("notes", "")}
                for item in store.checkins(aid, 30)]

    @app.get("/api/astronauts/{astronaut_id}/messages")
    async def astronaut_messages(astronaut_id: str, principal: dict = Depends(sec.rbac.require_permission("read_self"))):
        aid = backend_id(astronaut_id)
        if not sec.rbac.can_access_astronaut(principal, aid): raise HTTPException(403, "crew access denied")
        return [{"id": item.get("id", ""), "astronautId": ui_id(aid),
                 "reason": item.get("reason", "Crew report"), "detail": item.get("detail", ""),
                 "severity": item.get("severity", "attention"), "symptoms": item.get("symptoms", []),
                 "createdAt": item.get("created_ts", "")}
                for item in store.crew_messages(aid, 30)]

    @app.get("/api/astronauts/{astronaut_id}/plan")
    async def astronaut_plan(astronaut_id: str, principal: dict = Depends(sec.rbac.require_permission("read_self"))):
        aid = backend_id(astronaut_id)
        if not sec.rbac.can_access_astronaut(principal, aid): raise HTTPException(403, "crew access denied")
        snapshots = [item for item in store.uplinks(aid) if item["type"] == "plan_progress"]
        if not snapshots:
            return {"astronautId": ui_id(aid), "weekOf": "", "items": [], "completed": 0, "total": 0}
        payload = snapshots[-1]["payload"]
        return {"astronautId": ui_id(aid), "weekOf": payload.get("week", ""),
                "completed": int(payload.get("completed", 0)), "total": int(payload.get("total", 0)),
                "items": payload.get("items", [])}

    @app.get("/api/astronauts/{astronaut_id}/exposure")
    async def astronaut_exposure(astronaut_id: str, principal: dict = Depends(sec.rbac.require_permission("read_self"))):
        aid = backend_id(astronaut_id)
        if not sec.rbac.can_access_astronaut(principal, aid): raise HTTPException(403, "crew access denied")
        records = []
        for item in store.exposures(aid):
            cumulative = item.get("cumulative_dose", {}) or {}
            records.append({"id": item.get("event_id", "exposure"), "astronautId": ui_id(aid),
                            "missionId": f"current-{aid}", "date": str(item.get("start_ts", ""))[:10],
                            "doseMsv": float(cumulative.get("value", 0)) / 1000,
                            "symptoms": [symptom for checkin in item.get("symptom_checkins", [])
                                         for symptom in checkin.get("symptoms", [])],
                            "followUpUntil": item.get("followup_until"),
                            "note": "Received as a signed exposure record."})
        return {"astronautId": ui_id(aid), "records": records,
                "monitoringActive": _monitoring_active(records),
                "monitoringStartedAt": records[-1]["date"] if records else None,
                "monitoringUntil": _monitoring_until(records), "windowHours": 72}

    @app.get("/api/astronauts/{astronaut_id}/alerts")
    async def astronaut_alerts(astronaut_id: str, principal: dict = Depends(sec.rbac.require_permission("read_self"))):
        aid = backend_id(astronaut_id)
        if not sec.rbac.can_access_astronaut(principal, aid): raise HTTPException(403, "crew access denied")
        return _alerts(aid)

    def _alerts(aid=None):
        result = []
        seen = set()
        for item in store.list_alerts(aid, 200):
            summary = item["payload"].get("vitals_summary", item["payload"].get("psych_summary", {}))
            severity = summary.get("status", "attention")
            indicator = summary.get("indicator", "health")
            key = (item["astronaut_id"], metric_label(str(indicator)), severity)
            if not item["acknowledged"]:
                if key in seen:
                    continue
                seen.add(key)
            result.append({"id": item["alert_id"], "astronautId": ui_id(item["astronaut_id"]),
                "priority": "radiation" if "radiation" in indicator else "health", "severity": severity,
                "title": metric_label(str(indicator)), "why": " ".join(summary.get("reasons", [])),
                "createdAt": item["ts"], "acknowledged": item["acknowledged"], "source": "onboard hub", "channel": "station"})
            if len(result) >= 60:
                break
        return result

    @app.get("/api/astronauts/{astronaut_id}/missions")
    async def astronaut_missions(astronaut_id: str, principal: dict = Depends(sec.rbac.require_permission("read_self"))):
        aid = backend_id(astronaut_id)
        if not sec.rbac.can_access_astronaut(principal, aid): raise HTTPException(403, "crew access denied")
        return _mission_views(aid)

    @app.get("/api/astronauts/{astronaut_id}/radiation")
    async def astronaut_radiation(astronaut_id: str, principal: dict = Depends(sec.rbac.require_permission("read_self"))):
        aid = backend_id(astronaut_id)
        if not sec.rbac.can_access_astronaut(principal, aid): raise HTTPException(403, "crew access denied")
        uplinks = store.uplinks(aid)
        snapshot = _snapshot(uplinks) or {}
        if snapshot.get("radiation"):
            return snapshot["radiation"]
        readings, statuses = _collect(aid, uplinks)
        personal = [item for item in readings if item.get("source") == "dosimeter"]
        rates = [item for item in (personal or readings) if item.get("metric") in {"dose_rate", "radiation_dose_rate"}]
        cumulative = next((float(item["value"]) for item in reversed(readings)
                           if item.get("metric") == "cumulative_dose"), 0.0)
        latest = float(rates[-1]["value"]) if rates else 0.0
        level = next((x.get("status") for x in reversed(statuses)
                      if "radiation" in str(x.get("indicator", ""))), "normal")
        events = []
        seen = set()
        for item in rates[-20:]:
            hourly = str(item.get("ts", ""))[:13]
            if hourly in seen:
                continue
            seen.add(hourly)
            events.append({"id": f"{item.get('ts', '')}", "doseRate": float(item.get("value", 0)),
                           "startedAt": item.get("ts", ""), "endedAt": item.get("ts", ""),
                           "note": "Personal dosimeter reading." if personal else "Area monitor reading."})
        budget = 600.0
        cumulative_msv = cumulative / 1000
        return {"astronautId": ui_id(aid), "doseRate": round(latest, 2), "unit": "µSv/h",
            "cumulativeMsv": cumulative_msv, "budgetMsv": budget,
            "budgetUsedPct": min(100.0, cumulative_msv / budget * 100) if budget else 0.0,
            "status": level, "alertActive": level == "urgent", "personalDosimeterAvailable": bool(personal),
            "shelter": {"zone": "Cabin shielded sleep station", "direction": "behind",
                        "distanceM": 4,
                        "instructions": ["Move to the shielded sleep station and close the stowage cover.",
                                         "Take the personal dosimeter with you and re-read it there.",
                                         "Tell your crewmate and stay on the link until the reading settles."]},
            "latestEvent": events[-1] if events else None, "events": events[-6:]}

    @app.get("/api/security/state")
    async def security_state(principal: dict = Depends(sec.rbac.require_permission("read_crew"))):
        return {"level": "ok", "headline": "Local encrypted store active", "lastEventAt": "",
            "checks": [{"id": "confidentiality", "label": "Encrypted storage", "state": "ok", "detail": "Ground data is encrypted at rest."},
                       {"id": "integrity", "label": "Signed uplinks", "state": "ok", "detail": "Received envelopes are signature checked."},
                       {"id": "secure_communication", "label": "Local link", "state": "ok", "detail": "Services are bound to this computer."},
                       {"id": "offline_backup", "label": "Offline backup", "state": "ok", "detail": "Encrypted backup is maintained locally."}]}

    @app.get("/api/crew/{astronaut_id}")
    async def crew_member(astronaut_id: str, principal: dict = Depends(sec.rbac.require_permission("read_self"))):
        if not sec.rbac.can_access_astronaut(principal, astronaut_id):
            raise HTTPException(403, "crew access denied")
        member = store.get_crew(astronaut_id)
        if member is None: raise HTTPException(404, "crew member not found")
        sec.audit_log(principal["username"], "crew_member_access", astronaut_id, {})
        return member

    @app.get("/api/crew/{astronaut_id}/history")
    async def crew_history(astronaut_id: str, principal: dict = Depends(sec.rbac.require_permission("read_self"))):
        if not sec.rbac.can_access_astronaut(principal, astronaut_id):
            raise HTTPException(403, "crew history access denied")
        if store.get_crew(astronaut_id) is None: raise HTTPException(404, "crew member not found")
        sec.audit_log(principal["username"], "history_access", astronaut_id, {})
        return store.history(astronaut_id)

    @app.get("/api/missions")
    async def missions(principal: dict = Depends(sec.rbac.require_permission("read_crew"))):
        sec.audit_log(principal["username"], "mission_list_access", "missions", {})
        return store.missions()

    @app.get("/api/alerts")
    async def alerts(astronaut_id: str | None = None,
                     principal: dict = Depends(sec.rbac.require_permission("read_self"))):
        if astronaut_id and not sec.rbac.can_access_astronaut(principal, astronaut_id):
            raise HTTPException(403, "alert access denied")
        sec.audit_log(principal["username"], "alerts_access", astronaut_id or "crew", {})
        result = _alerts(astronaut_id)
        if principal.get("role") == "astronaut":
            result = [alert for alert in result if backend_id(alert["astronautId"]) == principal.get("astronaut_id")]
        return result

    @app.post("/api/alerts/{alert_id}/ack")
    async def acknowledge(alert_id: str, item: Ack,
                          principal: dict = Depends(sec.rbac.require_permission("ack_alert"))):
        if not store.acknowledge(alert_id, principal["username"]):
            raise HTTPException(404, "alert not found")
        sec.audit_log(principal["username"], "alert_acknowledge", alert_id, {"note": item.note})
        return {"alert_id": alert_id, "acknowledged": True}

    @app.post("/api/commands", status_code=202)
    async def issue_command(item: Command,
                            principal: dict = Depends(sec.rbac.require_permission("issue_command"))):
        astronaut_id = item.astronautId or item.astronaut_id or str(item.payload.get("astronaut_id") or "")
        if not astronaut_id:
            raise HTTPException(422, "astronautId is required")
        ui_type = item.type or str(item.payload.get("ui_type") or "")
        bundle_type = item.command_type or COMMAND_BUNDLES.get(ui_type)
        if bundle_type not in set(COMMAND_BUNDLES.values()):
            raise HTTPException(422, "unsupported command bundle type")
        ui_type = ui_type or bundle_type
        command_payload = {key: value for key, value in item.payload.items() if key not in {"astronaut_id", "ui_type"}}
        duplicate = next((row for row in store.commands()
                          if row["astronaut_id"] == astronaut_id and row["type"] == ui_type
                          and row["status"] == "pending" and row["payload"] == command_payload), None)
        if duplicate:
            return {"id": duplicate["id"], "msg_id": duplicate["msg_id"], "queued": True,
                    "astronautId": astronaut_id, "type": ui_type, "payload": command_payload,
                    "status": "pending", "createdAt": duplicate["created_ts"], "deliveredAt": None,
                    "createdBy": duplicate["created_by"], "audit": [],
                    "bundle": {"created_ts": duplicate["created_ts"]}}
        bundle_payload = {**item.payload, "astronaut_id": astronaut_id, "ui_type": ui_type or bundle_type}
        bundle = sec.sign_bundle(sec.make_bundle(bundle_type, bundle_payload))
        envelope = sec.make_envelope(bundle_type, {"bundle": bundle}, direction="downlink",
                                     priority=2, node_id="ground-01")
        signed = sec.sign_envelope(envelope)
        queue.enqueue(signed)
        store.save_command(signed["msg_id"], astronaut_id, ui_type, command_payload,
                           bundle["created_ts"], signed["msg_id"], created_by=principal["username"])
        store.create_backup()
        sec.audit_log(principal["username"], "issue_command", bundle_type,
                      {"msg_id": signed["msg_id"], "queued": True})
        return {"id": signed["msg_id"], "msg_id": signed["msg_id"], "queued": True,
                "astronautId": astronaut_id, "type": ui_type, "payload": command_payload,
                "status": "pending", "createdAt": bundle["created_ts"], "deliveredAt": None,
                "createdBy": principal["username"], "audit": [], "bundle": bundle}

    @app.get("/api/commands")
    async def list_commands(principal: dict = Depends(sec.rbac.require_permission("read_crew"))):
        sec.audit_log(principal["username"], "command_list_access", "commands", {})
        return store.commands()

    @app.get("/api/link/state")
    async def link_state(principal: dict = Depends(sec.rbac.require_permission("read_crew"))):
        connected = bool(queue.get_meta("connected", True))
        return {"connected": connected, "mode": "connected" if connected else "autonomous",
                "delay_seconds": float(queue.get_meta("delay_seconds", 0) or 0),
                "queue_size": queue.size(), "last_sync_ts": queue.get_meta("last_sync_ts"),
                "staleness": store.staleness(stale_after)}

    @app.get("/api/backup/state")
    async def backup_state(principal: dict = Depends(sec.rbac.require_permission("read_crew"))):
        return {**store.backup_state(), "queue_size": queue.size()}

    @app.get("/health")
    async def health(): return {"status": "ok", "mode": "last-known-state"}

    return app


app = create_app()
