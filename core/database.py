"""
数据库 + 迁移系统 v5
Schema Version: 5
"""
import sqlite3
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

SCHEMA_VERSION = 5

MIGRATIONS = {
    1: """
    CREATE TABLE IF NOT EXISTS schema_version (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        version INTEGER NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS raw_notes (
        id TEXT PRIMARY KEY, content TEXT NOT NULL,
        source_type TEXT NOT NULL, timestamp TEXT NOT NULL,
        tags TEXT DEFAULT "[]", context TEXT DEFAULT ""
    );
    CREATE TABLE IF NOT EXISTS todos (
        id TEXT PRIMARY KEY, content TEXT NOT NULL, done INTEGER DEFAULT 0,
        project_id TEXT, priority INTEGER DEFAULT 1,
        timestamp TEXT NOT NULL, completed_at TEXT
    );
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY, name TEXT NOT NULL,
        description TEXT DEFAULT "", status TEXT DEFAULT "active",
        timestamp TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL,
        timestamp TEXT NOT NULL, source_type TEXT DEFAULT 'user_quote',
        session_id TEXT DEFAULT "default"
    );
    CREATE TABLE IF NOT EXISTS current_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        state_json TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS asset_packages (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, version TEXT NOT NULL,
        manifest_json TEXT NOT NULL, installed_at TEXT NOT NULL, active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS model_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        config_json TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    INSERT OR IGNORE INTO schema_version (id, version, updated_at)
    VALUES (1, 1, datetime('now'));
    """,
    2: """
    CREATE TABLE IF NOT EXISTS memory_entries (
        id TEXT PRIMARY KEY, content TEXT NOT NULL, source_type TEXT NOT NULL,
        source_ref TEXT DEFAULT "", scope TEXT NOT NULL, project_id TEXT DEFAULT "",
        confidence REAL DEFAULT 0.8, retention TEXT DEFAULT "medium",
        status TEXT DEFAULT "active", created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL, supersedes TEXT DEFAULT "",
        deleted_at TEXT DEFAULT "", session_id TEXT DEFAULT "default",
        metadata TEXT DEFAULT "{}"
    );
    CREATE INDEX IF NOT EXISTS idx_memory_scope ON memory_entries(scope);
    CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_entries(project_id);
    CREATE INDEX IF NOT EXISTS idx_memory_status ON memory_entries(status);
    CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY, action TEXT NOT NULL, provider TEXT DEFAULT "",
        data_category TEXT DEFAULT "", outbound_data INTEGER DEFAULT 0,
        success INTEGER DEFAULT 1, timestamp TEXT NOT NULL, details TEXT DEFAULT ""
    );
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL,
        status TEXT NOT NULL, priority INTEGER DEFAULT 3,
        weight TEXT DEFAULT "light", completion_definition TEXT DEFAULT "",
        requires_confirm INTEGER DEFAULT 0, confirmation_state TEXT DEFAULT "pending",
        resource_budget TEXT DEFAULT "", plan TEXT DEFAULT "[]",
        checkpoint TEXT DEFAULT "", requested_by TEXT DEFAULT "xixi",
        owner TEXT DEFAULT "xixi", started_at TEXT DEFAULT "",
        completed_at TEXT DEFAULT "", failure_reason TEXT DEFAULT ""
    );
    UPDATE schema_version SET version = 2, updated_at = datetime('now') WHERE id = 1;
    """,
    3: """
    CREATE TABLE IF NOT EXISTS identity_registry (
        identity_id TEXT PRIMARY KEY,
        identity_version TEXT NOT NULL,
        personality_version TEXT DEFAULT "",
        render_version TEXT DEFAULT "",
        voice_version TEXT DEFAULT "",
        official INTEGER DEFAULT 0,
        branch_of TEXT DEFAULT "",
        inherited_until TEXT DEFAULT "",
        memory_inheritance_policy TEXT DEFAULT "full",
        status TEXT DEFAULT "active",
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        face_anchor_path TEXT DEFAULT "",
        fork_history TEXT DEFAULT "[]"
    );
    CREATE TABLE IF NOT EXISTS constitution_versions (
        id TEXT PRIMARY KEY, version TEXT NOT NULL,
        content TEXT NOT NULL, created_at TEXT NOT NULL, active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS identities (
        id TEXT PRIMARY KEY, name TEXT NOT NULL,
        description TEXT DEFAULT "", created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS state_machine (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        state TEXT NOT NULL DEFAULT "alone",
        emotion TEXT DEFAULT "peaceful",
        relationship_state TEXT DEFAULT "familiar",
        attention_target TEXT DEFAULT "idle",
        attention_target_id TEXT DEFAULT "",
        attention_intensity REAL DEFAULT 0.0,
        attention_since TEXT DEFAULT "",
        boot_mode TEXT DEFAULT "cold_start",
        entered_at TEXT DEFAULT "",
        last_interaction_at TEXT DEFAULT "",
        previous_state TEXT DEFAULT "",
        reason TEXT DEFAULT "",
        metadata TEXT DEFAULT "{}",
        updated_at TEXT NOT NULL
    );
    INSERT OR IGNORE INTO state_machine (id, state, updated_at)
    VALUES (1, 'alone', datetime('now'));
    UPDATE schema_version SET version = 3, updated_at = datetime('now') WHERE id = 1;
    """,
    4: """
    CREATE TABLE IF NOT EXISTS soul_packages (
        package_id TEXT PRIMARY KEY,
        version TEXT NOT NULL,
        path TEXT NOT NULL,
        manifest_json TEXT NOT NULL,
        active INTEGER DEFAULT 0,
        installed_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS body_packages (
        package_id TEXT PRIMARY KEY,
        version TEXT NOT NULL,
        path TEXT NOT NULL,
        manifest_json TEXT NOT NULL,
        active INTEGER DEFAULT 0,
        installed_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS extension_packages (
        package_id TEXT PRIMARY KEY,
        version TEXT NOT NULL,
        path TEXT NOT NULL,
        manifest_json TEXT NOT NULL,
        enabled INTEGER DEFAULT 0,
        installed_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    UPDATE schema_version SET version = 4, updated_at = datetime('now') WHERE id = 1;
    """,
    5: """
    -- v5: 添加 development 项目表和扩展测试记录
    CREATE TABLE IF NOT EXISTS dev_projects (
        project_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        project_type TEXT DEFAULT "extension",
        source_path TEXT NOT NULL,
        build_path TEXT DEFAULT "",
        status TEXT DEFAULT "draft",
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS extension_tests (
        test_id TEXT PRIMARY KEY,
        extension_id TEXT NOT NULL,
        test_result TEXT DEFAULT "",
        passed INTEGER DEFAULT 0,
        ran_at TEXT NOT NULL
    );
    UPDATE schema_version SET version = 5, updated_at = datetime('now') WHERE id = 1;
    """,
}


class Database:
    """SQLite 数据库，带迁移系统"""

    def __init__(self, path: str = "data/xixi.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        current = self._get_schema_version()
        for version in sorted(MIGRATIONS.keys()):
            if version > current:
                self._conn.executescript(MIGRATIONS[version])
                self._conn.commit()

    def _get_schema_version(self) -> int:
        try:
            row = self._conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
            return row[0] if row else 0
        except sqlite3.OperationalError:
            return 0

    def execute(self, sql: str, params=()):
        return self._conn.execute(sql, params)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    # ── Settings ──
    def get_setting(self, key: str, default: str = "") -> str:
        row = self.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str):
        now = datetime.now().isoformat()
        self.execute("""
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, value, now))
        self.commit()

    # ── State Machine ──
    def save_state(self, state_dict: dict):
        now = datetime.now().isoformat()
        snapshot = state_dict.get("snapshot", {})
        attention = snapshot.get("attention", {}) if isinstance(snapshot, dict) else state_dict.get("attention", {})
        if isinstance(attention, dict):
            att_target = attention.get("target", "idle")
            att_target_id = attention.get("target_id", "")
            att_intensity = attention.get("intensity", 0.0)
            att_since = attention.get("since", "")
        else:
            att_target, att_target_id, att_intensity, att_since = "idle", "", 0.0, ""
        snapshot = state_dict.get("snapshot", {})
        self.execute("""
            INSERT INTO state_machine (
                id, state, emotion, relationship_state,
                attention_target, attention_target_id, attention_intensity, attention_since,
                boot_mode, entered_at, last_interaction_at, previous_state, reason,
                metadata, updated_at
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                state = excluded.state,
                emotion = excluded.emotion,
                relationship_state = excluded.relationship_state,
                attention_target = excluded.attention_target,
                attention_target_id = excluded.attention_target_id,
                attention_intensity = excluded.attention_intensity,
                attention_since = excluded.attention_since,
                boot_mode = excluded.boot_mode,
                entered_at = excluded.entered_at,
                last_interaction_at = excluded.last_interaction_at,
                previous_state = excluded.previous_state,
                reason = excluded.reason,
                metadata = excluded.metadata,
                updated_at = excluded.updated_at
        """, (
            snapshot.get("state_id", "alone"),
            snapshot.get("emotion", "peaceful"),
            snapshot.get("relationship_state", "familiar"),
            att_target, att_target_id, att_intensity, att_since,
            snapshot.get("boot_mode", "cold_start"),
            snapshot.get("entered_at", ""),
            snapshot.get("last_interaction_at", ""),
            snapshot.get("previous_state", ""),
            snapshot.get("reason", ""),
            json.dumps(snapshot.get("metadata", {})),
            now,
        ))
        self.commit()

    def load_state(self) -> Optional[dict]:
        row = self.execute("SELECT * FROM state_machine WHERE id = 1").fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            metadata = json.loads(d.get("metadata", "{}"))
        except Exception:
            metadata = {}
        return {
            "state": d.get("state", "alone"),
            "snapshot": {
                "state_id": d.get("state", "alone"),
                "emotion": d.get("emotion", "peaceful"),
                "relationship_state": d.get("relationship_state", "familiar"),
                "attention": {
                    "target": d.get("attention_target", "idle"),
                    "target_id": d.get("attention_target_id", ""),
                    "intensity": d.get("attention_intensity", 0.0),
                    "since": d.get("attention_since", ""),
                },
                "boot_mode": d.get("boot_mode", "cold_start"),
                "entered_at": d.get("entered_at", ""),
                "last_interaction_at": d.get("last_interaction_at", ""),
                "previous_state": d.get("previous_state", ""),
                "reason": d.get("reason", ""),
                "metadata": metadata,
            },
            "label": d.get("state", "alone"),
            "pose": "standing",
            "mood": "peaceful",
        }

    # ── Memory ──
    def add_memory_entry(self, entry: dict):
        now = datetime.now().isoformat()
        metadata = json.dumps(entry.get("metadata", {}))
        self.execute("""
            INSERT INTO memory_entries (
                id, content, source_type, source_ref, scope, project_id,
                confidence, retention, status, created_at, updated_at,
                supersedes, deleted_at, session_id, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["id"], entry["content"], entry.get("source_type", "user_quote"),
            entry.get("source_ref", ""), entry.get("scope", "session"),
            entry.get("project_id", ""), entry.get("confidence", 0.8),
            entry.get("retention", "medium"), entry.get("status", "active"),
            now, now, "", "", entry.get("session_id", "default"), metadata,
        ))
        self.commit()

    def query_memory_entries(self, scope=None, source_type=None, status="active",
                             project_id=None, session_id=None, limit=50, order="DESC") -> List[Dict]:
        sql = "SELECT * FROM memory_entries WHERE 1=1"
        params = []
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        if scope is not None:
            sql += " AND scope = ?"
            params.append(scope)
        if source_type is not None:
            sql += " AND source_type = ?"
            params.append(source_type)
        if project_id is not None:
            sql += " AND project_id = ?"
            params.append(project_id)
        if session_id is not None:
            sql += " AND session_id = ?"
            params.append(session_id)
        sql += f" ORDER BY created_at {order} LIMIT ?"
        params.append(limit)
        rows = self.execute(sql, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["metadata"] = json.loads(d.get("metadata", "{}"))
            except Exception:
                d["metadata"] = {}
            result.append(d)
        return result

    def update_memory_entry(self, entry_id: str, updates: dict) -> bool:
        allowed = {"content", "source_type", "source_ref", "scope", "project_id",
                   "confidence", "retention", "status", "metadata", "supersedes"}
        fields = []
        params = []
        for k, v in updates.items():
            if k in allowed:
                fields.append(f"{k} = ?")
                if k == "metadata" and isinstance(v, dict):
                    params.append(json.dumps(v))
                else:
                    params.append(v)
        if not fields:
            return False
        params.append(entry_id)
        self.execute(f"UPDATE memory_entries SET {', '.join(fields)}, updated_at = ? WHERE id = ?",
                     (*params[:-1], datetime.now().isoformat(), entry_id))
        self.commit()
        return True

    def supersede_memory(self, old_entry_id: str, new_entry_id: str):
        self.execute("""
            UPDATE memory_entries SET status = 'superseded', supersedes = ?, updated_at = ?
            WHERE id = ?
        """, (new_entry_id, datetime.now().isoformat(), old_entry_id))
        self.commit()

    def delete_memory_entry(self, entry_id: str, permanent: bool = False) -> bool:
        if permanent:
            self.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))
        else:
            self.execute("""
                UPDATE memory_entries SET status = 'deleted', deleted_at = ? WHERE id = ?
            """, (datetime.now().isoformat(), entry_id))
        self.commit()
        return True

    # ── Identity ──
    def register_identity(self, data: dict):
        now = datetime.now().isoformat()
        fork_history = json.dumps(data.get("fork_history", []))
        self.execute("""
            INSERT INTO identity_registry (
                identity_id, identity_version, personality_version, render_version,
                voice_version, official, branch_of, inherited_until,
                memory_inheritance_policy, status, created_at, updated_at,
                face_anchor_path, fork_history
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(identity_id) DO UPDATE SET
                identity_version = excluded.identity_version,
                personality_version = excluded.personality_version,
                render_version = excluded.render_version,
                voice_version = excluded.voice_version,
                official = excluded.official,
                status = excluded.status,
                updated_at = excluded.updated_at,
                face_anchor_path = excluded.face_anchor_path,
                fork_history = excluded.fork_history
        """, (
            data["identity_id"], data.get("identity_version", "1.0.0"),
            data.get("personality_version", ""), data.get("render_version", ""),
            data.get("voice_version", ""), 1 if data.get("official", False) else 0,
            data.get("branch_of", ""), data.get("inherited_until", ""),
            data.get("memory_inheritance_policy", "full"),
            data.get("status", "active"), now, now,
            data.get("face_anchor_path", ""), fork_history,
        ))
        self.commit()

    def get_identity(self, identity_id: str) -> Optional[dict]:
        row = self.execute("SELECT * FROM identity_registry WHERE identity_id = ?", (identity_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["official"] = bool(d.get("official", 0))
        try:
            d["fork_history"] = json.loads(d.get("fork_history", "[]"))
        except Exception:
            d["fork_history"] = []
        return d

    # ── Tasks ──
    def add_task(self, task: dict):
        plan_json = json.dumps(task.get("plan", []))
        self.execute("""
            INSERT INTO tasks (
                id, name, type, status, priority, weight, completion_definition,
                requires_confirm, confirmation_state, resource_budget, plan,
                checkpoint, requested_by, owner, started_at, completed_at, failure_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task["id"], task["name"], task["type"], task["status"],
            task.get("priority", 3), task.get("weight", "light"),
            task.get("completion_definition", ""),
            1 if task.get("requires_confirm", False) else 0,
            task.get("confirmation_state", "pending"),
            task.get("resource_budget", ""), plan_json,
            task.get("checkpoint", ""), task.get("requested_by", "xixi"),
            task.get("owner", "xixi"), task.get("started_at", ""),
            task.get("completed_at", ""), task.get("failure_reason", ""),
        ))
        self.commit()

    def get_tasks(self, status: str = None) -> List[Dict]:
        if status:
            rows = self.execute("SELECT * FROM tasks WHERE status = ?", (status,)).fetchall()
        else:
            rows = self.execute("SELECT * FROM tasks").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["plan"] = json.loads(d.get("plan", "[]"))
            except Exception:
                d["plan"] = []
            d["requires_confirm"] = bool(d.get("requires_confirm", 0))
            result.append(d)
        return result

    def update_task_status(self, task_id: str, status: str, checkpoint: str = ""):
        self.execute("""
            UPDATE tasks SET status = ?, checkpoint = ? WHERE id = ?
        """, (status, checkpoint, task_id))
        self.commit()

    # ── Soul/Body/Extension Packages ──
    def register_package(self, table: str, package_id: str, version: str, path: str, manifest: dict):
        now = datetime.now().isoformat()
        manifest_json = json.dumps(manifest)
        self.execute(f"""
            INSERT INTO {table} (package_id, version, path, manifest_json, installed_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(package_id) DO UPDATE SET
                version = excluded.version,
                path = excluded.path,
                manifest_json = excluded.manifest_json,
                updated_at = excluded.updated_at
        """, (package_id, version, path, manifest_json, now, now))
        self.commit()

    def get_package(self, table: str, package_id: str) -> Optional[dict]:
        row = self.execute(f"SELECT * FROM {table} WHERE package_id = ?", (package_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["manifest"] = json.loads(d.get("manifest_json", "{}"))
        except Exception:
            d["manifest"] = {}
        return d

    def list_packages(self, table: str) -> List[dict]:
        rows = self.execute(f"SELECT * FROM {table}").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["manifest"] = json.loads(d.get("manifest_json", "{}"))
            except Exception:
                d["manifest"] = {}
            result.append(d)
        return result

    def set_package_active(self, table: str, package_id: str, active: bool):
        col = "active" if table in ("soul_packages", "body_packages") else "enabled"
        self.execute(f"UPDATE {table} SET {col} = ? WHERE package_id = ?",
                     (1 if active else 0, package_id))
        self.commit()

    # ── Dev Projects ──
    def add_dev_project(self, project_id: str, name: str, source_path: str, project_type: str = "extension"):
        now = datetime.now().isoformat()
        self.execute("""
            INSERT INTO dev_projects (project_id, name, project_type, source_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                name = excluded.name, updated_at = excluded.updated_at
        """, (project_id, name, project_type, source_path, now, now))
        self.commit()

    def get_dev_projects(self) -> List[dict]:
        rows = self.execute("SELECT * FROM dev_projects").fetchall()
        return [dict(r) for r in rows]
