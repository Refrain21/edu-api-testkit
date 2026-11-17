"""接口行为测试：直接使用 Flask 测试客户端，不启动网络服务。"""

import os
import tempfile
import unittest

from app.server import create_app
from data.generate_data import seed_database


class ScoreApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.db_path = os.path.join(cls.temp_dir.name, "api.db")
        seed_database(cls.db_path)
        app = create_app(db_path=cls.db_path, log_path=os.path.join(cls.temp_dir.name, "api.log"))
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def post_score(self, **overrides):
        payload = {
            "student_no": "S2023001",
            "course_code": "CS101",
            "term": "2025-2026-9",
            "status": "normal",
            "score": 80,
        }
        payload.update(overrides)
        return self.client.post("/api/scores", json=payload)

    def test_health(self):
        self.assertEqual(self.client.get("/health").get_json()["status"], "ok")

    def test_boundary_scores_are_accepted(self):
        self.assertEqual(self.post_score(score=0).status_code, 200)
        self.assertEqual(self.post_score(score=100, course_code="CS102").status_code, 200)

    def test_out_of_range_scores_are_rejected(self):
        for value in (-1, 100.5):
            response = self.post_score(score=value)
            self.assertEqual(response.status_code, 400)
            self.assertIn("0-100", response.get_json()["error"])

    def test_absent_with_score_is_rejected(self):
        response = self.post_score(status="absent", score=88)
        self.assertEqual(response.status_code, 400)

    def test_unknown_student_returns_404(self):
        self.assertEqual(self.post_score(student_no="S0000").status_code, 404)

    def test_missing_field_lists_field_name(self):
        response = self.post_score(term=None)
        self.assertEqual(response.status_code, 400)
        self.assertIn("term", response.get_json()["fields"])

    def test_repeat_submission_updates_single_row(self):
        body = {"student_no": "S2023002", "course_code": "CS101", "term": "2025-2026-9", "status": "normal"}
        first = self.client.post("/api/scores", json={**body, "score": 70}).get_json()
        second = self.client.post("/api/scores", json={**body, "score": 90}).get_json()
        self.assertEqual(first["action"], "created")
        self.assertEqual(second["action"], "updated")

        listing = self.client.get(
            "/api/scores", query_string={"student_no": "S2023002", "term": "2025-2026-9"}
        ).get_json()
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["items"][0]["score"], 90)

    def test_wrong_method_returns_405(self):
        self.assertEqual(self.client.put("/api/scores", json={}).status_code, 405)


if __name__ == "__main__":
    unittest.main()
