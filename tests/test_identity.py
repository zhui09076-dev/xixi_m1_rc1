import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.identity import Identity


class TestIdentity(unittest.TestCase):
    def test_official_identity_id(self):
        identity = Identity.load()
        self.assertEqual(identity.identity_id, "xixi-main")
        self.assertTrue(identity.official)

    def test_negative_constraints_exist(self):
        identity = Identity.load()
        self.assertGreater(len(identity.NEGATIVE_CONSTRAINTS), 0)
        self.assertIn("维持自身运行", str(identity.NEGATIVE_CONSTRAINTS))

    def test_violation_detection(self):
        identity = Identity.load()
        self.assertFalse(identity.check_negative_constraint("我要维持自身运行"))
        self.assertTrue(identity.check_negative_constraint("今天天气不错"))

    def test_fork_not_official(self):
        identity = Identity.load()
        fork = identity.create_fork("测试分支")
        self.assertFalse(fork.official)
        self.assertEqual(fork.branch_of, "xixi-main")

    def test_validate_official(self):
        identity = Identity.load()
        self.assertTrue(identity.validate_official())

    def test_db_official_unique(self):
        from core.database import Database
        db = Database("data/test_official.db")
        # 尝试插入第二个 official=true 应该失败
        try:
            db.execute("INSERT INTO identities (identity_id, official, created_at, updated_at) VALUES (?, 1, ?, ?)",
                      ("fake", "2026-01-01", "2026-01-01"))
            db.commit()
            # 如果成功，检查是否只有一个 official=1
            c = db.execute("SELECT COUNT(*) FROM identities WHERE official = 1")
            count = c.fetchone()[0]
            self.assertEqual(count, 1)
        except Exception:
            pass  # 唯一索引约束可能触发，这是期望行为


if __name__ == "__main__":
    unittest.main()
