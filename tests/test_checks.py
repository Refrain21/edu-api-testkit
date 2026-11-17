"""SQL 校验函数测试：确认校验项能发现不一致数据。"""

import os
import sqlite3
import tempfile
import unittest

from data.generate_data import seed_database
from tool.checks import REGISTRY


class ChecksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = os.path.join(cls.temp_dir.name, "checks.db")
        seed_database(cls.db_path, seed=42)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def setUp(self):
        self.conn = sqlite3.connect(self.db_path)

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def test_seed_data_passes_all_invariants(self):
        for name in (
            "orphan_scores",
            "score_out_of_range",
            "duplicate_scores",
            "warning_orphan",
            "warning_rule_mismatch",
            "fk_violations",
        ):
            with self.subTest(check=name):
                self.assertEqual(REGISTRY[name](self.conn), 0)

    def test_course_stats_matches_direct_query(self):
        total, avg = self.conn.execute(
            "SELECT COUNT(*), ROUND(AVG(score), 2) FROM scores "
            "WHERE course_id = (SELECT id FROM courses WHERE course_code = 'CS101') "
            "AND term = '2025-2026-1' AND status = 'normal' AND score IS NOT NULL"
        ).fetchone()
        stats = REGISTRY["course_stats"](self.conn, course_code="CS101", term="2025-2026-1")
        self.assertEqual(stats["total"], total)
        self.assertEqual(stats["avg"], avg)

    def test_deleted_warning_is_detected(self):
        self.conn.execute("DELETE FROM warnings WHERE id = (SELECT MIN(id) FROM warnings)")
        self.assertGreater(REGISTRY["warning_rule_mismatch"](self.conn), 0)

    def test_duplicate_score_is_detected(self):
        # 正式表有 UNIQUE 约束，这里用同结构但不带约束的内存表验证校验 SQL 本身有效
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE scores (student_id INTEGER, course_id INTEGER, term TEXT, "
            "score REAL, status TEXT)"
        )
        for _ in range(2):
            conn.execute(
                "INSERT INTO scores (student_id, course_id, term, score, status) "
                "VALUES (1, 1, '2025-2026-1', 80, 'normal')"
            )
        self.assertEqual(REGISTRY["duplicate_scores"](conn), 1)
        conn.close()


if __name__ == "__main__":
    unittest.main()
