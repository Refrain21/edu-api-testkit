"""预警规则单元测试。"""

import os
import sqlite3
import tempfile
import unittest

from app.rules import compute_level, recalculate_warning
from app.server import init_database


class ComputeLevelTest(unittest.TestCase):
    def test_no_scores_means_no_warning(self):
        self.assertEqual(compute_level([]), (None, None))

    def test_two_failed_courses_is_high(self):
        level, reason = compute_level([59, 58, 90])
        self.assertEqual(level, "high")
        self.assertIn("不及格 2 门", reason)

    def test_average_exactly_65_is_normal(self):
        self.assertEqual(compute_level([65, 65]), (None, None))

    def test_average_below_65_is_medium(self):
        level, reason = compute_level([64, 65])
        self.assertEqual(level, "medium")
        self.assertIn("64.50", reason)


class RecalculateWarningTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        init_database(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute(
            "INSERT INTO students (student_no, name, major, grade_year) VALUES ('S1', '张三', '大数据技术', 2023)"
        )
        for code in ("C1", "C2"):
            self.conn.execute(
                "INSERT INTO courses (course_code, name, credit, teacher) VALUES (?, ?, 3, '教师')",
                (code, f"课程{code}"),
            )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def _insert_score(self, course_code, score):
        self.conn.execute(
            "INSERT INTO scores (student_id, course_id, term, score, status) "
            "SELECT 1, id, '2025-2026-1', ?, 'normal' FROM courses WHERE course_code = ?",
            (score, course_code),
        )

    def test_warning_upgrades_and_is_idempotent(self):
        self._insert_score("C1", 50)
        warning = recalculate_warning(self.conn, 1, "2025-2026-1")
        self.assertEqual(warning["level"], "medium")

        self._insert_score("C2", 40)
        warning = recalculate_warning(self.conn, 1, "2025-2026-1")
        self.assertEqual(warning["level"], "high")

        # 重复调用不会产生多条预警
        recalculate_warning(self.conn, 1, "2025-2026-1")
        count = self.conn.execute("SELECT COUNT(*) FROM warnings").fetchone()[0]
        self.assertEqual(count, 1)

    def test_warning_is_removed_when_scores_become_good(self):
        self._insert_score("C1", 50)
        recalculate_warning(self.conn, 1, "2025-2026-1")
        self.conn.execute("UPDATE scores SET score = 90")
        self.assertIsNone(recalculate_warning(self.conn, 1, "2025-2026-1"))
        count = self.conn.execute("SELECT COUNT(*) FROM warnings").fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
