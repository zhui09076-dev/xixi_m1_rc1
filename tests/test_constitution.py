"""测试人格宪法"""
import unittest
from core.constitution import PersonalityConstitution


class TestConstitution(unittest.TestCase):
    def test_default_system_prompt(self):
        c = PersonalityConstitution(name="西西")
        prompt = c.to_system_prompt()
        self.assertIn("西西", prompt)

    def test_from_soul_package(self):
        soul_data = {
            "identity": {"name": "测试灵魂"},
            "version": "1.0.0",
            "constitution": {
                "negative_constraints": ["不能伤害用户"],
                "system_prompt_base": "你是测试灵魂。"
            }
        }
        c = PersonalityConstitution.from_soul_package(soul_data)
        self.assertEqual(c.name, "测试灵魂")
        self.assertIn("不能伤害用户", c.negative_constraints)


if __name__ == "__main__":
    unittest.main()
