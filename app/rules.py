"""学业预警规则。

规则与测试用例中的 SQL 重算逻辑（tool/checks.py: warning_rule_mismatch）保持一致：
- 不及格门数 >= 2  -> high（高风险）
- 否则学期平均分 < 65 -> medium（中风险）
- 其余情况不产生预警，且需要清理历史预警
"""

PASS_LINE = 60
HIGH_FAIL_COUNT = 2
MEDIUM_AVG_LINE = 65


def compute_level(valid_scores):
    """根据有效成绩计算预警等级，返回 (level, reason)。"""
    if not valid_scores:
        return None, None
    failed = sum(1 for item in valid_scores if item < PASS_LINE)
    avg = sum(valid_scores) / len(valid_scores)
    if failed >= HIGH_FAIL_COUNT:
        return "high", f"不及格 {failed} 门"
    if avg < MEDIUM_AVG_LINE:
        return "medium", f"学期平均分 {avg:.2f}"
    return None, None


def recalculate_warning(conn, student_id, term):
    """重算某个学生某个学期的预警，返回最新预警（dict 或 None）。

    调用方负责 commit。
    """
    rows = conn.execute(
        "SELECT score FROM scores "
        "WHERE student_id = ? AND term = ? AND status = 'normal' AND score IS NOT NULL",
        (student_id, term),
    ).fetchall()
    level, reason = compute_level([row[0] for row in rows])

    conn.execute(
        "DELETE FROM warnings WHERE student_id = ? AND term = ?", (student_id, term)
    )
    if level is None:
        return None

    conn.execute(
        "INSERT INTO warnings (student_id, term, level, reason) VALUES (?, ?, ?, ?)",
        (student_id, term, level, reason),
    )
    return {"student_id": student_id, "term": term, "level": level, "reason": reason}
