import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.asset_manager import AssetManager


class TestAssetManifest(unittest.TestCase):
    def test_manifest_loading(self):
        import json
        from pathlib import Path
        Path("assets").mkdir(exist_ok=True)
        manifest = {
            "packages": [{
                "id": "default", "name": "默认资产", "version": "1.0.0",
                "compatible_core": ">=1.0.0",
                "scenes": ["living_room"], "characters": ["standing", "sitting"],
                "manifest_path": "assets/manifest.json"
            }],
            "active_package": "default"
        }
        with open("assets/manifest.json", "w") as f:
            json.dump(manifest, f)

        am = AssetManager()
        pkg = am.get_active()
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.id, "default")


if __name__ == "__main__":
    unittest.main()
