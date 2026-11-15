from hub.view_models import alert_views, backend_id, indicator_views, series_view, ui_id


def test_astronaut_alias_and_reading_view_preserve_personal_baseline():
    assert backend_id("ast-zain") == "A-07"
    assert ui_id("A-07") == "ast-zain"
    readings = [
        {"metric": "heart_rate", "value": 60, "ts": "2026-11-01T00:00:00Z"},
        {"metric": "heart_rate", "value": 64, "ts": "2026-11-02T00:00:00Z"},
    ]
    statuses = [{"indicator": "heart_rate", "status": "attention", "reasons": ["Changed from baseline."]}]
    state = {"baselines": {"transit": {"heart_rate": {"mean": 62, "scale": 2}}}}
    result = indicator_views(readings, statuses, state)
    heart = next(item for item in result if item["key"] == "heartRate")
    assert heart["value"] == 64
    assert heart["status"] == "attention"
    assert heart["baseline"] == {"low": 60, "high": 64}
    assert heart["trend"] == "up"


def test_series_and_alert_ack_view_are_consistent():
    readings = [{"metric": "spo2", "value": 97, "ts": "2026-11-02T00:00:00Z"}]
    statuses = [{"astronaut_id": "A-07", "indicator": "spo2", "status": "urgent",
                 "computed_ts": "2026-11-02T00:00:00Z", "reasons": ["Below threshold."]}]
    series = series_view("spo2", readings, statuses, {}, "30d")
    real_point = next(item for item in series["samples"] if item["t"] == "2026-11-02T00:00:00Z")
    assert real_point["value"] == 97
    alert = alert_views(statuses)[0]
    assert alert["astronautId"] == "ast-zain"
    assert alert_views(statuses, {alert["id"]})[0]["acknowledged"] is True


def test_ui_routes_require_self_or_crew_permissions(tmp_path, monkeypatch):
    import sys
    from pathlib import Path
    from fastapi.testclient import TestClient

    root = Path(__file__).resolve().parents[2]
    for part in ("engine", "link", "attack_sim", "simulators"):
        sys.path.insert(0, str(root / part))
    sys.path.insert(0, str(root.parent / "security"))
    from astra_link import LinkQueue
    from hub.app import create_app
    from hub.store import HubStore
    import astra_security as sec

    store = HubStore(tmp_path / "hub.db")
    queue = LinkQueue(tmp_path / "link.db")
    client = TestClient(create_app(store=store, queue=queue))
    try:
        assert client.get("/api/crew/overview").status_code == 401
        assert client.get("/api/astronauts/ast-maya").status_code == 401
        assert client.get("/api/astronauts/ast-zain").status_code == 200

        viewer = sec.rbac.create_session({"username": "viewer-test", "role": "viewer", "astronaut_id": None})
        headers = {"Authorization": f"Bearer {viewer}"}
        overview = client.get("/api/crew/overview", headers=headers)
        assert overview.status_code == 200
        assert len(overview.json()["astronauts"]) == 3
        assert client.get("/api/astronauts/ast-maya", headers=headers).status_code == 200
        assert client.post("/api/alerts/A-07%3Aspo2%3A2026-01-01T00%3A00%3A00Z/ack", headers=headers).status_code == 403
    finally:
        store.close()
        queue.close()
