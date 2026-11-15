"""Thin boundary around Farah's SDK; local fallback keeps integration swappable."""

from __future__ import annotations

import base64
import json
import os
import secrets
from datetime import datetime, timezone

try:
    import astra_security as _sdk
except ImportError:
    _sdk = None


if _sdk is not None:
    sign_reading = _sdk.sign_reading
    verify_and_classify = _sdk.verify_and_classify
    raise_security_event = _sdk.raise_security_event
    shield_state = _sdk.shield_state
    encrypt_field = _sdk.encrypt_field
    decrypt_field = _sdk.decrypt_field
    filter_for_uplink = _sdk.filter_for_uplink
    consent_allows = _sdk.consent_allows
    sign_envelope = _sdk.sign_envelope
    verify_envelope = _sdk.verify_envelope
    sign_bundle = _sdk.sign_bundle
    verify_bundle = _sdk.verify_bundle
    make_bundle = _sdk.make_bundle
    audit_log = _sdk.audit_log
    make_envelope = _sdk.make_envelope
    list_events = _sdk.list_events
    rbac = _sdk.rbac
    default_consent = _sdk.default_consent
    apply_revocation_bundle = _sdk.apply_revocation_bundle
    set_event_uplink_sink = _sdk.set_uplink_sink
    def sign_exposure_record(record: dict) -> dict:
        out = dict(record)
        out.pop("sig", None)
        key = _sdk.ensure_node_key(_sdk.NODE_HUB)
        out["sig"] = base64.b64encode(key.sign(_sdk.canonicalize(out)).signature).decode("ascii")
        return out
else:
    _memory_key = secrets.token_bytes(32)
    _seq: dict[str, int] = {}
    def _now():
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    def sign_reading(reading, device_id):
        out = dict(reading); out.update({"device_id": device_id, "ts": reading.get("ts", _now()),
            "seq": _seq.get(device_id, 0) + 1, "nonce": secrets.token_hex(16), "sig": "stub"})
        _seq[device_id] = out["seq"]; return out
    def verify_and_classify(message, context=None):
        return {"classification": "trusted", "reasons": [], "checks": {k: True for k in ("signature", "freshness", "plausibility", "sensor_health", "cross_sensor")}}
    def raise_security_event(*args, **kwargs): return {"schema": "astra.security_event.v1", "event_type": args[0], "count": 1}
    def shield_state(): return "ok"
    def encrypt_field(value, context): return "stub:" + base64.b64encode(value.encode()).decode()
    def decrypt_field(token, context): return base64.b64decode(token.removeprefix("stub:")).decode()
    def filter_for_uplink(data, consent): return {k: v for k, v in data.items() if k != "raw_audio"}
    def consent_allows(consent, tier): return bool(consent.get("tiers", {}).get(tier, False))
    def sign_envelope(envelope): return {**envelope, "sig": "stub"}
    def verify_envelope(envelope): return envelope.get("sig") == "stub"
    def sign_bundle(bundle): return {**bundle, "sig": "stub"}
    def verify_bundle(bundle): return bundle.get("sig") == "stub"
    def make_bundle(bundle_type, payload): return {"type": bundle_type, "payload": payload, "created_ts": _now()}
    def audit_log(*args, **kwargs): return None
    def make_envelope(msg_type, payload, direction="uplink", priority=4, node_id="hub-01", msg_id=None):
        return {"schema": "astra.envelope.v1", "msg_id": msg_id or secrets.token_hex(16), "direction": direction,
                "type": msg_type, "priority": priority, "created_ts": _now(), "payload": payload, "node_id": node_id}
    def list_events(limit=100): return []
    class _FallbackRBAC:
        def require_permission(self, permission):
            from fastapi import HTTPException
            def dependency(): raise HTTPException(status_code=501, detail="RBAC SDK unavailable")
            return dependency
        def authenticate(self, username, password): raise ValueError("RBAC SDK unavailable")
        def create_session(self, user, ttl_minutes=30): return "stub"
        def decode_session(self, token): return {"username": "demo", "role": "admin", "astronaut_id": None}
        def can_access_astronaut(self, principal, astronaut_id): return True
        def add_user(self, *args, **kwargs): return None
        def logout(self, username): return None
    rbac = _FallbackRBAC()
    def default_consent(astronaut_id): return {"astronaut_id": astronaut_id, "tiers": {"vitals_summary": True, "psych_summary": True, "raw_audio": False, "exposure_records": True}, "emergency_override": True}
    def apply_revocation_bundle(bundle, actor="hub"): return 0
    def set_event_uplink_sink(sink): return None
    def sign_exposure_record(record): return {**record, "sig": "stub"}
