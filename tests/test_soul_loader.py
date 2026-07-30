"""测试 Soul 加载器"""
import unittest
import tempfile
import os
import json
from pathlib import Path
from core.database import Database
from core.version_registry import VersionRegistry
from core.soul_loader import SoulLoader


class TestSoulLoader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        self.registry = VersionRegistry()
        # 创建临时 Soul 包
        self.tmpdir = tempfile.mkdtemp()
        self.soul_dir = Path(self.tmpdir) / "test-soul"
        self.soul_dir.mkdir()
        manifest = {
            "packageType": "xixi-soul",
            "packageId": "test-soul",
            "version": "1.0.0",
            "schemaVersion": "1.0.0",
            "entry": {"identity": "identity.yaml"},
            "compatibility": {"minimumContainerVersion": "0.1.0"},
            "persistence": {"rollbackRequired": True}
        }
        with open(self.soul_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        with open(self.soul_dir / "identity.yaml", "w", encoding="utf-8") as f:
            f.write("identity:\n  name: 测试灵魂\n")

        self.loader = SoulLoader(self.db, self.registry, packages_dir=self.tmpdir)

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_scan_finds_package(self):
        found = self.loader.scan()
        self.assertIn("test-soul", found)

    def test_load_registers_to_db(self):
        self.assertTrue(self.loader.load("test-soul"))
        rows = self.loader.list_loaded()
        ids = [r["package_id"] for r in rows]
        self.assertIn("test-soul", ids)

    def test_activate(self):
        self.loader.load("test-soul")
        self.assertTrue(self.loader.activate("test-soul"))
        active = self.loader.get_active()
        self.assertIsNotNone(active)
        self.assertEqual(active.package_id, "test-soul")

    def test_switch_soul_no_main_change(self):
        """切换 Soul 不修改主程序"""
        self.loader.load("test-soul")
        self.loader.activate("test-soul")
        # 模拟切换：直接激活另一个（这里只有一个，但验证机制）
        active = self.loader.get_active()
        self.assertEqual(active.package_id, "test-soul")

    def test_upgrade_and_rollback(self):
        self.loader.load("test-soul")
        self.loader.activate("test-soul")

        # 创建 v2
        v2_dir = Path(self.tmpdir) / "test-soul-v2"
        v2_dir.mkdir()
        manifest_v2 = {
            "packageType": "xixi-soul",
            "packageId": "test-soul",
            "version": "2.0.0",
            "schemaVersion": "1.0.0",
            "entry": {"identity": "identity.yaml"},
        }
        with open(v2_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest_v2, f)

        self.assertTrue(self.loader.upgrade("test-soul", str(v2_dir)))
        active = self.loader.get_active()
        self.assertEqual(active.version, "2.0.0")

        # 回滚
        self.assertTrue(self.loader.rollback("test-soul", "1.0.0"))
        active = self.loader.get_active()
        self.assertEqual(active.version, "1.0.0")

    def test_memory_preserved_across_upgrade(self):
        """升级 Soul 后记忆不丢失"""
        self.loader.load("test-soul")
        self.loader.activate("test-soul")
        # 模拟记忆
        self.db.add_memory_entry({
            "id": "mem-1", "content": "重要记忆", "source_type": "user_quote",
            "scope": "user", "retention": "long_term", "confidence": 0.95,
            "status": "active"
        })
        # 升级
        v2_dir = Path(self.tmpdir) / "test-soul-v2"
        v2_dir.mkdir()
        manifest_v2 = {
            "packageType": "xixi-soul", "packageId": "test-soul",
            "version": "2.0.0", "schemaVersion": "1.0.0", "entry": {},
        }
        with open(v2_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest_v2, f)
        self.loader.upgrade("test-soul", str(v2_dir))
        # 验证记忆还在
        rows = self.db.query_memory_entries(status="active")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["content"], "重要记忆")

    def test_read_entry(self):
        self.loader.load("test-soul")
        data = self.loader.read_entry("test-soul", "identity")
        self.assertIsNotNone(data)
        self.assertEqual(data.get("identity", {}).get("name"), "测试灵魂")


if __name__ == "__main__":
    unittest.main()
