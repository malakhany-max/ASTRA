"""Encrypted local Ground Station store and backup."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hub import security_adapter as sec


class GroundStore:
    def __init__(self, path=None, backup_path=None):
        data_dir = Path(__file__).resolve().parents[1] / "data"
        self.path = Path(path or os.environ.get("ASTRA_GROUND_DB") or data_dir / "ground.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_path = Path(backup_path or os.environ.get("ASTRA_GROUND_BACKUP") or data_dir / "backup.enc")
        self.backup_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._cache: dict[str, str] = {}
        self._last_backup = 0.0
        self._backup_interval = 300.0
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS crew(astronaut_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS missions(mission_id TEXT PRIMARY KEY, astronaut_id TEXT, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS uplinks(id INTEGER PRIMARY KEY, msg_id TEXT UNIQUE, type TEXT, astronaut_id TEXT, ts TEXT, payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_ground_uplinks ON uplinks(astronaut_id, id);
        CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY, alert_id TEXT UNIQUE, astronaut_id TEXT, ts TEXT, payload TEXT NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS idx_ground_alerts ON alerts(astronaut_id, acknowledged, id);
        CREATE TABLE IF NOT EXISTS exposures(event_id TEXT PRIMARY KEY, astronaut_id TEXT, ts TEXT, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS commands(command_id TEXT PRIMARY KEY, astronaut_id TEXT NOT NULL, command_type TEXT NOT NULL, payload TEXT NOT NULL, created_ts TEXT NOT NULL, status TEXT NOT NULL, msg_id TEXT NOT NULL, created_by TEXT NOT NULL DEFAULT 'unknown');
        CREATE TABLE IF NOT EXISTS ground_kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS checkins(checkin_id TEXT PRIMARY KEY, astronaut_id TEXT, ts TEXT, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS crew_messages(message_id TEXT PRIMARY KEY, astronaut_id TEXT, ts TEXT, payload TEXT NOT NULL);
        """)
        command_columns = {row[1] for row in self.db.execute("PRAGMA table_info(commands)")}
        if "created_by" not in command_columns:
            self.db.execute("ALTER TABLE commands ADD COLUMN created_by TEXT NOT NULL DEFAULT 'unknown'")
        if "delivered_ts" not in command_columns:
            self.db.execute("ALTER TABLE commands ADD COLUMN delivered_ts TEXT")
        alert_columns = {row[1] for row in self.db.execute("PRAGMA table_info(alerts)")}
        if "indicator" not in alert_columns:
            self.db.execute("ALTER TABLE alerts ADD COLUMN indicator TEXT")
        if "severity" not in alert_columns:
            self.db.execute("ALTER TABLE alerts ADD COLUMN severity TEXT")
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.db.execute("DELETE FROM commands WHERE status='pending' AND created_ts < ?", (cutoff,))
        self.db.commit()

    def _encrypt(self, payload, context):
        return sec.encrypt_field(json.dumps(payload, sort_keys=True), context)

    def _decrypt(self, token, context):
        cached = self._cache.get(token)
        if cached is not None:
            return cached
        value = json.loads(sec.decrypt_field(token, context))
        if len(self._cache) > 4000:
            self._cache.clear()
        self._cache[token] = value
        return value

    def seed_profiles(self, profiles):
        for profile in profiles:
            aid = profile["astronaut_id"]
            token = self._encrypt(profile, f"ground:crew:{aid}")
            self.db.execute("INSERT INTO crew VALUES(?,?) ON CONFLICT(astronaut_id) DO UPDATE SET payload=excluded.payload", (aid, token))
            for mission in profile.get("mission_history", []):
                mission_id = mission["mission_id"]
                self.db.execute("INSERT INTO missions VALUES(?,?,?) ON CONFLICT(mission_id) DO UPDATE SET payload=excluded.payload",
                                (mission_id, aid, self._encrypt(mission, f"ground:mission:{mission_id}")))
        self.db.commit()

    def crew(self):
        return [self._decrypt(row["payload"], f"ground:crew:{row['astronaut_id']}")
                for row in self.db.execute("SELECT astronaut_id,payload FROM crew ORDER BY astronaut_id")]

    def get_crew(self, astronaut_id):
        row = self.db.execute("SELECT payload FROM crew WHERE astronaut_id=?", (astronaut_id,)).fetchone()
        return self._decrypt(row[0], f"ground:crew:{astronaut_id}") if row else None

    def missions(self, astronaut_id=None):
        if astronaut_id:
            rows = self.db.execute("SELECT mission_id,payload FROM missions WHERE astronaut_id=? ORDER BY mission_id", (astronaut_id,))
        else:
            rows = self.db.execute("SELECT mission_id,payload FROM missions ORDER BY mission_id")
        return [self._decrypt(row["payload"], f"ground:mission:{row['mission_id']}") for row in rows]

    def save_uplink(self, envelope, payload):
        msg_id = envelope["msg_id"]
        kind = envelope.get("type")
        aid = str(payload.get("astronaut_id") or payload.get("payload", {}).get("astronaut_id") or "unknown")
        ts = envelope.get("created_ts", "")
        token = self._encrypt(payload, f"ground:uplink:{msg_id}")
        self.db.execute("INSERT OR IGNORE INTO uplinks(msg_id,type,astronaut_id,ts,payload) VALUES(?,?,?,?,?)",
                        (msg_id, kind, aid, ts, token))
        if kind == "alert":
            summary = payload.get("vitals_summary") or payload.get("psych_summary") or {}
            if not summary:
                summary = payload.get("payload", {}).get("vitals_summary", {})
            indicator = str(summary.get("indicator") or "health")
            severity = str(summary.get("status") or "attention")
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            duplicate = self.db.execute(
                "SELECT 1 FROM alerts WHERE astronaut_id=? AND indicator=? AND severity=? AND acknowledged=0 AND ts>=? LIMIT 1",
                (aid, indicator, severity, cutoff)).fetchone()
            if not duplicate:
                self.db.execute("INSERT OR IGNORE INTO alerts(alert_id,astronaut_id,ts,payload,indicator,severity) VALUES(?,?,?,?,?,?)",
                                (msg_id, aid, ts, token, indicator, severity))
        elif kind == "exposure_record" and isinstance(payload, dict) and payload.get("event_id"):
            event_id = payload["event_id"]
            exp_token = self._encrypt(payload, f"ground:exposure:{event_id}")
            self.db.execute("INSERT INTO exposures VALUES(?,?,?,?) ON CONFLICT(event_id) DO UPDATE SET payload=excluded.payload,ts=excluded.ts",
                            (event_id, aid, ts, exp_token))
        elif kind == "checkin" and isinstance(payload.get("checkin"), dict):
            checkin = payload["checkin"]
            checkin_id = f"{aid}:{checkin.get('ts', ts)}"
            self.db.execute("INSERT OR REPLACE INTO checkins VALUES(?,?,?,?)",
                            (checkin_id, aid, str(checkin.get("ts") or ts), self._encrypt(checkin, f"ground:checkin:{checkin_id}")))
        elif kind == "crew_message" and isinstance(payload.get("crew_message"), dict):
            message = payload["crew_message"]
            self.db.execute("INSERT OR REPLACE INTO crew_messages VALUES(?,?,?,?)",
                            (msg_id, aid, str(message.get("created_ts") or ts),
                             self._encrypt(message, f"ground:message:{msg_id}")))
        elif kind == "command_ack" and isinstance(payload, dict):
            self.db.execute("UPDATE commands SET status='delivered', delivered_ts=? WHERE msg_id=?",
                            (str(payload.get("applied_ts") or ts), str(payload.get("msg_id") or "")))
        self.db.commit()
        self.set_kv(f"last_update:{aid}", ts)
        self._trim(aid)
        self.create_backup()
        return aid

    def _trim(self, astronaut_id):
        self.db.execute("DELETE FROM uplinks WHERE astronaut_id=? AND type='summary' AND id NOT IN "
                        "(SELECT id FROM uplinks WHERE astronaut_id=? AND type='summary' ORDER BY id DESC LIMIT 1600)",
                        (astronaut_id, astronaut_id))
        self.db.execute("DELETE FROM uplinks WHERE astronaut_id=? AND type<>'summary' AND id NOT IN "
                        "(SELECT id FROM uplinks WHERE astronaut_id=? AND type<>'summary' ORDER BY id DESC LIMIT 3000)",
                        (astronaut_id, astronaut_id))
        self.db.execute("DELETE FROM alerts WHERE astronaut_id=? AND id NOT IN "
                        "(SELECT id FROM alerts WHERE astronaut_id=? ORDER BY id DESC LIMIT 500)",
                        (astronaut_id, astronaut_id))
        self.db.execute("DELETE FROM checkins WHERE astronaut_id=? AND rowid NOT IN "
                        "(SELECT rowid FROM checkins WHERE astronaut_id=? ORDER BY ts DESC LIMIT 200)",
                        (astronaut_id, astronaut_id))
        self.db.execute("DELETE FROM crew_messages WHERE astronaut_id=? AND rowid NOT IN "
                        "(SELECT rowid FROM crew_messages WHERE astronaut_id=? ORDER BY ts DESC LIMIT 200)",
                        (astronaut_id, astronaut_id))
        self.db.commit()

    def checkins(self, astronaut_id, limit=30):
        rows = self.db.execute("SELECT checkin_id,payload FROM checkins WHERE astronaut_id=? ORDER BY ts DESC LIMIT ?",
                               (astronaut_id, limit)).fetchall()
        return [self._decrypt(row["payload"], f"ground:checkin:{row['checkin_id']}") for row in rows]

    def crew_messages(self, astronaut_id, limit=30):
        rows = self.db.execute("SELECT message_id,payload FROM crew_messages WHERE astronaut_id=? ORDER BY ts DESC LIMIT ?",
                               (astronaut_id, limit)).fetchall()
        return [{"id": row["message_id"],
                 **self._decrypt(row["payload"], f"ground:message:{row['message_id']}")} for row in rows]

    def history(self, astronaut_id):
        rows = self.db.execute("SELECT msg_id,type,payload FROM uplinks WHERE astronaut_id=? ORDER BY ts", (astronaut_id,)).fetchall()
        history = [{"msg_id": row["msg_id"], "type": row["type"],
                    "payload": self._decrypt(row["payload"], f"ground:uplink:{row['msg_id']}")} for row in rows]
        return {"astronaut_id": astronaut_id, "missions": self.missions(astronaut_id), "uplinks": history}

    def uplinks(self, astronaut_id, limit=400):
        rows = self.db.execute(
            "SELECT msg_id,type,ts,payload FROM uplinks WHERE astronaut_id=? ORDER BY id DESC LIMIT ?",
            (astronaut_id, limit)).fetchall()
        return [{"msg_id": row["msg_id"], "type": row["type"], "ts": row["ts"],
                 "payload": self._decrypt(row["payload"], f"ground:uplink:{row['msg_id']}")}
                for row in reversed(rows)]

    def list_alerts(self, astronaut_id=None, limit=200):
        sql, params = "SELECT * FROM alerts", []
        if astronaut_id:
            sql += " WHERE astronaut_id=?"; params.append(astronaut_id)
        sql += " ORDER BY ts DESC LIMIT ?"; params.append(limit)
        return [{"alert_id": row["alert_id"], "astronaut_id": row["astronaut_id"], "ts": row["ts"],
                 "acknowledged": bool(row["acknowledged"]),
                 "payload": self._decrypt(row["payload"], f"ground:uplink:{row['alert_id']}")}
                for row in self.db.execute(sql, tuple(params))]

    def acknowledge(self, alert_id, actor):
        cursor = self.db.execute("UPDATE alerts SET acknowledged=1 WHERE alert_id=?", (alert_id,))
        self.db.commit()
        return cursor.rowcount > 0

    def exposures(self, astronaut_id):
        rows = self.db.execute("SELECT event_id,payload FROM exposures WHERE astronaut_id=? ORDER BY ts", (astronaut_id,))
        return [self._decrypt(row["payload"], f"ground:exposure:{row['event_id']}") for row in rows]

    def save_command(self, command_id, astronaut_id, command_type, payload, created_ts, msg_id, status="pending", created_by="unknown"):
        token = self._encrypt(payload, f"ground:command:{command_id}")
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO commands(command_id,astronaut_id,command_type,payload,created_ts,status,msg_id,created_by) VALUES(?,?,?,?,?,?,?,?)",
                (command_id, astronaut_id, command_type, token, created_ts, status, msg_id, created_by),
            )
            self.db.commit()

    def mark_delivered(self, msg_ids):
        if not msg_ids:
            return 0
        marks = ",".join("?" for _ in msg_ids)
        with self.lock:
            changed = self.db.execute(
                f"UPDATE commands SET status='delivered', delivered_ts=COALESCE(delivered_ts, created_ts)"
                f" WHERE status='pending' AND msg_id IN ({marks})", tuple(msg_ids)).rowcount
            self.db.commit()
        return changed

    def pending_commands(self):
        return [dict(row) for row in self.db.execute(
            "SELECT command_id,msg_id,created_ts FROM commands WHERE status='pending'").fetchall()]

    def commands(self):
        rows = self.db.execute("SELECT * FROM commands ORDER BY created_ts DESC, command_id DESC LIMIT 50").fetchall()
        seen = set()
        results = []
        for row in rows:
            payload = self._decrypt(row["payload"], f"ground:command:{row['command_id']}")
            key = (row["astronaut_id"], row["command_type"], json.dumps(payload, sort_keys=True))
            if row["status"] == "pending":
                if key in seen:
                    continue
                seen.add(key)
            results.append({"id": row["command_id"], "astronaut_id": row["astronaut_id"],
                            "type": row["command_type"], "payload": payload,
                            "created_ts": row["created_ts"], "status": row["status"], "msg_id": row["msg_id"],
                            "created_by": row["created_by"], "delivered_ts": row["delivered_ts"]})
        return results

    def set_kv(self, key, value):
        self.db.execute("INSERT INTO ground_kv VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))
        self.db.commit()

    def get_kv(self, key, default=None):
        row = self.db.execute("SELECT value FROM ground_kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def staleness(self, stale_after_seconds=3600):
        now = datetime.now(timezone.utc)
        data = []
        for profile in self.crew():
            aid = profile["astronaut_id"]
            last = self.get_kv(f"last_update:{aid}")
            age = None
            if last:
                try: age = max(0.0, (now - datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds())
                except ValueError: pass
            data.append({"astronaut_id": aid, "last_update_ts": last,
                         "stale": age is None or age > stale_after_seconds, "age_seconds": age})
        return data

    def create_backup(self, force: bool = False):
        if not force and time.monotonic() - self._last_backup < self._backup_interval:
            return None
        uplink_rows = self.db.execute("SELECT msg_id,type,payload FROM uplinks ORDER BY id DESC LIMIT 2000").fetchall()
        uplinks = [{"msg_id": row["msg_id"], "type": row["type"],
                    "payload": self._decrypt(row["payload"], f"ground:uplink:{row['msg_id']}")} for row in uplink_rows]
        crew = self.crew()
        state = {"created_ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "crew": crew, "missions": self.missions(), "uplinks": uplinks,
                 "alerts": self.list_alerts(),
                 "commands": self.commands(),
                 "exposures": [record for profile in crew for record in self.exposures(profile["astronaut_id"])]}
        token = sec.encrypt_field(json.dumps(state, sort_keys=True), "ground-backup:v1")
        self.backup_path.write_text(token, encoding="ascii")
        self.set_kv("backup_ts", state["created_ts"])
        self._last_backup = time.monotonic()
        return state["created_ts"]

    def backup_state(self):
        available = self.backup_path.exists()
        return {"available": available, "last_backup_ts": self.get_kv("backup_ts"),
                "size_kb": round(self.backup_path.stat().st_size / 1024, 1) if available else 0,
                "encrypted": True, "path": str(self.backup_path.name)}

    def close(self): self.db.close()
