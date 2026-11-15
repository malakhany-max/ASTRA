"""Shared pytest fixtures for astra_security tests.

Every test runs against an isolated SQLite DB + keystore under tmp_path, and a
capturing uplink sink (so security events never touch the real link queue).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_security_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTRA_DB", str(tmp_path / "astra_security.db"))
    monkeypatch.setenv("ASTRA_KEYS_DIR", str(tmp_path / "keys"))
    monkeypatch.setenv("ASTRA_LINK_DB", str(tmp_path / "astra_link.db"))

    import astra_security as sec

    sec.reset_store()
    captured: list[dict] = []
    sec.set_uplink_sink(lambda envelope: captured.append(envelope))
    yield captured
    sec.set_uplink_sink(None)
    sec.reset_store()


@pytest.fixture()
def make_reading():
    """Factory returning a base (unsigned) reading dict."""
    def _make(metric="heart_rate", value=72.0, device_id="watch-A07",
              astronaut_id="A-07", source="wearable", **extra):
        reading = {
            "schema": "astra.reading.v1",
            "device_id": device_id,
            "astronaut_id": astronaut_id,
            "metric": metric,
            "value": value,
            "unit": "bpm",
            "source": source,
            "quality": 0.95,
        }
        reading.update(extra)
        return reading
    return _make


import astra_security as sec


@pytest.fixture()
def paired(make_reading):
    """Pairs watch-A07 with a freshly generated key."""
    sec.ensure_device_key("watch-A07")
    if not sec.is_trusted("watch-A07"):
        sec.pair_device("watch-A07", sec.get_public_key("watch-A07"), "A-07")
    return "watch-A07"
