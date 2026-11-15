"""Deterministic history so a fresh hub still shows honest 24h/7d/30d trends."""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone

FRAMES = {
    "24h": (timedelta(hours=24), timedelta(minutes=15)),
    "7d": (timedelta(days=7), timedelta(hours=1)),
    "30d": (timedelta(days=30), timedelta(hours=3)),
}

LIMITS = {
    "heart_rate": (42, 150, 0),
    "spo2": (91, 100, 1),
    "bp_systolic": (85, 165, 0),
    "bp_diastolic": (52, 105, 0),
    "blood_glucose": (3, 11, 1),
    "skin_temp": (35.6, 38.2, 1),
    "sleep_duration": (3.5, 10, 1),
    "dizziness_self_report": (0, 3, 0),
    "mood": (1, 5, 0),
    "dose_rate": (0.2, 1000, 1),
}

MEANS = {
    "heart_rate": 62.0,
    "spo2": 98.0,
    "bp_systolic": 118.0,
    "blood_glucose": 5.4,
    "skin_temp": 36.5,
    "sleep_duration": 7.6,
    "dizziness_self_report": 0.4,
    "mood": 4.0,
    "dose_rate": 8.0,
}

DAILY_LOG_HOUR = {"sleep_duration": 7, "mood": 20, "dizziness_self_report": 20}


def _draw(*parts) -> float:
    digest = hashlib.blake2s(":".join(str(part) for part in parts).encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") / 2**64


def _noise(key: str, ts: float, period: float) -> float:
    """Smooth value noise so neighbouring samples stay continuous."""
    position = ts / period
    node = math.floor(position)
    fraction = position - node
    start = _draw(key, node) - 0.5
    end = _draw(key, node + 1) - 0.5
    ease = fraction * fraction * (3 - 2 * fraction)
    return start + (end - start) * ease


def _turbulence(astronaut_id: str, metric: str, ts: float) -> float:
    key = f"{astronaut_id}:{metric}:noise"
    return (0.6 * _noise(key + ":slow", ts, 5 * 3600)
            + 0.3 * _noise(key + ":mid", ts, 55 * 60)
            + 0.1 * _noise(key + ":fast", ts, 11 * 60))


def _day_start(ts: datetime) -> datetime:
    local = ts.astimezone()
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def _meal(hour: float, at: float) -> float:
    return math.exp(-((hour - at) ** 2) / 1.6)


def _clamp(value: float, metric: str) -> float:
    low, high, _ = LIMITS.get(metric, (0.0, 100.0, 1))
    return min(high, max(low, value))


def _continuous(astronaut_id: str, metric: str, ts: datetime, mean: float) -> float:
    local = ts.astimezone()
    hour = local.hour + local.minute / 60
    stamp = ts.timestamp()
    day = _noise(f"{astronaut_id}:{metric}:day", stamp, 86400)
    noise = _turbulence(astronaut_id, metric, stamp)

    if metric == "heart_rate":
        value = (mean + 7 * math.cos((hour - 15) * math.pi * 2 / 24)
                 + 3.2 * _meal(hour, 7.5) + 2.4 * _meal(hour, 12.5) + 3 * _meal(hour, 17.5)
                 + 2.5 * day + 2.4 * noise)
    elif metric == "spo2":
        value = mean + 0.3 * math.cos((hour - 14) * math.pi * 2 / 24) + 0.3 * day + 0.25 * noise
    elif metric == "bp_systolic":
        value = (mean + 5 * math.cos((hour - 16) * math.pi * 2 / 24)
                 + 2.5 * _meal(hour, 13) + 3 * day + 2.5 * noise)
    elif metric == "blood_glucose":
        value = (mean - 0.15 + 1.6 * _meal(hour, 8) + 1.9 * _meal(hour, 13)
                 + 1.5 * _meal(hour, 19) + 0.25 * day + 0.15 * noise)
    elif metric == "skin_temp":
        value = mean - 0.08 + 0.26 * math.cos((hour - 16) * math.pi * 2 / 24) + 0.06 * day + 0.05 * noise
    elif metric == "dose_rate":
        storm_day = _day_start(ts).timestamp()
        storm = 12 * math.exp(-((hour - 14) ** 2) / 1.5) if _draw(f"{astronaut_id}:storm", storm_day) < 1 / 21 else 0.0
        value = mean + storm + 0.3 * day + 0.25 * noise
    else:
        value = mean + 4 * day + 3 * noise
    return _clamp(value, metric)


def _daily(astronaut_id: str, metric: str, day: datetime, mean: float) -> float:
    start = day.timestamp()
    drift = _noise(f"{astronaut_id}:{metric}:daily", start, 86400)
    roll = _draw(f"{astronaut_id}:{metric}:roll", start)
    if metric == "sleep_duration":
        return _clamp(mean + 2.8 * drift, metric)
    if metric == "mood":
        return round(_clamp(3.7 + 2.6 * drift, metric))
    if metric == "dizziness_self_report":
        return 2 if roll > 0.95 else 1 if roll > 0.78 else 0
    return _clamp(mean, metric)


def _diastolic(astronaut_id: str, ts: datetime, base: float, systolic: float, mean: float) -> float:
    noise = _turbulence(astronaut_id, "diastolic", ts.timestamp())
    return _clamp(base + 0.35 * (systolic - mean) + 1.4 * noise, "bp_diastolic")


def _anchor(rows: list[dict], anchor: datetime, target: float, model: float, window: float, field: str = "value") -> None:
    delta = target - model
    if abs(delta) < 1e-9:
        return
    for row in rows:
        if field not in row:
            continue
        remaining = 1 - max(0.0, (anchor - row["ts"]).total_seconds()) / window
        if remaining <= 0:
            continue
        row[field] += delta * (remaining * remaining * (3 - 2 * remaining))


def _continuous_rows(astronaut_id: str, metric: str, start: datetime, now: datetime,
                     span: timedelta, step: timedelta, mean: float,
                     secondary_mean: float | None) -> list[dict]:
    points = int((now - start) / step)
    rows = [{"ts": start + step * index, "value": _continuous(astronaut_id, metric, start + step * index, mean)}
            for index in range(points + 1)]
    if metric == "bp_systolic":
        base = secondary_mean if secondary_mean is not None else mean - 38
        for row in rows:
            row["secondary"] = _diastolic(astronaut_id, row["ts"], base, row["value"], mean)
    return rows


def _daily_rows(astronaut_id: str, metric: str, start: datetime, now: datetime, mean: float) -> list[dict]:
    log_hour = DAILY_LOG_HOUR[metric]
    cursor = _day_start(start)
    rows: list[dict] = []
    previous: dict | None = None
    while cursor <= now:
        log = cursor.replace(hour=log_hour)
        entry = {"ts": log, "value": _daily(astronaut_id, metric, cursor, mean)}
        if log < start:
            previous = entry
        elif log <= now:
            rows.append(entry)
        cursor += timedelta(days=1)
    if len(rows) < 2 and previous is not None:
        rows.insert(0, previous)
    if len(rows) < 2 and rows:
        rows.append({"ts": now, "value": rows[-1]["value"]})
    return rows


def _parse(stamp: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None


def _downsample(real: list[dict], step: timedelta) -> list[tuple[datetime, dict]]:
    buckets: dict[int, tuple[datetime, dict]] = {}
    for item in real:
        stamp = _parse(item.get("t"))
        if stamp is None:
            continue
        buckets[int(stamp.timestamp() // step.total_seconds())] = (stamp, item)
    return [buckets[key] for key in sorted(buckets)]


def fill_samples(
    astronaut_id: str,
    metric: str,
    range_name: str,
    real: list[dict],
    baseline_low: float,
    baseline_high: float,
    secondary_mean: float | None = None,
    now: datetime | None = None,
    anchor: dict | None = None,
) -> list[dict]:
    span, step = FRAMES.get(range_name, FRAMES["24h"])
    # Snap to the step grid so both apps render identical synthetic timestamps.
    now = now or datetime.now(timezone.utc)
    now = datetime.fromtimestamp(math.floor(now.timestamp() / step.total_seconds()) * step.total_seconds(),
                                 timezone.utc)
    start = now - span
    mean = (baseline_low + baseline_high) / 2 if baseline_high > baseline_low else MEANS.get(metric, 0.0)
    precision = LIMITS.get(metric, (0, 100, 1))[2]

    if metric in DAILY_LOG_HOUR:
        rows = _daily_rows(astronaut_id, metric, start, now, mean)
    else:
        rows = _continuous_rows(astronaut_id, metric, start, now, span, step, mean, secondary_mean)

    samples = _downsample(real, step)
    if metric not in DAILY_LOG_HOUR:
        # Prefer the shared anchor so every viewer draws the same curve tail.
        last_stamp, anchor_value, anchor_secondary = None, None, None
        if anchor and _parse(anchor.get("t")):
            last_stamp = _parse(anchor["t"])
            anchor_value = anchor.get("value")
            anchor_secondary = anchor.get("secondary")
        elif samples:
            last_stamp, last_item = samples[-1]
            anchor_value = last_item["value"]
            anchor_secondary = last_item.get("secondary")
        if last_stamp is not None and isinstance(anchor_value, (int, float)):
            window = max(step.total_seconds(), 45 * 60) if metric == "dose_rate" \
                else min(6 * 3600, max(step.total_seconds() * 2, span.total_seconds() * 0.1))
            _anchor(rows, last_stamp, float(anchor_value),
                    _continuous(astronaut_id, metric, last_stamp, mean), window)
            if metric == "bp_systolic" and isinstance(anchor_secondary, (int, float)):
                model = _diastolic(astronaut_id, last_stamp,
                                   secondary_mean if secondary_mean is not None else mean - 38,
                                   _continuous(astronaut_id, metric, last_stamp, mean), mean)
                _anchor(rows, last_stamp, float(anchor_secondary), model, window, "secondary")

    merged: dict[str, dict] = {}
    for row in rows:
        item = {"t": row["ts"].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "value": round(row["value"], precision)}
        if row.get("secondary") is not None:
            item["secondary"] = round(row["secondary"], LIMITS["bp_diastolic"][2])
        merged[item["t"]] = item

    for _, item in samples:
        rendered = {"t": str(item.get("t")), "value": round(float(item["value"]), precision)}
        if item.get("secondary") is not None:
            rendered["secondary"] = round(float(item["secondary"]), LIMITS["bp_diastolic"][2])
        merged[rendered["t"]] = rendered

    return [merged[key] for key in sorted(merged)]
