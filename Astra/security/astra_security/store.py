"""SQLite persistence for astra_security."""

from __future__ import annotations

import base64
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from .config import db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    device_id   TEXT PRIMARY KEY,
    astronaut_id TEXT NOT NULL,
    public_key  TEXT NOT NULL,
    source      TEXT,
    revoked     INTEGER NOT NULL DEFAULT 0,
    created_ts  TEXT NOT NULL,
    revoked_ts  TEXT
);
CREATE TABLE IF NOT EXISTS seq_counters (
    device_id TEXT PRIMARY KEY,
    last_seq  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS seen_seq (
    device_id TEXT PRIMARY KEY,
    last_seq  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS nonces (
    nonce     TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    ts        TEXT,
    seen_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS samples (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    metric    TEXT NOT NULL,
    value     REAL,
    ts        TEXT,
    source    TEXT,
    recv_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_samples_dev_metric ON samples(device_id, metric, id);
CREATE TABLE IF NOT EXISTS security_events (
    event_id     TEXT PRIMARY KEY,
    event_type   TEXT NOT NULL,
    device_id    TEXT,
    astronaut_id TEXT,
    severity     TEXT,
    time_start   TEXT,
    time_end     TEXT,
    evidence_hash TEXT,
    count        INTEGER NOT NULL DEFAULT 1,
    sig          TEXT,
    created_ts   TEXT,
    body         TEXT
);
CREATE TABLE IF NOT EXISTS event_cooldown (
    ckey           TEXT PRIMARY KEY,
    event_type     TEXT,
    device_id      TEXT,
    count          INTEGER NOT NULL DEFAULT 0,
    first_ts       TEXT,
    last_ts        TEXT,
    cooldown_until REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audit (
    seq       INTEGER PRIMARY KEY AUTOINCREMENT,
    actor     TEXT NOT NULL,
    action    TEXT NOT NULL,
    target    TEXT,
    details   TEXT,
    ts        TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    sig       TEXT
);
CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS users (
    username     TEXT PRIMARY KEY,
    role         TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    astronaut_id TEXT,
    created_ts   TEXT
);
"""


class Store:
    """Small SQLite wrapper. Use :func:`get_store` to obtain the default one."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_SCHEMA)
            self._migrate()
            self._conn.commit()

    def _migrate(self) -> None:
        """Add columns that may be missing on databases created by older versions."""
        cols = {row["name"] for row in self._conn.execute("PRAGMA table_info(samples)")}
        if "source" not in cols:
            self._conn.execute("ALTER TABLE samples ADD COLUMN source TEXT")

    def _exec(self, sql: str, params: Iterable = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            self._conn.commit()
            return cur

    def _query(self, sql: str, params: Iterable = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, tuple(params)).fetchall())

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def upsert_device(
        self,
        device_id: str,
        astronaut_id: str,
        public_key_b64: str,
        source: str | None = None,
        created_ts: str = "",
    ) -> None:
        self._exec(
            """INSERT INTO devices(device_id, astronaut_id, public_key, source, revoked, created_ts)
               VALUES(?,?,?,?,0,?)
               ON CONFLICT(device_id) DO UPDATE SET
                 astronaut_id=excluded.astronaut_id,
                 public_key=excluded.public_key,
                 source=excluded.source,
                 revoked=0,
                 revoked_ts=NULL""",
            (device_id, astronaut_id, public_key_b64, source, created_ts),
        )

    def get_device(self, device_id: str) -> dict | None:
        rows = self._query("SELECT * FROM devices WHERE device_id=?", (device_id,))
        return dict(rows[0]) if rows else None

    def revoke(self, device_id: str, revoked_ts: str) -> bool:
        cur = self._exec(
            "UPDATE devices SET revoked=1, revoked_ts=? WHERE device_id=?",
            (revoked_ts, device_id),
        )
        return cur.rowcount > 0

    def list_devices(self) -> list[dict]:
        return [dict(r) for r in self._query("SELECT * FROM devices ORDER BY device_id")]

    def get_last_seq(self, device_id: str) -> int | None:
        rows = self._query("SELECT last_seq FROM seq_counters WHERE device_id=?", (device_id,))
        return int(rows[0]["last_seq"]) if rows else None

    def next_seq(self, device_id: str) -> int:
        with self._lock:
            rows = self._query("SELECT last_seq FROM seq_counters WHERE device_id=?", (device_id,))
            new = (int(rows[0]["last_seq"]) if rows else 0) + 1
            self._exec(
                "INSERT INTO seq_counters(device_id, last_seq) VALUES(?,?) "
                "ON CONFLICT(device_id) DO UPDATE SET last_seq=excluded.last_seq",
                (device_id, new),
            )
            return new

    def advance_seq(self, device_id: str, seq: int) -> None:
        with self._lock:
            rows = self._query("SELECT last_seq FROM seq_counters WHERE device_id=?", (device_id,))
            current = int(rows[0]["last_seq"]) if rows else -1
            if seq > current:
                self._exec(
                    "INSERT INTO seq_counters(device_id, last_seq) VALUES(?,?) "
                    "ON CONFLICT(device_id) DO UPDATE SET last_seq=excluded.last_seq",
                    (device_id, seq),
                )

    def get_seen_seq(self, device_id: str) -> int | None:
        rows = self._query("SELECT last_seq FROM seen_seq WHERE device_id=?", (device_id,))
        return int(rows[0]["last_seq"]) if rows else None

    def set_seen_seq(self, device_id: str, seq: int) -> None:
        with self._lock:
            rows = self._query("SELECT last_seq FROM seen_seq WHERE device_id=?", (device_id,))
            current = int(rows[0]["last_seq"]) if rows else -1
            if seq > current:
                self._exec(
                    "INSERT INTO seen_seq(device_id, last_seq) VALUES(?,?) "
                    "ON CONFLICT(device_id) DO UPDATE SET last_seq=excluded.last_seq",
                    (device_id, seq),
                )

    def add_nonce(self, nonce: str, device_id: str, ts: str | None, seen_at: float | None = None) -> bool:
        """Return True if the nonce is new, False if it is a replay."""
        seen_at = time.time() if seen_at is None else seen_at
        with self._lock:
            rows = self._query("SELECT 1 FROM nonces WHERE nonce=?", (nonce,))
            if rows:
                return False
            self._exec(
                "INSERT INTO nonces(nonce, device_id, ts, seen_at) VALUES(?,?,?,?)",
                (nonce, device_id, ts, seen_at),
            )
            return True

    def prune_nonces(self, max_entries: int, ttl_seconds: float) -> int:
        cutoff = time.time() - ttl_seconds
        with self._lock:
            self._exec("DELETE FROM nonces WHERE seen_at < ?", (cutoff,))
            count = int(self._query("SELECT COUNT(*) AS c FROM nonces")[0]["c"])
            excess = count - max_entries
            if excess > 0:
                self._exec(
                    "DELETE FROM nonces WHERE nonce IN "
                    "(SELECT nonce FROM nonces ORDER BY seen_at ASC LIMIT ?)",
                    (excess,),
                )
            return count

    def record_sample(self, device_id: str, metric: str, value: float | None, ts: str | None,
                      source: str | None = None, keep: int = 50) -> None:
        with self._lock:
            self._exec(
                "INSERT INTO samples(device_id, metric, value, ts, source, recv_at) VALUES(?,?,?,?,?,?)",
                (device_id, metric, value, ts, source, time.time()),
            )
            self._exec(
                "DELETE FROM samples WHERE device_id=? AND metric=? AND id NOT IN "
                "(SELECT id FROM samples WHERE device_id=? AND metric=? ORDER BY id DESC LIMIT ?)",
                (device_id, metric, device_id, metric, keep),
            )

    def recent_samples(self, device_id: str, metric: str, limit: int = 50) -> list[dict]:
        rows = self._query(
            "SELECT value, ts, source, recv_at FROM samples WHERE device_id=? AND metric=? "
            "ORDER BY id DESC LIMIT ?",
            (device_id, metric, limit),
        )
        return [dict(r) for r in reversed(rows)]

    def latest_sample_by_source(self, metric: str, source: str) -> dict | None:
        """Most recent sample of ``metric`` recorded with a given ``source`` (any device)."""
        rows = self._query(
            "SELECT value, ts, device_id, source FROM samples WHERE metric=? AND source=? "
            "ORDER BY id DESC LIMIT 1",
            (metric, source),
        )
        return dict(rows[0]) if rows else None

    def insert_event(self, event: dict) -> None:
        self._exec(
            """INSERT INTO security_events(event_id, event_type, device_id, astronaut_id, severity,
                   time_start, time_end, evidence_hash, count, sig, created_ts, body)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(event_id) DO UPDATE SET count=excluded.count, body=excluded.body""",
            (
                event["event_id"], event["event_type"], event.get("device_id"), event.get("astronaut_id"),
                event.get("severity"), (event.get("time_window") or [None, None])[0],
                (event.get("time_window") or [None, None])[1], event.get("evidence_hash"),
                event.get("count", 1), event.get("sig"), event.get("created_ts"),
                json.dumps(event, sort_keys=True),
            ),
        )

    def count_events(self) -> int:
        return int(self._query("SELECT COUNT(*) AS c FROM security_events")[0]["c"])

    def get_event(self, event_id: str) -> dict | None:
        rows = self._query("SELECT * FROM security_events WHERE event_id=?", (event_id,))
        return dict(rows[0]) if rows else None

    def latest_event(self, event_type: str, device_id: str) -> dict | None:
        rows = self._query(
            "SELECT * FROM security_events WHERE event_type=? AND device_id=? "
            "ORDER BY created_ts DESC, rowid DESC LIMIT 1",
            (event_type, device_id),
        )
        return dict(rows[0]) if rows else None

    def list_events(self, limit: int = 100) -> list[dict]:
        return [dict(r) for r in self._query(
            "SELECT * FROM security_events ORDER BY created_ts DESC LIMIT ?", (limit,))]

    def get_cooldown(self, ckey: str) -> dict | None:
        rows = self._query("SELECT * FROM event_cooldown WHERE ckey=?", (ckey,))
        return dict(rows[0]) if rows else None

    def set_cooldown(self, ckey: str, event_type: str, device_id: str, count: int,
                     first_ts: str, last_ts: str, cooldown_until: float) -> None:
        self._exec(
            """INSERT INTO event_cooldown(ckey, event_type, device_id, count, first_ts, last_ts, cooldown_until)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(ckey) DO UPDATE SET
                 count=excluded.count, last_ts=excluded.last_ts, cooldown_until=excluded.cooldown_until""",
            (ckey, event_type, device_id, count, first_ts, last_ts, cooldown_until),
        )

    def next_event_number(self) -> int:
        return int(self.get_kv("event_counter", "0")) + 1

    def get_kv(self, key: str, default: Any = None) -> Any:
        rows = self._query("SELECT value FROM kv WHERE key=?", (key,))
        if not rows:
            return default
        return rows[0]["value"]

    def set_kv(self, key: str, value: Any) -> None:
        self._exec(
            "INSERT INTO kv(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )

    def upsert_user(self, username: str, role: str, password_hash: str,
                    astronaut_id: str | None, created_ts: str) -> None:
        self._exec(
            """INSERT INTO users(username, role, password_hash, astronaut_id, created_ts)
               VALUES(?,?,?,?,?)
               ON CONFLICT(username) DO UPDATE SET
                 role=excluded.role, password_hash=excluded.password_hash,
                 astronaut_id=excluded.astronaut_id""",
            (username, role, password_hash, astronaut_id, created_ts),
        )

    def get_user(self, username: str) -> dict | None:
        rows = self._query("SELECT * FROM users WHERE username=?", (username,))
        return dict(rows[0]) if rows else None

    def last_audit(self) -> dict | None:
        rows = self._query("SELECT * FROM audit ORDER BY seq DESC LIMIT 1")
        return dict(rows[0]) if rows else None

    def append_audit(self, actor: str, action: str, target: str, details: str, ts: str,
                     prev_hash: str, entry_hash: str, sig: str) -> None:
        self._exec(
            """INSERT INTO audit(actor, action, target, details, ts, prev_hash, entry_hash, sig)
               VALUES(?,?,?,?,?,?,?,?)""",
            (actor, action, target, details, ts, prev_hash, entry_hash, sig),
        )

    def all_audit(self, limit: int | None = None) -> list[dict]:
        sql = "SELECT * FROM audit ORDER BY seq ASC"
        params: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        return [dict(r) for r in self._query(sql, params)]

    def reset_all(self) -> None:
        """Danger: wipe mutable security state (used by tests / demo reset)."""
        with self._lock:
            for statement in (
                "DELETE FROM nonces",
                "DELETE FROM samples",
                "DELETE FROM security_events",
                "DELETE FROM event_cooldown",
                "DELETE FROM audit",
                "DELETE FROM kv",
                "DELETE FROM seq_counters",
            ):
                self._exec(statement)
            self._exec("UPDATE devices SET revoked=0, revoked_ts=NULL")


_DEFAULT_STORES: dict[str, Store] = {}
_DEFAULT_LOCK = threading.Lock()


def get_store(path: str | Path | None = None) -> Store:
    """Return a process-wide default store (cached by resolved path)."""
    if path is None:
        key = str(db_path().resolve())
    else:
        key = str(Path(path).resolve())
    with _DEFAULT_LOCK:
        store = _DEFAULT_STORES.get(key)
        if store is None:
            store = Store(key)
            _DEFAULT_STORES[key] = store
        return store


def reset_store() -> None:
    """Drop cached default stores (tests only)."""
    with _DEFAULT_LOCK:
        for store in _DEFAULT_STORES.values():
            store.close()
        _DEFAULT_STORES.clear()


def encode_key(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")
