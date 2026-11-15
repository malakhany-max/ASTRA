"""Scenario readings used by Hub's demo control endpoint."""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from urllib.parse import urlparse
from datetime import datetime, timezone

from .smartwatch import SmartwatchSimulator
from .dosimeter import DosimeterSimulator
from hub import security_adapter as sec


def _loopback_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def build_scenario_readings(name: str, astronaut_id: str = "A-07") -> list[dict]:
    watch = SmartwatchSimulator(astronaut_id, seed=19)
    now = datetime.now(timezone.utc)
    result = []
    if name == "sleep_degradation":
        result.extend(watch.generate(now, {"heart_rate": 62, "sleep_duration": 7.8}))
        result.extend(watch.generate(now, {"heart_rate": 62, "sleep_duration": 7.8}))
        for _ in range(2):
            result.extend(watch.generate(now, {"heart_rate": 70, "sleep_duration": 5.8}))
            result.append(sec.sign_reading({"schema": "astra.reading.v1", "astronaut_id": astronaut_id,
                "metric": "mood", "value": 2, "unit": "scale_1_5", "source": "self_report",
                "quality": 1.0, "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ")}, f"self-{astronaut_id}"))
    elif name == "radiation_spike":
        channels = DosimeterSimulator(astronaut_id).generate(spike=True, now=now)
        result.extend(channels["area_monitors"])
        result.extend(channels["personal"])
    elif name == "sensor_fault":
        device = f"watch-{astronaut_id.replace('-', '')}"
        for _ in range(8):
            result.append(sec.sign_reading({"schema": "astra.reading.v1", "astronaut_id": astronaut_id,
                "metric": "heart_rate", "value": 72, "unit": "bpm", "source": "wearable",
                "quality": 0.9, "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ")}, device))
    else:
        raise ValueError(f"unknown sensor scenario {name}")
    return result


class ScenarioRunner:
    def __init__(self, time_scale: float = 1.0):
        if time_scale <= 0: raise ValueError("time_scale must be > 0")
        self.time_scale = time_scale

    def generate(self, name: str, astronaut_id: str = "A-07") -> list[dict]:
        return build_scenario_readings(name, astronaut_id)

    async def play(self, name: str, astronaut_id: str = "A-07",
                   hub_url: str = "http://127.0.0.1:8000", interval_seconds: float = 1.0) -> list[dict]:
        """Send a deterministic scenario to a loopback Hub, with scaled pacing."""
        if not _loopback_url(hub_url):
            raise ValueError("simulator traffic is restricted to loopback HTTP")
        if interval_seconds < 0:
            raise ValueError("interval_seconds must be >= 0")
        results = []
        for reading in self.generate(name, astronaut_id):
            def send():
                req = urllib.request.Request(hub_url.rstrip("/") + "/ingest",
                    data=json.dumps(reading).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=5) as response:
                        return json.loads(response.read())
                except urllib.error.HTTPError as exc:
                    raise RuntimeError(f"Hub ingest failed with HTTP {exc.code}") from exc
            results.append(await asyncio.to_thread(send))
            if interval_seconds:
                await asyncio.sleep(interval_seconds * self.time_scale)
        return results
