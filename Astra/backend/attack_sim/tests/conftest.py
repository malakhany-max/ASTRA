"""Keep simulator tests away from the developer's configured keystore."""

import pytest


@pytest.fixture(autouse=True)
def isolated_security_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTRA_DB", str(tmp_path / "astra_security.db"))
    monkeypatch.setenv("ASTRA_KEYS_DIR", str(tmp_path / "keys"))
    import astra_security as sec

    sec.reset_store()
    sec.set_uplink_sink(lambda _envelope: None)
    yield
    sec.set_uplink_sink(None)
    sec.reset_store()
