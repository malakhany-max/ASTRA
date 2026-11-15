import pytest
from astra_link import LinkQueue


def env(msg_id, priority, ts):
    return {"schema": "astra.envelope.v1", "msg_id": msg_id, "priority": priority,
            "created_ts": ts, "direction": "uplink", "type": "summary", "payload": {}}


@pytest.fixture()
def q(tmp_path):
    queue = LinkQueue(tmp_path / "q.db", max_size=5)
    yield queue
    queue.close()


def test_priority_then_time_order(q):
    q.enqueue(env("a", 4, "2026-11-13T10:00:00Z"))
    q.enqueue(env("b", 2, "2026-11-13T10:00:01Z"))
    q.enqueue(env("c", 1, "2026-11-13T10:00:02Z"))
    q.enqueue(env("d", 3, "2026-11-13T10:00:03Z"))
    q.enqueue(env("e", 1, "2026-11-13T09:00:00Z"))
    assert [m["msg_id"] for m in q.next_batch()] == ["e", "c", "b", "d", "a"]


def test_idempotent_by_msg_id(q):
    assert q.enqueue(env("x", 2, "2026-11-13T10:00:00Z")) is True
    assert q.enqueue(env("x", 2, "2026-11-13T10:00:00Z")) is False
    assert q.size() == 1


def test_sent_not_resent_or_reenqueued(q):
    q.enqueue(env("x", 2, "2026-11-13T10:00:00Z"))
    q.mark_sent("x")
    assert q.next_batch() == []
    assert q.enqueue(env("x", 2, "2026-11-13T10:00:00Z")) is False


def test_bound_drops_lowest_priority_never_p1(q):
    for i in range(3):
        q.enqueue(env(f"p1-{i}", 1, f"2026-11-13T10:00:0{i}Z"))
    for i in range(5):
        q.enqueue(env(f"p4-{i}", 4, f"2026-11-13T11:00:0{i}Z"))
    ids = {m["msg_id"] for m in q.next_batch(limit=50)}
    assert {"p1-0", "p1-1", "p1-2"} <= ids
    assert q.size() == 5


def test_p1_never_dropped_even_over_bound(q):
    for i in range(8):
        q.enqueue(env(f"p1-{i}", 1, f"2026-11-13T10:00:0{i}Z"))
    assert q.size() == 8


def test_backoff_hides_then_releases(q):
    q.enqueue(env("x", 1, "2026-11-13T10:00:00Z"))
    delay = q.mark_failed("x", now=1000.0)
    assert delay > 0
    assert q.next_batch(now=1000.0) == []
    assert [m["msg_id"] for m in q.next_batch(now=1000.0 + delay + 1)] == ["x"]
