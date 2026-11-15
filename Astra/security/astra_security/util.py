"""Small shared helpers: canonical JSON, time, hashing, base64."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone


def canonicalize(obj: dict) -> bytes:
    """Canonical JSON: sorted keys, no whitespace, UTF-8. ``sig`` is excluded."""
    body = {k: v for k, v in obj.items() if k != "sig"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp, tolerating a trailing ``Z``."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def seconds_between(a: str, b: str) -> float:
    return (parse_iso(a) - parse_iso(b)).total_seconds()


def shift_iso(value: str, seconds: float) -> str:
    return iso(parse_iso(value) + timedelta(seconds=seconds))


def new_nonce() -> str:
    """16 random bytes as 32 lowercase hex characters (contract 7.1)."""
    return secrets.token_hex(16)


def is_valid_nonce(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 32:
        return False
    return all(c in "0123456789abcdef" for c in value)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_prefixed(data: bytes) -> str:
    return "sha256:" + sha256_hex(data)


def b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))
