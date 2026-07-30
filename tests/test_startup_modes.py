"""测试启动模式"""
import unittest
from core.state import StateMachine, BootMode, XiXiState


class TestStartupModes(unittest.TestCase):
    def test_cold_start(self):
        sm = StateMachine(boot_mode=BootMode.COLD_START)
        self.assertEqual(sm.snapshot.boot_mode, "cold_start")

    def test_reconnect(self):
        sm = StateMachine(boot_mode=BootMode.RECONNECT)
        self.assertEqual(sm.snapshot.boot_mode, "reconnect")

    def test_restore(self):
        sm = StateMachine(boot_mode=BootMode.RESTORE)
        self.assertEqual(sm.snapshot.boot_mode, "restore")


if __name__ == "__main__":
    unittest.main()
