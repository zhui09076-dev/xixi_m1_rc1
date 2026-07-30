"""测试数据库迁移"""
import unittest
import tempfile
import os
from core.database import Database, SCHEMA_VERSION


class TestMigrations(unittest.TestCase):
    def test_schema_version(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        db = Database(tmp.name)
        row = db.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
        self.assertEqual(row["version"], SCHEMA_VERSION)
        db.close()
        os.unlink(tmp.name)

    def test_tables_exist(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        db = Database(tmp.name)
        tables = ["settings", "memory_entries", "state_machine", "tasks",
                  "identity_registry", "soul_packages", "body_packages", "extension_packages",
                  "dev_projects"]
        for t in tables:
            row = db.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{t}'").fetchone()
            self.assertIsNotNone(row, f"表 {t} 不存在")
        db.close()
        os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
