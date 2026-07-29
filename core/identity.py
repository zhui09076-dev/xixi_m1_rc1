"""
身份模块 v1.1
===========
- 唯一官方身份管理
- 数据库层保证 official=true 唯一性
- 脸部身份锚点
- 负向安全约束
"""

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
    identity_id: str = "xixi-main"
    identity_version: str = "1.0.0"
    personality_version: str = "1.0.0"
    render_version: str = "1.0.0"
    voice_version: str = "1.0.0"
    official: bool = True
    branch_of: Optional[str] = None
    inherited_until: Optional[str] = None
    memory_inheritance_policy: str = "full"
    status: str = "active"  # active/inactive/archived/branch/deleted
    created_at: str = ""
    updated_at: str = ""
    face_anchor_path: str = ""
    fork_history: List[dict] = field(default_factory=list)

    # 负向安全约束 — 不可覆盖
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
            # 过滤掉不可覆盖的负向约束，确保始终存在
            filtered = {k: v for k, v in data.items() if k != "NEGATIVE_CONSTRAINTS"}
            inst = cls(**filtered)
            return inst
        # 首次创建默认身份
        inst = cls()
        inst.save(path)
        return inst

    def check_negative_constraint(self, intent: str) -> bool:
        """检查意图是否违反负向约束。返回 True 表示安全，False 表示违规。"""
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
        """创建分支身份，不覆盖正式身份。分支 official=false。"""
        fork_id = f"{self.identity_id}-fork-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        fork = Identity(
            identity_id=fork_id,
            identity_version=self.identity_version,
            personality_version=self.personality_version,
            render_version=self.render_version,
            voice_version=self.voice_version,
            official=False,  # 分支不能是官方身份
            branch_of=self.identity_id,
            inherited_until=datetime.now().isoformat(),
            memory_inheritance_policy="none",  # 不自动同步私人记忆
            status="branch",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            face_anchor_path=self.face_anchor_path,
        )
        # 记录到主身份历史
        self.fork_history.append({
            "fork_id": fork_id,
            "parent_id": self.identity_id,
            "forked_at": datetime.now().isoformat(),
            "reason": reason,
        })
        self.updated_at = datetime.now().isoformat()
        return fork

    def validate_official(self) -> bool:
        """验证当前身份是否符合官方身份规则"""
        if self.official:
            return self.identity_id == "xixi-main"
        return True
