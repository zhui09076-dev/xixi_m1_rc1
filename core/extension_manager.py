"""扩展管理器

负责：
- 扫描 extensions/ 目录
- 安装 / 启用 / 停用 / 升级 / 回滚 / 卸载
- 权限沙箱（声明制）
- 新增扩展不要求修改容器核心代码
"""
import json
import shutil
import zipfile
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime

from core.database import Database
from core.version_registry import VersionRegistry, VersionRecord


EXTENSION_SCHEMA_REQUIRED = {
    "packageType", "packageId", "version", "name", "entry"
}


@dataclass
class ExtensionManifest:
    package_id: str
    version: str
    name: str
    description: str
    entry: str
    permissions: List[str]
    config: Dict[str, Any]
    tests: List[str]
    raw: Dict[str, Any]

    @classmethod
    def from_dict(cls, d: dict) -> "ExtensionManifest":
        return cls(
            package_id=d["packageId"],
            version=d["version"],
            name=d["name"],
            description=d.get("description", ""),
            entry=d["entry"],
            permissions=d.get("permissions", []),
            config=d.get("config", {}),
            tests=d.get("tests", []),
            raw=d,
        )


class ExtensionManager:
    """扩展管理器"""

    def __init__(self, db: Database, registry: VersionRegistry,
                 extensions_dir: str = "extensions"):
        self.db = db
        self.registry = registry
        self.extensions_dir = Path(extensions_dir)
        self._manifests: Dict[str, ExtensionManifest] = {}
        self._instances: Dict[str, Any] = {}
        self._hooks: Dict[str, List[Callable]] = {}

    # ═══════════════════════════════════════════════════════════
    # 扫描与发现
    # ═══════════════════════════════════════════════════════════

    def scan(self) -> List[str]:
        """扫描已安装的扩展"""
        found = []
        if not self.extensions_dir.exists():
            return found
        for subdir in self.extensions_dir.iterdir():
            if subdir.is_dir():
                manifest_path = subdir / "manifest.json"
                if manifest_path.exists():
                    try:
                        with open(manifest_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if self._validate_manifest(data):
                            eid = data["packageId"]
                            self._manifests[eid] = ExtensionManifest.from_dict(data)
                            found.append(eid)
                    except Exception:
                        continue
        return found

    def _validate_manifest(self, data: dict) -> bool:
        return EXTENSION_SCHEMA_REQUIRED.issubset(data.keys())

    # ═══════════════════════════════════════════════════════════
    # 安装（从目录或 zip）
    # ═══════════════════════════════════════════════════════════

    def install(self, source_path: str) -> str:
        """安装扩展，返回 package_id"""
        src = Path(source_path)
        if not src.exists():
            raise FileNotFoundError(f"扩展源不存在: {source_path}")

        # 如果是 zip，先解压到 temp
        if src.suffix == ".zip":
            temp_dir = Path("temp") / f"ext-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(temp_dir)
            # 找 manifest
            manifest_path = self._find_manifest(temp_dir)
            if not manifest_path:
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise ValueError("zip 中未找到有效的 manifest.json")
            src = manifest_path.parent

        manifest_path = src / "manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not self._validate_manifest(data):
            raise ValueError("manifest.json 缺少必要字段")

        eid = data["packageId"]
        version = data["version"]

        # 复制到 extensions 目录
        target = self.extensions_dir / eid
        if target.exists():
            # 备份旧版本
            backup = self.extensions_dir / f"{eid}-backup-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            shutil.copytree(target, backup, dirs_exist_ok=True)
            shutil.rmtree(target)

        shutil.copytree(src, target)

        # 注册到数据库
        self.db.register_package(
            "extension_packages", eid, version,
            str(target), data
        )
        self.registry.register(VersionRecord(
            package_id=eid, package_type="extension",
            version=version, path=str(target),
            active=False,
        ))
        self._manifests[eid] = ExtensionManifest.from_dict(data)
        return eid

    def _find_manifest(self, root: Path) -> Optional[Path]:
        for p in root.rglob("manifest.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if self._validate_manifest(data):
                    return p
            except Exception:
                continue
        return None

    # ═══════════════════════════════════════════════════════════
    # 启用 / 停用
    # ═══════════════════════════════════════════════════════════

    def enable(self, package_id: str) -> bool:
        """启用扩展（加载入口模块）"""
        manifest = self._manifests.get(package_id)
        if not manifest:
            if not self.scan() or package_id not in self._manifests:
                return False
            manifest = self._manifests[package_id]

        ext_dir = self.extensions_dir / package_id
        entry_path = ext_dir / manifest.entry

        if not entry_path.exists():
            return False

        # 动态加载
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                f"ext_{package_id}", str(entry_path)
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 调用 create_extension
            if hasattr(module, "create_extension"):
                instance = module.create_extension(self)
                self._instances[package_id] = instance
                if hasattr(instance, "on_enable"):
                    instance.on_enable()
        except Exception as e:
            print(f"扩展 {package_id} 加载失败: {e}")
            return False

        self.db.set_package_active("extension_packages", package_id, True)
        self.registry.set_active(package_id, True)
        return True

    def disable(self, package_id: str) -> bool:
        """停用扩展"""
        instance = self._instances.get(package_id)
        if instance and hasattr(instance, "on_disable"):
            instance.on_disable()

        self._instances.pop(package_id, None)
        self.db.set_package_active("extension_packages", package_id, False)
        self.registry.set_active(package_id, False)
        return True

    # ═══════════════════════════════════════════════════════════
    # 升级 / 回滚 / 卸载
    # ═══════════════════════════════════════════════════════════

    def upgrade(self, package_id: str, new_source_path: str) -> bool:
        """升级扩展"""
        # 先停用
        was_enabled = self.is_enabled(package_id)
        if was_enabled:
            self.disable(package_id)

        # 备份
        old_dir = self.extensions_dir / package_id
        if old_dir.exists():
            old_manifest = self._manifests.get(package_id)
            old_version = old_manifest.version if old_manifest else "unknown"
            backup_dir = self.extensions_dir / f"{package_id}-backup-{old_version}"
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            shutil.copytree(old_dir, backup_dir)
            shutil.rmtree(old_dir)

        # 安装新版本
        self.install(new_source_path)

        # 如果之前是启用的，重新启用
        if was_enabled:
            self.enable(package_id)
        return True

    def rollback(self, package_id: str, backup_version: str) -> bool:
        """回滚到指定版本"""
        backup_dir = self.extensions_dir / f"{package_id}-backup-{backup_version}"
        if not backup_dir.exists():
            return False

        was_enabled = self.is_enabled(package_id)
        if was_enabled:
            self.disable(package_id)

        target = self.extensions_dir / package_id
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(backup_dir, target)

        # 重新读取 manifest
        with open(target / "manifest.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        self._manifests[package_id] = ExtensionManifest.from_dict(data)
        self.db.register_package(
            "extension_packages", package_id, backup_version,
            str(target), data
        )

        if was_enabled:
            self.enable(package_id)
        return True

    def uninstall(self, package_id: str) -> bool:
        """卸载扩展"""
        if self.is_enabled(package_id):
            self.disable(package_id)

        target = self.extensions_dir / package_id
        if target.exists():
            shutil.rmtree(target)

        # 清理备份
        for backup in self.extensions_dir.glob(f"{package_id}-backup-*"):
            shutil.rmtree(backup)

        self._manifests.pop(package_id, None)
        self.db.execute("DELETE FROM extension_packages WHERE package_id = ?", (package_id,))
        self.db.commit()
        return True

    # ═══════════════════════════════════════════════════════════
    # 查询
    # ═══════════════════════════════════════════════════════════

    def is_enabled(self, package_id: str) -> bool:
        row = self.db.get_package("extension_packages", package_id)
        return bool(row.get("enabled")) if row else False

    def get_instance(self, package_id: str) -> Optional[Any]:
        return self._instances.get(package_id)

    def list_extensions(self) -> List[dict]:
        return self.db.list_packages("extension_packages")

    def get_manifest(self, package_id: str) -> Optional[ExtensionManifest]:
        return self._manifests.get(package_id)

    def run_extension_tests(self, package_id: str) -> dict:
        """运行扩展自带的测试"""
        manifest = self._manifests.get(package_id)
        if not manifest or not manifest.tests:
            return {"passed": False, "reason": "无测试文件"}

        ext_dir = self.extensions_dir / package_id
        results = []
        for test_file in manifest.tests:
            test_path = ext_dir / test_file
            if not test_path.exists():
                continue
            try:
                import subprocess
                result = subprocess.run(
                    ["python", "-m", "unittest", str(test_path), "-v"],
                    capture_output=True, text=True, timeout=30
                )
                results.append({
                    "file": test_file,
                    "passed": result.returncode == 0,
                    "output": result.stdout if result.returncode == 0 else result.stderr,
                })
            except Exception as e:
                results.append({"file": test_file, "passed": False, "output": str(e)})

        all_passed = all(r["passed"] for r in results)
        return {"passed": all_passed, "details": results}
