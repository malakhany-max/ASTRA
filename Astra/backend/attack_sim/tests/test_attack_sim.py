import pytest

from attack_sim import SCENARIOS, run_all, run_evaluation, run_scenario, trigger_scenario


@pytest.mark.parametrize("scenario,classification", [
    ("forged_signature", "suspect_tamper"),
    ("replay", "suspect_tamper"),
    ("spoofed_device", "suspect_tamper"),
    ("tampered_in_transit", "suspect_tamper"),
    ("timestamp_manipulation", "suspect_tamper"),
    ("dosimeter_fake_spike", "suspect_fault"),
    ("dosimeter_false_all_clear", "suspect_fault"),
    ("flatline_sensor_fault", "suspect_fault"),
])
def test_attack_detection_and_security_uplink(scenario, classification):
    result = run_scenario(scenario)
    assert result["detected"] is True
    assert result["classification"] == classification
    assert result["security_event_created"] is True
    assert result["uplink_envelope_created"] is True
    assert result["latency_ms"] >= 0


def test_replay_is_detected_after_first_delivery():
    result = run_scenario("replay")
    assert result["initial"]["classification"] == "trusted"
    assert result["result"]["classification"] == "suspect_tamper"
    assert result["result"]["checks"]["freshness"] is False


def test_run_all_returns_each_scenario():
    results = run_all()
    assert [item["scenario"] for item in results] == list(SCENARIOS)
    assert all(item["detected"] for item in results)


def test_evaluation_report_has_metrics_and_benign_control():
    report = run_evaluation()
    assert report["summary"]["detection_rate"] == 1.0
    assert report["summary"]["false_positive_rate"] == 0.0
    assert report["control"]["classification"] == "trusted"


def test_hub_scenario_helper_and_legacy_aliases():
    assert trigger_scenario("timestamp_manipulation")["detected"]
    assert run_scenario("tampered_message")["scenario"] == "tampered_in_transit"


@pytest.mark.parametrize("demo_name,scenario", [
    ("attack_forged", "forged_signature"),
    ("attack_replay", "replay"),
    ("attack_spoof", "spoofed_device"),
    ("attack_dosimeter_fake", "dosimeter_fake_spike"),
])
def test_hub_demo_names_match_shared_api(demo_name, scenario):
    result = trigger_scenario(demo_name)
    assert result["scenario"] == scenario
    assert result["detected"] is True


def test_unknown_scenario_has_helpful_error():
    with pytest.raises(ValueError, match="unknown scenario"):
        run_scenario("not-an-attack")
