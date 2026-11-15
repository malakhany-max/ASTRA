from astra_ground.store import GroundStore


def test_encrypted_uplink_history_alert_ack_and_backup(tmp_path):
    store = GroundStore(tmp_path / "ground.db", tmp_path / "backup.enc")
    try:
        store.seed_profiles([{"astronaut_id": "A-07", "name": "Demo", "mission_history": []}])
        envelope = {"msg_id": "message-1", "type": "alert", "created_ts": "2026-01-01T00:00:00Z"}
        payload = {"astronaut_id": "A-07", "vitals_summary": {"status": "attention"}}
        assert store.save_uplink(envelope, payload) == "A-07"
        history = store.history("A-07")
        assert history["uplinks"][0]["payload"] == payload
        alerts = store.list_alerts("A-07")
        assert len(alerts) == 1 and not alerts[0]["acknowledged"]
        assert store.acknowledge("message-1", "flight")
        assert store.list_alerts("A-07")[0]["acknowledged"]
        assert store.backup_path.exists()
        assert store.backup_state()["available"]
    finally:
        store.close()


def test_command_history_is_persisted_with_encrypted_payload(tmp_path):
    store = GroundStore(tmp_path / "ground.db", tmp_path / "backup.enc")
    try:
        store.save_command("cmd-1", "A-07", "thresholds", {"key": "heartRate", "low": 55},
                           "2026-01-01T00:00:00Z", "msg-1")
        assert store.commands() == [{
            "id": "cmd-1", "astronaut_id": "A-07", "type": "thresholds",
            "payload": {"key": "heartRate", "low": 55},
            "created_ts": "2026-01-01T00:00:00Z", "status": "pending", "msg_id": "msg-1", "created_by": "unknown",
            "delivered_ts": None,
        }]
    finally:
        store.close()


def test_mark_delivered_reconciles_hidden_pending_duplicates(tmp_path):
    store = GroundStore(tmp_path / "ground.db", tmp_path / "backup.enc")
    try:
        store.save_command("cmd-1", "A-07", "schedule", {"checkinTime": "19:30"},
                           "2026-01-01T00:00:00Z", "msg-1")
        store.save_command("cmd-2", "A-07", "schedule", {"checkinTime": "19:30"},
                           "2026-01-01T00:01:00Z", "msg-2")
        assert [row["msg_id"] for row in store.pending_commands()] == ["msg-1", "msg-2"]
        assert store.mark_delivered(["msg-1", "msg-2"]) == 2
        delivered = {row["msg_id"]: row for row in store.commands()}
        assert delivered["msg-1"]["status"] == "delivered"
        assert delivered["msg-2"]["delivered_ts"] == "2026-01-01T00:01:00Z"
    finally:
        store.close()


def test_command_api_enforces_roles_and_returns_ui_history(tmp_path, monkeypatch):
    import sys
    from pathlib import Path
    from fastapi.testclient import TestClient

    root = Path(__file__).resolve().parents[2]
    for part in ("link", "simulators", "ground-backend", "hub"):
        sys.path.insert(0, str(root / part))
    sys.path.insert(0, str(root.parent / "security"))
    import astra_security as sec
    from astra_link import LinkQueue
    from astra_ground.app import create_app

    monkeypatch.setenv("ASTRA_KEYS_DIR", str(tmp_path / "keys"))
    monkeypatch.setenv("ASTRA_DB", str(tmp_path / "security.db"))
    sec.reset_store()
    store = GroundStore(tmp_path / "ground.db", tmp_path / "backup.enc")
    queue = LinkQueue(tmp_path / "link.db")
    client = TestClient(create_app(store=store, queue=queue))
    surgeon = sec.rbac.create_session({"username": "surgeon-test", "role": "flight_surgeon", "astronaut_id": None})
    viewer = sec.rbac.create_session({"username": "viewer-test", "role": "viewer", "astronaut_id": None})
    try:
        assert client.get("/api/commands").status_code == 401
        command = client.post("/api/commands", headers={"Authorization": f"Bearer {surgeon}"}, json={
            "command_type": "thresholds_bundle",
            "payload": {"astronaut_id": "A-07", "ui_type": "thresholds", "key": "heartRate", "low": 55},
        })
        assert command.status_code == 202
        history = client.get("/api/commands", headers={"Authorization": f"Bearer {viewer}"})
        assert history.status_code == 200
        assert history.json()[0]["type"] == "thresholds"
        denied = client.post("/api/commands", headers={"Authorization": f"Bearer {viewer}"}, json={
            "command_type": "config_bundle", "payload": {"astronaut_id": "A-07"},
        })
        assert denied.status_code == 403
    finally:
        store.close()
        queue.close()
        sec.reset_store()
