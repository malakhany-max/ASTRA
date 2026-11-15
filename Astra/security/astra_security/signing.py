"""Canonical JSON + Ed25519 reading signatures."""

from __future__ import annotations

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from .keys import ensure_device_key, get_public_key
from .store import get_store
from .util import b64d, b64e, canonicalize, is_valid_nonce, new_nonce, now_iso

__all__ = [
    "canonicalize",
    "now_iso",
    "new_nonce",
    "sign_reading",
    "sign_reading_with_key",
    "verify_signature",
    "verify_reading_signature",
]


def sign_reading(reading: dict, device_id: str) -> dict:
    """Sign a reading, adding ``ts`` (if missing), ``seq``, ``nonce`` and ``sig``."""
    signing_key = ensure_device_key(device_id)
    return sign_reading_with_key(reading, signing_key, device_id=device_id)


def sign_reading_with_key(reading: dict, signing_key: SigningKey,
                          device_id: str | None = None, advance: bool = True) -> dict:
    """Sign a reading with an explicit key (used by simulators and attack_sim)."""
    out = dict(reading)
    out.setdefault("schema", "astra.reading.v1")
    if device_id is not None:
        out.setdefault("device_id", device_id)
    dev = out.get("device_id", device_id)
    if not dev:
        raise ValueError("reading has no device_id")

    if not out.get("ts"):
        out["ts"] = now_iso()

    store = get_store()
    if out.get("seq") is None:
        out["seq"] = store.next_seq(dev)
    elif advance:
        store.advance_seq(dev, int(out["seq"]))

    if not out.get("nonce"):
        out["nonce"] = new_nonce()

    out["sig"] = b64e(signing_key.sign(canonicalize(out)).signature)
    return out


def verify_signature(reading: dict, public_key: VerifyKey) -> bool:
    """Return True iff ``reading['sig']`` is a valid signature over the rest."""
    sig = reading.get("sig")
    if not sig:
        return False
    try:
        public_key.verify(canonicalize(reading), b64d(sig))
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False


def verify_reading_signature(reading: dict) -> bool:
    """Resolve the device's pinned public key and verify the signature."""
    device_id = reading.get("device_id")
    if not device_id:
        return False
    public_key = get_public_key(device_id)
    if public_key is None:
        return False
    return verify_signature(reading, public_key)


def validate_reading_shape(reading: dict) -> list[str]:
    """Cheap structural validation (no crypto). Returns a list of problems."""
    problems: list[str] = []
    if not isinstance(reading, dict):
        return ["reading is not an object"]
    for field in ("device_id", "metric", "value", "ts", "seq", "nonce", "sig"):
        if field not in reading:
            problems.append(f"missing field: {field}")
    if "nonce" in reading and not is_valid_nonce(reading["nonce"]):
        problems.append("nonce is not 32 lowercase hex chars")
    if "value" in reading and not isinstance(reading["value"], (int, float)):
        problems.append("value is not numeric")
    if "seq" in reading and not isinstance(reading["seq"], int):
        problems.append("seq is not an integer")
    return problems
