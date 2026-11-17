"""被测系统（SUT）：学生成绩与学业预警服务。

技术栈：Flask + SQLite。对外提供 6 个接口，供自动化测试用例调用：
  POST /api/scores                        成绩录入（含参数校验、唯一约束、预警重算）
  GET  /api/scores                        按学生/学期查询成绩
  GET  /api/stats/course/<course_code>    课程成绩统计（聚合函数）
  GET  /api/students/<student_no>/profile 学生画像（多表联查 + 分组）
  GET  /api/warnings                      预警列表
  GET  /health                            健康检查
"""

import logging
import os
import sqlite3
import time

from flask import Blueprint, Flask, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException

from app.rules import recalculate_warning

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "var", "school.db")
DEFAULT_LOG_PATH = os.path.join(BASE_DIR, "logs", "app.log")

VALID_STATUS = ("normal", "absent", "exempt")
api = Blueprint("api", __name__)


def init_database(db_path):
    """建库建表（幂等），返回数据库文件路径。"""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        with open(SCHEMA_PATH, encoding="utf-8") as fp:
            conn.executescript(fp.read())
        conn.commit()
    finally:
        conn.close()
    return db_path


def setup_logging(log_path):
    """接口访问日志写入文件，格式便于 logscan 与 Linux grep/awk 解析。"""
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    logger = logging.getLogger("api")
    logger.setLevel(logging.INFO)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DB_PATH"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def fail(status, message, **extra):
    payload = {"ok": False, "error": message}
    payload.update(extra)
    return jsonify(payload), status


@api.post("/api/scores")
def upsert_score():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return fail(400, "请求体必须是 JSON 对象")

    missing = [key for key in ("student_no", "course_code", "term", "status") if not payload.get(key)]
    if missing:
        return fail(400, "缺少必填字段", fields=missing)

    status = payload["status"]
    if status not in VALID_STATUS:
        return fail(400, "status 仅支持 normal/absent/exempt")

    score = payload.get("score")
    if status == "normal":
        # bool 是 int 子类，需要显式排除
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            return fail(400, "正常考试时 score 必须为 0-100 的数字")
        if not 0 <= score <= 100:
            return fail(400, "score 超出 0-100 的合法区间")
    elif score not in (None, ""):
        return fail(400, "缺考或免修时 score 必须为空")
    else:
        score = None

    db = get_db()
    student = db.execute(
        "SELECT id FROM students WHERE student_no = ?", (payload["student_no"],)
    ).fetchone()
    if student is None:
        return fail(404, "学生不存在")
    course = db.execute(
        "SELECT id FROM courses WHERE course_code = ?", (payload["course_code"],)
    ).fetchone()
    if course is None:
        return fail(404, "课程不存在")

    term = str(payload["term"]).strip()
    existing = db.execute(
        "SELECT id FROM scores WHERE student_id = ? AND course_id = ? AND term = ?",
        (student["id"], course["id"], term),
    ).fetchone()

    if existing is not None:
        db.execute(
            "UPDATE scores SET score = ?, status = ?, updated_at = datetime('now', 'localtime') "
            "WHERE id = ?",
            (score, status, existing["id"]),
        )
        action, score_id = "updated", existing["id"]
    else:
        cursor = db.execute(
            "INSERT INTO scores (student_id, course_id, term, score, status) VALUES (?, ?, ?, ?, ?)",
            (student["id"], course["id"], term, score, status),
        )
        action, score_id = "created", cursor.lastrowid

    # 成绩变更后按规则重算预警，测试用例会再次用 SQL 交叉核对
    warning = recalculate_warning(db, student["id"], term)
    db.commit()

    return jsonify(
        {
            "ok": True,
            "action": action,
            "id": score_id,
            "student_no": payload["student_no"],
            "course_code": payload["course_code"],
            "term": term,
            "warning": warning,
        }
    )


@api.get("/api/scores")
def list_scores():
    student_no = request.args.get("student_no")
    if not student_no:
        return fail(400, "缺少 student_no 参数")

    db = get_db()
    student = db.execute(
        "SELECT id, name FROM students WHERE student_no = ?", (student_no,)
    ).fetchone()
    if student is None:
        return fail(404, "学生不存在")

    term = request.args.get("term")
    sql = (
        "SELECT c.course_code, c.name AS course_name, s.term, s.score, s.status "
        "FROM scores s JOIN courses c ON c.id = s.course_id "
        "WHERE s.student_id = ?"
    )
    params = [student["id"]]
    if term:
        sql += " AND s.term = ?"
        params.append(term)
    sql += " ORDER BY s.term, c.course_code"
    rows = db.execute(sql, params).fetchall()

    return jsonify(
        {
            "ok": True,
            "student_no": student_no,
            "name": student["name"],
            "term": term,
            "count": len(rows),
            "items": [dict(row) for row in rows],
        }
    )


@api.get("/api/stats/course/<course_code>")
def course_stats(course_code):
    term = request.args.get("term")
    if not term:
        return fail(400, "缺少 term 参数")

    db = get_db()
    course = db.execute(
        "SELECT id, name, credit FROM courses WHERE course_code = ?", (course_code,)
    ).fetchone()
    if course is None:
        return fail(404, "课程不存在")

    row = db.execute(
        "SELECT COUNT(*) AS total, "
        "ROUND(AVG(score), 2) AS avg, MAX(score) AS max, MIN(score) AS min, "
        "SUM(CASE WHEN score >= 60 THEN 1 ELSE 0 END) AS passed "
        "FROM scores "
        "WHERE course_id = ? AND term = ? AND status = 'normal' AND score IS NOT NULL",
        (course["id"], term),
    ).fetchone()

    total = row["total"] or 0
    passed = row["passed"] or 0
    return jsonify(
        {
            "ok": True,
            "course_code": course_code,
            "course_name": course["name"],
            "term": term,
            "total": total,
            "avg": row["avg"],
            "max": row["max"],
            "min": row["min"],
            "passed": passed,
            "pass_rate": round(passed / total, 4) if total else None,
        }
    )


@api.get("/api/students/<student_no>/profile")
def student_profile(student_no):
    db = get_db()
    student = db.execute(
        "SELECT id, student_no, name, major, grade_year FROM students WHERE student_no = ?",
        (student_no,),
    ).fetchone()
    if student is None:
        return fail(404, "学生不存在")

    overview = db.execute(
        "SELECT COUNT(*) AS total, ROUND(AVG(score), 2) AS avg, "
        "SUM(CASE WHEN score < 60 THEN 1 ELSE 0 END) AS failed "
        "FROM scores "
        "WHERE student_id = ? AND status = 'normal' AND score IS NOT NULL",
        (student["id"],),
    ).fetchone()

    term_rows = db.execute(
        "SELECT term, COUNT(*) AS total, ROUND(AVG(score), 2) AS avg, "
        "SUM(CASE WHEN score < 60 THEN 1 ELSE 0 END) AS failed "
        "FROM scores "
        "WHERE student_id = ? AND status = 'normal' AND score IS NOT NULL "
        "GROUP BY term ORDER BY term",
        (student["id"],),
    ).fetchall()

    warning_row = db.execute(
        "SELECT term, level, reason FROM warnings WHERE student_id = ? "
        "ORDER BY term DESC LIMIT 1",
        (student["id"],),
    ).fetchone()

    return jsonify(
        {
            "ok": True,
            "student_no": student["student_no"],
            "name": student["name"],
            "major": student["major"],
            "grade_year": student["grade_year"],
            "total": overview["total"] or 0,
            "avg": overview["avg"],
            "failed": overview["failed"] or 0,
            "terms": [dict(row) for row in term_rows],
            "warning": dict(warning_row) if warning_row else None,
        }
    )


@api.get("/api/warnings")
def list_warnings():
    term = request.args.get("term")
    db = get_db()
    sql = (
        "SELECT st.student_no, st.name, w.term, w.level, w.reason "
        "FROM warnings w JOIN students st ON st.id = w.student_id"
    )
    params = []
    if term:
        sql += " WHERE w.term = ?"
        params.append(term)
    sql += " ORDER BY CASE w.level WHEN 'high' THEN 0 ELSE 1 END, st.student_no"
    rows = db.execute(sql, params).fetchall()

    return jsonify(
        {
            "ok": True,
            "term": term,
            "count": len(rows),
            "items": [dict(row) for row in rows],
        }
    )


@api.get("/health")
def health():
    return jsonify({"ok": True, "status": "ok"})


def create_app(db_path=None, log_path=None):
    """创建 Flask 应用。测试执行器会用临时日志路径以免污染演示日志。"""
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or os.environ.get("SCHOOL_DB") or DEFAULT_DB_PATH
    app.config["LOG_PATH"] = log_path or os.environ.get("SCHOOL_LOG") or DEFAULT_LOG_PATH
    init_database(app.config["DB_PATH"])
    app.extensions["api_logger"] = setup_logging(app.config["LOG_PATH"])
    # 关闭 werkzeug 默认的控制台访问日志，访问记录已写入 logs/app.log
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    @app.before_request
    def mark_start():
        g.started_at = time.perf_counter()

    @app.after_request
    def log_request(response):
        elapsed = int((time.perf_counter() - g.get("started_at", time.perf_counter())) * 1000)
        message = f"{request.method} {request.path} -> {response.status_code} ({elapsed}ms)"
        logger = app.extensions["api_logger"]
        if response.status_code >= 500:
            logger.error(message)
        elif response.status_code >= 400:
            logger.warning(message)
        else:
            logger.info(message)
        return response

    @app.errorhandler(Exception)
    def handle_unexpected(exc):
        # 405/404 等由路由层产生的 HTTP 异常保留原始状态码，不能当作 500
        if isinstance(exc, HTTPException):
            return jsonify({"ok": False, "error": exc.description}), exc.code
        app.extensions["api_logger"].exception("未捕获异常: %s", exc)
        return jsonify({"ok": False, "error": "服务器内部错误"}), 500

    app.register_blueprint(api)
    return app
