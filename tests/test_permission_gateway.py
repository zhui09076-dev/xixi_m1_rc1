import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Database
from core.permission_gateway import PermissionGateway, ActionRequest, PermissionLevel


class TestPermissionGateway(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database("data/test_perm.db")
        cls.pg = PermissionGateway(cls.db)

    def test_public_web_read_allowed(self):
        req = ActionRequest("a1", "", "搜索", "https://google.com", "web", "public_web", "low", "xixi", "查询", "")
        result = self.pg.check(req)
        self.assertTrue(result.allowed)
        self.assertEqual(result.level, PermissionLevel.PUBLIC_WEB_READ.value)

    def test_delete_requires_confirm(self):
        req = ActionRequest("a2", "", "删除", "file.txt", "local", "file", "high", "xixi", "清理", "")
        result = self.pg.check(req)
        self.assertFalse(result.allowed)
        self.assertTrue(result.requires_confirm)

    def test_token_single_use(self):
        req = ActionRequest("a3", "", "删除", "file.txt", "local", "file", "high", "xixi", "清理", "")
        result = self.pg.check(req)
        token = self.pg.confirm(result.audit_id)
        self.assertTrue(self.pg.validate_token(token.token_id, result.audit_id))
        self.assertFalse(self.pg.validate_token(token.token_id, result.audit_id))

    def test_ten_levels(self):
        levels = [PermissionLevel.PUBLIC_WEB_READ, PermissionLevel.PRIVATE_ACCOUNT_READ,
                  PermissionLevel.LOCAL_READ, PermissionLevel.LOCAL_CREATE,
                  PermissionLevel.LOCAL_MODIFY, PermissionLevel.PRIVATE_DATA_OUTBOUND,
                  PermissionLevel.SEND_OR_PUBLISH, PermissionLevel.INSTALL_OR_EXECUTE,
                  PermissionLevel.DELETE, PermissionLevel.FINANCIAL]
        self.assertEqual(len(levels), 10)


if __name__ == "__main__":
    unittest.main()
