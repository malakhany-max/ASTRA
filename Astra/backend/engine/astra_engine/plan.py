"""Weekly plan adapter using companion content when available."""

from __future__ import annotations

from pathlib import Path

import yaml

LABELS = {
    "heart_rate": "resting heart rate", "hrv_rmssd": "heart-rate variability",
    "spo2": "oxygen saturation", "skin_temp": "skin temperature",
    "sleep_duration": "sleep", "activity_level": "activity",
    "bp_systolic": "blood pressure", "bp_diastolic": "blood pressure",
    "blood_glucose": "blood glucose", "mood": "mood",
    "dizziness_self_report": "dizziness", "radiation_dose_rate": "radiation dose",
    "radiation_cumulative": "cumulative dose", "dose_rate": "radiation dose",
    "cumulative_dose": "cumulative dose", "post_exposure_followup": "exposure follow-up",
    "gravity_transition": "gravity transition",
}

CATEGORY_NOTES = {
    "exercise": "Movement is matched to your recent activity and sleep.",
    "nutrition": "Meals are timed to keep energy steady across the shift.",
    "sleep": "Rest windows protect recovery where mission tasks allow.",
    "wellbeing": "Short check-ins keep small changes visible early.",
}


def make_weekly_plan(astronaut_id: str, week: int, statuses: list[dict], content: dict | None = None) -> dict:
    content = dict(content or {})
    if not content:
        path = Path(__file__).resolve().parents[1] / "content.yaml"
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                content = yaml.safe_load(handle) or {}
    focus = []
    for item in statuses:
        if item.get("status") == "normal":
            continue
        label = LABELS.get(str(item.get("indicator", "")), str(item.get("indicator", "")).replace("_", " "))
        if label and label not in focus:
            focus.append(label)
    focus = focus[:2]
    base = "Personal review this week: " + " and ".join(focus) + "." if focus else "Routine personal-baseline monitoring this week."
    return {
        "schema": "astra.plan.v1", "astronaut_id": astronaut_id, "week": int(week),
        "exercise": content.get("exercise", [{"title": "Crew-approved movement option", "notes": "Choose the movement block that fits today's schedule."}]),
        "nutrition": content.get("nutrition", [{"title": "Routine nutrition check-in", "notes": "Keep meals and water regular across the shift."}]),
        "sleep": content.get("sleep", [{"title": "Protect a consistent rest opportunity", "notes": "Keep the same sleep window where tasks allow."}]),
        "wellbeing": content.get("wellbeing", [{"title": "Brief check-in with a crewmate", "notes": "A short conversation counts."}]),
        "rationale": base,
        "rationale_by_category": {name: base + " " + note for name, note in CATEGORY_NOTES.items()},
    }
