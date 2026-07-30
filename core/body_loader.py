"""Body 内容包加载器

负责：
- 扫描 bodies/ 目录
- 读取 manifest.json
- 分层渲染管理
- 缩放 / 锚点 / 状态映射
- 缺失资源回退
"""
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from core.database import Database
from core.version_registry import VersionRegistry, VersionRecord


BODY_SCHEMA_REQUIRED = {
    "packageType", "packageId", "version", "layers"
}


@dataclass
class BodyManifest:
    package_id: str
    version: str
    status: str
    layers: Dict[str, str]
    poses: Dict[str, str]
    state_mapping: Dict[str, Dict[str, str]]
    anchor: Dict[str, float]
    scale: float
    raw: Dict[str, Any]

    @classmethod
    def from_dict(cls, d: dict) -> "BodyManifest":
        return cls(
            package_id=d["packageId"],
            version=d["version"],
            status=d.get("status", ""),
            layers=d.get("layers", {}),
            poses=d.get("poses", {}),
            state_mapping=d.get("state_mapping", {}),
            anchor=d.get("anchor", {"x": 0.5, "y": 0.8}),
            scale=d.get("scale", 1.0),
            raw=d,
        )


class BodyLoader:
    """Body 包加载器"""

    def __init__(self, db: Database, registry: VersionRegistry,
                 packages_dir: str = "bodies"):
        self.db = db
        self.registry = registry
        self.packages_dir = Path(packages_dir)
        self._active_body: Optional[str] = None
        self._manifests: Dict[str, BodyManifest] = {}
        self._fallback_body_id: Optional[str] = None

    # ═══════════════════════════════════════════════════════════
    # 扫描与发现
    # ═══════════════════════════════════════════════════════════

    def scan(self) -> List[str]:
        """扫描 packages_dir 下所有 Body 包"""
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
                            body_id = data["packageId"]
                            self._manifests[body_id] = BodyManifest.from_dict(data)
                            found.append(body_id)
                    except Exception:
                        continue
        return found

    def _validate_manifest(self, data: dict) -> bool:
        return BODY_SCHEMA_REQUIRED.issubset(data.keys())

    # ═══════════════════════════════════════════════════════════
    # 加载与注册
    # ═══════════════════════════════════════════════════════════

    def load(self, package_id: str) -> bool:
        manifest = self._manifests.get(package_id)
        if not manifest:
            if not self.scan() or package_id not in self._manifests:
                return False
            manifest = self._manifests[package_id]

        path = self.packages_dir / package_id
        self.db.register_package(
            "body_packages", package_id, manifest.version,
            str(path), manifest.raw
        )
        self.registry.register(VersionRecord(
            package_id=package_id,
            package_type="body",
            version=manifest.version,
            path=str(path),
            active=False,
        ))
        return True

    def load_all(self) -> List[str]:
        self.scan()
        loaded = []
        for bid in self._manifests:
            if self.load(bid):
                loaded.append(bid)
        return loaded

    # ═══════════════════════════════════════════════════════════
    # 启用与切换
    # ═══════════════════════════════════════════════════════════

    def activate(self, package_id: str) -> bool:
        if package_id not in self._manifests:
            if not self.load(package_id):
                return False

        # 停用其他
        for bid in self._manifests:
            if bid != package_id:
                self.db.set_package_active("body_packages", bid, False)
                self.registry.set_active(bid, False)

        self.db.set_package_active("body_packages", package_id, True)
        self.registry.set_active(package_id, True)
        self._active_body = package_id
        return True

    def get_active(self) -> Optional[BodyManifest]:
        if self._active_body:
            return self._manifests.get(self._active_body)
        rows = self.db.list_packages("body_packages")
        for r in rows:
            if r.get("active"):
                self._active_body = r["package_id"]
                return self._manifests.get(self._active_body)
        return None

    # ═══════════════════════════════════════════════════════════
    # 升级与回滚
    # ═══════════════════════════════════════════════════════════

    def upgrade(self, package_id: str, new_path: str) -> bool:
        manifest_path = Path(new_path) / "manifest.json"
        if not manifest_path.exists():
            return False
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not self._validate_manifest(data):
            return False

        old = self.db.get_package("body_packages", package_id)
        if old:
            backup_dir = self.packages_dir / f"{package_id}-backup-{old['version']}"
            old_path = Path(old["path"])
            if old_path.exists():
                shutil.copytree(old_path, backup_dir, dirs_exist_ok=True)

        new_manifest = BodyManifest.from_dict(data)
        self._manifests[package_id] = new_manifest
        self.db.register_package(
            "body_packages", package_id, new_manifest.version,
            new_path, new_manifest.raw
        )
        self.registry.register(VersionRecord(
            package_id=package_id,
            package_type="body",
            version=new_manifest.version,
            path=new_path,
            active=old.get("active", False) if old else False,
        ))
        return True

    def rollback(self, package_id: str, backup_version: str) -> bool:
        backup_dir = self.packages_dir / f"{package_id}-backup-{backup_version}"
        if not backup_dir.exists():
            return False

        manifest_path = backup_dir / "manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        new_manifest = BodyManifest.from_dict(data)
        self._manifests[package_id] = new_manifest
        self.db.register_package(
            "body_packages", package_id, backup_version,
            str(backup_dir), new_manifest.raw
        )
        self.registry.rollback(package_id, backup_version, str(backup_dir))
        return True

    # ═══════════════════════════════════════════════════════════
    # 分层与渲染接口
    # ═══════════════════════════════════════════════════════════

    def get_layer_path(self, package_id: str, layer_name: str) -> Optional[str]:
        """获取某图层的资源路径"""
        manifest = self._manifests.get(package_id)
        if not manifest:
            return None
        rel_path = manifest.layers.get(layer_name)
        if not rel_path:
            return None
        full = self.packages_dir / package_id / rel_path
        if full.exists():
            return str(full)
        # 回退到占位资源
        return self._get_fallback_layer(layer_name)

    def get_pose_path(self, package_id: str, pose_name: str) -> Optional[str]:
        """获取某姿势的资源路径"""
        manifest = self._manifests.get(package_id)
        if not manifest:
            return None
        rel_path = manifest.poses.get(pose_name)
        if not rel_path:
            return None
        full = self.packages_dir / package_id / rel_path
        if full.exists():
            return str(full)
        return None

    def map_state_to_pose(self, package_id: str, state_id: str) -> Tuple[str, str]:
        """将状态 ID 映射为 (pose, mood)"""
        manifest = self._manifests.get(package_id)
        if not manifest:
            return "standing", "neutral"
        mapping = manifest.state_mapping.get(state_id, {})
        return mapping.get("pose", "standing"), mapping.get("mood", "neutral")

    def get_anchor(self, package_id: str) -> Tuple[float, float]:
        """获取锚点 (x, y)"""
        manifest = self._manifests.get(package_id)
        if not manifest:
            return 0.5, 0.8
        return manifest.anchor.get("x", 0.5), manifest.anchor.get("y", 0.8)

    def get_scale(self, package_id: str) -> float:
        """获取缩放比例"""
        manifest = self._manifests.get(package_id)
        if not manifest:
            return 1.0
        return manifest.scale

    def _get_fallback_layer(self, layer_name: str) -> Optional[str]:
        """获取占位图层"""
        fallback = self.packages_dir / "example_body" / f"{layer_name}" / "README.txt"
        if fallback.exists():
            return str(fallback)
        return None

    def set_fallback_body(self, package_id: str):
        """设置回退 Body"""
        self._fallback_body_id = package_id

    def list_loaded(self) -> List[dict]:
        return self.db.list_packages("body_packages")
