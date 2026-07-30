"""测试任务调度器"""
import unittest
import tempfile
import os
from core.database import Database
from core.task_scheduler import TaskScheduler


class TestTaskScheduler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        self.ts = TaskScheduler(self.db)

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_cognitive_task_limit(self):
        """重任务 + 轻任务限制"""
        h1 = self.ts.submit("重任务1", "heavy")
        h2 = self.ts.submit("重任务2", "heavy")
        status = self.ts.get_queue_status()
        self.assertEqual(status["running_heavy"], h1)
        self.assertEqual(status["queued_count"], 1)

    def test_unlimited_types_not_restricted(self):
        """UI/系统/IO 不受限制"""
        u1 = self.ts.submit("UI任务1", "ui")
        u2 = self.ts.submit("UI任务2", "ui")
        s1 = self.ts.submit("系统任务", "system")
        status = self.ts.get_queue_status()
        self.assertTrue(status["can_accept_heavy"])
        self.assertTrue(status["can_accept_light"])

    def test_is_cognitive_task(self):
        self.assertTrue(self.ts.is_cognitive_task("heavy"))
        self.assertTrue(self.ts.is_cognitive_task("light"))
        self.assertFalse(self.ts.is_cognitive_task("ui"))
        self.assertFalse(self.ts.is_cognitive_task("system"))


if __name__ == "__main__":
    unittest.main()
