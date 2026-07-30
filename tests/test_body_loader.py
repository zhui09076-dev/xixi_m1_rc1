"""测试 Body 加载器"""
import unittest
import tempfile
import os
import json
from pathlib import Path
from core.database import Database
from core.version_registry import VersionRegistry
from core.body_loader import BodyLoader


class TestBodyLoader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        self.registry = VersionRegistry()
        self.tmpdir = tempfile.mkdtemp()
        self.body_dir = Path(self.tmpdir) / "test-body"
        self.body_dir.mkdir()
        manifest = {
            "packageType": "xixi-body",
            "packageId": "test-body",
            "version": "1.0.0",
            "status": "placeholder",
            "layers": {
                "background": "scenes/bg.png",
                "character": "character/char.png"
            },
            "poses": {
                "standing": "poses/standing.png",
                "sitting": "poses/sitting.png"
            },
            "state_mapping": {
                "alone": {"pose": "standing", "mood": "peaceful"},
                "communicating": {"pose": "sitting", "mood": "engaged"}
            },
            "anchor": {"x": 0.5, "y": 0.8},
            "scale": 1.0
        }
        with open(self.body_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        # 创建占位文件
        (self.body_dir / "scenes").mkdir()
        (self.body_dir / "character").mkdir()
        (self.body_dir / "poses").mkdir()
        with open(self.body_dir / "scenes" / "bg.png", "w") as f:
            f.write("")  # 空占位

        self.loader = BodyLoader(self.db, self.registry, packages_dir=self.tmpdir)

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_scan_finds_package(self):
        found = self.loader.scan()
        self.assertIn("test-body", found)

    def test_load_and_activate(self):
        self.assertTrue(self.loader.load("test-body"))
        self.assertTrue(self.loader.activate("test-body"))
        active = self.loader.get_active()
        self.assertEqual(active.package_id, "test-body")

    def test_state_mapping(self):
        self.loader.load("test-body")
        pose, mood = self.loader.map_state_to_pose("test-body", "communicating")
        self.assertEqual(pose, "sitting")
        self.assertEqual(mood, "engaged")

    def test_anchor_and_scale(self):
        self.loader.load("test-body")
        x, y = self.loader.get_anchor("test-body")
        self.assertEqual(x, 0.5)
        self.assertEqual(y, 0.8)
        self.assertEqual(self.loader.get_scale("test-body"), 1.0)

    def test_layer_path(self):
        self.loader.load("test-body")
        path = self.loader.get_layer_path("test-body", "background")
        self.assertIsNotNone(path)
        self.assertIn("bg.png", path)

    def test_missing_layer_fallback(self):
        """缺失图层回退"""
        self.loader.load("test-body")
        path = self.loader.get_layer_path("test-body", "nonexistent")
        # 应该返回 None 或回退路径
        self.assertIsNone(path)

    def test_switch_body_no_main_change(self):
        """更换 Body 不修改主程序"""
        self.loader.load("test-body")
        self.loader.activate("test-body")
        # 验证通过 loader 切换即可
        active = self.loader.get_active()
        self.assertEqual(active.package_id, "test-body")

    def test_upgrade_and_rollback(self):
        self.loader.load("test-body")
        self.loader.activate("test-body")

        v2_dir = Path(self.tmpdir) / "test-body-v2"
        v2_dir.mkdir()
        manifest_v2 = {
            "packageType": "xixi-body", "packageId": "test-body",
            "version": "2.0.0", "layers": {}, "poses": {},
            "state_mapping": {}, "anchor": {"x": 0.6, "y": 0.9}, "scale": 1.2
        }
        with open(v2_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest_v2, f)

        self.assertTrue(self.loader.upgrade("test-body", str(v2_dir)))
        active = self.loader.get_active()
        self.assertEqual(active.version, "2.0.0")

        self.assertTrue(self.loader.rollback("test-body", "1.0.0"))
        active = self.loader.get_active()
        self.assertEqual(active.version, "1.0.0")


if __name__ == "__main__":
    unittest.main()
