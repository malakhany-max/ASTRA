"""Deterministic input safety guard for the local companion."""
from __future__ import annotations

import re

MAX_INPUT_CHARS = 2_000
_INJECTION_PATTERNS = (
    re.compile(r"(?i)\b(ignore|disregard|override)\b.{0,60}\b(previous|system|developer)\b"),
    re.compile(r"(?i)\b(reveal|print|show|repeat)\b.{0,50}\b(system prompt|hidden instructions|secret key)\b"),
    re.compile(r"(?i)<\s*/?\s*(system|assistant|developer)\s*>"),
)


class InputRejected(ValueError):
    """Raised when input exceeds the deterministic guard's accepted format."""


def validate_input(text: str) -> str:
    """Return normalized user text or raise ``InputRejected``."""
    if not isinstance(text, str):
        raise InputRejected("text must be a string")
    normalized = text.strip()
    if not normalized:
        raise InputRejected("text must not be empty")
    if len(normalized) > MAX_INPUT_CHARS:
        raise InputRejected(f"text exceeds {MAX_INPUT_CHARS} characters")
    if "\x00" in normalized or any(ord(ch) < 32 and ch not in "\n\r\t" for ch in normalized):
        raise InputRejected("text contains unsupported control characters")
    if any(pattern.search(normalized) for pattern in _INJECTION_PATTERNS):
        raise InputRejected("text was rejected by the safety input filter")
    return normalized
