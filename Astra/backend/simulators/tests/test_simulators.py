import pytest

from simulators.scenario_runner import ScenarioRunner, _loopback_url, build_scenario_readings


def test_scenarios_generate_signed_readings():
    readings = build_scenario_readings("radiation_spike", "A-07")
    assert readings
    assert all(item["astronaut_id"] == "A-07" and item["sig"] for item in readings)
    assert any(item["source"] == "area_monitor" for item in readings)
    assert any(item["source"] == "dosimeter" for item in readings)


def test_runner_enforces_loopback_and_time_scale():
    with pytest.raises(ValueError):
        ScenarioRunner(time_scale=0)
    assert _loopback_url("http://127.0.0.1:8000")
    assert not _loopback_url("https://127.0.0.1")
    assert not _loopback_url("http://example.com")
