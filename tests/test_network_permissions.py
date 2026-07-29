import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Database
from core.permission_gateway import PermissionGateway, ActionRequest


class TestNetworkPermissions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database("data/test_net.db")
        cls.pg = PermissionGateway(cls.db)

    def test_public_search_allowed(self):
        req = ActionRequest("n1", "", "搜索", "https://duckduckgo.com", "web", "public_web", "low", "xixi", "搜索", "")
        r = self.pg.check(req)
        self.assertTrue(r.allowed)

    def test_private_outbound_rejected(self):
        req = ActionRequest("n2", "", "发送", "https://api.example.com", "web", "private_chat", "high", "xixi", "发送记忆", "")
        r = self.pg.check(req)
        self.assertFalse(r.allowed)
        self.assertIn("私人数据外发", r.reason)

    def test_audit_log_written(self):
        req = ActionRequest("n3", "", "搜索", "https://google.com", "web", "public_web", "low", "xixi", "测试", "")
        self.pg.check(req)
        logs = self.db.get_audit_logs(limit=1)
        self.assertGreaterEqual(len(logs), 1)

    def test_download_not_execute(self):
        req = ActionRequest("n4", "", "下载", "https://example.com/file.exe", "web", "public_web", "low", "xixi", "下载", "")
        r = self.pg.check(req)
        self.assertTrue(r.allowed)  # 下载允许
        # 执行需要额外确认
        req2 = ActionRequest("n5", "", "执行", "file.exe", "local", "executable", "high", "xixi", "运行", "")
        r2 = self.pg.check(req2)
        self.assertFalse(r2.allowed)


if __name__ == "__main__":
    unittest.main()
