"""
Memory Manager - 六类记忆系统完整实现
支持: 原话保存、角色隔离、supersede替代链、可恢复删除、永久清除、重启恢复、打断不写
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("xixi.memory")


class MemoryManager:
    """
    六类记忆管理器

    记忆空间:
    - raw: 用户原话（不可覆盖）
    - working: 当前上下文（临时）
    - project: 项目相关（按 project_id 过滤）
    - user: 用户长期偏好（高置信度）
    - relationship: 关系记忆（写入阈值更高）
    - private_sandbox: 西西临时反思（不自动成为事实）
    """

    VALID_SPACES = {"raw", "working", "project", "user", "relationship", "private_sandbox"}
    VALID_SOURCE_TYPES = {
        "user_quote", "user_decision", "confirmed_fact", "tool_result",
        "xixi_opinion", "xixi_inference", "creative_content", "system_event"
    }
    VALID_STATUSES = {"active", "superseded", "soft_deleted", "purged"}

    def __init__(self, db_path: str = "data/xixi.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._ensure_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """每个线程独立连接（线程安全）"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _ensure_tables(self) -> None:
        """确保记忆相关表存在"""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS xixi_memory_entries (
                id TEXT PRIMARY KEY,
                space TEXT NOT NULL CHECK(space IN ('raw', 'working', 'project', 'user', 'relationship', 'private_sandbox')),
                content TEXT NOT NULL,
                source_type TEXT CHECK(source_type IN ('user_quote', 'user_decision', 'confirmed_fact', 'tool_result', 'xixi_opinion', 'xixi_inference', 'creative_content', 'system_event')),
                source_ref TEXT,
                project_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                retention TEXT,
                status TEXT DEFAULT 'active' CHECK(status IN ('active', 'superseded', 'soft_deleted', 'purged')),
                supersedes TEXT,
                superseded_by TEXT,
                confidence REAL CHECK(confidence >= 0 AND confidence <= 1),
                tags TEXT,
                role TEXT CHECK(role IN ('user', 'assistant', 'system')),
                FOREIGN KEY (supersedes) REFERENCES xixi_memory_entries(id),
                FOREIGN KEY (superseded_by) REFERENCES xixi_memory_entries(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_space ON xixi_memory_entries(space)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_status ON xixi_memory_entries(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_project ON xixi_memory_entries(project_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_created ON xixi_memory_entries(created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_supersedes ON xixi_memory_entries(supersedes)
        """)
        conn.commit()

    # ── 写入 ──

    def add_raw_note(self, content: str, source: str = "user_input", 
                     role: str = "user", project_id: Optional[str] = None) -> str:
        """
        保存用户原话。不可覆盖。

        参数:
            content: 原始内容
            source: 来源标识
            role: 'user' 或 'assistant'（关键：西西回复不能保存为 user_quote）
            project_id: 关联项目

        返回: 记录 ID
        """
        if role not in ("user", "assistant", "system"):
            raise ValueError(f"Invalid role: {role}")

        memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                INSERT INTO xixi_memory_entries 
                (id, space, content, source_type, source_ref, project_id, created_at, updated_at, 
                 retention, status, confidence, tags, role)
                VALUES (?, 'raw', ?, 'user_quote', ?, ?, ?, ?, 'conversation', 'active', 1.0, ?, ?)
            """, (memory_id, content, source, project_id, now, now, 
                  json.dumps([source]), role))
            conn.commit()

        logger.info("Raw note saved: id=%s role=%s", memory_id, role)
        return memory_id

    def add_conversation(self, role: str, content: str, 
                         project_id: Optional[str] = None) -> str:
        """
        保存对话记录。区分 user 和 assistant 角色。
        被打断的残缺回复不应调用此方法。
        """
        if role not in ("user", "assistant"):
            raise ValueError(f"Invalid conversation role: {role}")

        # 用户消息同时保存为 raw note
        if role == "user":
            return self.add_raw_note(content, source="conversation", role="user", project_id=project_id)

        # assistant 回复保存为 working memory（临时）
        return self.add_memory(
            content=content,
            space="working",
            source_type="xixi_opinion",
            project_id=project_id,
            role="assistant",
            retention="conversation",
        )

    def add_memory(
        self,
        content: str,
        space: str = "working",
        source_type: Optional[str] = None,
        project_id: Optional[str] = None,
        confidence: Optional[float] = None,
        tags: Optional[List[str]] = None,
        role: Optional[str] = None,
        retention: Optional[str] = None,
    ) -> str:
        """
        添加记忆。

        参数:
            space: raw/working/project/user/relationship/private_sandbox
            source_type: user_quote/user_decision/confirmed_fact/tool_result/xixi_opinion/xixi_inference/creative_content/system_event
            retention: 保留策略 (conversation/temporary/project/long_term/permanent)
        """
        if space not in self.VALID_SPACES:
            raise ValueError(f"Invalid space: {space}")
        if source_type and source_type not in self.VALID_SOURCE_TYPES:
            raise ValueError(f"Invalid source_type: {source_type}")

        memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                INSERT INTO xixi_memory_entries 
                (id, space, content, source_type, project_id, created_at, updated_at,
                 retention, status, confidence, tags, role)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """, (
                memory_id, space, content, source_type, project_id,
                now, now, retention, confidence,
                json.dumps(tags) if tags else None, role
            ))
            conn.commit()

        logger.info("Memory saved: id=%s space=%s source=%s", memory_id, space, source_type)
        return memory_id

    # ── 纠正与替代 ──

    def supersede_memory(self, old_id: str, new_content: str, reason: str = "",
                         source_type: str = "user_decision") -> str:
        """
        用新记录替代旧记录。

        规则:
        - 旧记录标记为 superseded，保留历史
        - 新记录 active，指向旧记录
        - 原话(raw)不能被 supersede
        """
        # 检查旧记录
        old = self.get_memory_by_id(old_id)
        if not old:
            raise ValueError(f"Memory not found: {old_id}")
        if old["space"] == "raw":
            raise ValueError("Raw notes cannot be superseded")

        new_id = f"mem_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = self._get_connection()
            # 标记旧记录
            conn.execute("""
                UPDATE xixi_memory_entries 
                SET status = 'superseded', updated_at = ?, superseded_by = ?
                WHERE id = ?
            """, (now, new_id, old_id))

            # 创建新记录
            conn.execute("""
                INSERT INTO xixi_memory_entries 
                (id, space, content, source_type, project_id, created_at, updated_at,
                 retention, status, supersedes, confidence, tags, role)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, 1.0, ?, ?)
            """, (
                new_id, old["space"], new_content, source_type,
                old.get("project_id"), now, now,
                old.get("retention"), old_id,
                json.dumps(["supersede", reason]) if reason else json.dumps(["supersede"]),
                old.get("role")
            ))
            conn.commit()

        logger.info("Memory superseded: %s -> %s (reason: %s)", old_id, new_id, reason)
        return new_id

    def correct_memory(self, memory_id: str, new_content: str, reason: str = "") -> str:
        """纠正记忆的便捷方法（内部调用 supersede）"""
        return self.supersede_memory(memory_id, new_content, reason=reason, 
                                     source_type="user_decision")

    # ── 删除 ──

    def soft_delete_memory(self, memory_id: str) -> None:
        """可恢复删除"""
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                UPDATE xixi_memory_entries 
                SET status = 'soft_deleted', updated_at = ?
                WHERE id = ? AND status = 'active'
            """, (datetime.now(timezone.utc).isoformat(), memory_id))
            conn.commit()
        logger.info("Memory soft deleted: %s", memory_id)

    def restore_memory(self, memory_id: str) -> None:
        """恢复已删除的记忆"""
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                UPDATE xixi_memory_entries 
                SET status = 'active', updated_at = ?
                WHERE id = ? AND status = 'soft_deleted'
            """, (datetime.now(timezone.utc).isoformat(), memory_id))
            conn.commit()
        logger.info("Memory restored: %s", memory_id)

    def purge_memory(self, memory_id: str) -> None:
        """永久清除（需要用户确认后调用）"""
        with self._lock:
            conn = self._get_connection()
            # 标记为 purged，不物理删除（保持审计）
            conn.execute("""
                UPDATE xixi_memory_entries 
                SET status = 'purged', content = '[PURGED]', updated_at = ?
                WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), memory_id))
            conn.commit()
        logger.info("Memory purged: %s", memory_id)

    def delete_by_scope(self, scope_query: str) -> Tuple[int, List[str]]:
        """
        按范围删除。模糊范围先返回澄清请求。

        返回: (删除数量, [被删除的ID列表])
        """
        # 简单实现：按内容匹配
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT id FROM xixi_memory_entries 
                WHERE content LIKE ? AND status = 'active'
            """, (f"%{scope_query}%",))
            ids = [row[0] for row in cursor.fetchall()]

            if len(ids) > 5:
                # 范围太模糊，返回澄清请求
                return -1, ids  # -1 表示需要澄清

            for mid in ids:
                conn.execute("""
                    UPDATE xixi_memory_entries SET status = 'soft_deleted', updated_at = ?
                    WHERE id = ?
                """, (datetime.now(timezone.utc).isoformat(), mid))
            conn.commit()

        return len(ids), ids

    # ── 读取 ──

    def get_memory_by_id(self, memory_id: str) -> Optional[Dict]:
        """按 ID 获取记忆"""
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM xixi_memory_entries WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def get_memory_history(self, memory_id: str) -> List[Dict]:
        """获取替代链历史"""
        history = []
        current = self.get_memory_by_id(memory_id)
        while current:
            history.append(current)
            if current.get("supersedes"):
                current = self.get_memory_by_id(current["supersedes"])
            else:
                break
        return history

    def search_relevant(
        self,
        query: Optional[str] = None,
        space: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 10,
        include_superseded: bool = False,
    ) -> List[Dict]:
        """
        检索相关记忆。

        优先级:
        1. 当前用户决定
        2. 当前项目事实
        3. 用户原话
        4. 工具真实结果
        5. 稳定长期偏好
        6. 关系记忆
        """
        conditions = ["status = 'active'"]
        params = []

        if space:
            conditions.append("space = ?")
            params.append(space)
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)
        if query:
            conditions.append("content LIKE ?")
            params.append(f"%{query}%")

        where_clause = " AND ".join(conditions)

        conn = self._get_connection()
        cursor = conn.execute(f"""
            SELECT * FROM xixi_memory_entries 
            WHERE {where_clause}
            ORDER BY 
                CASE space
                    WHEN 'raw' THEN 1
                    WHEN 'project' THEN 2
                    WHEN 'user' THEN 3
                    WHEN 'relationship' THEN 4
                    WHEN 'working' THEN 5
                    WHEN 'private_sandbox' THEN 6
                END,
                created_at DESC
            LIMIT ?
        """, params + [limit])

        return [dict(row) for row in cursor.fetchall()]

    def get_recent_conversations(
        self,
        limit: int = 10,
        as_messages: bool = False,
    ) -> List[Dict]:
        """
        获取最近对话历史。

        参数:
            limit: 返回条数
            as_messages: True 时返回 LLM 消息格式 [{"role": "user"/"assistant", "content": "..."}]
        """
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT role, content, created_at AS timestamp, id, status 
            FROM xixi_memory_entries 
            WHERE space = 'raw' OR space = 'working'
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        rows = list(reversed(rows))  # 按时间正序

        if as_messages:
            return [
                {"role": row[0], "content": row[1]}
                for row in rows
                if row[0] in ("user", "assistant") and row[4] == "active"
            ]
        return [
            {"role": row[0], "content": row[1], "timestamp": row[2], "id": row[3], "status": row[4]}
            for row in rows
        ]

    def get_project_memories(self, project_id: str, limit: int = 20) -> List[Dict]:
        """获取项目相关记忆"""
        return self.search_relevant(space="project", project_id=project_id, limit=limit)

    def get_user_preferences(self) -> List[Dict]:
        """获取用户长期偏好"""
        return self.search_relevant(space="user", limit=20)

    # ── 自然语言控制 ──

    def process_natural_language_command(self, text: str) -> Dict[str, Any]:
        """
        处理自然语言记忆控制命令。

        支持:
        - "记住..." -> save_memory
        - "不要记" -> 标记当前上下文不保存
        - "纠正..." -> supersede
        - "删除..." -> soft_delete（需确认范围）
        - "彻底删除..." -> purge（需确认）
        """
        text_lower = text.lower().strip()

        # 明确"记住"
        if text_lower.startswith("记住") or text_lower.startswith("请记住"):
            content = text[text.find("记住") + 2:].strip(" ：:.，")
            if content:
                mem_id = self.add_memory(content, space="user", source_type="user_decision")
                return {"action": "save_memory", "id": mem_id, "space": "user"}

        # 明确"不要记"
        if "不要记" in text_lower or "不用记" in text_lower or "别记" in text_lower:
            return {"action": "skip_save", "reason": "user_explicitly_declined"}

        # 纠正
        if text_lower.startswith("纠正") or text_lower.startswith("更正"):
            # 需要更复杂的解析，这里简化
            return {"action": "needs_clarification", "reason": "请提供要纠正的记录ID和新内容"}

        # 删除
        if text_lower.startswith("删除"):
            scope = text[text.find("删除") + 2:].strip()
            count, ids = self.delete_by_scope(scope)
            if count == -1:
                return {"action": "needs_clarification", "scope": scope, "matched_count": len(ids)}
            return {"action": "soft_delete", "count": count, "ids": ids}

        return {"action": "none"}

    # ── 清理 ──

    def cleanup(self) -> None:
        """关闭连接"""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# RC3 compatibility interface
from .memory_legacy import MemorySystem
