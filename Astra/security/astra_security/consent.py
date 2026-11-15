"""Consent filtering for uplink."""

from __future__ import annotations

TIERS = ("vitals_summary", "psych_summary", "raw_audio", "exposure_records")

_OVERRIDABLE = ("vitals_summary", "psych_summary", "exposure_records")


def default_consent(astronaut_id: str) -> dict:
    """Mission defaults: vitals, wellbeing and exposure shared; raw audio never."""
    return {
        "astronaut_id": astronaut_id,
        "tiers": {
            "vitals_summary": True,
            "psych_summary": True,
            "raw_audio": False,
            "exposure_records": True,
        },
        "emergency_override": True,
    }


def consent_allows(consent: dict, tier: str) -> bool:
    return bool(consent.get("tiers", {}).get(tier, False))


def filter_for_uplink(data: dict, consent: dict) -> dict:
    """Return a copy of ``data`` with non-consented tiers removed."""
    if not isinstance(data, dict):
        return data

    out = {k: v for k, v in data.items() if k != "raw_audio"}

    emergency = bool(data.get("emergency")) and bool(consent.get("emergency_override", False))

    for tier in TIERS:
        if tier == "raw_audio":
            continue
        if tier not in out:
            continue
        allowed = consent_allows(consent, tier) or (emergency and tier in _OVERRIDABLE)
        if not allowed:
            out.pop(tier, None)

    return out
