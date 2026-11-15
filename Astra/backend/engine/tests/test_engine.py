from astra_engine import evaluate, make_weekly_plan


PROFILE = {"astronaut_id": "A-07", "height_cm": 175, "weight_kg": 70,
           "fitness_level": "mission-trained", "mission_history": [], "preferences": {}}


def reading(metric, value):
    return {"astronaut_id": "A-07", "metric": metric, "value": value, "ts": "2026-11-13T12:00:00Z"}


def calibrate(config):
    state = {}
    for _ in range(int(config.get("engine_tuning", {}).get("calibration_samples", 3))):
        _, state = evaluate(PROFILE, state,
            [reading("heart_rate", 60), reading("sleep_duration", 8), reading("mood", 4)],
            {"phase": "transit", "now": "2026-11-13T12:00:00Z"}, config)
    return state


def test_normal_personal_baseline_stays_normal(engine_config):
    state = calibrate(engine_config)
    statuses, _ = evaluate(PROFILE, state,
        [reading("heart_rate", 61), reading("sleep_duration", 7.9)],
        {"phase": "transit", "now": "2026-11-13T13:00:00Z"}, engine_config)
    assert all(item["status"] == "normal" for item in statuses)
    assert all(item["baseline_ref"] == "baseline-transit-v1" for item in statuses)


def test_sleep_degradation_triggers_attention_after_persistence(engine_config):
    state = calibrate(engine_config)
    context = {"phase": "transit", "now": "2026-11-13T13:00:00Z"}
    statuses, state = evaluate(PROFILE, state,
        [reading("heart_rate", 70), reading("sleep_duration", 6), reading("mood", 2)],
        context, engine_config)
    context["now"] = "2026-11-14T13:00:00Z"
    statuses, state = evaluate(PROFILE, state,
        [reading("heart_rate", 70), reading("sleep_duration", 5.8), reading("mood", 2)],
        context, engine_config)
    context["now"] = "2026-11-15T13:00:00Z"
    statuses, _ = evaluate(PROFILE, state,
        [reading("heart_rate", 70), reading("sleep_duration", 5.6), reading("mood", 2)],
        context, engine_config)
    by_metric = {item["indicator"]: item for item in statuses}
    assert by_metric["sleep_duration"]["status"] == "attention"
    assert any("co-occurring" in reason for reason in by_metric["sleep_duration"]["reasons"])


def test_radiation_spike_is_immediate_decision_level_three(engine_config):
    statuses, state = evaluate(PROFILE, {}, [reading("dose_rate", 600)],
        {"phase": "transit", "now": "2026-11-13T13:00:00Z", "exposure_event": True,
         "shelter_active": True}, engine_config)
    dose = next(item for item in statuses if item["indicator"] == "radiation_dose_rate")
    assert dose["status"] == "urgent" and dose["decision_level"] == 3
    assert state["post_exposure"]["exposure_record"]["schema"] == "astra.exposure_record.v1"
    assert state["post_exposure"]["exposure_record"]["shielding"] == "shelter_active"


def test_untrusted_dosimeter_never_produces_all_clear(engine_config):
    statuses, _ = evaluate(PROFILE, {}, [],
        {"phase": "transit", "dosimeter_trusted": False}, engine_config)
    radiation = next(item for item in statuses if item["indicator"] == "radiation_dose_rate")
    assert radiation["status"] == "attention" and radiation["decision_level"] == 2
    assert "offline" in radiation["reasons"][0]


def test_gravity_transition_adds_orthostatic_caution(engine_config):
    statuses, _ = evaluate(PROFILE, {}, [],
        {"phase": "surface", "gravity_transition": True}, engine_config)
    transition = next(item for item in statuses if item["indicator"] == "gravity_transition")
    assert transition["decision_level"] == 2
    assert "orthostatic" in transition["recommended_action"]


def test_post_exposure_checkin_schedule_and_cooccurring_trends(engine_config):
    state = {}
    for _ in range(3):
        _, state = evaluate(PROFILE, state,
            [reading("skin_temp", 36.5), reading("dose_rate", 8)],
            {"phase": "transit", "now": "2026-11-13T00:00:00Z"}, engine_config)
    _, state = evaluate(PROFILE, state, [reading("dose_rate", 600)],
        {"phase": "transit", "now": "2026-11-13T01:00:00Z", "exposure_event": True}, engine_config)
    statuses, state = evaluate(PROFILE, state, [reading("skin_temp", 38.0)],
        {"phase": "transit", "now": "2026-11-13T07:00:00Z", "symptoms": ["fatigue"],
         "symptom_severity": 1, "force_checkin": True}, engine_config)
    followup = next(item for item in statuses if item["indicator"] == "post_exposure_followup")
    record = state["post_exposure"]["exposure_record"]
    assert followup["status"] == "attention"
    assert any("co-occurring" in reason for reason in followup["reasons"])
    assert len(record["symptom_checkins"]) == 2
    assert record["symptom_checkins"][-1]["symptoms"] == ["fatigue"]


def test_plan_schema_and_placeholder_content(engine_config):
    plan = make_weekly_plan("A-07", 12, [])
    assert plan["schema"] == "astra.plan.v1"
    assert plan["exercise"] and plan["rationale"]
