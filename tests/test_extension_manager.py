"""测试扩展管理器"""
import unittest
import tempfile
import os
import json
import shutil
from pathlib import Path
from core.database import Database
from core.version_registry import VersionRegistry
from core.extension_manager import ExtensionManager


class TestExtensionManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        self.registry = VersionRegistry()
        self.tmpdir = tempfile.mkdtemp()
        self.ext_dir = Path(self.tmpdir) / "test-ext"
        self.ext_dir.mkdir()
        self.ext_root = Path(self.tmpdir) / "extensions"
        self.ext_root.mkdir()
        manifest = {
            "packageType": "xixi-extension",
            "packageId": "test-ext",
            "version": "1.0.0",
            "name": "测试扩展",
            "description": "用于测试",
            "entry": "main.py",
            "permissions": ["local_read"],
            "config": {"enabled_by_default": False},
            "tests": ["test_extension.py"]
        }
        with open(self.ext_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        with open(self.ext_dir / "main.py", "w", encoding="utf-8") as f:
            f.write("""
class TestExtension:
    def __init__(self, container):
        self.container = container
    def on_enable(self):
        pass
    def on_disable(self):
        pass
    def greet(self, name):
        return f"Hello {name}"
def create_extension(container):
    return TestExtension(container)
""")
        with open(self.ext_dir / "test_extension.py", "w", encoding="utf-8") as f:
            f.write("""
import unittest
class MockContainer:
    pass
class TestExt(unittest.TestCase):
    def test_greet(self):
        # 简单测试，不依赖外部导入
        self.assertEqual(1, 1)
if __name__ == "__main__":
    unittest.main()
""")

        self.mgr = ExtensionManager(self.db, self.registry, extensions_dir=str(self.ext_root))

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_scan_finds_extension(self):
        self.mgr.install(str(self.ext_dir))
        found = self.mgr.scan()
        self.assertIn("test-ext", found)

    def test_install(self):
        eid = self.mgr.install(str(self.ext_dir))
        self.assertEqual(eid, "test-ext")
        rows = self.mgr.list_extensions()
        ids = [r["package_id"] for r in rows]
        self.assertIn("test-ext", ids)

    def test_enable_and_disable(self):
        self.mgr.install(str(self.ext_dir))
        self.assertTrue(self.mgr.enable("test-ext"))
        self.assertTrue(self.mgr.is_enabled("test-ext"))
        self.assertTrue(self.mgr.disable("test-ext"))
        self.assertFalse(self.mgr.is_enabled("test-ext"))

    def test_upgrade(self):
        self.mgr.install(str(self.ext_dir))
        self.mgr.enable("test-ext")

        v2_dir = Path(self.tmpdir) / "test-ext-v2"
        v2_dir.mkdir()
        manifest_v2 = {
            "packageType": "xixi-extension", "packageId": "test-ext",
            "version": "2.0.0", "name": "测试扩展V2",
            "description": "", "entry": "main.py",
            "permissions": [], "config": {}, "tests": []
        }
        with open(v2_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest_v2, f)
        with open(v2_dir / "main.py", "w", encoding="utf-8") as f:
            f.write("def create_extension(c): return None\n")

        self.assertTrue(self.mgr.upgrade("test-ext", str(v2_dir)))
        manifest = self.mgr.get_manifest("test-ext")
        self.assertEqual(manifest.version, "2.0.0")

    def test_rollback(self):
        self.mgr.install(str(self.ext_dir))
        v2_dir = Path(self.tmpdir) / "test-ext-v2"
        v2_dir.mkdir()
        manifest_v2 = {
            "packageType": "xixi-extension", "packageId": "test-ext",
            "version": "2.0.0", "name": "V2",
            "description": "", "entry": "main.py",
            "permissions": [], "config": {}, "tests": []
        }
        with open(v2_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest_v2, f)
        with open(v2_dir / "main.py", "w", encoding="utf-8") as f:
            f.write("def create_extension(c): return None\n")

        self.mgr.upgrade("test-ext", str(v2_dir))
        self.assertTrue(self.mgr.rollback("test-ext", "1.0.0"))
        manifest = self.mgr.get_manifest("test-ext")
        self.assertEqual(manifest.version, "1.0.0")

    def test_uninstall(self):
        self.mgr.install(str(self.ext_dir))
        self.assertTrue(self.mgr.uninstall("test-ext"))
        rows = self.mgr.list_extensions()
        ids = [r["package_id"] for r in rows]
        self.assertNotIn("test-ext", ids)

    def test_no_core_code_modification(self):
        """新增扩展不要求修改容器核心代码"""
        self.mgr.install(str(self.ext_dir))
        self.mgr.enable("test-ext")
        instance = self.mgr.get_instance("test-ext")
        self.assertIsNotNone(instance)


if __name__ == "__main__":
    unittest.main()
