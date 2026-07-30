"""测试容器加载"""
import unittest
import tempfile
import os
import sys
from pathlib import Path

# 确保能找到项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import Database
from core.config import Config


class TestContainerLoading(unittest.TestCase):
    def test_config_load(self):
        c = Config.load("config.yaml")
        self.assertIsNotNone(c)
        self.assertIn("window", c.to_dict())

    def test_database_init(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        db = Database(tmp.name)
        self.assertIsNotNone(db)
        db.close()
        os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
