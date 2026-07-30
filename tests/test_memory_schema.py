"""测试记忆模式"""
import unittest
import tempfile
import os
from core.database import Database
from core.memory import MemorySystem


class TestMemorySchema(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        self.mem = MemorySystem(self.db)

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_memory_entry_structure(self):
        eid = self.mem.create("内容", source_type="user_quote", scope="session",
                              project_id="p1", retention="long_term", confidence=0.9)
        entry = self.mem.get_by_id(eid)
        self.assertEqual(entry["content"], "内容")
        self.assertEqual(entry["scope"], "session")
        self.assertEqual(entry["retention"], "long_term")
        self.assertEqual(entry["confidence"], 0.9)

    def test_query_by_scope(self):
        self.mem.create("会话记忆", scope="session")
        self.mem.create("长期记忆", scope="user")
        session_mem = self.mem.query(scope="session")
        self.assertEqual(len(session_mem), 1)
        self.assertEqual(session_mem[0]["content"], "会话记忆")


if __name__ == "__main__":
    unittest.main()
