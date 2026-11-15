"""Load shared decision thresholds and local non-medical engine tuning."""

from pathlib import Path
import os

import yaml


def load_engine_config() -> dict:
    root = Path(os.environ.get("ASTRA_ROOT", Path(__file__).resolve().parents[2]))
    with (root / "config" / "thresholds.yaml").open("r", encoding="utf-8") as handle:
        thresholds = yaml.safe_load(handle) or {}
    local_path = root / "engine" / "defaults.yaml"
    with local_path.open("r", encoding="utf-8") as handle:
        tuning = yaml.safe_load(handle) or {}
    thresholds["engine_tuning"] = tuning
    return thresholds
