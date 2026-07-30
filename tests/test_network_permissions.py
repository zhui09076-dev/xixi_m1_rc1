"""测试网络权限"""
import unittest
import tempfile
import os
from core.database import Database
from core.permission_gateway import PermissionGateway, ActionRequest


class TestNetworkPermissions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        self.pg = PermissionGateway(self.db)

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_public_search_no_token(self):
        """普通公开搜索不使用复杂一次性令牌"""
        req = ActionRequest(
            action_id="n1", action_type="web_search", target="https://search.example.com",
            scope="public", data_category="public_info", risk_level="low",
            requested_by="xixi", reason="搜索", created_at=""
        )
        result = self.pg.request_permission(req)
        self.assertTrue(result.allowed)
        self.assertIsNone(result.token)

    def test_high_risk_uses_token(self):
        """高风险操作使用一次性确认"""
        req = ActionRequest(
            action_id="n2", action_type="payment", target="https://pay.example.com",
            scope="outbound", data_category="financial", risk_level="critical",
            requested_by="xixi", reason="付款", created_at=""
        )
        result = self.pg.request_permission(req)
        self.assertFalse(result.allowed)
        self.assertTrue(result.requires_confirm)


if __name__ == "__main__":
    unittest.main()
