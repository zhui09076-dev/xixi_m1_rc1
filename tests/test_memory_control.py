"""测试记忆系统"""
import unittest
import tempfile
import os
from core.database import Database
from core.memory import MemorySystem


class TestMemorySystem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        self.mem = MemorySystem(self.db)

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_create_and_query(self):
        eid = self.mem.create("测试内容", source_type="user_quote", scope="session")
        self.assertTrue(eid)
        results = self.mem.query(scope="session")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["content"], "测试内容")

    def test_supersede(self):
        old_id = self.mem.create("旧内容")
        new_id = self.mem.supersede(old_id, "新内容", reason="纠正")
        self.assertTrue(new_id)
        old = self.mem.get_by_id(old_id)
        self.assertEqual(old["status"], "superseded")

    def test_delete_soft(self):
        eid = self.mem.create("待删除")
        self.assertTrue(self.mem.delete(eid, permanent=False))
        result = self.mem.get_by_id(eid)
        self.assertEqual(result["status"], "deleted")

    def test_delete_permanent(self):
        eid = self.mem.create("永久删除")
        self.assertTrue(self.mem.delete(eid, permanent=True))
        result = self.mem.get_by_id(eid)
        self.assertIsNone(result)

    def test_add_chat(self):
        self.mem.add_chat("user", "你好")
        self.mem.add_chat("xixi", "你好呀")
        recent = self.mem.get_recent_chat(limit=2)
        self.assertEqual(len(recent), 2)


if __name__ == "__main__":
    unittest.main()
