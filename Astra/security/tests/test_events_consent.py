import astra_security as sec


def test_event_shape_and_uplink(isolated_security_env):
    ev = sec.raise_security_event(
        "forged_signature", "watch-A07", "A-07",
        ["2026-11-13T10:00:00Z", "2026-11-13T10:00:05Z"], "high", {"note": "x"})
    assert ev["schema"] == "astra.security_event.v1"
    assert ev["evidence_hash"].startswith("sha256:")
    assert "value" not in ev
    assert any(e.get("priority") == 1 for e in isolated_security_env)
    assert sec.shield_state() in ("degraded", "alert")


def test_repeats_increase_count_not_flood(isolated_security_env):
    args = ("replay", "watch-A07", "A-07",
            ["2026-11-13T10:00:00Z", "2026-11-13T10:00:05Z"], "medium", {"n": 1})
    sec.raise_security_event(*args)
    ev = sec.raise_security_event(*args)
    assert ev["count"] >= 2


def test_raw_audio_never_uplinked():
    consent = {"astronaut_id": "A-07", "emergency_override": True,
               "tiers": {"vitals_summary": True, "psych_summary": True,
                         "raw_audio": True, "exposure_records": True}}
    out = sec.filter_for_uplink({"raw_audio": b"xx", "vitals_summary": {"hr": 70}}, consent)
    assert "raw_audio" not in out


def test_psych_removed_without_consent():
    consent = {"astronaut_id": "A-07", "emergency_override": False,
               "tiers": {"vitals_summary": True, "psych_summary": False,
                         "raw_audio": False, "exposure_records": True}}
    out = sec.filter_for_uplink({"psych_summary": {"mood": 2}, "vitals_summary": {"hr": 70}}, consent)
    assert "psych_summary" not in out
    assert "vitals_summary" in out


def test_sensitive_envelope_payload_is_encrypted_and_verifiable():
    payload = {"astronaut_id": "A-07", "dose": 12.5}
    envelope = sec.make_envelope("exposure_record", payload, msg_id="exposure-1")
    signed = sec.sign_envelope(envelope)
    assert signed["payload"]["protection"] == "astra_encrypted_payload_v1"
    assert "12.5" not in str(signed["payload"])
    assert sec.verify_envelope(signed)
    assert sec.decrypt_envelope_payload(signed) == payload

    tampered = dict(signed)
    tampered["payload"] = {**signed["payload"], "ciphertext": "gcm1:tampered"}
    assert sec.verify_envelope(tampered) is False
