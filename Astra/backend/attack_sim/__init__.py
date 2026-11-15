"""Offline attack scenarios for ASTRA's security SDK."""

from __future__ import annotations

import base64
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

_security_source = str(Path(__file__).resolve().parents[2] / "security")
if _security_source not in sys.path:
    sys.path.insert(0, _security_source)

import astra_security as sec

__all__ = ["SCENARIOS", "run_scenario", "run_all", "run_evaluation", "trigger_scenario"]

SCENARIOS = (
    "forged_signature",
    "replay",
    "spoofed_device",
    "tampered_in_transit",
    "timestamp_manipulation",
    "dosimeter_fake_spike",
    "dosimeter_false_all_clear",
    "flatline_sensor_fault",
)
_ALIASES = {
    "unpaired_device": "spoofed_device",
    "tampered_message": "tampered_in_transit",
    "implausible_value": "dosimeter_fake_spike",
    "attack_forged": "forged_signature",
    "attack_replay": "replay",
    "attack_spoof": "spoofed_device",
    "attack_dosimeter_fake": "dosimeter_fake_spike",
}


def _reading(device_id: str, *, metric: str = "heart_rate", value: float = 72.0,
             source: str = "wearable", unit: str = "bpm") -> dict[str, Any]:
    output = {
        "schema": "astra.reading.v1", "device_id": device_id,
        "astronaut_id": "A-07", "metric": metric, "value": value,
        "unit": unit, "source": source, "quality": 0.95,
    }
    return output


def _classify(message: dict, attack: str, *, context: dict | None = None) -> dict:
    verify_context = {"attack": attack}
    if context:
        verify_context.update(context)
    return sec.verify_and_classify(message, verify_context)


def _run(name: str) -> dict[str, Any]:
    device_id = f"attack-sim-{name}"
    key = sec.ensure_device_key(device_id)
    captured: list[dict] = []
    sec.set_uplink_sink(captured.append)
    store = sec.get_store()
    before_events = store.count_events()
    expected = "suspect_tamper"
    start = time.perf_counter()
    message: dict

    if name in ("forged_signature", "tampered_in_transit"):
        message = sec.sign_reading_with_key(_reading(device_id), key, device_id=device_id)
        if name == "forged_signature":
            message["sig"] = base64.b64encode(b"\0" * 64).decode("ascii")
        else:
            message["value"] = 73.0
        result = _classify(message, name)
    elif name == "replay":
        message = sec.sign_reading_with_key(_reading(device_id), key, device_id=device_id)
        initial = sec.verify_and_classify(dict(message), {"raise_events": False})
        result = _classify(dict(message), name)
        result["initial_classification"] = initial["classification"]
    elif name == "spoofed_device":
        rogue_id = f"{device_id}-rogue"
        rogue_key, _ = sec.generate_keypair()
        message = sec.sign_reading_with_key(_reading(rogue_id), rogue_key, device_id=rogue_id)
        result = _classify(message, name)
    elif name == "timestamp_manipulation":
        old_ts = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        message = sec.sign_reading_with_key(_reading(device_id), key, device_id=device_id)
        message["ts"] = old_ts
        message = sec.sign_reading_with_key(message, key, device_id=device_id, advance=False)
        result = _classify(message, name)
    elif name in ("dosimeter_fake_spike", "dosimeter_false_all_clear"):
        value = 500.0 if name == "dosimeter_fake_spike" else 1.0
        message = sec.sign_reading_with_key(
            _reading(device_id, metric="dose_rate", value=value, source="dosimeter", unit="uSv/h"),
            key, device_id=device_id,
        )
        expected = "suspect_fault"
        result = _classify(message, name, context={"cross:dose_rate:area_monitor": 40.0})
    elif name == "flatline_sensor_fault":
        expected = "suspect_fault"
        results = []
        message = {}
        for _ in range(8):
            message = sec.sign_reading_with_key(_reading(device_id, value=72.0), key, device_id=device_id)
            results.append(sec.verify_and_classify(message))
        result = results[-1]
        result["samples_checked"] = len(results)
        result["any_fault_detected"] = any(r["classification"] == "suspect_fault" for r in results)
    else:
        raise ValueError(f"unknown scenario {name!r}; choose from: {', '.join(SCENARIOS)}")

    latency_ms = (time.perf_counter() - start) * 1000
    classification = result["classification"]
    detected = (result.get("any_fault_detected", False) or classification == expected)
    if name == "replay":
        detected = result.get("initial_classification") == "trusted" and classification == expected
    event_count = store.count_events() - before_events
    sec.set_uplink_sink(None)
    output = {
        "scenario": name,
        "detected": detected,
        "expected_classification": expected,
        "classification": classification,
        "reasons": result["reasons"],
        "latency_ms": round(latency_ms, 3),
        "security_event_created": event_count > 0,
        "security_events_created": event_count,
        "uplink_envelope_created": bool(captured),
        "uplink_envelopes_created": len(captured),
        "message": message,
        "result": result,
    }
    if name == "replay":
        output["initial"] = {"classification": result["initial_classification"]}
    return output


_SCENARIO_RUNNERS: dict[str, Callable[[], dict[str, Any]]] = {}


def run_scenario(name: str) -> dict[str, Any]:
    """Run an attack by name; return detection, classification, latency and event data."""
    name = _ALIASES.get(name, name)
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario {name!r}; choose from: {', '.join(SCENARIOS)}")
    return _SCENARIO_RUNNERS.get(name, lambda: _run(name))()


def _runner(name: str) -> Callable[[], dict[str, Any]]:
    return lambda: _run(name)


for _scenario in SCENARIOS:
    _function = _runner(_scenario)
    _function.__name__ = f"attack_{_scenario}"
    globals()[_function.__name__] = _function
    _SCENARIO_RUNNERS[_scenario] = _function
    __all__.append(_function.__name__)


def trigger_scenario(name: str) -> dict[str, Any]:
    """Hub-facing entry point; accepts shared API names such as ``attack_forged``."""
    return run_scenario(name)


def run_all() -> list[dict[str, Any]]:
    """Run each of the eight attacks once, using an isolated device identity."""
    return [run_scenario(name) for name in SCENARIOS]


def run_evaluation(scenarios: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Run attacks plus trusted controls and calculate evaluation metrics."""
    attacks = run_all() if scenarios is None else [run_scenario(name) for name in scenarios]
    control_id = "attack-sim-benign-control"
    control_key = sec.ensure_device_key(control_id)
    sec.set_uplink_sink(lambda _envelope: None)
    control_message = sec.sign_reading_with_key(_reading(control_id), control_key, device_id=control_id)
    control_result = sec.verify_and_classify(control_message)
    sec.set_uplink_sink(None)
    false_positives = int(control_result["classification"] != "trusted")
    detections = sum(item["detected"] for item in attacks)
    return {
        "summary": {
            "attack_count": len(attacks),
            "detected_count": detections,
            "detection_rate": round(detections / len(attacks), 4) if attacks else 0.0,
            "control_count": 1,
            "false_positive_count": false_positives,
            "false_positive_rate": float(false_positives),
        },
        "control": {"classification": control_result["classification"], "false_positive": bool(false_positives)},
        "attacks": attacks,
    }
