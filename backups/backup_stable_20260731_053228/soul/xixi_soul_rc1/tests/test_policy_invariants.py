from __future__ import annotations

import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


class PolicyInvariantTests(unittest.TestCase):
    def test_raw_memory_is_immutable(self):
        doc = yaml.safe_load((ROOT / "memory_policy.yaml").read_text(encoding="utf-8"))
        self.assertTrue(doc["memory_policy"]["core_principles"]["raw_content_immutable"])
        self.assertTrue(doc["memory_policy"]["core_principles"]["derived_content_cannot_replace_raw"])

    def test_public_web_default_open_private_outbound_confirmed(self):
        doc = yaml.safe_load((ROOT / "autonomy.yaml").read_text(encoding="utf-8"))
        public_ops = doc["autonomy"]["network"]["ordinary_without_confirmation"]
        confirm_ops = doc["autonomy"]["network"]["explicit_confirmation"]
        self.assertIn("搜索公开网页", public_ops)
        self.assertIn("将私人数据发送到外部服务", confirm_ops)

    def test_attention_is_cognitive_not_system_thread_limit(self):
        doc = yaml.safe_load((ROOT / "autonomy.yaml").read_text(encoding="utf-8"))
        attention = doc["autonomy"]["attention"]
        self.assertEqual(attention["heavy_cognitive_tasks"], 1)
        self.assertIn("database_flush", attention["does_not_limit_background_system_work"])

    def test_interruption_is_semantic(self):
        doc = yaml.safe_load((ROOT / "conversation.yaml").read_text(encoding="utf-8"))
        interrupt = doc["conversation"]["interruption"]
        self.assertIn("我家停电了", interrupt["non_examples"])
        self.assertIn("停下", interrupt["strong_examples"])


if __name__ == "__main__":
    unittest.main()
