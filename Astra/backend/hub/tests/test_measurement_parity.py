"""The Ground must render exactly the measurements the onboard hub renders."""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
for part in ("engine", "link", "attack_sim", "simulators"):
    sys.path.insert(0, str(ROOT / part))
sys.path.insert(0, str(ROOT.parent / "security"))
sys.path.insert(0, str(ROOT / "ground-backend"))

import astra_security as sec
from astra_ground.app import create_app as create_ground_app
from astra_ground.store import GroundStore
from astra_link import LinkQueue
from hub.app import create_app as create_hub_app
from hub.store import HubStore

READINGS = [
    ("heart_rate", 61.0, "bpm", "wearable"),
    ("spo2", 98.0, "%", "wearable"),
    ("bp_systolic", 117.0, "mmHg", "clinical_device"),
    ("bp_diastolic", 75.0, "mmHg", "clinical_device"),
    ("blood_glucose", 5.3, "mmol/L", "clinical_device"),
    ("skin_temp", 36.5, "degC", "wearable"),
    ("sleep_duration", 7.4, "h", "wearable"),
    ("mood", 4.0, "scale_1_5", "self_report"),
    ("dizziness_self_report", 0.0, "scale_0_3", "self_report"),
    ("dose_rate", 8.4, "uSv/h", "dosimeter"),
    ("cumulative_dose", 12400.0, "uSv", "dosimeter"),
]


def _pair(tmp_path):
    hub = TestClient(create_hub_app(store=HubStore(tmp_path / "hub.db"),
                                    queue=LinkQueue(tmp_path / "hub-link.db")))
    ground = TestClient(create_ground_app(store=GroundStore(path=tmp_path / "ground.db",
                                                            backup_path=tmp_path / "backup.enc"),
                                          queue=LinkQueue(tmp_path / "ground-link.db")))
    return hub, ground


def _ingest_and_deliver(hub, ground, metrics=READINGS):
    run = uuid.uuid4().hex[:8]
    # Off-grid seconds keep the samples clear of the synthetic fill timeline.
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(hours=3, seconds=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for metric, value, unit, source in metrics:
        reading = {"schema": "astra.reading.v1", "astronaut_id": "A-07", "metric": metric,
                   "value": value, "unit": unit, "source": source, "quality": 1.0, "ts": ts}
        response = hub.post("/ingest", json=sec.sign_reading(reading, f"parity-{run}-{metric}"))
        assert response.status_code == 202, response.text
        assert response.json()["classification"] == "trusted", metric
    # The link sends one summary per cycle; the next cycle carries the whole set.
    hub.app.state.store.set_kv("summary_sent:A-07", 0)
    flush_ts = (now - timedelta(seconds=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    flush = {"schema": "astra.reading.v1", "astronaut_id": "A-07", "metric": "heart_rate",
             "value": 61.5, "unit": "bpm", "source": "wearable", "quality": 1.0, "ts": flush_ts}
    assert hub.post("/ingest", json=sec.sign_reading(flush, f"parity-{run}-cycle")).status_code == 202
    envelopes = hub.app.state.link_queue.next_batch(200)
    assert envelopes
    for envelope in envelopes:
        assert ground.post("/uplink", json=envelope).status_code == 202
    return {ts, flush_ts}


def _viewer_headers():
    return {"Authorization": "Bearer " + sec.rbac.create_session(
        {"username": "parity-viewer", "role": "viewer", "astronaut_id": None})}


def test_ground_indicators_match_the_hub(tmp_path):
    hub, ground = _pair(tmp_path)
    _ingest_and_deliver(hub, ground)
    hub_cards = hub.get("/api/astronauts/ast-zain/indicators").json()
    ground_cards = ground.get("/api/astronauts/ast-zain/indicators", headers=_viewer_headers()).json()

    assert [card["key"] for card in ground_cards] == [card["key"] for card in hub_cards]
    assert ground_cards == hub_cards

    hub_radiation = hub.get("/api/astronauts/ast-zain/radiation").json()
    ground_radiation = ground.get("/api/astronauts/ast-zain/radiation", headers=_viewer_headers()).json()
    assert ground_radiation == hub_radiation


def test_ground_series_span_every_indicator(tmp_path):
    hub, ground = _pair(tmp_path)
    sent_at = _ingest_and_deliver(hub, ground)
    for key in ("heartRate", "spo2", "bloodPressure", "bloodGlucose", "temperature",
                "sleep", "dizziness", "mood", "radiation"):
        hub_series = hub.get(f"/api/astronauts/ast-zain/indicators/{key}?range=24h").json()
        ground_series = ground.get(f"/api/astronauts/ast-zain/indicators/{key}?range=24h",
                                   headers=_viewer_headers()).json()
        assert ground_series["baseline"] == hub_series["baseline"], key
        hub_points = [sample for sample in hub_series["samples"] if sample["t"] in sent_at]
        ground_points = [sample for sample in ground_series["samples"] if sample["t"] in sent_at]
        assert ground_points == hub_points, key


def test_ground_series_history_matches_the_hub(tmp_path):
    hub, ground = _pair(tmp_path)
    sent_at = _ingest_and_deliver(hub, ground)
    for key in ("heartRate", "spo2", "bloodPressure", "bloodGlucose", "temperature",
                "sleep", "dizziness", "mood", "radiation"):
        hub_samples = {sample["t"]: sample for sample in
                       hub.get(f"/api/astronauts/ast-zain/indicators/{key}?range=24h").json()["samples"]
                       if sample["t"] not in sent_at}
        ground_samples = {sample["t"]: sample for sample in
                          ground.get(f"/api/astronauts/ast-zain/indicators/{key}?range=24h",
                                     headers=_viewer_headers()).json()["samples"]
                          if sample["t"] not in sent_at}
        shared = sorted(set(hub_samples) & set(ground_samples))
        assert shared, key
        assert [hub_samples[stamp] for stamp in shared] == [ground_samples[stamp] for stamp in shared], key
