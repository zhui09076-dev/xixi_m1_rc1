"""测试 Identity 模块"""
import unittest
import tempfile
import os
from core.database import Database
from core.identity import Identity, IdentityManager


class TestIdentity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_active_identity_id_mechanism(self):
        mgr = IdentityManager(self.db)
        self.assertTrue(mgr.active_identity_id)
        # 切换身份
        id2 = Identity(identity_id="test-id-2", official=False)
        mgr.register_identity(id2)
        self.assertTrue(mgr.switch_identity("test-id-2"))
        self.assertEqual(mgr.active_identity_id, "test-id-2")

    def test_validate_official_not_hardcoded(self):
        id1 = Identity(identity_id="custom-official", official=True)
        self.assertTrue(id1.validate_official())
        self.assertTrue(id1.validate_official({"custom-official"}))
        self.assertFalse(id1.validate_official({"other-id"}))

    def test_no_permanent_hardcoded_string(self):
        mgr = IdentityManager(self.db)
        active = mgr.active_identity_id
        self.assertIsInstance(active, str)
        self.assertNotEqual(active, "xixi-main")  # 不应写死


if __name__ == "__main__":
    unittest.main()
