import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.intent_classifier import IntentClassifier, IntentType


class TestIntentProtocol(unittest.TestCase):
    def setUp(self):
        self.clf = IntentClassifier()

    def test_interruption_keywords(self):
        r = self.clf.classify("停下")
        self.assertEqual(r.intent, IntentType.INTERRUPTION)

    def test_power_outage_not_interruption(self):
        r = self.clf.classify("我家停电了")
        self.assertNotEqual(r.intent, IntentType.INTERRUPTION)

    def test_advice_priority(self):
        r = self.clf.classify("你觉得怎么办")
        self.assertEqual(r.intent, IntentType.ADVICE)

    def test_output_fields(self):
        r = self.clf.classify("测试")
        self.assertIsNotNone(r.confidence)
        self.assertIsNotNone(r.matched_rule)
        self.assertIsNotNone(r.created_at)

    def test_eight_intents(self):
        intents = [IntentType.EXPRESSION, IntentType.UNDERSTANDING,
                   IntentType.QUESTION, IntentType.ADVICE,
                   IntentType.DECISION, IntentType.INSTRUCTION,
                   IntentType.CORRECTION, IntentType.INTERRUPTION]
        self.assertEqual(len(intents), 8)


if __name__ == "__main__":
    unittest.main()
