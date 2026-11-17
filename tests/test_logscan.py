"""日志分析工具测试。"""

import argparse
import os
import tempfile
import unittest

from tool.logscan import apply_filters, parse_line, read_records, summarize

SAMPLE = """2026-11-17 10:00:01 | INFO    | api | GET /health -> 200 (1ms)
2026-11-17 10:00:02 | INFO    | api | POST /api/scores -> 200 (8ms)
2026-11-17 10:00:03 | WARNING | api | POST /api/scores -> 400 (3ms)
2026-11-17 10:00:04 | ERROR   | api | GET /api/stats/course/CS101 -> 500 (152ms)
"""


class LogScanTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "app.log")
        with open(self.path, "w", encoding="utf-8") as fp:
            fp.write(SAMPLE)

    def tearDown(self):
        self.temp_dir.cleanup()

    def args(self, **kwargs):
        defaults = {"level": None, "status": None, "path": None, "min_ms": None, "grep": None}
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_parse_line_extracts_request_fields(self):
        record = parse_line(SAMPLE.splitlines()[1])
        self.assertEqual(record["level"], "INFO")
        self.assertEqual(record["method"], "POST")
        self.assertEqual(record["status"], 200)
        self.assertEqual(record["ms"], 8)

    def test_filter_by_level_and_status(self):
        records = read_records(self.path)
        self.assertEqual(len(apply_filters(records, self.args(level="ERROR"))), 1)
        self.assertEqual(len(apply_filters(records, self.args(status="4xx"))), 1)

    def test_summary_counts(self):
        stats = summarize(read_records(self.path), slow_ms=100)
        self.assertEqual(stats["requests"], 4)
        self.assertEqual(stats["levels"]["WARNING"], 1)
        self.assertEqual(stats["statuses"]["2xx"], 2)
        self.assertEqual(stats["slow_requests"], 1)

    def test_min_ms_filter(self):
        records = read_records(self.path)
        matched = apply_filters(records, self.args(min_ms=100))
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["status"], 500)


if __name__ == "__main__":
    unittest.main()
