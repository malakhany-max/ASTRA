"""Signed downlink bundles."""

from __future__ import annotations

from nacl.signing import SigningKey

from .audit import audit_log
from .keys import NODE_GROUND, ensure_node_key, get_node_verify_key, revoke_device
from .util import b64d, b64e, canonicalize, now_iso

BUNDLE_TYPES = (
    "config_bundle", "thresholds_bundle", "guideline_bundle",
    "revocation_list", "history_bundle",
)


def make_bundle(bundle_type: str, payload: dict) -> dict:
    return {"type": bundle_type, "created_ts": now_iso(), "payload": payload}


def sign_bundle(bundle: dict, private_key: SigningKey | None = None) -> dict:
    """Sign a downlink bundle (defaults to the Ground Station node key)."""
    out = dict(bundle)
    out.setdefault("created_ts", now_iso())
    key = private_key or ensure_node_key(NODE_GROUND)
    out["sig"] = b64e(key.sign(canonicalize(out)).signature)
    return out


def verify_bundle(bundle: dict, public_key=None) -> bool:
    """Verify a downlink bundle against the pinned Ground key (or an explicit key)."""
    if not isinstance(bundle, dict) or not bundle.get("sig"):
        return False
    key = public_key or get_node_verify_key(NODE_GROUND)
    if key is None:
        return False
    try:
        key.verify(canonicalize(bundle), b64d(bundle["sig"]))
        return True
    except Exception:
        return False


def make_revocation_bundle(device_ids: list[str], reason: str = "") -> dict:
    """Build a Ground-signed revocation list bundle."""
    return sign_bundle(make_bundle("revocation_list", {
        "device_ids": list(device_ids),
        "reason": reason,
        "issued_ts": now_iso(),
    }))


def apply_revocation_bundle(bundle: dict, actor: str = "hub") -> int:
    """Verify a revocation bundle and revoke the listed devices. Returns count."""
    from .errors import SecurityError

    if not verify_bundle(bundle):
        raise SecurityError("revocation bundle signature invalid")
    device_ids = bundle.get("payload", {}).get("device_ids", [])
    count = 0
    for device_id in device_ids:
        if revoke_device(device_id):
            count += 1
    audit_log(actor, "apply_revocation_bundle", "trust_store",
              {"device_ids": device_ids, "revoked": count})
    return count
