"""Store-and-forward link APIs shared by Hub and Link Simulator."""

import os
import threading

from .queue import LinkQueue

_uplink_queue: LinkQueue | None = None
_uplink_lock = threading.Lock()


def get_uplink_queue() -> LinkQueue:
    """Return the process-wide queue used by security-event uplinks."""
    global _uplink_queue
    with _uplink_lock:
        if _uplink_queue is None:
            _uplink_queue = LinkQueue(os.environ.get("ASTRA_LINK_DB") or "astra_link.db")
        return _uplink_queue


__all__ = ["LinkQueue", "get_uplink_queue"]
