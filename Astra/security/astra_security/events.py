"""Security events + shield state."""

from __future__ import annotations

import logging
import time
from typing import Callable

from .audit import audit_log
from .config import sec_get
from .envelope import make_envelope, sign_envelope
from .keys import NODE_HUB
from .store import get_store
from .util import canonicalize, now_iso, sha256_prefixed

_log = logging.getLogger("astra_security.events")

_SEVERITIES = ("low", "medium", "high", "critical")
_SHIELD_RANK = {"ok": 0, "degraded": 1, "alert": 2}

_uplink_sink: Callable[[dict], object] | None = None


def set_uplink_sink(sink: Callable[[dict], object] | None) -> None:
    """Install a callable that receives signed uplink envelopes."""
    global _uplink_sink
    _uplink_sink = sink


def _default_sink() -> Callable[[dict], object] | None:
    try:
        from astra_link import get_uplink_queue
    except Exception:
        return None
    queue = get_uplink_queue()
    return queue.enqueue


def _enqueue(envelope: dict) -> bool:
    sink = _uplink_sink or _default_sink()
    if sink is None:
        _log.debug("no uplink sink configured; envelope not queued")
        return False
    try:
        sink(envelope)
        return True
    except Exception as exc:
        _log.warning("failed to enqueue security envelope: %s", exc)
        return False


def shield_state() -> str:
    """Return the current shield state: ``ok`` | ``degraded`` | ``alert``."""
    return get_store().get_kv("shield_state", "ok")


def _bump_shield(severity: str) -> str:
    store = get_store()
    alert = set(sec_get("security_events.alert_severities", ["high", "critical"]))
    degraded = set(sec_get("security_events.degraded_severities", ["medium"]))
    target = "alert" if severity in alert else "degraded" if severity in degraded else "ok"
    current = store.get_kv("shield_state", "ok")
    if _SHIELD_RANK[target] >= _SHIELD_RANK.get(current, 0):
        store.set_kv("shield_state", target)
    return store.get_kv("shield_state", "ok")


def reset_shield() -> None:
    get_store().set_kv("shield_state", "ok")


def _sign_event(event: dict) -> dict:
    from .keys import ensure_node_key

    out = dict(event)
    key = ensure_node_key(NODE_HUB)
    out["sig"] = _b64_sign(key, out)
    return out


def _b64_sign(key, event: dict) -> str:
    from .util import b64e

    return b64e(key.sign(canonicalize(event)).signature)


def raise_security_event(
    event_type: str,
    device_id: str,
    astronaut_id: str,
    time_window: list | None = None,
    severity: str = "medium",
    evidence: dict | None = None,
    **kwargs,
) -> dict:
    """Build, correlate, store, sign and enqueue a security event."""
    store = get_store()
    severity = severity if severity in _SEVERITIES else "medium"
    now = now_iso()
    window = list(time_window) if time_window else [now, now]
    if len(window) != 2:
        window = [now, now]

    evidence = evidence if isinstance(evidence, dict) else {}
    evidence_hash = sha256_prefixed(canonicalize(evidence))

    cooldown = float(sec_get("security_events.cooldown_seconds", 60))
    ckey = f"{event_type}|{device_id}"
    existing = store.get_cooldown(ckey)
    now_epoch = time.time()

    if existing and now_epoch < float(existing["cooldown_until"]):
        row = store.latest_event(event_type, device_id)
        if row is not None:
            event = _row_to_event(row)
            event["count"] = int(event.get("count", 1)) + 1
            event["time_window"] = [event.get("time_window", [now, now])[0], now]
            event["evidence_hash"] = evidence_hash
            event = _sign_event(event)
            store.insert_event(event)
            store.set_cooldown(ckey, event_type, device_id, event["count"],
                               existing["first_ts"], now, float(existing["cooldown_until"]))
            _bump_shield(severity)
            return event

    event_id = f"SEC-{store.next_event_number():04d}"
    store.set_kv("event_counter", store.next_event_number())
    event = {
        "schema": "astra.security_event.v1",
        "event_id": event_id,
        "event_type": event_type,
        "device_id": device_id,
        "astronaut_id": astronaut_id,
        "time_window": window,
        "severity": severity,
        "evidence_hash": evidence_hash,
        "count": 1,
    }
    event = _sign_event(event)
    store.insert_event(event)
    store.set_cooldown(ckey, event_type, device_id, 1, now, now, now_epoch + cooldown)

    envelope = sign_envelope(make_envelope(
        "security_event", event, direction="uplink",
        priority=1, node_id=NODE_HUB,
    ))
    queued = _enqueue(envelope)

    audit_log("security", "security_event", event_id,
              {"event_type": event_type, "device_id": device_id, "severity": severity,
               "queued": queued})
    _bump_shield(severity)
    return event


def _row_to_event(row: dict) -> dict:
    import json

    if row.get("body"):
        try:
            return json.loads(row["body"])
        except json.JSONDecodeError:
            pass
    return {
        "schema": "astra.security_event.v1",
        "event_id": row["event_id"],
        "event_type": row["event_type"],
        "device_id": row["device_id"],
        "astronaut_id": row["astronaut_id"],
        "time_window": [row["time_start"], row["time_end"]],
        "severity": row["severity"],
        "evidence_hash": row["evidence_hash"],
        "count": row["count"],
    }


def list_events(limit: int = 100) -> list[dict]:
    return get_store().list_events(limit)
