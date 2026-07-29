import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Database
from core.memory import MemorySystem


class TestMemoryControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database("data/test_control.db")
        cls.memory = MemorySystem(cls.db)

    def test_remember_command(self):
        result = self.memory.handle_memory_command("记住这件事：我喜欢蓝色")
        self.assertIn("已记住", result)

    def test_forget_requires_clarification(self):
        result = self.memory.handle_memory_command("忘掉刚才那段")
        self.assertIn("请确认范围", result)

    def test_purge_requires_target(self):
        result = self.memory.handle_memory_command("彻底删除")
        self.assertIn("请指定", result)

    def test_correction_creates_supersedes(self):
        old_id = self.memory.add_long_term("旧信息")
        new_id = self.memory.correct_memory(old_id, "新信息", "用户纠正")
        self.assertNotEqual(old_id, new_id)
        row = self.db.execute("SELECT status FROM memory_entries WHERE id = ?", (old_id,)).fetchone()
        self.assertEqual(row["status"], "superseded")

    def test_preserve_original_setting(self):
        result = self.memory.handle_memory_command("保留我的原话")
        self.assertIn("已设置", result)


if __name__ == "__main__":
    unittest.main()
