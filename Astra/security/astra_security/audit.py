"""Append-only audit log stored as a hash chain."""

from __future__ import annotations

import json

from .keys import NODE_AUDIT, ensure_node_key
from .store import get_store
from .util import b64d, b64e, canonicalize, now_iso, sha256_hex

GENESIS_HASH = "0" * 64


def _payload(actor: str, action: str, target: str, details: dict, ts: str) -> bytes:
    return canonicalize({"actor": actor, "action": action, "target": target,
                         "details": details, "ts": ts})


def _entry_hash(prev_hash: str, payload: bytes) -> str:
    return sha256_hex(prev_hash.encode("ascii") + payload)


def audit_log(actor: str, action: str, target: str, details: dict | None = None) -> None:
    """Append an entry to the tamper-evident audit chain."""
    store = get_store()
    details = details or {}
    ts = now_iso()
    last = store.last_audit()
    prev_hash = last["entry_hash"] if last else GENESIS_HASH
    payload = _payload(actor, action, target, details, ts)
    entry_hash = _entry_hash(prev_hash, payload)
    sig = b64e(ensure_node_key(NODE_AUDIT).sign((prev_hash + entry_hash).encode("ascii")).signature)
    store.append_audit(actor, action, target, json.dumps(details, sort_keys=True),
                       ts, prev_hash, entry_hash, sig)


def get_entries(limit: int | None = None) -> list[dict]:
    return get_store().all_audit(limit)


def verify_chain() -> bool:
    """Return True iff the whole audit chain is intact."""
    ok, _ = verify_chain_detailed()
    return ok


def verify_chain_detailed() -> tuple[bool, list[str]]:
    errors: list[str] = []
    prev_hash = GENESIS_HASH
    for row in get_store().all_audit():
        try:
            details = json.loads(row["details"]) if row["details"] else {}
        except json.JSONDecodeError:
            errors.append(f"row {row['seq']}: details is not valid JSON")
            return False, errors
        payload = _payload(row["actor"], row["action"], row["target"], details, row["ts"])
        expected = _entry_hash(prev_hash, payload)
        if row["prev_hash"] != prev_hash:
            errors.append(f"row {row['seq']}: prev_hash mismatch (chain broken)")
            return False, errors
        if row["entry_hash"] != expected:
            errors.append(f"row {row['seq']}: entry_hash mismatch (row edited)")
            return False, errors
        key = ensure_node_key(NODE_AUDIT).verify_key
        try:
            key.verify((prev_hash + row["entry_hash"]).encode("ascii"), b64d(row["sig"] or ""))
        except Exception:
            errors.append(f"row {row['seq']}: signature invalid")
            return False, errors
        prev_hash = row["entry_hash"]
    return True, errors
