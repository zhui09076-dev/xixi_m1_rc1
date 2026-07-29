import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Database, SCHEMA_VERSION
from core.version_registry import VersionRegistry


class TestMigrations(unittest.TestCase):
    def test_schema_version_is_3(self):
        self.assertEqual(SCHEMA_VERSION, 3)

    def test_version_registry_persistence(self):
        db = Database("data/test_mig.db")
        vr = VersionRegistry.load()
        db.save_version_registry(vr.to_dict())
        loaded = db.get_version_registry()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["core"], "1.0.0")

    def test_identity_table_exists(self):
        db = Database("data/test_mig2.db")
        c = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='identities'").fetchone()
        self.assertIsNotNone(c)


if __name__ == "__main__":
    unittest.main()
