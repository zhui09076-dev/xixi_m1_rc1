"""测试意图分类器"""
import unittest
from core.intent_classifier import IntentClassifier, IntentType


class TestIntentClassifier(unittest.TestCase):
    def setUp(self):
        self.clf = IntentClassifier()

    def test_returns_none_for_normal_chat(self):
        """普通聊天应返回 None"""
        result = self.clf.classify("今天天气不错")
        self.assertIsNone(result)

    def test_detects_interruption(self):
        result = self.clf.classify("停下")
        self.assertIsNotNone(result)
        self.assertEqual(result.intent, IntentType.INTERRUPTION)

    def test_detects_correction(self):
        result = self.clf.classify("你记错了")
        self.assertIsNotNone(result)
        self.assertEqual(result.intent, IntentType.CORRECTION)

    def test_detects_memory_command(self):
        result = self.clf.classify("记住我的名字")
        self.assertIsNotNone(result)
        self.assertEqual(result.intent, IntentType.MEMORY_COMMAND)


if __name__ == "__main__":
    unittest.main()
