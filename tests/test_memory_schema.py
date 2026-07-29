import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Database, SCHEMA_VERSION


class TestMemorySchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database("data/test_schema.db")

    def test_schema_version(self):
        c = self.db.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
        self.assertEqual(c[0], SCHEMA_VERSION)

    def test_memory_entry_fields(self):
        self.db.add_memory_entry({
            "id": "test-001", "content": "测试", "source_type": "user_quote",
            "scope": "session", "confidence": 0.9, "retention": "session",
            "status": "active", "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00"
        })
        row = self.db.execute("SELECT * FROM memory_entries WHERE id = 'test-001'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["content"], "测试")

    def test_supersedes_field(self):
        c = self.db.execute("PRAGMA table_info(memory_entries)").fetchall()
        fields = [r["name"] for r in c]
        self.assertIn("supersedes", fields)
        self.assertIn("status", fields)
        self.assertIn("metadata", fields)

    def test_sandbox_not_auto_upgrade(self):
        from core.memory import MemorySystem
        mem = MemorySystem(self.db)
        eid = mem.add_sandbox("临时推测")
        row = self.db.execute("SELECT scope, confidence FROM memory_entries WHERE id = ?", (eid,)).fetchone()
        self.assertEqual(row["scope"], "private_sandbox")
        self.assertLess(row["confidence"], 0.6)


if __name__ == "__main__":
    unittest.main()
