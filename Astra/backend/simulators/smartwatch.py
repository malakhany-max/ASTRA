"""Synthetic smartwatch stream; no device or network access is required."""

from __future__ import annotations

import math
import random
from datetime import datetime, timezone

from hub import security_adapter as sec


class SmartwatchSimulator:
    DEMO_BASELINE = {"heart_rate": 62.0, "hrv_rmssd": 48.0, "spo2": 98.0,
                     "skin_temp": 36.5, "sleep_duration": 7.8, "activity_level": 35.0,
                     "bp_systolic": 118.0, "bp_diastolic": 76.0, "blood_glucose": 5.4}
    UNITS = {"heart_rate": "bpm", "hrv_rmssd": "ms", "spo2": "%", "skin_temp": "celsius",
             "sleep_duration": "hours", "activity_level": "index_0_100",
             "bp_systolic": "mmHg", "bp_diastolic": "mmHg", "blood_glucose": "mmol/L"}

    def __init__(self, astronaut_id: str, baseline: dict | None = None,
                 device_id: str | None = None, seed: int = 7):
        self.astronaut_id = astronaut_id
        self.device_id = device_id or f"watch-{astronaut_id.replace('-', '')}"
        self.baseline = {**self.DEMO_BASELINE, **(baseline or {})}
        self.rng = random.Random(seed)
        self.sample = 0
        self.slots: dict[str, int] = {}

    def generate(self, now: datetime | None = None, overrides: dict | None = None) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        hour = now.hour + now.minute / 60
        awake = 1.0 if 7 <= hour < 23 else 0.3
        circadian = math.sin((hour - 7) * math.pi / 16)
        values = {
            "heart_rate": self.baseline["heart_rate"] + 3 * circadian + self.rng.gauss(0, 1.2),
            "hrv_rmssd": self.baseline["hrv_rmssd"] - 2 * circadian + self.rng.gauss(0, 2.0),
            "spo2": self.baseline["spo2"] + self.rng.gauss(0, 0.25),
            "skin_temp": self.baseline["skin_temp"] + self.rng.gauss(0, 0.08),
            "sleep_duration": self.baseline["sleep_duration"] if hour < 8 else self.baseline["sleep_duration"] + self.rng.gauss(0, 0.1),
            "activity_level": max(0.0, min(100.0, self.baseline["activity_level"] * awake + 15 * max(0, circadian) + self.rng.gauss(0, 3))),
        }
        slots = {"bp": int(hour // 12), "glucose": int(hour // 6)}
        if slots["bp"] != self.slots.get("bp"):
            self.slots["bp"] = slots["bp"]
            values["bp_systolic"] = self.baseline["bp_systolic"] + self.rng.gauss(0, 2.5)
            values["bp_diastolic"] = self.baseline["bp_diastolic"] + self.rng.gauss(0, 1.8)
        if slots["glucose"] != self.slots.get("glucose"):
            self.slots["glucose"] = slots["glucose"]
            values["blood_glucose"] = max(3.4, self.baseline["blood_glucose"] + self.rng.gauss(0, 0.25))
        values.update({key: value for key, value in (overrides or {}).items() if key in values})
        self.sample += 1
        ts = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = []
        for metric, value in values.items():
            reading = {"schema": "astra.reading.v1", "astronaut_id": self.astronaut_id,
                       "metric": metric, "value": round(float(value), 3), "unit": self.UNITS[metric],
                       "source": "wearable", "quality": 0.95, "ts": ts}
            result.append(sec.sign_reading(reading, self.device_id))
        return result


def post_readings(readings: list[dict], hub_url: str = "http://127.0.0.1:8000") -> list[dict]:
    """POST only to loopback Hub; refuses nonlocal URLs to preserve offline runtime."""
    import urllib.error
    import urllib.request
    from urllib.parse import urlsplit

    parsed = urlsplit(hub_url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("simulators may only connect to the local Hub")
    results = []
    for reading in readings:
        req = urllib.request.Request(hub_url.rstrip("/") + "/ingest", data=__import__("json").dumps(reading).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                results.append(__import__("json").loads(response.read()))
        except urllib.error.HTTPError as exc:
            results.append({"http_status": exc.code, "detail": exc.read().decode(errors="replace")})
    return results
