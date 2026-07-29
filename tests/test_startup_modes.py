import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import BootMode


class TestStartupModes(unittest.TestCase):
    def test_three_modes(self):
        self.assertEqual(len(BootMode), 3)
        self.assertIn(BootMode.RECONNECT, BootMode)
        self.assertIn(BootMode.RESTORE, BootMode)
        self.assertIn(BootMode.COLD_START, BootMode)


if __name__ == "__main__":
    unittest.main()
