"""数据库校验（等价于 SQL 数据校验用例）。

每个函数返回一个标量或字典，执行器会把返回值与用例中声明的 expect 做比较。
覆盖多表联查、聚合函数、子查询、CASE WHEN、GROUP BY + HAVING 等常用 SQL 能力，
对应岗位要求中的"掌握常用 SQL 语句，能独立完成数据校验"。
"""

REGISTRY = {}


def db_check(name):
    """把函数注册为可在用例 JSON 中引用的校验项。"""

    def decorator(func):
        REGISTRY[name] = func
        return func

    return decorator


def _scalar(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return None if row is None else row[0]


@db_check("score_of")
def score_of(conn, student_no, course_code, term):
    """多表联查：读取指定学生/课程/学期的成绩，用于验证接口写入是否真正落库。"""
    return _scalar(
        conn,
        "SELECT s.score FROM scores s "
        "JOIN students st ON st.id = s.student_id "
        "JOIN courses c ON c.id = s.course_id "
        "WHERE st.student_no = ? AND c.course_code = ? AND s.term = ?",
        (student_no, course_code, term),
    )


@db_check("score_status")
def score_status(conn, student_no, course_code, term):
    """多表联查：读取成绩记录的状态（normal/absent/exempt）。"""
    return _scalar(
        conn,
        "SELECT s.status FROM scores s "
        "JOIN students st ON st.id = s.student_id "
        "JOIN courses c ON c.id = s.course_id "
        "WHERE st.student_no = ? AND c.course_code = ? AND s.term = ?",
        (student_no, course_code, term),
    )


@db_check("score_rows")
def score_rows(conn, student_no, course_code, term):
    """聚合：统计同一学生/课程/学期的记录条数，验证唯一约束与重复提交处理。"""
    return _scalar(
        conn,
        "SELECT COUNT(*) FROM scores s "
        "JOIN students st ON st.id = s.student_id "
        "JOIN courses c ON c.id = s.course_id "
        "WHERE st.student_no = ? AND c.course_code = ? AND s.term = ?",
        (student_no, course_code, term),
    )


@db_check("warning_level")
def warning_level(conn, student_no, term):
    """子查询：按学号取预警等级，验证规则引擎结果。"""
    return _scalar(
        conn,
        "SELECT level FROM warnings "
        "WHERE student_id = (SELECT id FROM students WHERE student_no = ?) AND term = ?",
        (student_no, term),
    )


@db_check("warning_count")
def warning_count(conn, student_no, term):
    """聚合：预警条数，验证重算时不会产生重复预警。"""
    return _scalar(
        conn,
        "SELECT COUNT(*) FROM warnings "
        "WHERE student_id = (SELECT id FROM students WHERE student_no = ?) AND term = ?",
        (student_no, term),
    )


@db_check("course_stats")
def course_stats(conn, course_code, term):
    """聚合 + CASE WHEN：独立重算课程统计，用于和接口返回值交叉验证。"""
    row = conn.execute(
        "SELECT COUNT(*) AS total, ROUND(AVG(score), 2) AS avg, "
        "MAX(score) AS max, MIN(score) AS min, "
        "SUM(CASE WHEN score >= 60 THEN 1 ELSE 0 END) AS passed "
        "FROM scores "
        "WHERE course_id = (SELECT id FROM courses WHERE course_code = ?) "
        "AND term = ? AND status = 'normal' AND score IS NOT NULL",
        (course_code, term),
    ).fetchone()
    total = row[0] or 0
    passed = row[4] or 0
    return {
        "total": total,
        "avg": row[1],
        "max": row[2],
        "min": row[3],
        "pass_rate": round(passed / total, 4) if total else None,
    }


@db_check("profile_overview")
def profile_overview(conn, student_no):
    """聚合：学生整体成绩概览。"""
    row = conn.execute(
        "SELECT COUNT(*) AS total, ROUND(AVG(score), 2) AS avg, "
        "SUM(CASE WHEN score < 60 THEN 1 ELSE 0 END) AS failed "
        "FROM scores "
        "WHERE student_id = (SELECT id FROM students WHERE student_no = ?) "
        "AND status = 'normal' AND score IS NOT NULL",
        (student_no,),
    ).fetchone()
    return {"total": row[0] or 0, "avg": row[1] or 0, "failed": row[2] or 0}


# ---------------------------------------------------------------------------
# 全库不变量校验：正常应恒为 0，用于发现跨接口操作后的数据一致性问题
# ---------------------------------------------------------------------------


@db_check("orphan_scores")
def orphan_scores(conn):
    """多表联查：成绩表是否存在找不到学生或课程的孤儿记录。"""
    return _scalar(
        conn,
        "SELECT COUNT(*) FROM scores s "
        "LEFT JOIN students st ON st.id = s.student_id "
        "LEFT JOIN courses c ON c.id = s.course_id "
        "WHERE st.id IS NULL OR c.id IS NULL",
    )


@db_check("score_out_of_range")
def score_out_of_range(conn):
    """边界校验：库中是否存在超出 0-100 的成绩。"""
    return _scalar(
        conn,
        "SELECT COUNT(*) FROM scores WHERE score IS NOT NULL AND (score < 0 OR score > 100)",
    )


@db_check("duplicate_scores")
def duplicate_scores(conn):
    """GROUP BY + HAVING：是否存在同一学生同一课程同一学期的重复成绩。"""
    return _scalar(
        conn,
        "SELECT COUNT(*) FROM ("
        "  SELECT student_id, course_id, term FROM scores "
        "  GROUP BY student_id, course_id, term HAVING COUNT(*) > 1"
        ")",
    )


@db_check("warning_orphan")
def warning_orphan(conn):
    """多表联查：预警表是否存在孤儿记录。"""
    return _scalar(
        conn,
        "SELECT COUNT(*) FROM warnings w "
        "LEFT JOIN students st ON st.id = w.student_id "
        "WHERE st.id IS NULL",
    )


@db_check("warning_rule_mismatch")
def warning_rule_mismatch(conn):
    """子查询 + CASE WHEN：用 SQL 重算预警规则，与 warnings 表逐条比对。

    不一致的情况有两种：等级算错 / 该清理的预警没清理 / 多余的预警记录。
    """
    return _scalar(
        conn,
        "WITH agg AS ("
        "  SELECT student_id, term, COUNT(*) AS total,"
        "         SUM(CASE WHEN score < 60 THEN 1 ELSE 0 END) AS failed,"
        "         AVG(score) AS avg_score"
        "  FROM scores WHERE status = 'normal' AND score IS NOT NULL"
        "  GROUP BY student_id, term"
        "), expected AS ("
        "  SELECT student_id, term,"
        "         CASE WHEN failed >= 2 THEN 'high'"
        "              WHEN avg_score < 65 THEN 'medium'"
        "              ELSE NULL END AS level"
        "  FROM agg"
        ") "
        "SELECT COUNT(*) FROM ("
        "  SELECT e.student_id FROM expected e "
        "  LEFT JOIN warnings w ON w.student_id = e.student_id AND w.term = e.term "
        "  WHERE COALESCE(e.level, 'none') <> COALESCE(w.level, 'none') "
        "  UNION ALL "
        "  SELECT w.student_id FROM warnings w "
        "  LEFT JOIN expected e ON e.student_id = w.student_id AND e.term = w.term "
        "  WHERE e.student_id IS NULL"
        ")",
    )


@db_check("fk_violations")
def fk_violations(conn):
    """PRAGMA foreign_key_check：数据库层面的外键完整性检查。"""
    return len(conn.execute("PRAGMA foreign_key_check").fetchall())
