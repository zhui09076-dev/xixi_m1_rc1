"""测试 Ollama 降级模式"""
import unittest
from core.llm import LLMEngine


class TestOllamaDegraded(unittest.TestCase):
    def test_offline_reason(self):
        llm = LLMEngine()
        self.assertFalse(llm.is_available())
        self.assertEqual(llm.get_offline_reason(), "")  # 初始未检查，为空

    def test_config_all_parameterized(self):
        llm = LLMEngine()
        keys = ["host", "model", "timeout", "context_length", "num_gpu",
                "num_thread", "temperature", "top_p", "top_k", "repeat_penalty", "keep_alive"]
        for k in keys:
            self.assertIn(k, llm.config)

    def test_abort_synchronous_safe(self):
        """abort 在同步上下文不崩溃"""
        llm = LLMEngine()
        try:
            llm.abort()
        except Exception as e:
            self.fail(f"abort() 在同步上下文抛异常: {e}")


if __name__ == "__main__":
    unittest.main()
