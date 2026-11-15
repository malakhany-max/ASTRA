"""Link Simulator core: cut / delay / forward, with size cap and rate limiting.

Pure logic (no HTTP). The FastAPI app wraps this class. `forward` is a callable
that delivers one envelope to the Ground Backend and returns True on success.
Priority-1 traffic (security alerts, urgent health/radiation) is never rate limited.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Callable

from .queue import LinkQueue

MAX_ENVELOPE_BYTES = 64 * 1024
RATE_LIMIT_PER_MIN = 120
REQUIRED_FIELDS = ("msg_id", "priority", "created_ts", "type")


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class LinkSimulator:
    def __init__(self, queue: LinkQueue, forward: Callable[[dict], bool],
                 max_bytes: int = MAX_ENVELOPE_BYTES,
                 rate_per_min: int = RATE_LIMIT_PER_MIN):
        self.queue = queue
        self.forward = forward
        self.max_bytes = max_bytes
        self.rate_per_min = rate_per_min
        self.connected = bool(queue.get_meta("connected", True))
        self.delay_seconds = float(queue.get_meta("delay_seconds", 0.0))
        self.last_sync_ts: str | None = queue.get_meta("last_sync_ts")
        self._due: dict[str, float] = {}
        self._hits: dict[str, deque] = defaultdict(deque)

    def state(self) -> dict:
        return {
            "connected": self.connected,
            "mode": "connected" if self.connected else "autonomous",
            "delay_seconds": self.delay_seconds,
            "last_sync_ts": self.last_sync_ts,
            "queue_size": self.queue.size(),
        }

    def connect(self) -> None:
        self.connected = True
        self.queue.set_meta("connected", True)

    def disconnect(self) -> None:
        self.connected = False
        self.queue.set_meta("connected", False)
        self._due.clear()

    def set_delay(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("delay must be >= 0")
        self.delay_seconds = float(seconds)
        self.queue.set_meta("delay_seconds", self.delay_seconds)

    def _rate_limited(self, node_id: str, now: float) -> bool:
        hits = self._hits[node_id]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= self.rate_per_min:
            return True
        hits.append(now)
        return False

    def submit(self, envelope: dict, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        if not isinstance(envelope, dict):
            return {"accepted": False, "reason": "envelope must be an object"}
        missing = [k for k in REQUIRED_FIELDS if k not in envelope]
        if missing:
            return {"accepted": False, "reason": f"missing fields: {missing}"}
        raw_priority = envelope["priority"]
        if not isinstance(raw_priority, int) or isinstance(raw_priority, bool):
            return {"accepted": False, "reason": "priority must be an integer"}
        priority = raw_priority
        if priority not in (1, 2, 3, 4):
            return {"accepted": False, "reason": "priority must be 1..4"}
        try:
            size = len(json.dumps(envelope).encode("utf-8"))
        except (TypeError, ValueError):
            return {"accepted": False, "reason": "envelope not serializable"}
        if size > self.max_bytes:
            return {"accepted": False, "reason": "envelope too large"}
        node = str(envelope.get("node_id", "unknown"))
        if priority != 1 and self._rate_limited(node, now):
            return {"accepted": False, "reason": "rate limited"}
        queued = self.queue.enqueue(envelope)
        return {"accepted": True, "duplicate": not queued}

    def pump(self, now: float | None = None, limit: int = 50) -> list[str]:
        """Deliver whatever is due. Returns delivered msg_ids, in delivery order."""
        if not self.connected:
            return []
        now = time.time() if now is None else now
        delivered: list[str] = []
        for env in self.queue.next_batch(limit=limit, now=now):
            mid = env["msg_id"]
            due = self._due.setdefault(mid, now + self.delay_seconds)
            if now < due:
                continue
            try:
                ok = self.forward(env) is True
            except Exception:
                ok = False
            if ok:
                self.queue.mark_sent(mid)
                self._due.pop(mid, None)
                self.last_sync_ts = _iso(now)
                self.queue.set_meta("last_sync_ts", self.last_sync_ts)
                delivered.append(mid)
            else:
                self.queue.mark_failed(mid, now=now)
                self._due.pop(mid, None)
        return delivered
