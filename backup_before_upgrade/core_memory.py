"""记忆系统 v5 — 稳定接口，策略由 Soul 包决定"""
import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from core.database import Database


class MemorySystem:
    """
    记忆系统：提供稳定的 CRUD + supersede + 删除接口。
    记忆策略（保留/遗忘/重要性判断）由外部 Soul 内容包通过 policy_callback 注入。
    """

    def __init__(self, db: Database, policy_callback: Optional[Callable] = None):
        self.db = db
        self._policy_callback = policy_callback
        self._preserve_original = False
        self._load_settings()

    def _gen_id(self, seed: str) -> str:
        return hashlib.md5(f"{datetime.now().isoformat()}{seed}".encode()).hexdigest()[:12]

    def _load_settings(self):
        row = self.db.execute("SELECT value FROM settings WHERE key = ?", ("preserve_original",)).fetchone()
        if row:
            self._preserve_original = row["value"].lower() == "true"

    def _save_setting(self, key: str, value: str):
        self.db.execute("""
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, value, datetime.now().isoformat()))
        self.db.commit()

    # ═══════════════════════════════════════════════════════════
    # 核心 CRUD 接口（稳定，不随 Soul 包变化）
    # ═══════════════════════════════════════════════════════════

    def create(self, content: str, source_type: str = "user_quote",
               source_ref: str = "", scope: str = "session", project_id: str = "",
               retention: str = "medium", confidence: float = 0.8,
               session_id: str = "default", metadata: dict = None) -> str:
        eid = self._gen_id(f"mem{content}")
        entry = {
            "id": eid, "content": content, "source_type": source_type,
            "source_ref": source_ref, "scope": scope, "project_id": project_id,
            "retention": retention, "confidence": confidence,
            "session_id": session_id, "metadata": metadata or {},
            "status": "active",
        }
        self.db.add_memory_entry(entry)
        return eid

    def query(self, scope=None, source_type=None, status="active",
              project_id=None, session_id=None, limit=50, order="DESC") -> List[Dict]:
        return self.db.query_memory_entries(
            scope=scope, source_type=source_type, status=status,
            project_id=project_id, session_id=session_id, limit=limit, order=order
        )

    def get_by_id(self, entry_id: str) -> Optional[Dict]:
        row = self.db.execute("SELECT * FROM memory_entries WHERE id = ?", (entry_id,)).fetchone()
        if row:
            d = dict(row)
            try:
                d["metadata"] = json.loads(d.get("metadata", "{}"))
            except Exception:
                d["metadata"] = {}
            return d
        return None

    def update(self, entry_id: str, updates: dict) -> bool:
        return self.db.update_memory_entry(entry_id, updates)

    def supersede(self, old_entry_id: str, new_content: str,
                  reason: str = "用户纠正", **kwargs) -> str:
        new_id = self.create(new_content, **kwargs)
        self.db.supersede_memory(old_entry_id, new_id)
        self.update(new_id, {"metadata": {"supersedes_reason": reason, "supersedes": old_entry_id}})
        return new_id

    def delete(self, entry_id: str, permanent: bool = False) -> bool:
        return self.db.delete_memory_entry(entry_id, permanent=permanent)

    def restore(self, entry_id: str) -> bool:
        return self.update(entry_id, {"status": "active", "deleted_at": ""})

    # ═══════════════════════════════════════════════════════════
    # 便捷方法
    # ═══════════════════════════════════════════════════════════

    def add_raw(self, content: str, source_type: str = "user_quote",
                source_ref: str = "", retention: str = "session",
                conversation_id: str = "", metadata: dict = None) -> str:
        scope = "session" if retention == "session" else "conversation"
        return self.create(content, source_type=source_type, source_ref=source_ref,
                           scope=scope, retention=retention, session_id=conversation_id,
                           metadata=metadata)

    def add_working(self, content: str, source_type: str = "xixi_opinion",
                    retention: str = "session", conversation_id: str = "") -> str:
        return self.create(content, source_type=source_type, scope="session",
                           retention=retention, session_id=conversation_id, confidence=0.7)

    def add_project_memory(self, project_id: str, content: str,
                           source_type: str = "xixi_opinion") -> str:
        confidence = 0.95 if source_type == "user_decision" else 0.7
        return self.create(content, source_type=source_type, scope="project",
                           project_id=project_id, retention="project", confidence=confidence)

    def add_long_term(self, content: str, source_type: str = "user_decision") -> str:
        return self.create(content, source_type=source_type, scope="user",
                           retention="long_term", confidence=0.95)

    def add_relationship(self, content: str) -> str:
        return self.create(content, source_type="xixi_opinion", scope="relationship",
                           retention="long_term", confidence=0.75)

    def add_sandbox(self, content: str) -> str:
        return self.create(content, source_type="xixi_inference", scope="private_sandbox",
                           retention="temporary", confidence=0.5)

    def add_chat(self, role: str, content: str, source_type: str = "user_quote",
                 session_id: str = "default", conversation_id: str = "") -> str:
        confidence = 1.0 if role == "user" else 0.8
        return self.create(content, source_type=source_type, scope="session",
                           session_id=session_id, confidence=confidence)

    def get_recent_chat(self, limit: int = 10, session_id: str = "default") -> List[Dict]:
        rows = self.db.query_memory_entries(
            scope=None, status="active", session_id=session_id,
            limit=limit, order="DESC"
        )
        return [{"role": "user" if r["source_type"] == "user_quote" else "xixi",
                 "content": r["content"]} for r in reversed(rows)
                if r["scope"] in ("session", "conversation")]

    def correct_memory(self, old_entry_id: str, new_content: str,
                       reason: str = "用户纠正") -> str:
        return self.supersede(old_entry_id, new_content, reason=reason,
                              source_type="user_decision", scope="user",
                              retention="long_term", confidence=0.95)

    # ═══════════════════════════════════════════════════════════
    # 记忆命令处理（保留原有交互命令）
    # ═══════════════════════════════════════════════════════════

    def handle_memory_command(self, text: str) -> Optional[str]:
        text_lower = text.lower().strip()

        if "保留我的原话" in text_lower or "保留原话" in text_lower:
            self._preserve_original = True
            self._save_setting("preserve_original", "true")
            return "已设置：后续记录将保留原始文本，整理内容仅作为附加信息。"

        if any(kw in text_lower for kw in ["随口说说", "随便说说", "不要记住", "别记住", "不要记进"]):
            return "已标记：当前内容 retention=temporary，不会进入长期记忆。"

        if any(kw in text_lower for kw in ["记住", "记下来"]):
            if "：" in text or ":" in text:
                content = text.split("：")[-1] if "：" in text else text.split(":")[-1]
                content = content.strip()
                if content:
                    self.create(content, source_type="user_quote", scope="user", retention="long_term", confidence=0.95)
                    return "已记住。"
            return "已记住。"

        if any(kw in text_lower for kw in ["记错了", "理解错了", "纠正", "改成"]):
            return "请告诉我正确的内容，我会用新条目替代旧条目。"

        if any(kw in text_lower for kw in ["忘掉", "删除刚才", "彻底删除", "完全删除"]):
            return "请确认范围：请指定要删除的记忆 ID，或说'删除最后一条'。"

        if "列出记忆" in text_lower or "列出来" in text_lower:
            recent = self.query(status="active", limit=10)
            if not recent:
                return "当前没有活跃记忆。"
            lines = [f"[{i+1}] {r['content'][:40]}... (ID: {r['id']})" for i, r in enumerate(recent)]
            return "最近记忆：\n" + "\n".join(lines)

        if "来源" in text_lower or "从哪里来的" in text_lower:
            return "请提供记忆 ID，我可以查询来源信息。"

        return None

    # ═══════════════════════════════════════════════════════════
    # Soul 包策略注入接口
    # ═══════════════════════════════════════════════════════════

    def set_policy_callback(self, callback: Optional[Callable]):
        self._policy_callback = callback

    def apply_policy(self, entry: dict) -> dict:
        if self._policy_callback:
            return self._policy_callback(entry)
        return entry
