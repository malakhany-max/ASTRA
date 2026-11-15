from hub.store import HubStore


def test_sensitive_hub_data_round_trips_from_encrypted_store(tmp_path):
    store = HubStore(tmp_path / "hub.db")
    try:
        reading = {"astronaut_id": "A-07", "metric": "heart_rate", "value": 63,
                   "ts": "2026-01-01T00:00:00Z", "sig": "demo"}
        store.save_reading(reading)
        assert store.readings("A-07", "heart_rate") == [reading]
        status = {"astronaut_id": "A-07", "indicator": "heart_rate", "status": "normal",
                  "computed_ts": "2026-01-01T00:00:00Z"}
        store.save_status(status)
        assert store.statuses("A-07") == [status]
        assert "gcm1:" in store.db.execute("SELECT token FROM readings").fetchone()[0]
    finally:
        store.close()


def test_hub_backup_is_written_as_an_encrypted_snapshot(tmp_path):
    store = HubStore(tmp_path / "hub.db")
    try:
        store.save_profile({"astronaut_id": "A-07", "name": "Fictional crew member"})
        stamp = store.create_backup()
        state = store.backup_state()
        assert state["available"] is True
        assert state["encrypted"] is True
        assert state["last_backup_ts"] == stamp
        assert b"Fictional crew member" not in store.backup_path.read_bytes()
    finally:
        store.close()
