"""测试资产清单"""
import unittest
import tempfile
import json
import os
from core.asset_manager import AssetManager


class TestAssetManifest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manifest_path = os.path.join(self.tmpdir, "manifest.json")

    def tearDown(self):
        if os.path.exists(self.manifest_path):
            os.unlink(self.manifest_path)
        os.rmdir(self.tmpdir)

    def test_create_default_manifest(self):
        am = AssetManager(self.manifest_path)
        self.assertEqual(am._manifest["version"], "1.0.0")

    def test_register_and_get(self):
        am = AssetManager(self.manifest_path)
        am.register_scene("room", "scenes/room.png")
        self.assertEqual(am.get_scene("room"), "scenes/room.png")


if __name__ == "__main__":
    unittest.main()
