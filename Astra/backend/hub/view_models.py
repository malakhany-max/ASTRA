"""Presentation adapters for the Astronaut App's documented view models."""

from __future__ import annotations

from datetime import datetime, timezone

from .series_fill import fill_samples

ID_ALIASES = {"ast-zain": "A-07", "ast-maya": "A-03", "ast-idris": "A-11"}
REVERSE_ID_ALIASES = {value: key for key, value in ID_ALIASES.items()}
INDICATORS = {
    "heartRate": ("heart_rate", "Heart rate", "bpm"),
    "spo2": ("spo2", "SpO₂", "%"),
    "bloodPressure": ("bp_systolic", "Blood pressure", "mmHg"),
    "bloodGlucose": ("blood_glucose", "Blood glucose", "mmol/L"),
    "temperature": ("skin_temp", "Temperature", "°C"),
    "sleep": ("sleep_duration", "Sleep", "h"),
    "dizziness": ("dizziness_self_report", "Dizziness", "score"),
    "mood": ("mood", "Mood", "/5"),
    "radiation": ("dose_rate", "Radiation dose rate", "µSv/h"),
}


def backend_id(value: str) -> str:
    return ID_ALIASES.get(value, value)


def ui_id(value: str) -> str:
    return REVERSE_ID_ALIASES.get(value, value)


def _worst(statuses: list[dict]) -> str:
    levels = {"normal": 0, "unknown": 0, "attention": 1, "urgent": 2}
    return max((item.get("status", "unknown") for item in statuses), key=lambda level: levels.get(level, 0), default="unknown")


def _latest(readings: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in readings:
        grouped.setdefault(str(item.get("metric")), []).append(item)
    for items in grouped.values():
        items.sort(key=lambda item: str(item.get("ts", "")))
    return grouped


def reading_anchors(readings: list[dict]) -> dict[str, dict]:
    """Newest value per metric, shared by both apps so history curves line up."""
    anchors = {}
    for metric, items in _latest(readings).items():
        latest = items[-1]
        if not isinstance(latest.get("value"), (int, float)):
            continue
        anchors[metric] = {"t": latest.get("ts", ""), "value": float(latest["value"])}
    if "bp_systolic" in anchors and "bp_diastolic" in anchors:
        anchors["bp_systolic"]["secondary"] = anchors["bp_diastolic"]["value"]
    return anchors


BASELINE_DEFAULTS = {
    "heart_rate": (62.0, 7.0), "spo2": (98.0, 1.0), "bp_systolic": (118.0, 8.0),
    "blood_glucose": (5.4, 0.8), "skin_temp": (36.5, 0.3), "sleep_duration": (7.6, 0.8),
    "dizziness_self_report": (0.5, 0.8), "mood": (4.0, 0.7), "dose_rate": (8.0, 3.0),
}


def _baseline(state: dict, metric: str, value: float,
              overrides: dict | None = None) -> dict[str, float]:
    override = (overrides or {}).get(metric)
    if isinstance(override, dict) and isinstance(override.get("low"), (int, float)) \
            and isinstance(override.get("high"), (int, float)):
        return {"low": float(override["low"]), "high": float(override["high"])}
    for phase in state.get("baselines", {}).values():
        item = phase.get(metric)
        if item and isinstance(item.get("mean"), (int, float)):
            mean, scale = float(item["mean"]), float(item.get("scale", 0))
            return {"low": mean - scale, "high": mean + scale}
    center, spread = BASELINE_DEFAULTS.get(metric, (value or 0.0, max(1.0, abs(value or 0.0) * 0.15)))
    return {"low": round(center - spread, 3), "high": round(center + spread, 3)}


def indicator_views(readings: list[dict], statuses: list[dict], state: dict,
                    overrides: dict | None = None) -> list[dict]:
    grouped = _latest(readings)
    status_by_metric = {item.get("indicator"): item for item in statuses}
    views = []
    for key, (metric, label, unit) in INDICATORS.items():
        samples = grouped.get(metric, [])
        if metric == "bp_systolic":
            secondary_values = grouped.get("bp_diastolic", [])
            if not samples:
                continue
        elif not samples:
            continue
        current = samples[-1]
        value = float(current["value"])
        prior = float(samples[-2]["value"]) if len(samples) > 1 else value
        status = status_by_metric.get(metric, {})
        if key == "radiation":
            status = status_by_metric.get("radiation_dose_rate", status)
        if key == "bloodPressure":
            secondary = float(secondary_values[-1]["value"]) if secondary_values else None
        else:
            secondary = None
        views.append({
            "key": key, "label": label, "unit": unit, "value": value, "secondary": secondary,
            "status": status.get("status", "normal"),
            "reason": " ".join(status.get("reasons", [])) or "No change from the last trusted measurement.",
            "updatedAt": current.get("ts", ""), "baseline": _baseline(state, metric, value, overrides),
            "trend": "up" if value > prior else "down" if value < prior else "stable",
            "precision": 1 if key in {"bloodGlucose", "temperature", "sleep", "radiation"} else 0,
        })
    return views


def series_view(key: str, readings: list[dict], statuses: list[dict], state: dict, range_name: str,
                overrides: dict | None = None, astronaut_id: str = "unknown",
                anchors: dict | None = None) -> dict:
    metric, label, unit = INDICATORS[key]
    grouped = _latest(readings)
    days = {"24h": 1, "7d": 7, "30d": 30}.get(range_name, 1)
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    real: list[dict] = []
    for sample in grouped.get(metric, []):
        try:
            stamp = datetime.fromisoformat(str(sample["ts"]).replace("Z", "+00:00")).timestamp()
        except (KeyError, ValueError):
            continue
        if stamp >= cutoff:
            real.append({"t": sample.get("ts", ""), "value": sample["value"]})
    if key == "bloodPressure":
        dia_by_ts = {str(item.get("ts", "")): item["value"] for item in grouped.get("bp_diastolic", [])}
        for item in real:
            item["secondary"] = dia_by_ts.get(str(item["t"]))
    last = float(real[-1]["value"]) if real else 0.0
    secondary_mean = float(real[-1]["secondary"]) if real and real[-1].get("secondary") is not None else None
    baseline = _baseline(state, metric, last, overrides)
    samples = fill_samples(astronaut_id, metric, range_name, real,
                           baseline["low"], baseline["high"], secondary_mean,
                           anchor=(anchors or {}).get(metric))
    return {"key": key, "label": label, "unit": unit, "baseline": baseline,
            "range": range_name, "samples": samples}


ALERT_LABELS = {
    "radiation_dose_rate": "Radiation dose rate",
    "radiation_cumulative": "Cumulative radiation dose",
    "post_exposure_followup": "Post-exposure follow-up",
    "gravity_transition": "Gravity transition",
    "hrv_rmssd": "Heart-rate variability",
    "activity_level": "Activity level",
    "dose_rate": "Radiation dose rate",
    "cumulative_dose": "Cumulative radiation dose",
    "skin_temp": "Skin temperature",
    "heart_rate": "Resting heart rate",
    "sleep_duration": "Sleep duration",
    "blood_glucose": "Blood glucose",
    "bp_systolic": "Blood pressure",
    "dizziness_self_report": "Dizziness",
}


def metric_label(name: str) -> str:
    if name in ALERT_LABELS:
        return ALERT_LABELS[name]
    if name in INDICATORS:
        return INDICATORS[name][1]
    return name.replace("_", " ").strip().title()


def alert_views(statuses: list[dict], acknowledged: set[str] | None = None) -> list[dict]:
    acknowledged = acknowledged or set()
    latest: dict[str, dict] = {}
    for item in statuses:
        metric = str(item.get("indicator", "health"))
        current = latest.get(metric)
        if current is None or str(item.get("computed_ts", "")) >= str(current.get("computed_ts", "")):
            latest[metric] = item
    result = []
    for metric, item in latest.items():
        if item.get("status") == "normal":
            continue
        alert_id = f"{item.get('astronaut_id', 'unknown')}:{metric}:{item.get('status', 'attention')}"
        result.append({
            "id": alert_id,
            "astronautId": ui_id(str(item.get("astronaut_id", "unknown"))),
            "priority": "radiation" if metric.startswith("radiation") else "health",
            "severity": item.get("status", "attention"), "title": metric_label(metric),
            "why": " ".join(item.get("reasons", [])), "createdAt": item.get("computed_ts", ""),
            "acknowledged": alert_id in acknowledged, "source": "onboard hub", "channel": "station",
        })
    result.sort(key=lambda entry: str(entry.get("createdAt", "")), reverse=True)
    return result
