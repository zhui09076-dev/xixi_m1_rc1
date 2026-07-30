"""测试权限网关"""
import unittest
import tempfile
import os
from core.database import Database
from core.permission_gateway import PermissionGateway, ActionRequest, PermissionCategory


class TestPermissionGateway(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        self.pg = PermissionGateway(self.db, authorized_paths=["assets", "data", "temp"])

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_public_web_allowed(self):
        req = ActionRequest(
            action_id="a1", action_type="web_search", target="https://example.com",
            scope="public", data_category="public_info", risk_level="low",
            requested_by="xixi", reason="搜索", created_at=""
        )
        result = self.pg.request_permission(req)
        self.assertTrue(result.allowed)
        self.assertEqual(result.category, PermissionCategory.ORDINARY.value)
        self.assertFalse(result.requires_confirm)

    def test_authorized_path_allowed(self):
        req = ActionRequest(
            action_id="a2", action_type="read", target="assets/test.txt",
            scope="local", data_category="asset", risk_level="low",
            requested_by="xixi", reason="读取", created_at=""
        )
        result = self.pg.request_permission(req)
        self.assertTrue(result.allowed)
        self.assertEqual(result.category, PermissionCategory.SCOPED.value)

    def test_private_outbound_needs_confirm(self):
        req = ActionRequest(
            action_id="a3", action_type="upload", target="https://api.example.com",
            scope="outbound", data_category="personal_info", risk_level="high",
            requested_by="xixi", reason="上传私人数据", created_at=""
        )
        result = self.pg.request_permission(req)
        self.assertFalse(result.allowed)
        self.assertTrue(result.requires_confirm)
        self.assertEqual(result.category, PermissionCategory.OUTBOUND_PRIVATE.value)

    def test_irreversible_needs_confirm(self):
        req = ActionRequest(
            action_id="a4", action_type="delete_permanent", target="data/file.txt",
            scope="local", data_category="user_data", risk_level="critical",
            requested_by="xixi", reason="删除", created_at=""
        )
        result = self.pg.request_permission(req)
        self.assertFalse(result.allowed)
        self.assertTrue(result.requires_confirm)
        self.assertEqual(result.category, PermissionCategory.IRREVERSIBLE.value)

    def test_real_path_resolution(self):
        """测试真实父子目录关系，非字符串包含"""
        req = ActionRequest(
            action_id="a5", action_type="read", target="assets_fake/test.txt",
            scope="local", data_category="asset", risk_level="low",
            requested_by="xixi", reason="读取", created_at=""
        )
        result = self.pg.request_permission(req)
        self.assertFalse(result.allowed)


if __name__ == "__main__":
    unittest.main()
