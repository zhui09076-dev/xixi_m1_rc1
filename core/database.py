"""
数据库 + 迁移系统 v3
===================
Schema Version: 3
新增: identities 表（official 唯一约束）、memory_entries 完整字段、
      tasks 完整字段、audit_logs 完整字段、version_registry 表
"""

import sqlite3
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

SCHEMA_VERSION = 3

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
        id TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        source_type TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        tags TEXT DEFAULT "[]",
        context TEXT DEFAULT ""
    );

    CREATE TABLE IF NOT EXISTS todos (
        id TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        done INTEGER DEFAULT 0,
        project_id TEXT,
        priority INTEGER DEFAULT 1,
        timestamp TEXT NOT NULL,
        completed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT "",
        status TEXT DEFAULT "active",
        timestamp TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        source_type TEXT DEFAULT 'user_quote',
        session_id TEXT DEFAULT "default"
    );

    CREATE TABLE IF NOT EXISTS current_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        state_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS asset_packages (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        version TEXT NOT NULL,
        manifest_json TEXT NOT NULL,
        installed_at TEXT NOT NULL,
        active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS model_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        config_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    INSERT OR IGNORE INTO schema_version (id, version, updated_at)
    VALUES (1, 1, datetime('now'));
    """,

    2: """
    CREATE TABLE IF NOT EXISTS memory_entries (
        id TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_ref TEXT DEFAULT "",
        scope TEXT NOT NULL,
        project_id TEXT DEFAULT "",
        confidence REAL DEFAULT 0.8,
        retention TEXT DEFAULT "medium",
        status TEXT DEFAULT "active",
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        supersedes TEXT DEFAULT "",
        deleted_at TEXT DEFAULT "",
        session_id TEXT DEFAULT "default"
    );

    CREATE INDEX IF NOT EXISTS idx_memory_scope ON memory_entries(scope);
    CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_entries(project_id);
    CREATE INDEX IF NOT EXISTS idx_memory_status ON memory_entries(status);
    CREATE INDEX IF NOT EXISTS idx_memory_source ON memory_entries(source_type);

    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        status TEXT DEFAULT "queued",
        priority INTEGER DEFAULT 3,
        plan_json TEXT DEFAULT "[]",
        checkpoint TEXT DEFAULT "",
        created_at TEXT NOT NULL,
        started_at TEXT DEFAULT "",
        completed_at TEXT DEFAULT "",
        owner TEXT DEFAULT "xixi",
        requires_confirm INTEGER DEFAULT 0
    );

    CREATE INDEX IF NOT EXISTS idx_task_status ON tasks(status);
    CREATE INDEX IF NOT EXISTS idx_task_type ON tasks(type);

    CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        initiator TEXT NOT NULL,
        permission_level TEXT NOT NULL,
        tool TEXT NOT NULL,
        action TEXT NOT NULL,
        input_summary TEXT DEFAULT "",
        output_summary TEXT DEFAULT "",
        success INTEGER DEFAULT 1,
        rollback_info TEXT DEFAULT "",
        tool_result TEXT DEFAULT ""
    );

    CREATE TABLE IF NOT EXISTS version_registry (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        versions_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    ALTER TABLE current_state ADD COLUMN boot_mode TEXT DEFAULT 'cold_start';

    UPDATE schema_version SET version = 2, updated_at = datetime('now') WHERE id = 1;
    """,

    3: """
    -- v3: 完整身份系统 + 记忆字段扩展 + 任务字段扩展
    CREATE TABLE IF NOT EXISTS identities (
        identity_id TEXT PRIMARY KEY,
        identity_version TEXT NOT NULL DEFAULT '1.0.0',
        personality_version TEXT NOT NULL DEFAULT '1.0.0',
        render_version TEXT NOT NULL DEFAULT '1.0.0',
        voice_version TEXT NOT NULL DEFAULT '1.0.0',
        official INTEGER NOT NULL DEFAULT 0,
        branch_of TEXT DEFAULT NULL,
        inherited_until TEXT DEFAULT NULL,
        memory_inheritance_policy TEXT DEFAULT 'full',
        status TEXT DEFAULT 'active',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        face_anchor_path TEXT DEFAULT "",
        fork_history_json TEXT DEFAULT "[]"
    );

    -- 保证只有一个 official=true
    CREATE UNIQUE INDEX IF NOT EXISTS idx_identity_official 
    ON identities(official) WHERE official = 1;

    -- 扩展 memory_entries
    ALTER TABLE memory_entries ADD COLUMN conversation_id TEXT DEFAULT "";
    ALTER TABLE memory_entries ADD COLUMN metadata TEXT DEFAULT "{}";

    -- 扩展 tasks
    ALTER TABLE tasks ADD COLUMN weight TEXT DEFAULT "";
    ALTER TABLE tasks ADD COLUMN completion_definition TEXT DEFAULT "";
    ALTER TABLE tasks ADD COLUMN confirmation_state TEXT DEFAULT "pending";
    ALTER TABLE tasks ADD COLUMN resource_budget TEXT DEFAULT "";
    ALTER TABLE tasks ADD COLUMN failure_reason TEXT DEFAULT "";
    ALTER TABLE tasks ADD COLUMN result_ref TEXT DEFAULT "";
    ALTER TABLE tasks ADD COLUMN requested_by TEXT DEFAULT "xixi";

    -- 扩展 audit_logs
    ALTER TABLE audit_logs ADD COLUMN task_id TEXT DEFAULT "";
    ALTER TABLE audit_logs ADD COLUMN provider TEXT DEFAULT "";
    ALTER TABLE audit_logs ADD COLUMN domain TEXT DEFAULT "";
    ALTER TABLE audit_logs ADD COLUMN operation TEXT DEFAULT "";
    ALTER TABLE audit_logs ADD COLUMN data_category TEXT DEFAULT "";
    ALTER TABLE audit_logs ADD COLUMN outbound_data TEXT DEFAULT "";
    ALTER TABLE audit_logs ADD COLUMN authorization_id TEXT DEFAULT "";
    ALTER TABLE audit_logs ADD COLUMN error TEXT DEFAULT "";
    ALTER TABLE audit_logs ADD COLUMN user_confirmed INTEGER DEFAULT 0;

    UPDATE schema_version SET version = 3, updated_at = datetime('now') WHERE id = 1;
    """
}


class Database:
    def __init__(self, path: str = "data/xixi.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        c = self.conn.cursor()
        try:
            c.execute("SELECT version FROM schema_version WHERE id = 1")
            row = c.fetchone()
            current = row[0] if row else 0
        except sqlite3.OperationalError:
            current = 0

        for version, sql in sorted(MIGRATIONS.items()):
            if version > current:
                try:
                    c.executescript(sql)
                    self.conn.commit()
                    print(f"[DB] 迁移到 Schema v{version}")
                except Exception as e:
                    print(f"[DB] 迁移 v{version} 出错: {e}")
                    raise

    def backup(self) -> str:
        backup_path = self.path.parent / f"xixi_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(self.path, backup_path)
        return str(backup_path)

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, params: List[tuple]):
        return self.conn.executemany(sql, params)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    # --- State ---
    def get_state(self) -> Optional[Dict]:
        c = self.execute("SELECT state_json, boot_mode FROM current_state WHERE id = 1")
        row = c.fetchone()
        if row:
            data = json.loads(row[0])
            data["boot_mode"] = row[1] if row[1] else "cold_start"
            return data
        return None

    def set_state(self, state: Dict):
        snapshot = state.get("snapshot", state)
        json_str = json.dumps(snapshot, ensure_ascii=False)
        boot_mode = state.get("boot_mode", "cold_start")
        self.execute("""
            INSERT INTO current_state (id, state_json, boot_mode, updated_at) 
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET 
                state_json = excluded.state_json,
                boot_mode = excluded.boot_mode,
                updated_at = excluded.updated_at
        """, (json_str, boot_mode, datetime.now().isoformat()))
        self.commit()

    # --- Identity ---
    def save_identity(self, identity: Dict):
        self.execute("""
            INSERT INTO identities 
            (identity_id, identity_version, personality_version, render_version, voice_version,
             official, branch_of, inherited_until, memory_inheritance_policy, status,
             created_at, updated_at, face_anchor_path, fork_history_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(identity_id) DO UPDATE SET
                identity_version = excluded.identity_version,
                personality_version = excluded.personality_version,
                render_version = excluded.render_version,
                voice_version = excluded.voice_version,
                official = excluded.official,
                branch_of = excluded.branch_of,
                inherited_until = excluded.inherited_until,
                memory_inheritance_policy = excluded.memory_inheritance_policy,
                status = excluded.status,
                updated_at = excluded.updated_at,
                face_anchor_path = excluded.face_anchor_path,
                fork_history_json = excluded.fork_history_json
        """, (
            identity["identity_id"], identity["identity_version"],
            identity["personality_version"], identity["render_version"],
            identity["voice_version"], 1 if identity.get("official", False) else 0,
            identity.get("branch_of"), identity.get("inherited_until"),
            identity.get("memory_inheritance_policy", "full"),
            identity.get("status", "active"),
            identity["created_at"], identity["updated_at"],
            identity.get("face_anchor_path", ""),
            json.dumps(identity.get("fork_history", []), ensure_ascii=False)
        ))
        self.commit()

    def get_identity(self, identity_id: str = "xixi-main") -> Optional[Dict]:
        c = self.execute("SELECT * FROM identities WHERE identity_id = ?", (identity_id,))
        row = c.fetchone()
        if row:
            d = dict(row)
            d["official"] = bool(d["official"])
            d["fork_history"] = json.loads(d.get("fork_history_json", "[]"))
            return d
        return None

    def get_official_identity(self) -> Optional[Dict]:
        c = self.execute("SELECT * FROM identities WHERE official = 1 LIMIT 1")
        row = c.fetchone()
        if row:
            d = dict(row)
            d["official"] = bool(d["official"])
            d["fork_history"] = json.loads(d.get("fork_history_json", "[]"))
            return d
        return None

    # --- Memory Entries v3 ---
    def add_memory_entry(self, entry: Dict) -> str:
        self.execute("""
            INSERT INTO memory_entries 
            (id, content, source_type, source_ref, scope, project_id, conversation_id,
             confidence, retention, status, created_at, updated_at, 
             supersedes, deleted_at, session_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["id"], entry["content"], entry.get("source_type", "system_event"),
            entry.get("source_ref", ""), entry.get("scope", "session"),
            entry.get("project_id", ""), entry.get("conversation_id", ""),
            entry.get("confidence", 0.8), entry.get("retention", "session"),
            entry.get("status", "active"),
            entry.get("created_at", datetime.now().isoformat()),
            entry.get("updated_at", datetime.now().isoformat()),
            entry.get("supersedes", ""), entry.get("deleted_at", ""),
            entry.get("session_id", "default"),
            json.dumps(entry.get("metadata", {}), ensure_ascii=False)
        ))
        self.commit()
        return entry["id"]

    def get_memory_entries(self, scope: str = None, project_id: str = None, 
                           limit: int = 50) -> List[Dict]:
        sql = "SELECT * FROM memory_entries WHERE status != 'deleted'"
        params = []
        if scope:
            sql += " AND scope = ?"
            params.append(scope)
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        c = self.execute(sql, tuple(params))
        return [dict(r) for r in c.fetchall()]

    def soft_delete_memory(self, entry_id: str):
        self.execute("""
            UPDATE memory_entries 
            SET status = 'deleted', deleted_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), entry_id))
        self.commit()

    def hard_delete_memory(self, entry_id: str):
        self.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))
        self.execute("UPDATE memory_entries SET supersedes = '' WHERE supersedes = ?", (entry_id,))
        self.commit()

    def set_purge_pending(self, entry_id: str):
        self.execute("""
            UPDATE memory_entries SET status = 'purge_pending', updated_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), entry_id))
        self.commit()

    def supersede_memory(self, old_id: str, new_id: str):
        self.execute("""
            UPDATE memory_entries 
            SET status = 'superseded', updated_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), old_id))
        self.execute("""
            UPDATE memory_entries 
            SET supersedes = ?
            WHERE id = ?
        """, (old_id, new_id))
        self.commit()

    # --- Tasks v3 ---
    def add_task(self, task: Dict) -> str:
        self.execute("""
            INSERT INTO tasks 
            (id, name, type, status, priority, weight, completion_definition,
             requires_confirm, confirmation_state, resource_budget,
             plan_json, checkpoint, created_at, started_at, completed_at,
             failure_reason, result_ref, requested_by, owner)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task["id"], task["name"], task["type"], task.get("status", "queued"),
            task.get("priority", 3), task.get("weight", ""),
            task.get("completion_definition", ""),
            1 if task.get("requires_confirm", False) else 0,
            task.get("confirmation_state", "pending"),
            task.get("resource_budget", ""),
            json.dumps(task.get("plan", []), ensure_ascii=False),
            task.get("checkpoint", ""),
            task.get("created_at", datetime.now().isoformat()),
            task.get("started_at", ""), task.get("completed_at", ""),
            task.get("failure_reason", ""), task.get("result_ref", ""),
            task.get("requested_by", "xixi"), task.get("owner", "xixi")
        ))
        self.commit()
        return task["id"]

    def get_tasks(self, status: str = None, type_filter: str = None) -> List[Dict]:
        sql = "SELECT * FROM tasks WHERE 1=1"
        params = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if type_filter:
            sql += " AND type = ?"
            params.append(type_filter)
        sql += " ORDER BY priority DESC, created_at DESC"
        c = self.execute(sql, tuple(params))
        return [dict(r) for r in c.fetchall()]

    def update_task_status(self, task_id: str, status: str, checkpoint: str = ""):
        self.execute("""
            UPDATE tasks SET status = ?, checkpoint = ? WHERE id = ?
        """, (status, checkpoint, task_id))
        self.commit()

    # --- Audit Logs v3 ---
    def add_audit_log(self, log: Dict) -> str:
        self.execute("""
            INSERT INTO audit_logs 
            (id, timestamp, task_id, initiator, permission_level, tool, action,
             provider, domain, operation, data_category, outbound_data,
             authorization_id, input_summary, output_summary, success,
             rollback_info, tool_result, error, user_confirmed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log["id"], log.get("timestamp", datetime.now().isoformat()),
            log.get("task_id", ""), log["initiator"], log["permission_level"],
            log["tool"], log["action"], log.get("provider", ""),
            log.get("domain", ""), log.get("operation", ""),
            log.get("data_category", ""), log.get("outbound_data", ""),
            log.get("authorization_id", ""), log.get("input_summary", ""),
            log.get("output_summary", ""), 1 if log.get("success", True) else 0,
            log.get("rollback_info", ""), log.get("tool_result", ""),
            log.get("error", ""), 1 if log.get("user_confirmed", False) else 0
        ))
        self.commit()
        return log["id"]

    def get_audit_logs(self, limit: int = 100) -> List[Dict]:
        c = self.execute("""
            SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        return [dict(r) for r in c.fetchall()]

    # --- Version Registry ---
    def save_version_registry(self, versions: Dict):
        self.execute("""
            INSERT INTO version_registry (id, versions_json, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                versions_json = excluded.versions_json,
                updated_at = excluded.updated_at
        """, (json.dumps(versions, ensure_ascii=False), datetime.now().isoformat()))
        self.commit()

    def get_version_registry(self) -> Optional[Dict]:
        c = self.execute("SELECT versions_json FROM version_registry WHERE id = 1")
        row = c.fetchone()
        return json.loads(row[0]) if row else None
