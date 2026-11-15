import pytest
from fastapi.testclient import TestClient

from astra_link import LinkQueue
from astra_link.app import create_app
from astra_link.link_sim import LinkSimulator


def env(msg_id, priority, ts="2026-11-13T10:00:00Z"):
    return {"schema": "astra.envelope.v1", "msg_id": msg_id, "priority": priority,
            "created_ts": ts, "type": "alert", "node_id": "hub-01", "payload": {}}


@pytest.fixture()
def client(tmp_path):
    q = LinkQueue(tmp_path / "q.db")
    got = []
    sim = LinkSimulator(q, lambda e: got.append(e["msg_id"]) or True, max_bytes=2000)
    c = TestClient(create_app(sim))
    c.got = got
    c.sim = sim
    yield c
    q.close()


def test_state_default(client):
    s = client.get("/link/state").json()
    assert s["connected"] is True and s["mode"] == "connected" and s["queue_size"] == 0


def test_cut_submit_restore_delivers_by_priority(client):
    assert client.post("/link/disconnect").json()["mode"] == "autonomous"
    for mid, pr, ts in [("a", 4, "t1"), ("b", 1, "t2"), ("c", 2, "t3")]:
        assert client.post("/link/submit", json=env(mid, pr, ts)).status_code == 202
    assert client.get("/link/state").json()["queue_size"] == 3
    client.post("/link/connect")
    client.sim.pump()
    assert client.got == ["b", "c", "a"]


def test_delay_endpoint_and_validation(client):
    assert client.post("/link/delay", json={"seconds": 5}).json()["delay_seconds"] == 5
    assert client.post("/link/delay", json={"seconds": -1}).status_code == 422


def test_oversize_and_malformed(client):
    big = env("big", 2)
    big["payload"] = {"x": "y" * 5000}
    assert client.post("/link/submit", json=big).status_code == 413
    assert client.post("/link/submit", json={"msg_id": "x"}).status_code == 400
    assert client.post("/link/submit", content=b"not json").status_code == 400


def test_submit_uses_slowapi_and_keeps_priority_one_exempt(client):
    for i in range(125):
        response = client.post("/link/submit", json=env(f"p1-{i}", 1))
        assert response.status_code == 202

    for i in range(120):
        envelope = env(f"routine-{i}", 2)
        envelope["node_id"] = f"hub-{i}"
        assert client.post("/link/submit", json=envelope).status_code == 202

    envelope = env("routine-over-limit", 2)
    envelope["node_id"] = "another-hub"
    assert client.post("/link/submit", json=envelope).status_code == 429
