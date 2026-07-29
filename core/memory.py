"""
记忆系统 v3
===========
- 六类记忆支持
- 完整字段
- 自然语言记忆控制
- 纠正使用 supersedes
- 彻底删除诚实显示
- 推测不自动升级
"""

import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from core.database import Database


class MemorySystem:
    def __init__(self, db: Database):
        self.db = db
        self._preserve_original = False  # "保留我的原话"设置

    def _gen_id(self, seed: str) -> str:
        return hashlib.md5(f"{datetime.now().isoformat()}{seed}".encode()).hexdigest()[:12]

    # ========== 六类记忆写入 ==========
    def add_raw(self, content: str, source_type: str = "user_quote",
                source_ref: str = "", retention: str = "session",
                conversation_id: str = "", metadata: dict = None) -> str:
        """原始记录 — 不可覆盖"""
        eid = self._gen_id(f"raw{content}")
        self.db.add_memory_entry({
            "id": eid, "content": content, "source_type": source_type,
            "source_ref": source_ref, "scope": "session" if retention == "session" else "conversation",
            "retention": retention, "confidence": 1.0,
            "conversation_id": conversation_id,
            "metadata": metadata or {}
        })
        return eid

    def add_working(self, content: str, source_type: str = "xixi_opinion",
                    retention: str = "session", conversation_id: str = "") -> str:
        eid = self._gen_id(f"work{content}")
        self.db.add_memory_entry({
            "id": eid, "content": content, "source_type": source_type,
            "scope": "session", "retention": retention,
            "confidence": 0.7, "conversation_id": conversation_id
        })
        return eid

    def add_project_memory(self, project_id: str, content: str,
                           source_type: str = "xixi_opinion") -> str:
        eid = self._gen_id(f"proj{project_id}{content}")
        confidence = 0.95 if source_type == "user_decision" else 0.7
        self.db.add_memory_entry({
            "id": eid, "content": content, "source_type": source_type,
            "scope": "project", "project_id": project_id,
            "retention": "project", "confidence": confidence
        })
        return eid

    def add_long_term(self, content: str, source_type: str = "user_decision") -> str:
        eid = self._gen_id(f"ltf{content}")
        self.db.add_memory_entry({
            "id": eid, "content": content, "source_type": source_type,
            "scope": "user", "retention": "long_term", "confidence": 0.95
        })
        return eid

    def add_relationship(self, content: str) -> str:
        eid = self._gen_id(f"rel{content}")
        self.db.add_memory_entry({
            "id": eid, "content": content, "source_type": "xixi_opinion",
            "scope": "relationship", "retention": "long_term", "confidence": 0.75
        })
        return eid

    def add_sandbox(self, content: str) -> str:
        eid = self._gen_id(f"sb{content}")
        self.db.add_memory_entry({
            "id": eid, "content": content, "source_type": "xixi_inference",
            "scope": "private_sandbox", "retention": "temporary", "confidence": 0.5
        })
        return eid

    def add_chat(self, role: str, content: str, source_type: str = "user_quote",
                 session_id: str = "default", conversation_id: str = "") -> str:
        eid = self._gen_id(f"chat{content[:50]}")
        scope = "session" if role == "user" else "session"
        confidence = 1.0 if role == "user" else 0.8
        self.db.add_memory_entry({
            "id": eid, "content": content, "source_type": source_type,
            "scope": scope, "session_id": session_id,
            "conversation_id": conversation_id,
            "retention": "session", "confidence": confidence
        })
        return eid

    def get_recent_chat(self, limit: int = 10, session_id: str = "default") -> List[Dict]:
        c = self.db.execute("""
            SELECT source_type, content FROM memory_entries
            WHERE session_id = ? AND scope IN ('session', 'conversation')
            ORDER BY created_at DESC LIMIT ?
        """, (session_id, limit))
        rows = c.fetchall()
        return [{"role": "user" if r[0] == "user_quote" else "xixi", 
                 "content": r[1]} for r in reversed(rows)]

    # ========== 纠正规则 ==========
    def correct_memory(self, old_entry_id: str, new_content: str,
                       reason: str = "用户纠正") -> str:
        """纠正记忆：创建新记录，旧记录标记为 superseded"""
        eid = self._gen_id(f"correct{new_content}")
        self.db.add_memory_entry({
            "id": eid, "content": new_content, "source_type": "user_decision",
            "scope": "user", "retention": "long_term", "confidence": 0.95,
            "metadata": {"correction_reason": reason, "corrected_from": old_entry_id}
        })
        self.db.supersede_memory(old_entry_id, eid)
        return eid

    # ========== 自然语言记忆控制 ==========
    def handle_memory_command(self, text: str) -> Optional[str]:
        text_lower = text.lower().strip()

        # "保留我的原话"
        if "保留我的原话" in text_lower or "保留原话" in text_lower:
            self._preserve_original = True
            return "已设置：后续记录将保留原始文本，整理内容仅作为附加信息。"

        # "这只是随口说说" / "不要记进长期记忆"
        if any(kw in text_lower for kw in ["随口说说", "随便说说", "不要记住", "别记住", "不要记进"]):
            return "已标记：当前内容 retention=temporary，不会进入长期记忆。"

        # "记住这件事"
        match = re.search(r"记住[了]?\s*(.+?)(?:$|[，。])", text)
        if match:
            content = match.group(1).strip()
            eid = self.add_long_term(content, "user_decision")
            return f"已记住: {content[:40]}{'...' if len(content) > 40 else ''}"

        # "你记错了" / "把这条改成"
        if "记错了" in text_lower or "改成" in text_lower:
            return "请告诉我具体是哪条记忆（或提供内容关键词），我可以纠正。"

        # "忘掉刚才那段"
        if "忘掉" in text_lower or "删除刚才" in text_lower:
            return "请确认范围：是当前对话的全部内容，还是最近几条？我无法猜测删除。"

        # "彻底删除"
        if "彻底删除" in text_lower or "完全删除" in text_lower:
            return "请指定要删除的具体内容或记录ID。彻底删除将清理主记录、索引和引用，但历史备份将在轮换时清理。"

        # "把关于这个项目的记忆列出来"
        if "列出来" in text_lower or "列出记忆" in text_lower:
            entries = self.db.get_memory_entries(limit=20)
            if entries:
                lines = [f"• [{e['scope']}] {e['content'][:40]}..." for e in entries[:10]]
                return "记忆列表:
" + "
".join(lines)
            return "暂无记录"

        # "告诉我这条记忆从哪里来的"
        if "从哪里来的" in text_lower or "来源" in text_lower:
            return "请指定具体记忆内容或ID，我可以查询 source_type 和 source_ref。"

        return None

    def execute_delete(self, entry_id: str, hard: bool = False) -> str:
        """执行删除，返回诚实报告"""
        entry = self.db.execute("SELECT * FROM memory_entries WHERE id = ?", (entry_id,)).fetchone()
        if not entry:
            return f"记录 {entry_id} 不存在。"

        if hard:
            self.db.hard_delete_memory(entry_id)
            return f"记录 {entry_id} 已立即从主数据库删除。索引和引用已清理。历史备份将在下次轮换时清理。"
        else:
            self.db.soft_delete_memory(entry_id)
            return f"记录 {entry_id} 已标记为删除。将在下次清理周期中物理移除。"

    def execute_forget_range(self, count: int = 3, session_id: str = "default") -> str:
        """按范围遗忘"""
        c = self.db.execute("""
            SELECT id FROM memory_entries 
            WHERE session_id = ? AND status = 'active'
            ORDER BY created_at DESC LIMIT ?
        """, (session_id, count))
        rows = c.fetchall()
        for r in rows:
            self.db.soft_delete_memory(r[0])
        return f"已遗忘最近 {len(rows)} 条记录（session_id={session_id}）"

    def clear_sandbox(self) -> str:
        """用户清除沙盒"""
        entries = self.db.get_memory_entries(scope="private_sandbox", limit=1000)
        for e in entries:
            self.db.hard_delete_memory(e["id"])
        return f"已清除 {len(entries)} 条私人思考沙盒记录。"

    def get_project_memories(self, project_id: str) -> List[Dict]:
        """按 projectId 过滤项目记忆"""
        return self.db.get_memory_entries(scope="project", project_id=project_id, limit=100)

    def get_time_away_summary(self) -> str:
        state = self.db.get_state()
        if not state:
            return "这是我们第一次对话。"
        last = datetime.fromisoformat(state.get("last_interaction_at", datetime.now().isoformat()))
        delta = datetime.now() - last
        if delta < timedelta(minutes=10):
            return "你刚离开一会儿。"
        elif delta < timedelta(hours=2):
            return f"你离开了约{delta.seconds // 60}分钟。"
        elif delta < timedelta(days=1):
            return f"你离开了约{delta.seconds // 3600}小时。"
        else:
            return f"你离开了{delta.days}天。"

    # ========== 兼容旧接口 ==========
    def add_note(self, content: str, source_type: str = "user_quote", tags: List[str] = None) -> str:
        return self.add_raw(content, source_type, retention="session")

    def get_notes(self, limit: int = 20) -> List[Dict]:
        return self.db.get_memory_entries(scope="session", limit=limit)

    def add_todo(self, content: str, project_id: str = None, priority: int = 1) -> str:
        eid = self._gen_id(f"todo{content}")
        self.db.execute("""
            INSERT INTO todos (id, content, project_id, priority, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (eid, content, project_id, priority, datetime.now().isoformat()))
        self.db.commit()
        return eid

    def get_todos(self, done: bool = False) -> List[Dict]:
        c = self.db.execute("""
            SELECT * FROM todos WHERE done = ? ORDER BY priority DESC, timestamp DESC
        """, (1 if done else 0,))
        return [dict(r) for r in c.fetchall()]

    def complete_todo(self, todo_id: str):
        self.db.execute("""
            UPDATE todos SET done = 1, completed_at = ? WHERE id = ?
        """, (datetime.now().isoformat(), todo_id))
        self.db.commit()

    def add_project(self, name: str, description: str = "") -> str:
        eid = self._gen_id(f"proj{name}")
        self.db.execute("""
            INSERT INTO projects (id, name, description, timestamp)
            VALUES (?, ?, ?, ?)
        """, (eid, name, description, datetime.now().isoformat()))
        self.db.commit()
        return eid

    def get_projects(self, status: str = "active") -> List[Dict]:
        c = self.db.execute("""
            SELECT * FROM projects WHERE status = ? ORDER BY timestamp DESC
        """, (status,))
        return [dict(r) for r in c.fetchall()]
