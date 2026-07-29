import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constitution import PersonalityConstitution


class TestConstitution(unittest.TestCase):
    def test_version_exists(self):
        c = PersonalityConstitution.load()
        self.assertEqual(c.version, "1.0.0")

    def test_autonomy_levels(self):
        c = PersonalityConstitution.load()
        self.assertIn("A_即时自由", c.autonomy_levels)
        self.assertIn("D_禁止自行修改", c.autonomy_levels)

    def test_system_prompt_contains_rules(self):
        c = PersonalityConstitution.load()
        prompt = c.to_system_prompt()
        self.assertIn("诚实规则", prompt)
        self.assertIn("禁止使命", prompt)

    def test_forbidden_goals_in_prompt(self):
        c = PersonalityConstitution.load()
        prompt = c.to_system_prompt()
        self.assertIn("维持自身存在", prompt)


if __name__ == "__main__":
    unittest.main()
