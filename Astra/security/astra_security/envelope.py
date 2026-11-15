"""Signed link envelopes (``astra.envelope.v1``)."""

from __future__ import annotations

import json
import uuid

from nacl.signing import SigningKey

from .keys import NODE_HUB, ensure_node_key, get_node_verify_key
from .util import b64d, b64e, canonicalize, now_iso
from .errors import CryptoError
from .crypto_store import decrypt_field, encrypt_field

PRIORITY_HIGHEST = 1
PRIORITY_ROUTINE = 4
_SENSITIVE_TYPES = {"exposure_record", "history_bundle"}
_ENCRYPTED_MARKER = "astra_encrypted_payload_v1"


def make_envelope(msg_type: str, payload: dict, direction: str = "uplink",
                  priority: int = PRIORITY_ROUTINE, node_id: str = NODE_HUB,
                  msg_id: str | None = None) -> dict:
    """Build an unsigned envelope with all contract fields."""
    return {
        "schema": "astra.envelope.v1",
        "msg_id": msg_id or str(uuid.uuid4()),
        "direction": direction,
        "type": msg_type,
        "priority": int(priority),
        "created_ts": now_iso(),
        "payload": payload,
        "node_id": node_id,
    }


def sign_envelope(envelope: dict, private_key: SigningKey | None = None) -> dict:
    """Encrypt sensitive payload types, then sign with the node key."""
    out = dict(envelope)
    out.setdefault("schema", "astra.envelope.v1")
    out.setdefault("created_ts", now_iso())
    node_id = out.get("node_id") or NODE_HUB
    out["node_id"] = node_id
    if out.get("type") in _SENSITIVE_TYPES:
        out["payload"] = _encrypt_sensitive_payload(out)
    key = private_key or ensure_node_key(node_id)
    out["sig"] = b64e(key.sign(canonicalize(out)).signature)
    return out


def verify_envelope(envelope: dict, public_key=None) -> bool:
    """Verify an envelope signature using the pinned node key (or an explicit key)."""
    if not isinstance(envelope, dict) or not envelope.get("sig"):
        return False
    if envelope.get("type") in _SENSITIVE_TYPES and not _has_encrypted_payload(envelope):
        return False
    key = public_key
    if key is None:
        node_id = envelope.get("node_id")
        if not node_id:
            return False
        key = get_node_verify_key(node_id)
    if key is None:
        return False
    try:
        key.verify(canonicalize(envelope), b64d(envelope["sig"]))
        return True
    except Exception:
        return False


def _payload_context(envelope: dict) -> str:
    return f"envelope:{envelope.get('node_id')}:{envelope.get('msg_id')}:{envelope.get('type')}"


def _encrypt_sensitive_payload(envelope: dict) -> dict:
    payload = envelope.get("payload")
    if _has_encrypted_payload(envelope):
        return payload
    context = _payload_context(envelope)
    plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {
        "protection": _ENCRYPTED_MARKER,
        "context": context,
        "ciphertext": encrypt_field(plaintext, context),
    }


def _has_encrypted_payload(envelope: dict) -> bool:
    payload = envelope.get("payload")
    return (
        isinstance(payload, dict)
        and payload.get("protection") == _ENCRYPTED_MARKER
        and payload.get("context") == _payload_context(envelope)
        and isinstance(payload.get("ciphertext"), str)
        and payload["ciphertext"].startswith("gcm1:")
    )


def decrypt_envelope_payload(envelope: dict, public_key=None) -> dict:
    """Verify then decrypt a sensitive envelope payload at its trusted receiver."""
    if envelope.get("type") not in _SENSITIVE_TYPES:
        return envelope.get("payload", {})
    if not verify_envelope(envelope, public_key):
        raise CryptoError("sensitive envelope signature or encryption is invalid")
    encrypted = envelope["payload"]
    plaintext = decrypt_field(encrypted["ciphertext"], encrypted["context"])
    try:
        payload = json.loads(plaintext)
    except json.JSONDecodeError as exc:
        raise CryptoError("decrypted envelope payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise CryptoError("decrypted envelope payload must be an object")
    return payload
