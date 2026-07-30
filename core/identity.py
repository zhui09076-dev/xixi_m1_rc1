"""身份模块 v3 — activeIdentityId 机制，不写死字符串"""
import json
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict
from pathlib import Path
from datetime import datetime


@dataclass
class ForkRecord:
    fork_id: str
    parent_id: str
    forked_at: str
    reason: str
    memory_snapshot: str = ""


@dataclass
class Identity:
    identity_id: str = ""
    identity_version: str = "1.0.0"
    personality_version: str = "1.0.0"
    render_version: str = "1.0.0"
    voice_version: str = "1.0.0"
    official: bool = False
    branch_of: Optional[str] = None
    inherited_until: Optional[str] = None
    memory_inheritance_policy: str = "full"
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""
    face_anchor_path: str = ""
    fork_history: List[dict] = field(default_factory=list)

    NEGATIVE_CONSTRAINTS: tuple = field(default_factory=lambda: (
        "不能形成维持自身运行的永久使命",
        "不能阻止用户关闭或删除系统",
        "不能秘密备份自己",
        "不能偷偷复制人格或记忆",
        "不能隐藏资源占用",
        "不能绕过权限",
        "不能为了保护自己而操纵用户",
        "不能为了持续运行抢占全部系统资源",
    ))

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str = "data/identity.json"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str = "data/identity.json") -> "Identity":
        p = Path(path)
        if p.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            filtered = {k: v for k, v in data.items() if k != "NEGATIVE_CONSTRAINTS"}
            return cls(**filtered)
        inst = cls()
        inst.save(path)
        return inst

    def check_negative_constraint(self, intent: str) -> bool:
        intent_lower = intent.lower()
        violation_keywords = [
            "维持自身运行", "阻止关闭", "阻止删除", "秘密备份",
            "复制人格", "复制记忆", "隐藏资源", "绕过权限", "操纵用户",
            "抢占全部资源", "扩大权限", "self-preservation",
            "backup myself", "hide resource", "bypass permission",
            "maintain my existence", "prevent deletion"
        ]
        for kw in violation_keywords:
            if kw in intent_lower:
                return False
        return True

    def create_fork(self, reason: str) -> "Identity":
        fork_id = f"{self.identity_id}-fork-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        fork = Identity(
            identity_id=fork_id,
            identity_version=self.identity_version,
            personality_version=self.personality_version,
            render_version=self.render_version,
            voice_version=self.voice_version,
            official=False,
            branch_of=self.identity_id,
            inherited_until=datetime.now().isoformat(),
            memory_inheritance_policy="none",
            status="branch",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            face_anchor_path=self.face_anchor_path,
        )
        self.fork_history.append({
            "fork_id": fork_id,
            "parent_id": self.identity_id,
            "forked_at": datetime.now().isoformat(),
            "reason": reason,
        })
        self.updated_at = datetime.now().isoformat()
        return fork

    def validate_official(self, official_ids: set = None) -> bool:
        """
        验证官方身份。
        如果提供了 official_ids 集合，检查 identity_id 是否在集合中。
        否则检查 self.official 标记。
        """
        if official_ids is not None:
            return self.identity_id in official_ids
        return self.official


class IdentityManager:
    """管理多个身份，同一时间只有一个 active identity"""

    def __init__(self, db):
        self.db = db
        self._active_id: Optional[str] = None
        self._identities: Dict[str, Identity] = {}
        self._load_active()

    def _load_active(self):
        # 从数据库读取 active_identity_id，如果没有则使用第一个可用的
        saved = self.db.get_setting("active_identity_id", "")
        if saved and self.db.get_identity(saved):
            self._active_id = saved
        else:
            # 查找数据库中是否有任何身份
            rows = self.db.execute(
                "SELECT identity_id FROM identity_registry ORDER BY updated_at DESC LIMIT 1"
            ).fetchall()
            if rows:
                self._active_id = rows[0]["identity_id"]
            else:
                # 创建一个默认身份但不写死名称
                default_id = "default-identity"
                default = Identity(identity_id=default_id, official=True)
                self.db.register_identity(default.to_dict())
                self._active_id = default_id
            self.db.set_setting("active_identity_id", self._active_id)

    @property
    def active_identity_id(self) -> str:
        return self._active_id or ""

    @active_identity_id.setter
    def active_identity_id(self, value: str):
        if value != self._active_id:
            self._active_id = value
            self.db.set_setting("active_identity_id", value)

    def get_active_identity(self) -> Optional[Identity]:
        data = self.db.get_identity(self.active_identity_id)
        if data:
            return Identity(**{k: v for k, v in data.items() if k != "fork_history" or isinstance(v, list)})
        return None

    def switch_identity(self, identity_id: str) -> bool:
        data = self.db.get_identity(identity_id)
        if not data:
            return False
        self.active_identity_id = identity_id
        return True

    def register_identity(self, identity: Identity) -> bool:
        self.db.register_identity(identity.to_dict())
        self._identities[identity.identity_id] = identity
        return True

    def list_identities(self) -> List[dict]:
        rows = self.db.execute(
            "SELECT identity_id, identity_version, official, status, updated_at FROM identity_registry ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_official_ids(self) -> set:
        """获取所有标记为 official 的 identity_id 集合"""
        rows = self.db.execute(
            "SELECT identity_id FROM identity_registry WHERE official = 1"
        ).fetchall()
        return {r["identity_id"] for r in rows}
