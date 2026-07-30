"""Soul 内容包加载器

负责：
- 扫描 souls/ 目录
- 读取 manifest.json
- 校验 schema
- 注册到数据库
- 启用 / 切换 / 升级 / 回滚
- 保留记忆不丢失
"""
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

from core.database import Database
from core.version_registry import VersionRegistry, VersionRecord


SOUL_SCHEMA_REQUIRED = {
    "packageType", "packageId", "version", "schemaVersion", "entry"
}


@dataclass
class SoulManifest:
    package_id: str
    version: str
    schema_version: str
    entry: Dict[str, str]
    compatibility: Dict[str, Any]
    persistence: Dict[str, Any]
    raw: Dict[str, Any]

    @classmethod
    def from_dict(cls, d: dict) -> "SoulManifest":
        return cls(
            package_id=d["packageId"],
            version=d["version"],
            schema_version=d.get("schemaVersion", "1.0.0"),
            entry=d.get("entry", {}),
            compatibility=d.get("compatibility", {}),
            persistence=d.get("persistence", {}),
            raw=d,
        )


class SoulLoader:
    """Soul 包加载器"""

    def __init__(self, db: Database, registry: VersionRegistry,
                 packages_dir: str = "souls"):
        self.db = db
        self.registry = registry
        self.packages_dir = Path(packages_dir)
        self._active_soul: Optional[str] = None
        self._manifests: Dict[str, SoulManifest] = {}

    # ═══════════════════════════════════════════════════════════
    # 扫描与发现
    # ═══════════════════════════════════════════════════════════

    def scan(self) -> List[str]:
        """扫描 packages_dir 下所有 Soul 包，返回 package_id 列表"""
        found = []
        if not self.packages_dir.exists():
            return found
        for subdir in self.packages_dir.iterdir():
            if subdir.is_dir():
                manifest_path = subdir / "manifest.json"
                if manifest_path.exists():
                    try:
                        with open(manifest_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if self._validate_manifest(data):
                            soul_id = data["packageId"]
                            self._manifests[soul_id] = SoulManifest.from_dict(data)
                            found.append(soul_id)
                    except Exception:
                        continue
        return found

    def _validate_manifest(self, data: dict) -> bool:
        """校验 manifest 必要字段"""
        return SOUL_SCHEMA_REQUIRED.issubset(data.keys())

    # ═══════════════════════════════════════════════════════════
    # 加载与注册
    # ═══════════════════════════════════════════════════════════

    def load(self, package_id: str) -> bool:
        """加载指定 Soul 包到数据库（不激活）"""
        manifest = self._manifests.get(package_id)
        if not manifest:
            if not self.scan() or package_id not in self._manifests:
                return False
            manifest = self._manifests[package_id]

        path = self.packages_dir / package_id
        self.db.register_package(
            "soul_packages", package_id, manifest.version,
            str(path), manifest.raw
        )
        self.registry.register(VersionRecord(
            package_id=package_id,
            package_type="soul",
            version=manifest.version,
            path=str(path),
            active=False,
        ))
        return True

    def load_all(self) -> List[str]:
        """加载所有发现的 Soul 包"""
        self.scan()
        loaded = []
        for sid in self._manifests:
            if self.load(sid):
                loaded.append(sid)
        return loaded

    # ═══════════════════════════════════════════════════════════
    # 启用与切换
    # ═══════════════════════════════════════════════════════════

    def activate(self, package_id: str) -> bool:
        """激活指定 Soul 包（同一时间只有一个）"""
        if package_id not in self._manifests:
            if not self.load(package_id):
                return False

        # 停用其他
        for sid in self._manifests:
            if sid != package_id:
                self.db.set_package_active("soul_packages", sid, False)
                self.registry.set_active(sid, False)

        # 激活目标
        self.db.set_package_active("soul_packages", package_id, True)
        self.registry.set_active(package_id, True)
        self._active_soul = package_id
        return True

    def get_active(self) -> Optional[SoulManifest]:
        """获取当前激活的 Soul 包"""
        if self._active_soul:
            return self._manifests.get(self._active_soul)
        # 从数据库恢复
        rows = self.db.list_packages("soul_packages")
        for r in rows:
            if r.get("active"):
                self._active_soul = r["package_id"]
                return self._manifests.get(self._active_soul)
        return None

    # ═══════════════════════════════════════════════════════════
    # 升级与回滚
    # ═══════════════════════════════════════════════════════════

    def upgrade(self, package_id: str, new_path: str) -> bool:
        """升级 Soul 包（保留记忆）"""
        manifest_path = Path(new_path) / "manifest.json"
        if not manifest_path.exists():
            return False
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not self._validate_manifest(data):
            return False

        # 备份旧版本
        old = self.db.get_package("soul_packages", package_id)
        if old:
            backup_dir = self.packages_dir / f"{package_id}-backup-{old['version']}"
            old_path = Path(old["path"])
            if old_path.exists():
                shutil.copytree(old_path, backup_dir, dirs_exist_ok=True)

        # 替换为新版本
        new_manifest = SoulManifest.from_dict(data)
        self._manifests[package_id] = new_manifest
        self.db.register_package(
            "soul_packages", package_id, new_manifest.version,
            new_path, new_manifest.raw
        )
        self.registry.register(VersionRecord(
            package_id=package_id,
            package_type="soul",
            version=new_manifest.version,
            path=new_path,
            active=old.get("active", False) if old else False,
        ))
        return True

    def rollback(self, package_id: str, backup_version: str) -> bool:
        """回滚到指定版本"""
        backup_dir = self.packages_dir / f"{package_id}-backup-{backup_version}"
        if not backup_dir.exists():
            return False

        manifest_path = backup_dir / "manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        new_manifest = SoulManifest.from_dict(data)
        self._manifests[package_id] = new_manifest
        self.db.register_package(
            "soul_packages", package_id, backup_version,
            str(backup_dir), new_manifest.raw
        )
        self.registry.rollback(package_id, backup_version, str(backup_dir))
        return True

    # ═══════════════════════════════════════════════════════════
    # 读取 Soul 内容
    # ═══════════════════════════════════════════════════════════

    def read_entry(self, package_id: str, entry_name: str) -> Optional[dict]:
        """读取 Soul 包中某个 entry 文件（YAML/JSON）"""
        manifest = self._manifests.get(package_id)
        if not manifest:
            return None
        filename = manifest.entry.get(entry_name)
        if not filename:
            return None
        path = self.packages_dir / package_id / filename
        if not path.exists():
            return None
        try:
            if path.suffix in (".yaml", ".yml"):
                import yaml
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            elif path.suffix == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            elif path.suffix == ".txt":
                with open(path, "r", encoding="utf-8") as f:
                    return {"content": f.read()}
        except Exception:
            return None
        return None

    def read_identity(self, package_id: str) -> Optional[dict]:
        return self.read_entry(package_id, "identity")

    def read_constitution(self, package_id: str) -> Optional[dict]:
        return self.read_entry(package_id, "constitution")

    def read_personality(self, package_id: str) -> Optional[dict]:
        return self.read_entry(package_id, "personality")

    def read_memory_policy(self, package_id: str) -> Optional[dict]:
        return self.read_entry(package_id, "memoryPolicy")

    def list_loaded(self) -> List[dict]:
        """列出所有已加载的 Soul 包"""
        return self.db.list_packages("soul_packages")
