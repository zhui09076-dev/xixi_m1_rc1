import tempfile
import unittest
from pathlib import Path

from core.config import Config
from core.database import Database
from core.memory import MemoryManager
from core.permission_gateway import PermissionGateway
from core.protocol_server import MsgType, XixiEnvelope
from core.soul_loader import load_soul_package
from core.task_scheduler import TaskScheduler, TaskWeight


class IntegrationRepairTests(unittest.TestCase):
    def test_config_dot_path(self):
        config = Config.load("config.yaml")
        self.assertEqual(config.get("protocol.port"), 17861)

    def test_new_tables_do_not_collide_with_rc3(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "xixi.db"
            db = Database(str(db_path))
            memory = MemoryManager(str(db_path))
            scheduler = TaskScheduler(str(db_path))
            permissions = PermissionGateway(str(db_path), authorized_paths=[temp_dir])
            memory.add_raw_note("测试", role="user")
            scheduler.submit_task("重任务", weight=TaskWeight.HEAVY)
            names = {
                row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertIn("memory_entries", names)
            self.assertIn("xixi_memory_entries", names)
            self.assertIn("tasks", names)
            self.assertIn("xixi_tasks", names)
            self.assertIn("xixi_permission_requests", names)
            memory.cleanup()
            scheduler.cleanup()
            permissions.cleanup()
            db.close()

    def test_soul_package_checksum(self):
        soul = load_soul_package(
            "supplements/soul/xixi_soul_rc1", verify_checksums=True
        )
        self.assertEqual(soul.package_id, "xixi-soul-main")

    def test_protocol_envelope(self):
        envelope = XixiEnvelope.create(
            MsgType.USER_INPUT, "ui", "container", "ses_test",
            "trc_test", 0, {"text": "你好", "mode": "text"},
        )
        ok, code, message = XixiEnvelope.validate(envelope)
        self.assertTrue(ok, (code, message))


if __name__ == "__main__":
    unittest.main()
