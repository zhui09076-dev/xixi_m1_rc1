import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm import LLMEngine
from core.constitution import PersonalityConstitution


class TestOllamaDegraded(unittest.TestCase):
    def test_no_mock_reply(self):
        llm = LLMEngine(
            host="http://localhost:99999",
            model="test",
            constitution=PersonalityConstitution()
        )
        self.assertFalse(llm.is_available())

    def test_engine_has_abort(self):
        llm = LLMEngine(constitution=PersonalityConstitution())
        llm.abort()
        self.assertTrue(llm._abort_flag)

    def test_degraded_message(self):
        import asyncio
        llm = LLMEngine(
            host="http://localhost:99999",
            model="test",
            constitution=PersonalityConstitution()
        )
        async def test():
            chunks = []
            async for chunk in llm.chat_stream("测试"):
                chunks.append(chunk)
            result = "".join(chunks)
            self.assertIn("大脑当前不可用", result)
        asyncio.run(test())


if __name__ == "__main__":
    unittest.main()
