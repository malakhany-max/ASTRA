"""Create CSV and Markdown evaluation summaries for the demo scenarios."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for directory in ("engine", "../security"):
    path = str((ROOT / directory).resolve())
    if path not in sys.path: sys.path.insert(0, path)

from astra_engine import evaluate
from astra_engine.config import load_engine_config


PROFILE = {"astronaut_id": "A-07", "preferences": {}, "mission_history": []}


def _reading(metric, value): return {"metric": metric, "value": value}


def evaluate_scenarios() -> list[dict]:
    config = load_engine_config()
    rows = []
    normal_state = {}
    false_alarms = 0
    normal_windows = 0
    for day in range(8):
        _, normal_state = evaluate(PROFILE, normal_state,
            [_reading("heart_rate", 62), _reading("sleep_duration", 7.8), _reading("mood", 4)],
            {"phase": "transit", "mission_day": day, "now": f"2026-11-{1 + day:02d}T12:00:00Z"}, config)
    for day in range(8, 13):
        statuses, normal_state = evaluate(PROFILE, normal_state,
            [_reading("heart_rate", 62), _reading("sleep_duration", 7.8), _reading("mood", 4)],
            {"phase": "transit", "mission_day": day, "now": f"2026-11-{day - 4:02d}T12:00:00Z"}, config)
        normal_windows += 1
        false_alarms += int(any(s["status"] != "normal" for s in statuses))
    false_alarm_rate = false_alarms / normal_windows
    rows.append({"scenario": "normal", "detection_lead_time_days": "", "false_alarm_rate": false_alarm_rate,
                 "expected": "normal", "observed": "normal" if false_alarms == 0 else "attention"})

    state = {}
    for _ in range(3):
        _, state = evaluate(PROFILE, state, [_reading("heart_rate", 60), _reading("sleep_duration", 8), _reading("mood", 4)],
                            {"phase": "transit", "now": "2026-11-01T12:00:00Z"}, config)
    lead_time = None
    for day in range(5):
        statuses, state = evaluate(PROFILE, state,
            [_reading("heart_rate", 70), _reading("sleep_duration", 5.8), _reading("mood", 2)],
            {"phase": "transit", "mission_day": 60 + day, "now": f"2026-11-{day + 2:02d}T12:00:00Z"}, config)
        if any(item["status"] != "normal" for item in statuses) and lead_time is None:
            lead_time = day
    rows.append({"scenario": "sleep_degradation", "detection_lead_time_days": lead_time,
                 "false_alarm_rate": false_alarm_rate, "expected": "attention", "observed": "attention" if lead_time is not None else "normal"})

    statuses, _ = evaluate(PROFILE, {}, [_reading("dose_rate", 600)],
        {"phase": "transit", "now": "2026-11-13T12:00:00Z", "exposure_event": True}, config)
    radiation = next(s for s in statuses if s["indicator"] == "radiation_dose_rate")
    rows.append({"scenario": "radiation_spike", "detection_lead_time_days": 0,
                 "false_alarm_rate": false_alarm_rate, "expected": "urgent", "observed": radiation["status"]})

    statuses, _ = evaluate(PROFILE, {}, [],
        {"phase": "surface", "gravity_transition": True, "now": "2026-11-13T12:00:00Z"}, config)
    transition = next(s for s in statuses if s["indicator"] == "gravity_transition")
    rows.append({"scenario": "gravity_transition", "detection_lead_time_days": 0,
                 "false_alarm_rate": false_alarm_rate, "expected": "attention", "observed": transition["status"]})

    import astra_security as sec
    device = "evaluation-flatline"
    sec.ensure_device_key(device)
    fault_result = None
    for _ in range(8):
        msg = sec.sign_reading({"schema": "astra.reading.v1", "astronaut_id": "A-07", "metric": "heart_rate",
            "value": 72, "unit": "bpm", "source": "wearable", "quality": 0.95}, device)
        fault_result = sec.verify_and_classify(msg, {"raise_events": False})
    detected_fault = fault_result["classification"] == "suspect_fault"
    accuracy = (int(detected_fault) + int(lead_time is not None)) / 2
    rows.append({"scenario": "flatline_fault", "detection_lead_time_days": "",
                 "false_alarm_rate": false_alarm_rate, "expected": "sensor_fault", "observed": "sensor_fault" if detected_fault else "trusted",
                 "fault_vs_change_accuracy": accuracy})
    for row in rows: row.setdefault("fault_vs_change_accuracy", "")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "results")
    args = parser.parse_args()
    rows = evaluate_scenarios()
    args.out.mkdir(parents=True, exist_ok=True)
    csv_path = args.out / "evaluation.csv"
    fields = ["scenario", "detection_lead_time_days", "false_alarm_rate", "fault_vs_change_accuracy", "expected", "observed"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    md_path = args.out / "evaluation.md"
    with md_path.open("w", encoding="utf-8") as handle:
        handle.write("# ASTRA Synthetic Scenario Evaluation\n\n")
        handle.write("Synthetic prototype metrics; not mission or clinical validation.\n\n")
        handle.write("| Scenario | Lead time (days) | False alarm rate | Fault vs change accuracy | Expected | Observed |\n|---|---:|---:|---:|---|---|\n")
        for row in rows:
            handle.write("| " + " | ".join(str(row[field]) for field in fields) + " |\n")
    print(csv_path); print(md_path)


if __name__ == "__main__": main()
