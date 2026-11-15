"""Encrypted SQLite persistence for the onboard Hub."""

from __future__ import annotations

import json
import base64
import os
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

from . import security_adapter as sec


class HubStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.environ.get("ASTRA_HUB_DB") or Path(__file__).resolve().parents[1] / "data" / "hub.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_path = Path(os.environ.get("ASTRA_HUB_BACKUP", self.path.with_suffix(".backup.enc")))
        self.backup_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._last_backup = 0.0
        self._backup_interval = 300.0
        self._cache: dict[str, str] = {}
        self._writes = 0
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY, astronaut_id TEXT, metric TEXT, ts TEXT, token TEXT);
        CREATE INDEX IF NOT EXISTS idx_hub_readings ON readings(astronaut_id, metric, id);
        CREATE INDEX IF NOT EXISTS idx_hub_readings_all ON readings(astronaut_id, id);
        CREATE TABLE IF NOT EXISTS statuses(id INTEGER PRIMARY KEY, astronaut_id TEXT, ts TEXT, token TEXT);
        CREATE INDEX IF NOT EXISTS idx_hub_statuses ON statuses(astronaut_id, id);
        CREATE TABLE IF NOT EXISTS checkins(id INTEGER PRIMARY KEY, astronaut_id TEXT, ts TEXT, token TEXT);
        CREATE TABLE IF NOT EXISTS consents(astronaut_id TEXT PRIMARY KEY, payload TEXT);
        CREATE TABLE IF NOT EXISTS plans(astronaut_id TEXT PRIMARY KEY, week INTEGER, payload TEXT);
        CREATE TABLE IF NOT EXISTS engine_state(astronaut_id TEXT PRIMARY KEY, payload TEXT);
        CREATE TABLE IF NOT EXISTS hub_kv(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS anomalies(id INTEGER PRIMARY KEY, astronaut_id TEXT, ts TEXT, kind TEXT, details TEXT);
        CREATE TABLE IF NOT EXISTS profiles(astronaut_id TEXT PRIMARY KEY, payload TEXT);
        CREATE TABLE IF NOT EXISTS exposure_records(event_id TEXT PRIMARY KEY, astronaut_id TEXT, ts TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS downlink_bundles(bundle_id INTEGER PRIMARY KEY, type TEXT, ts TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS astronaut_settings(astronaut_id TEXT PRIMARY KEY, token TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS alert_acknowledgements(alert_id TEXT PRIMARY KEY, actor TEXT NOT NULL, ts TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS plan_items(astronaut_id TEXT, week TEXT, item_id TEXT, done INTEGER NOT NULL, updated_ts TEXT NOT NULL, PRIMARY KEY(astronaut_id, week, item_id));
        """)
        self.db.commit()

    def _save_secret(self, table, astronaut_id, value, column="payload"):
        context = f"hub:{table}:{astronaut_id}"
        token = sec.encrypt_field(json.dumps(value, sort_keys=True), context)
        with self.lock:
            if table == "readings":
                cur = self.db.execute("INSERT INTO readings(astronaut_id,metric,ts,token) VALUES(?,?,?,?)",
                                      (astronaut_id, value.get("metric"), value.get("ts", ""), token))
                row_id = cur.lastrowid
            elif table == "statuses":
                cur = self.db.execute("INSERT INTO statuses(astronaut_id,ts,token) VALUES(?,?,?)",
                                      (astronaut_id, value.get("computed_ts", ""), token)); row_id = cur.lastrowid
            else:
                cur = self.db.execute("INSERT INTO checkins(astronaut_id,ts,token) VALUES(?,?,?)",
                                      (astronaut_id, value.get("ts", ""), token)); row_id = cur.lastrowid
            self.db.commit()
            self._writes += 1
            if self._writes % 200 == 0:
                self.prune()
        return row_id

    def _decrypt_token(self, token, context):
        cached = self._cache.get(token)
        if cached is not None:
            return cached
        value = sec.decrypt_field(token, context)
        if len(self._cache) > 4000:
            self._cache.clear()
        self._cache[token] = value
        return value

    def prune(self):
        limits = (("readings", 4000), ("statuses", 900), ("checkins", 200), ("anomalies", 800))
        with self.lock:
            for table, keep in limits:
                for row in self.db.execute(f"SELECT DISTINCT astronaut_id FROM {table}").fetchall():
                    self.db.execute(
                        f"DELETE FROM {table} WHERE astronaut_id=? AND id NOT IN "
                        f"(SELECT id FROM {table} WHERE astronaut_id=? ORDER BY id DESC LIMIT ?)",
                        (row[0], row[0], keep))
            self.db.execute("DELETE FROM anomalies WHERE id NOT IN (SELECT id FROM anomalies ORDER BY id DESC LIMIT 1200)")
            self.db.commit()

    def save_reading(self, reading): return self._save_secret("readings", reading["astronaut_id"], reading)
    def save_status(self, status): return self._save_secret("statuses", status["astronaut_id"], status)
    def save_checkin(self, checkin): return self._save_secret("checkins", checkin["astronaut_id"], checkin)

    def _decode_rows(self, rows, table, astronaut_id):
        context = f"hub:{table}:{astronaut_id}"
        return [json.loads(self._decrypt_token(row["token"], context)) for row in rows]

    def readings(self, astronaut_id, metric=None, limit=500):
        sql, params = "SELECT token FROM readings WHERE astronaut_id=?", [astronaut_id]
        if metric:
            sql += " AND metric=?"; params.append(metric)
        sql += " ORDER BY id DESC LIMIT ?"; params.append(limit)
        rows = self.db.execute(sql, params).fetchall()
        return list(reversed(self._decode_rows(rows, "readings", astronaut_id)))

    def latest_readings(self, astronaut_id, per_metric=2):
        rows = self.db.execute(
            "SELECT token FROM readings WHERE id IN ("
            "SELECT id FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY metric ORDER BY id DESC) AS rank"
            " FROM readings WHERE astronaut_id=?) WHERE rank <= ?) ORDER BY id",
            (astronaut_id, per_metric)).fetchall()
        return self._decode_rows(rows, "readings", astronaut_id)

    def psych_readings(self, astronaut_id, limit=30):
        rows = self.db.execute(
            "SELECT token FROM readings WHERE astronaut_id=? AND ("
            "metric LIKE 'mood%' OR metric LIKE 'dizziness%' OR metric LIKE 'wellbeing%') "
            "ORDER BY id DESC LIMIT ?", (astronaut_id, limit)).fetchall()
        return list(reversed(self._decode_rows(rows, "readings", astronaut_id)))

    def statuses(self, astronaut_id, limit=100):
        rows = self.db.execute("SELECT token FROM statuses WHERE astronaut_id=? ORDER BY id DESC LIMIT ?",
                               (astronaut_id, limit)).fetchall()
        return list(reversed(self._decode_rows(rows, "statuses", astronaut_id)))

    def checkins(self, astronaut_id, limit=200):
        rows = self.db.execute("SELECT token FROM checkins WHERE astronaut_id=? ORDER BY id DESC LIMIT ?",
                               (astronaut_id, limit)).fetchall()
        return list(reversed(self._decode_rows(rows, "checkins", astronaut_id)))

    def latest_reading(self, astronaut_id, metric):
        result = self.readings(astronaut_id, metric, 1)
        return result[-1] if result else None

    def get_state(self, astronaut_id):
        row = self.db.execute("SELECT payload FROM engine_state WHERE astronaut_id=?", (astronaut_id,)).fetchone()
        return json.loads(self._decrypt_token(row[0], f"hub:engine_state:{astronaut_id}")) if row else {}

    def set_state(self, astronaut_id, state):
        token = sec.encrypt_field(json.dumps(state, sort_keys=True), f"hub:engine_state:{astronaut_id}")
        self.db.execute("INSERT INTO engine_state VALUES(?,?) ON CONFLICT(astronaut_id) DO UPDATE SET payload=excluded.payload",
                        (astronaut_id, token)); self.db.commit()

    def get_consent(self, astronaut_id):
        row = self.db.execute("SELECT payload FROM consents WHERE astronaut_id=?", (astronaut_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def set_consent(self, astronaut_id, consent):
        self.db.execute("INSERT INTO consents VALUES(?,?) ON CONFLICT(astronaut_id) DO UPDATE SET payload=excluded.payload",
                        (astronaut_id, json.dumps(consent, sort_keys=True))); self.db.commit()

    def get_settings(self, astronaut_id):
        row = self.db.execute("SELECT token FROM astronaut_settings WHERE astronaut_id=?", (astronaut_id,)).fetchone()
        return json.loads(self._decrypt_token(row[0], f"hub:settings:{astronaut_id}")) if row else None

    def set_settings(self, astronaut_id, settings):
        token = sec.encrypt_field(json.dumps(settings, sort_keys=True), f"hub:settings:{astronaut_id}")
        self.db.execute("INSERT INTO astronaut_settings VALUES(?,?) ON CONFLICT(astronaut_id) DO UPDATE SET token=excluded.token",
                        (astronaut_id, token)); self.db.commit()

    def plan_progress(self, astronaut_id, week):
        rows = self.db.execute("SELECT item_id,done FROM plan_items WHERE astronaut_id=? AND week=?",
                               (astronaut_id, week)).fetchall()
        return {row[0]: bool(row[1]) for row in rows}

    def set_plan_item(self, astronaut_id, week, item_id, done, ts):
        self.db.execute(
            "INSERT INTO plan_items VALUES(?,?,?,?,?) ON CONFLICT(astronaut_id,week,item_id) "
            "DO UPDATE SET done=excluded.done, updated_ts=excluded.updated_ts",
            (astronaut_id, week, item_id, int(bool(done)), ts))
        self.db.commit()

    def acknowledge_alert(self, alert_id, actor, ts):
        self.db.execute("INSERT OR REPLACE INTO alert_acknowledgements VALUES(?,?,?)", (alert_id, actor, ts))
        self.db.commit()

    def acknowledged_alerts(self):
        return {row[0] for row in self.db.execute("SELECT alert_id FROM alert_acknowledgements")}

    def set_kv(self, key, value):
        self.db.execute("INSERT INTO hub_kv VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, json.dumps(value))); self.db.commit()

    def get_kv(self, key, default=None):
        row = self.db.execute("SELECT value FROM hub_kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def add_anomaly(self, astronaut_id, kind, details, ts):
        self.db.execute("INSERT INTO anomalies(astronaut_id,ts,kind,details) VALUES(?,?,?,?)",
                        (astronaut_id, ts, kind, json.dumps(details, sort_keys=True))); self.db.commit()

    def save_profile(self, profile):
        astronaut_id = profile["astronaut_id"]
        token = sec.encrypt_field(json.dumps(profile, sort_keys=True), f"hub:profiles:{astronaut_id}")
        self.db.execute("INSERT INTO profiles VALUES(?,?) ON CONFLICT(astronaut_id) DO UPDATE SET payload=excluded.payload",
                        (astronaut_id, token)); self.db.commit()

    def profiles(self):
        rows = self.db.execute("SELECT astronaut_id,payload FROM profiles ORDER BY astronaut_id").fetchall()
        return [json.loads(self._decrypt_token(row[1], f"hub:profiles:{row[0]}")) for row in rows]

    def save_plan(self, plan):
        astronaut_id = plan["astronaut_id"]
        token = sec.encrypt_field(json.dumps(plan, sort_keys=True), f"hub:plans:{astronaut_id}")
        self.db.execute("INSERT INTO plans VALUES(?,?,?) ON CONFLICT(astronaut_id) DO UPDATE SET week=excluded.week,payload=excluded.payload",
                        (astronaut_id, plan["week"], token)); self.db.commit()

    def get_plan(self, astronaut_id):
        row = self.db.execute("SELECT payload FROM plans WHERE astronaut_id=?", (astronaut_id,)).fetchone()
        return json.loads(self._decrypt_token(row[0], f"hub:plans:{astronaut_id}")) if row else None

    def save_exposure(self, record):
        token = sec.encrypt_field(json.dumps(record, sort_keys=True), f"hub:exposure:{record['event_id']}")
        self.db.execute("INSERT INTO exposure_records VALUES(?,?,?,?) ON CONFLICT(event_id) DO UPDATE SET payload=excluded.payload,ts=excluded.ts",
                        (record["event_id"], record["astronaut_id"], record["end_ts"], token)); self.db.commit()

    def exposures(self, astronaut_id):
        rows = self.db.execute("SELECT event_id,payload FROM exposure_records WHERE astronaut_id=? ORDER BY ts", (astronaut_id,)).fetchall()
        return [json.loads(self._decrypt_token(row[1], f"hub:exposure:{row[0]}")) for row in rows]

    def save_bundle(self, bundle):
        self.db.execute("INSERT INTO downlink_bundles(type,ts,payload) VALUES(?,?,?)",
                        (bundle.get("type"), bundle.get("created_ts"), json.dumps(bundle, sort_keys=True))); self.db.commit()

    def create_backup(self, force: bool = False):
        """Write an encrypted SQLite snapshot and its timestamp."""
        from datetime import datetime, timezone

        if not force and time.monotonic() - self._last_backup < self._backup_interval:
            return None
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.db.execute("INSERT INTO hub_kv VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        ("backup_ts", json.dumps(stamp)))
        self.db.commit()
        handle, raw_path = tempfile.mkstemp(prefix="astra-hub-backup-", suffix=".db", dir=str(self.backup_path.parent))
        os.close(handle)
        try:
            snapshot = sqlite3.connect(raw_path)
            try:
                with self.lock:
                    self.db.backup(snapshot)
                snapshot.commit()
            finally:
                snapshot.close()
            encoded = base64.b64encode(Path(raw_path).read_bytes()).decode("ascii")
            token = sec.encrypt_field(encoded, "hub-backup:v1")
            self.backup_path.write_text(token, encoding="ascii")
        finally:
            Path(raw_path).unlink(missing_ok=True)
        self._last_backup = time.monotonic()
        return stamp

    def backup_state(self):
        return {"available": self.backup_path.is_file(), "last_backup_ts": self.get_kv("backup_ts"),
                "size_kb": round(self.backup_path.stat().st_size / 1024, 1) if self.backup_path.is_file() else 0,
                "encrypted": True}

    def reset_demo(self):
        for table in ("readings", "statuses", "checkins", "plans", "plan_items", "engine_state", "hub_kv", "anomalies", "exposure_records", "alert_acknowledgements"):
            self.db.execute(f"DELETE FROM {table}")
        self.db.commit()

    def close(self): self.db.close()
