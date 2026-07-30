"""示例扩展测试"""
import unittest


class MockContainer:
    pass


class TestExampleExtension(unittest.TestCase):
    def test_greet(self):
        from extensions.example_extension.main import ExampleExtension
        ext = ExampleExtension(MockContainer())
        result = ext.greet("用户")
        self.assertIn("用户", result)


if __name__ == "__main__":
    unittest.main()
