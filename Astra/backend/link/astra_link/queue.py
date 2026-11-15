"""Store-and-forward queue (SQLite) for ASTRA link traffic.

Order: priority first (1 = highest), then created_ts.
Idempotent by msg_id. Failed sends back off. Bounded size: drops the lowest
priority first and never drops priority 1.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

DEFAULT_MAX_SIZE = 1000
BACKOFF_BASE_S = 2.0
BACKOFF_CAP_S = 300.0


class LinkQueue:
    def __init__(self, db_path=None, max_size: int = DEFAULT_MAX_SIZE):
        self.db_path = str(db_path or os.environ.get("ASTRA_LINK_DB") or "astra_link.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.max_size = max_size
        self._lock = threading.Lock()
        self._con = sqlite3.connect(self.db_path, check_same_thread=False)
        self._con.execute(
            """CREATE TABLE IF NOT EXISTS queue (
                msg_id TEXT PRIMARY KEY,
                priority INTEGER NOT NULL,
                created_ts TEXT NOT NULL,
                envelope TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt REAL NOT NULL DEFAULT 0
            )"""
        )
        self._con.execute("CREATE TABLE IF NOT EXISTS link_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self._con.commit()

    def enqueue(self, envelope: dict) -> bool:
        """Add an envelope. Returns False if msg_id was already seen (idempotent)."""
        msg_id = str(envelope["msg_id"])
        priority = int(envelope.get("priority", 4))
        created = str(envelope.get("created_ts", ""))
        with self._lock:
            cur = self._con.execute(
                "INSERT OR IGNORE INTO queue (msg_id, priority, created_ts, envelope)"
                " VALUES (?, ?, ?, ?)",
                (msg_id, priority, created, json.dumps(envelope, sort_keys=True)),
            )
            inserted = cur.rowcount == 1
            self._enforce_bound()
            self._con.commit()
        return inserted

    def _enforce_bound(self) -> None:
        pending = self._con.execute(
            "SELECT COUNT(*) FROM queue WHERE status='pending'").fetchone()[0]
        excess = pending - self.max_size
        if excess <= 0:
            return
        rows = self._con.execute(
            "SELECT msg_id FROM queue WHERE status='pending' AND priority > 1"
            " ORDER BY priority DESC, created_ts ASC LIMIT ?", (excess,)).fetchall()
        self._con.executemany("DELETE FROM queue WHERE msg_id=?", rows)

    def next_batch(self, limit: int = 20, now: float | None = None) -> list[dict]:
        now = time.time() if now is None else now
        with self._lock:
            rows = self._con.execute(
                "SELECT envelope FROM queue WHERE status='pending' AND next_attempt <= ?"
                " ORDER BY priority ASC, created_ts ASC, msg_id ASC LIMIT ?",
                (now, limit)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def mark_sent(self, msg_id: str) -> None:
        with self._lock:
            self._con.execute("UPDATE queue SET status='sent' WHERE msg_id=?", (msg_id,))
            self._con.commit()

    def mark_failed(self, msg_id: str, now: float | None = None) -> float:
        """Record a failed attempt and schedule a retry with exponential backoff."""
        now = time.time() if now is None else now
        with self._lock:
            row = self._con.execute(
                "SELECT attempts FROM queue WHERE msg_id=?", (msg_id,)).fetchone()
            attempts = (row[0] if row else 0) + 1
            delay = min(BACKOFF_BASE_S * (2 ** (attempts - 1)), BACKOFF_CAP_S)
            self._con.execute(
                "UPDATE queue SET attempts=?, next_attempt=? WHERE msg_id=?",
                (attempts, now + delay, msg_id))
            self._con.commit()
        return delay

    def size(self) -> int:
        with self._lock:
            return self._con.execute(
                "SELECT COUNT(*) FROM queue WHERE status='pending'").fetchone()[0]

    def sent_ids(self) -> set[str]:
        with self._lock:
            return {row[0] for row in self._con.execute(
                "SELECT msg_id FROM queue WHERE status='sent'")}

    def set_meta(self, key: str, value) -> None:
        with self._lock:
            self._con.execute(
                "INSERT INTO link_meta(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)),
            )
            self._con.commit()

    def get_meta(self, key: str, default=None):
        with self._lock:
            row = self._con.execute("SELECT value FROM link_meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def close(self) -> None:
        self._con.close()
