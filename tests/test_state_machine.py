"""测试状态机持久化"""
import unittest
import tempfile
import os
from core.database import Database
from core.state import StateMachine, XiXiState, BootMode


class TestStatePersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_save_and_load_state(self):
        sm = StateMachine(initial_state=XiXiState.COMMUNICATING, boot_mode=BootMode.RESTORE)
        sm.set_emotion("happy")
        sm.set_attention("user", intensity=0.8)

        # 保存到数据库
        self.db.save_state(sm.to_dict())

        # 从数据库加载
        loaded = self.db.load_state()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["state"], "communicating")
        self.assertEqual(loaded["snapshot"]["emotion"], "happy")
        self.assertEqual(loaded["snapshot"]["attention"]["target"], "user")

    def test_state_machine_from_dict(self):
        sm = StateMachine(initial_state=XiXiState.ALONE)
        sm.transition(XiXiState.THINKING, "用户提问")
        d = sm.to_dict()

        sm2 = StateMachine.from_dict(d)
        self.assertEqual(sm2.state, XiXiState.THINKING)
        self.assertEqual(sm2.snapshot.previous_state, "alone")


if __name__ == "__main__":
    unittest.main()
