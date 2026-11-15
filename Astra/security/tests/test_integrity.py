import base64
from datetime import datetime, timedelta, timezone

import astra_security as sec


def test_valid_reading_trusted(paired, make_reading):
    r = sec.sign_reading(make_reading(), paired)
    res = sec.verify_and_classify(r)
    assert res["classification"] == "trusted", res


def test_seq_monotonic(paired, make_reading):
    a = sec.sign_reading(make_reading(), paired)
    b = sec.sign_reading(make_reading(), paired)
    assert b["seq"] > a["seq"]


def test_forged_signature_is_tamper(paired, make_reading):
    r = sec.sign_reading(make_reading(), paired)
    r["sig"] = base64.b64encode(b"\0" * 64).decode()
    res = sec.verify_and_classify(r)
    assert res["classification"] == "suspect_tamper"
    assert res["checks"]["signature"] is False


def test_tampered_value_is_tamper(paired, make_reading):
    r = sec.sign_reading(make_reading(), paired)
    r["value"] = 150
    assert sec.verify_and_classify(r)["classification"] == "suspect_tamper"


def test_replay_is_tamper(paired, make_reading):
    r = sec.sign_reading(make_reading(), paired)
    assert sec.verify_and_classify(dict(r))["classification"] == "trusted"
    res = sec.verify_and_classify(dict(r))
    assert res["classification"] == "suspect_tamper"
    assert res["checks"]["freshness"] is False


def test_timestamp_outside_wide_window_is_clock_tamper(paired, make_reading):
    old = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = sec.sign_reading(make_reading(ts=old), paired)
    res = sec.verify_and_classify(r, {"raise_events": False})
    assert res["classification"] == "suspect_tamper"
    assert res["checks"]["freshness"] is False


def test_unpaired_device_is_tamper(paired, make_reading):
    rogue_key, _ = sec.generate_keypair()
    r = sec.sign_reading_with_key(make_reading(device_id="rogue-99"), rogue_key)
    assert sec.verify_and_classify(r)["classification"] == "suspect_tamper"


def test_implausible_is_fault_not_tamper(paired, make_reading):
    r = sec.sign_reading(make_reading(value=900), paired)
    res = sec.verify_and_classify(r)
    assert res["classification"] == "suspect_fault"
    assert res["checks"]["plausibility"] is False


def test_flatline_is_fault(paired, make_reading):
    results = [
        sec.verify_and_classify(sec.sign_reading(make_reading(value=72.0), paired))
        for _ in range(60)
    ]
    assert any(r["classification"] == "suspect_fault" for r in results)
    assert not any(r["classification"] == "suspect_tamper" for r in results)


def test_dropout_is_sensor_fault(paired, make_reading):
    now = datetime.now(timezone.utc)
    history = [
        {"value": 70 + i, "ts": (now - timedelta(seconds=10 - 2 * i)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        for i in range(4)
    ]
    current_ts = (now + timedelta(seconds=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = sec.sign_reading(make_reading(value=75, ts=current_ts), paired)
    res = sec.verify_and_classify(r, {"raise_events": False, "window": history})
    assert res["classification"] == "suspect_fault"
    assert res["checks"]["sensor_health"] is False
    assert any("dropout" in reason for reason in res["reasons"])


def test_heart_rate_activity_cross_sensor_mismatch_is_fault(paired, make_reading):
    r = sec.sign_reading(make_reading(value=200), paired)
    res = sec.verify_and_classify(
        r, {"raise_events": False, "cross:activity_level:None": 0},
    )
    assert res["classification"] == "suspect_fault"
    assert res["checks"]["cross_sensor"] is False

