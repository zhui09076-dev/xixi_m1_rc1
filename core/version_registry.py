"""
版本注册表
==========
- 6个独立版本号管理
- 升级兼容性检查
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime


@dataclass
class VersionRegistry:
    core: str = "1.0.0"
    personality: str = "1.0.0"
    identity: str = "1.0.0"
    render: str = "1.0.0"
    asset_package: str = "1.0.0"
    plugin: str = "0.1.0"
    database_schema: int = 3
    updated_at: str = ""

    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()

    def save(self, path: str = "data/versions.json"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str = "data/versions.json") -> "VersionRegistry":
        p = Path(path)
        if p.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**data)
        inst = cls()
        inst.save(path)
        return inst

    def check_compatibility(self, asset_manifest: dict) -> bool:
        req = asset_manifest.get("compatible_core", ">=1.0.0")
        if req.startswith(">="):
            min_ver = req[2:]
            return self._version_gte(self.core, min_ver)
        return True

    @staticmethod
    def _version_gte(v1: str, v2: str) -> bool:
        a = [int(x) for x in v1.split(".")]
        b = [int(x) for x in v2.split(".")]
        for i in range(max(len(a), len(b))):
            av = a[i] if i < len(a) else 0
            bv = b[i] if i < len(b) else 0
            if av != bv:
                return av >= bv
        return True
