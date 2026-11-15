"""Personal dosimeter plus two fixed area monitors, with explicit spike mode."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from pathlib import Path

import yaml

from hub import security_adapter as sec


class DosimeterSimulator:
    def __init__(self, astronaut_id: str, dose_rate: float = 12.0,
                 neutron_dose_rate: float = 1.2, seed: int = 11):
        self.astronaut_id = astronaut_id
        self.dose_rate = float(dose_rate)
        self.neutron_dose_rate = float(neutron_dose_rate)
        self.cumulative = 0.0
        self.sample = 0
        self.rng = random.Random(seed)

    def generate(self, spike: bool = False, now: datetime | None = None,
                 interval_seconds: float = 60.0) -> dict[str, list[dict]]:
        now = now or datetime.now(timezone.utc)
        ts = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.sample += 1
        if spike:
            thresholds_path = Path(__file__).resolve().parents[1] / "config" / "thresholds.yaml"
            with thresholds_path.open("r", encoding="utf-8") as handle:
                urgent = float(yaml.safe_load(handle)["status_thresholds"]["radiation"]["urgent_uSv_per_h"])
            rate = max(self.dose_rate * 8, urgent * 1.2)
        else:
            rate = max(0.0, self.dose_rate + self.rng.gauss(0, 0.7))
        neutron = max(0.0, self.neutron_dose_rate * (5 if spike else 1) + self.rng.gauss(0, 0.08))
        self.cumulative += (rate + neutron) * (interval_seconds / 3600)
        channels = (("dose_rate", rate, "uSv/h"), ("neutron_dose_rate", neutron, "uSv/h"),
                    ("cumulative_dose", self.cumulative, "uSv"))
        personal = [sec.sign_reading({"schema": "astra.reading.v1", "astronaut_id": self.astronaut_id,
                    "metric": metric, "value": round(value, 3), "unit": unit, "source": "dosimeter",
                    "quality": 0.97, "ts": ts}, f"dose-{self.astronaut_id.replace('-', '')}")
                    for metric, value, unit in channels]
        area = []
        for index, factor in ((1, 1.02), (2, 1.08)):
            for metric, value, unit in channels:
                area.append(sec.sign_reading({"schema": "astra.reading.v1", "astronaut_id": self.astronaut_id,
                    "metric": metric, "value": round(value * factor, 3), "unit": unit,
                    "source": "area_monitor", "quality": 0.99, "ts": ts},
                    f"area-{index}-{self.astronaut_id.replace('-', '')}"))
        return {"personal": personal, "area_monitors": area}
