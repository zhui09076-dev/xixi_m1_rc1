import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import XiXiState, StateMachine, BootMode


class TestStateMachine(unittest.TestCase):
    def test_eight_states(self):
        self.assertEqual(len(XiXiState), 8)

    def test_state_persistence(self):
        sm = StateMachine(XiXiState.ALONE, BootMode.COLD_START)
        sm.set_emotion("happy")
        sm.set_attention("user", "u1", 0.8)
        d = sm.to_dict()
        restored = StateMachine.from_dict(d)
        self.assertEqual(restored.snapshot.emotion, "happy")
        self.assertEqual(restored.snapshot.attention["target"], "user")
        self.assertEqual(restored.snapshot.boot_mode, "cold_start")

    def test_transition(self):
        sm = StateMachine(XiXiState.ALONE)
        result = sm.transition(XiXiState.COMMUNICATING, "开始交流")
        self.assertEqual(result["from"], "alone")
        self.assertEqual(result["to"], "communicating")

    def test_idle_timeout(self):
        sm = StateMachine(XiXiState.COMMUNICATING)
        result = sm.on_idle(5)
        self.assertEqual(result["to"], "accompanying")


if __name__ == "__main__":
    unittest.main()
