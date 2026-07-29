import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Database
from core.task_scheduler import TaskScheduler


class TestTaskScheduler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database("data/test_task.db")
        cls.scheduler = TaskScheduler(cls.db)

    def test_one_heavy_one_light(self):
        h1 = self.scheduler.submit("重任务1", "heavy")
        h2 = self.scheduler.submit("重任务2", "heavy")
        status = self.scheduler.get_queue_status()
        self.assertIsNotNone(status["running_heavy"])
        self.assertEqual(status["queued_count"], 1)

    def test_requires_confirmation_not_running(self):
        t = self.scheduler.submit("高风险任务", "heavy", requires_confirm=True)
        rows = self.db.execute("SELECT status FROM tasks WHERE id = ?", (t,)).fetchall()
        self.assertEqual(rows[0]["status"], "waiting_confirmation")

    def test_confirm_then_run(self):
        t = self.scheduler.submit("确认后任务", "heavy", requires_confirm=True)
        result = self.scheduler.confirm_task(t)
        self.assertTrue(result)
        rows = self.db.execute("SELECT status FROM tasks WHERE id = ?", (t,)).fetchall()
        self.assertEqual(rows[0]["status"], "queued")


if __name__ == "__main__":
    unittest.main()
