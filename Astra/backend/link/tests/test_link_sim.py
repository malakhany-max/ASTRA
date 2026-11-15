import pytest
from astra_link import LinkQueue
from astra_link.link_sim import LinkSimulator


def env(msg_id, priority, ts, node="hub-01"):
    return {"schema": "astra.envelope.v1", "msg_id": msg_id, "priority": priority,
            "created_ts": ts, "type": "summary", "node_id": node, "payload": {}}


@pytest.fixture()
def sim(tmp_path):
    q = LinkQueue(tmp_path / "q.db")
    delivered = []
    s = LinkSimulator(q, lambda e: delivered.append(e["msg_id"]) or True,
                      max_bytes=2000, rate_per_min=3)
    s.delivered = delivered
    yield s
    q.close()


def test_held_while_cut_then_delivered_by_priority(sim):
    sim.disconnect()
    for mid, pr, ts in [("a", 4, "t1"), ("b", 2, "t2"), ("c", 1, "t3"), ("d", 3, "t4")]:
        assert sim.submit(env(mid, pr, ts), now=1.0)["accepted"]
    assert sim.pump(now=2.0) == []
    assert sim.state()["mode"] == "autonomous" and sim.state()["queue_size"] == 4
    sim.connect()
    assert sim.pump(now=3.0) == ["c", "b", "d", "a"]
    assert sim.state()["queue_size"] == 0 and sim.state()["last_sync_ts"]


def test_delay_holds_until_due(sim):
    sim.set_delay(10)
    sim.submit(env("a", 2, "t1"), now=100.0)
    assert sim.pump(now=100.0) == []
    assert sim.pump(now=105.0) == []
    assert sim.pump(now=111.0) == ["a"]


def test_oversize_rejected(sim):
    e = env("big", 2, "t1")
    e["payload"] = {"x": "y" * 5000}
    res = sim.submit(e, now=1.0)
    assert res["accepted"] is False and "large" in res["reason"]


def test_malformed_rejected(sim):
    assert sim.submit({"msg_id": "x"}, now=1.0)["accepted"] is False
    assert sim.submit(env("p", 9, "t1"), now=1.0)["accepted"] is False


def test_rate_limit_but_priority1_exempt(sim):
    for i in range(3):
        assert sim.submit(env(f"r{i}", 4, f"t{i}"), now=10.0)["accepted"]
    assert sim.submit(env("r3", 4, "t9"), now=10.0)["reason"] == "rate limited"
    assert sim.submit(env("alert", 1, "t9"), now=10.0)["accepted"] is True


def test_failed_forward_retries_later(tmp_path):
    q = LinkQueue(tmp_path / "q2.db")
    calls = {"n": 0}

    def flaky(e):
        calls["n"] += 1
        return calls["n"] > 1

    s = LinkSimulator(q, flaky)
    s.submit(env("a", 1, "t1"), now=1.0)
    assert s.pump(now=1.0) == []
    assert s.pump(now=1.5) == []
    assert s.pump(now=100.0) == ["a"]
    q.close()


def test_duplicate_submit_delivered_once(sim):
    sim.submit(env("a", 2, "t1"), now=1.0)
    assert sim.submit(env("a", 2, "t1"), now=1.0)["duplicate"] is True
    assert sim.pump(now=2.0) == ["a"]
    assert sim.pump(now=3.0) == []
