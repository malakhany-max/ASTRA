"""Pure baseline, trend, radiation, exposure, and gravity-mode evaluation."""

from __future__ import annotations

import statistics
from copy import deepcopy
from datetime import datetime, timedelta

METRIC_LABELS = {
    "heart_rate": "Resting heart rate",
    "hrv_rmssd": "Heart-rate variability",
    "spo2": "Oxygen saturation",
    "skin_temp": "Skin temperature",
    "sleep_duration": "Sleep duration",
    "activity_level": "Activity level",
    "bp_systolic": "Blood pressure",
    "bp_diastolic": "Blood pressure",
    "blood_glucose": "Blood glucose",
    "mood": "Mood",
    "dizziness_self_report": "Dizziness report",
    "dose_rate": "Radiation dose rate",
    "cumulative_dose": "Cumulative radiation dose",
    "neutron_dose_rate": "Neutron dose rate",
}

MIN_SCALE = {
    "heart_rate": 3.0, "hrv_rmssd": 3.0, "spo2": 0.6, "skin_temp": 0.15,
    "sleep_duration": 0.4, "activity_level": 5.0, "bp_systolic": 4.0,
    "bp_diastolic": 3.0, "blood_glucose": 0.4, "mood": 0.6, "dizziness_self_report": 0.5,
}


def _label(metric: str) -> str:
    return METRIC_LABELS.get(metric, metric.replace("_", " ").capitalize())


def _now(context: dict, readings: list[dict]) -> str:
    if context.get("now"):
        return str(context["now"])
    if readings:
        timestamp = readings[-1].get("ts")
        if timestamp:
            return str(timestamp)
    return "1970-01-01T00:00:00Z"


def _status(astronaut_id, indicator, status, confidence, reasons, baseline_ref,
            action, decision_level, now):
    return {"schema": "astra.status.v1", "astronaut_id": astronaut_id,
            "indicator": indicator, "status": status,
            "confidence": round(max(0.0, min(1.0, confidence)), 3),
            "reasons": reasons, "baseline_ref": baseline_ref,
            "recommended_action": action, "decision_level": decision_level,
            "computed_ts": now}


def _stats(values):
    center = statistics.median(values)
    mad = statistics.median([abs(value - center) for value in values])
    return statistics.fmean(values), max(1.4826 * mad, statistics.pstdev(values), 1e-6)


def evaluate(profile: dict, state: dict | None, new_readings: list[dict],
             context: dict | None, config: dict) -> tuple[list[dict], dict]:
    """Pure deterministic evaluation. Config carries shared medical thresholds."""
    state = deepcopy(state or {})
    context = dict(context or {})
    config = dict(config or {})
    tuning = config.get("engine_tuning", {})
    thresholds = config.get("status_thresholds", config)
    phase = str(context.get("phase", "default"))
    astronaut_id = str(profile.get("astronaut_id", "unknown"))
    now = _now(context, new_readings)
    calibration_n = int(tuning.get("calibration_samples", 3))
    alpha = float(tuning.get("ewma_alpha", 0.08))
    persistence_n = int(tuning.get("persistence_windows", 2))
    z_cutoff = float(tuning.get("deviation_z_cutoff", 2.0))
    phase_baselines = state.setdefault("baselines", {}).setdefault(phase, {})
    windows = state.setdefault("rolling", {})
    persistence = state.setdefault("persistence", {})
    baseline_ref = str(state.setdefault("baseline_versions", {}).setdefault(phase, f"baseline-{phase}-v1"))
    grouped: dict[str, list[float]] = {}
    latest: dict[str, float] = {}
    for reading in new_readings:
        metric, value = reading.get("metric"), reading.get("value")
        if isinstance(metric, str) and isinstance(value, (int, float)) and not isinstance(value, bool):
            grouped.setdefault(metric, []).append(float(value))
            latest[metric] = float(value)

    statuses = []
    for metric, values in grouped.items():
        window = windows.setdefault(metric, [])
        window.extend(values)
        del window[:-int(tuning.get("rolling_window_samples", 30))]
        baseline = phase_baselines.get(metric)
        if baseline is None or baseline.get("n", 0) < calibration_n:
            calibration = list(baseline.get("calibration", [])) if baseline else []
            calibration.extend(values)
            calibration = calibration[-calibration_n:]
            if len(calibration) < calibration_n:
                phase_baselines[metric] = {"n": len(calibration), "calibration": calibration}
                statuses.append(_status(
                    astronaut_id, metric, "normal", 0.25,
                    [f"Learning your personal range for {_label(metric).lower()} ({len(calibration)} of {calibration_n} readings)."],
                    baseline_ref, "Continue routine monitoring.", 1, now))
                continue
            mean, scale = _stats(calibration)
            scale = max(scale, MIN_SCALE.get(metric, 0.0))
            baseline = {"mean": mean, "scale": scale, "n": len(calibration), "calibration": calibration}
            phase_baselines[metric] = baseline

        mean, scale = float(baseline["mean"]), max(float(baseline["scale"]), MIN_SCALE.get(metric, 0.0))
        observed = statistics.fmean(values)
        z_score = (observed - mean) / scale
        percent = ((observed - mean) / abs(mean) * 100) if mean else 0.0
        rule_name = {"heart_rate": "resting_heart_rate", "dose_rate": "radiation",
                     "cumulative_dose": "radiation"}.get(metric, metric)
        rule = thresholds.get(rule_name, {})
        level, decision, action = "normal", 1, "Continue routine personal-baseline monitoring."
        reasons = [f"{_label(metric)} is steady within your personal range."]
        if metric == "heart_rate":
            if rule.get("attention_pct") is not None and abs(percent) >= float(rule["attention_pct"]):
                level, decision = "attention", 2
                reasons = [f"Resting heart rate changed {percent:+.1f}% versus personal baseline."]
                action = "Re-measure and review the personal trend with the crew."
            if rule.get("urgent_pct") is not None and abs(percent) >= float(rule["urgent_pct"]):
                level, decision = "urgent", 3
                action = "Follow the onboard urgent health protocol and request crew review."
        elif metric == "sleep_duration":
            down = max(0.0, -percent)
            if rule.get("attention_pct_down") is not None and down >= float(rule["attention_pct_down"]):
                level, decision = "attention", 2
                reasons = [f"Sleep duration is down {down:.1f}% versus personal baseline."]
                action = "Review the sleep trend and mission schedule with the crew."
            if rule.get("urgent_pct_down") is not None and down >= float(rule["urgent_pct_down"]):
                level, decision = "urgent", 3
                action = "Request prompt crew review of the sleep trend."
        elif metric == "spo2":
            if rule.get("attention_below") is not None and observed < float(rule["attention_below"]):
                level, decision = "attention", 2
                reasons = ["SpO2 is below the configured review threshold."]
                action = "Repeat the measurement and request crew review if it persists."
            if rule.get("urgent_below") is not None and observed < float(rule["urgent_below"]):
                level, decision = "urgent", 3
                action = "Follow the onboard urgent health protocol."
        elif metric in {"dose_rate", "cumulative_dose", "neutron_dose_rate"}:
            reasons = [f"{_label(metric)} is checked by the radiation review."]
        elif abs(z_score) >= z_cutoff:
            level, decision = "attention", 2
            direction = "above" if z_score > 0 else "below"
            reasons = [f"{_label(metric)} is {direction} your usual personal range."]
            action = "Review this change against the astronaut's personal baseline."

        streak = persistence.get(metric, 0) + 1 if level != "normal" else 0
        persistence[metric] = streak
        if level == "attention" and streak < persistence_n:
            level, decision = "normal", 1
            reasons.append("Waiting for another consistent reading before raising this for review.")
            action = "Continue monitoring for a persistent trend."
        statuses.append(_status(astronaut_id, metric, level,
                                0.5 + min(abs(z_score), 5) / 10, reasons,
                                baseline_ref, action, decision, now))
        baseline["mean"] = (1 - alpha) * mean + alpha * observed
        baseline["scale"] = max(scale, abs(observed - mean) * alpha)
        baseline["n"] = int(baseline.get("n", calibration_n)) + len(values)

    _multi_indicator(statuses, grouped, phase_baselines)
    statuses.extend(_radiation(astronaut_id, state, latest, context, thresholds, baseline_ref, now))
    if context.get("gravity_transition"):
        statuses.append(_status(
            astronaut_id, "gravity_transition", "attention", 0.6,
            ["Gravity transition is active; increase dizziness and balance check frequency."],
            baseline_ref, "Use orthostatic caution and ask for crew support if symptoms occur.", 2, now))
    _exposure(state, latest, context, thresholds, astronaut_id, baseline_ref, now, statuses, tuning)
    state["last_phase"], state["last_updated_ts"] = phase, now
    return statuses, state


def _multi_indicator(statuses, grouped, baselines):
    by_name = {item["indicator"]: item for item in statuses}
    sleep, hr = by_name.get("sleep_duration"), by_name.get("heart_rate")
    mood = grouped.get("mood", [])
    mood_baseline = baselines.get("mood", {})
    mood_down = bool(mood and mood_baseline and statistics.fmean(mood) < mood_baseline.get("mean", 0))
    if sleep and hr and mood_down and sleep["status"] != "normal" and hr["status"] != "normal":
        sleep["status"] = "urgent" if max(sleep["decision_level"], hr["decision_level"]) == 3 else "attention"
        sleep["decision_level"] = max(sleep["decision_level"], hr["decision_level"], 2)
        sleep["reasons"].append("Sleep down, resting heart rate up, and mood down are co-occurring personal trends.")
        sleep["recommended_action"] = "Discuss the combined trends with the crew."


def _radiation(astronaut_id, state, latest, context, thresholds, baseline_ref, now):
    cfg = thresholds.get("radiation", {})
    statuses = []
    rate = latest.get("dose_rate")
    trusted = context.get("dosimeter_trusted", True)
    area = [float(value) for value in context.get("area_monitor_dose_rates", [])]
    radiation_state = state.setdefault("radiation", {})
    untrusted_note = None
    if not trusted:
        if area:
            rate = max(area)
            untrusted_note = "The personal dosimeter is offline, so area monitors are shown. This is not a personal all-clear."
        else:
            statuses.append(_status(astronaut_id, "radiation_dose_rate", "attention", 0.6,
                ["The personal dosimeter is offline and no area monitor reading is available."],
                baseline_ref, "Re-seat the personal dosimeter and ask a crewmate to check the area monitor.", 2, now))
    if rate is not None:
        rate = float(rate)
        level, decision, reasons, action = "normal", 1, [f"Personal dose rate is {rate:g} uSv/h."], "Continue radiation monitoring."
        attention, urgent = cfg.get("attention_uSv_per_h"), cfg.get("urgent_uSv_per_h")
        if attention is not None and rate >= float(attention):
            level, decision = "attention", 2
            reasons.append("Dose rate reached the configured review level.")
            action = "Check shielding and verify with area monitors."
        if urgent is not None and rate >= float(urgent):
            level, decision = "urgent", 3
            reasons.append("Dose rate reached the configured urgent level; confirm shelter status.")
            action = "Follow the radiation shelter procedure and verify with a second monitor."
        rise = cfg.get("rate_rise_attention_uSv_per_h_per_min")
        previous = radiation_state.get("last_dose_rate")
        if rise is not None and previous is not None and rate - previous >= float(rise):
            level, decision = "urgent", 3
            reasons.append("Dose rate is rising rapidly; this is a co-occurring sensor signal to verify.")
            action = "Follow the radiation shelter procedure and verify with a second monitor."
        if untrusted_note:
            reasons.append(untrusted_note)
            if level == "normal":
                level, decision = "attention", 2
                action = "Re-seat the personal dosimeter and compare it with the area monitors."
        statuses.append(_status(astronaut_id, "radiation_dose_rate", level, 0.8,
                                reasons, baseline_ref, action, decision, now))
        radiation_state["last_dose_rate"] = rate

    cumulative, budget = latest.get("cumulative_dose"), context.get("cumulative_dose_budget_uSv")
    if cumulative is not None:
        cumulative = float(cumulative)
        threshold = cfg.get("cumulative_attention_uSv")
        level, decision = "normal", 1
        reasons = [f"Cumulative personal dose is {cumulative:g} uSv."]
        action = "Continue routine monitoring of cumulative exposure."
        if threshold is not None and cumulative >= float(threshold):
            level, decision = "attention", 2
            reasons.append("Cumulative dose reached the configured review level.")
            action = "Review cumulative exposure with the radiation safety officer."
        if budget is not None:
            remaining = max(0.0, float(budget) - cumulative)
            reasons.append(f"Remaining configured cumulative-dose budget: {remaining:g} uSv.")
            rates = [float(value) for value in context.get("recent_cumulative_dose_rates", [])]
            if rates and statistics.fmean(rates) > 0:
                horizon = remaining / statistics.fmean(rates)
                reasons.append(f"At the recent rate, remaining-budget horizon is {horizon:.1f} hours.")
            if remaining == 0:
                level, decision = "urgent", 3
                action = "Follow mission radiation procedures and request review."
        statuses.append(_status(astronaut_id, "radiation_cumulative", level, 0.7,
                                reasons, baseline_ref, action, decision, now))
    return statuses


def _exposure(state, latest, context, thresholds, astronaut_id, baseline_ref, now, statuses, tuning):
    cfg = thresholds.get("radiation", {})
    rate = latest.get("dose_rate")
    spike = rate is not None and cfg.get("urgent_uSv_per_h") is not None and rate >= float(cfg["urgent_uSv_per_h"])
    followup = state.setdefault("post_exposure", {})
    if (spike or context.get("exposure_event")) and not followup.get("active"):
        followup.update({"active": True, "start_ts": now,
                         "event_id": str(context.get("exposure_event_id", "RAD-" + now.replace(":", "").replace("-", ""))),
                         "followup_window_hours": int(context.get("followup_window_hours", 72)),
                         "peak_dose_rate": float(rate or 0), "symptom_checkins": [],
                         "next_checkin_ts": now})
    if not followup.get("active"):
        return
    if rate is not None:
        followup["peak_dose_rate"] = max(float(followup.get("peak_dose_rate", 0)), float(rate))
    try:
        start = datetime.fromisoformat(followup["start_ts"].replace("Z", "+00:00"))
        current = datetime.fromisoformat(now.replace("Z", "+00:00"))
    except (KeyError, ValueError):
        start = current = None
    if start and current and (current - start).total_seconds() >= followup["followup_window_hours"] * 3600:
        followup["active"] = False
        return
    symptoms = list(context.get("symptoms", []))
    severity = int(context.get("symptom_severity", 0))
    observed_trends = []
    phase_baselines = state.get("baselines", {}).get(context.get("phase", state.get("last_phase", "default")), {})
    trend_cutoff = float(tuning.get("post_exposure_trend_z_cutoff", tuning.get("deviation_z_cutoff", 2.0)))
    for metric in ("skin_temp", "heart_rate", "hrv_rmssd", "sleep_duration", "activity_level"):
        observed = latest.get(metric)
        baseline = phase_baselines.get(metric)
        if observed is not None and baseline and float(baseline.get("scale", 0)) > 0:
            z_score = (float(observed) - float(baseline["mean"])) / float(baseline["scale"])
            if abs(z_score) >= trend_cutoff:
                observed_trends.append(f"{_label(metric)} changed during the post-exposure follow-up window.")
    level = 3 if spike or context.get("significant_symptom") else 2 if symptoms or severity > 0 or observed_trends or context.get("trend_change") else 1
    try:
        next_checkin = datetime.fromisoformat(followup.get("next_checkin_ts", now).replace("Z", "+00:00"))
        due = current is None or current >= next_checkin or bool(context.get("force_checkin"))
    except ValueError:
        due = True
    if due:
        followup["symptom_checkins"].append({"ts": now, "symptoms": symptoms, "severity": severity})
        interval = float(tuning.get("followup_checkin_interval_hours", 6))
        followup["next_checkin_ts"] = (current + timedelta(hours=interval)).strftime("%Y-%m-%dT%H:%M:%SZ") if current else now
    followup["symptom_checkins"] = followup["symptom_checkins"][-12:]
    followup["escalation_level"] = level
    cumulative = float(latest.get("cumulative_dose", followup.get("cumulative_dose", 0)))
    followup["cumulative_dose"] = cumulative
    statuses.append(_status(astronaut_id, "post_exposure_followup", "urgent" if level == 3 else "attention" if level == 2 else "normal",
        0.8, ["Post-exposure monitoring is active; later changes are co-occurring, not assumed caused by radiation.", *observed_trends],
        baseline_ref, "Complete the scheduled symptom check-in; symptoms warrant medical review.", 3 if level == 3 else 2 if level == 2 else 1, now))
    followup["exposure_record"] = {
        "schema": "astra.exposure_record.v1",
        "event_id": str(followup.get("event_id") or context.get("exposure_event_id") or "RAD-" + now.replace(":", "").replace("-", "")),
        "astronaut_id": astronaut_id, "start_ts": followup["start_ts"], "end_ts": now,
        "peak_dose_rate": {"value": float(followup["peak_dose_rate"]), "unit": "uSv/h"},
        "cumulative_dose": {"value": cumulative, "unit": "uSv"},
        "location": str(context.get("location", "unknown")),
        "shielding": "shelter_active" if context.get("shelter_active") else "none",
        "sensor_integrity": "trusted" if context.get("dosimeter_trusted", True) else "untrusted",
        "followup_window_hours": int(followup["followup_window_hours"]),
        "symptom_checkins": list(followup["symptom_checkins"]), "escalation_level": level, "sig": "",
    }
