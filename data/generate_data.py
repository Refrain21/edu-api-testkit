"""模拟数据生成脚本（数据来源说明见下方说明，运行后写入 var/school.db）。

数据来源
--------
本项目全部数据均为脚本生成的模拟数据，不含任何真实学生信息，不抓取外部数据。

生成逻辑
--------
1. 随机种子固定为 42，重复执行得到完全一致的数据库，保证测试结果可复现。
2. 120 名学生（学号 S2023001 起），专业为大数据技术/软件技术，入学年份 2023 或 2024。
3. 8 门课程，覆盖数据结构、数据库原理、Python、Linux、软件测试基础等。
4. 2 个学期（2025-2026-1、2025-2026-2），每名学生每学期随机修 4 门课；
   成绩服从 N(72, 13) 并截断到 0-100 后取整，约 6% 记为缺考、6% 记为免修，
   保证样本中会出现不及格记录，从而触发不同等级的预警。
5. 额外写入 2 名测试专用学生 S9999 / S9998（无任何成绩），
   供"场景法"用例从零开始构造预警业务流，避免与随机数据互相干扰。

命令行
------
    python -m data.generate_data            # 重建 var/school.db
    python -m data.generate_data --keep     # 保留已有数据（仅补建表结构）
"""

import argparse
import random
import sqlite3

from app.rules import recalculate_warning
from app.server import DEFAULT_DB_PATH, init_database

SURNAMES = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
GIVEN_NAMES = [
    "子涵", "欣怡", "雨桐", "浩然", "思远", "嘉怡", "博文", "若曦",
    "宇轩", "诗涵", "俊杰", "梓萱", "一鸣", "佳宁", "宇航", "语彤",
    "天佑", "书瑶", "明轩", "静怡", "泽宇", "清扬", "皓轩", "婉婷",
]

COURSES = [
    ("CS101", "数据结构", 4.0, "王立"),
    ("CS102", "数据库原理", 3.5, "李倩"),
    ("CS103", "Python程序设计", 3.0, "陈昊"),
    ("CS104", "大数据技术基础", 3.5, "周敏"),
    ("CS105", "Linux操作系统", 2.5, "孙鹏"),
    ("CS106", "软件测试基础", 2.0, "赵宁"),
    ("CS107", "数据可视化", 2.5, "吴珊"),
    ("CS108", "计算机网络", 3.0, "郑凯"),
]

TERMS = ("2025-2026-1", "2025-2026-2")
MAJORS = ("大数据技术", "软件技术")
TEST_STUDENTS = (("S9999", "测试学生A"), ("S9998", "测试学生B"))


def _clear(conn):
    conn.execute("DELETE FROM warnings")
    conn.execute("DELETE FROM scores")
    conn.execute("DELETE FROM courses")
    conn.execute("DELETE FROM students")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('students','courses','scores','warnings')")


def seed_database(db_path=None, seed=42, reset=True):
    """生成模拟数据，返回统计信息。"""
    db_path = db_path or DEFAULT_DB_PATH
    init_database(db_path)
    rng = random.Random(seed)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        if reset:
            _clear(conn)

        conn.executemany(
            "INSERT INTO courses (course_code, name, credit, teacher) VALUES (?, ?, ?, ?)",
            COURSES,
        )
        course_ids = {
            row["course_code"]: row["id"] for row in conn.execute("SELECT id, course_code FROM courses")
        }

        students = []
        for index in range(1, 121):
            student_no = f"S{2023000 + index}"
            name = rng.choice(SURNAMES) + rng.choice(GIVEN_NAMES)
            students.append((student_no, name, rng.choice(MAJORS), rng.choice((2023, 2024))))
        for student_no, name in TEST_STUDENTS:
            students.append((student_no, name, "大数据技术", 2024))
        conn.executemany(
            "INSERT INTO students (student_no, name, major, grade_year) VALUES (?, ?, ?, ?)",
            students,
        )
        student_ids = {
            row["student_no"]: row["id"] for row in conn.execute("SELECT id, student_no FROM students")
        }

        real_students = [row[0] for row in students if row[0] not in dict(TEST_STUDENTS)]
        score_rows = []
        for student_no in real_students:
            for term in TERMS:
                picked = rng.sample([code for code, *_ in COURSES], 4)
                for course_code in picked:
                    roll = rng.random()
                    if roll < 0.06:
                        score_rows.append((student_ids[student_no], course_ids[course_code], term, None, "absent"))
                    elif roll < 0.12:
                        score_rows.append((student_ids[student_no], course_ids[course_code], term, None, "exempt"))
                    else:
                        score = round(min(100, max(0, rng.gauss(72, 13))))
                        score_rows.append((student_ids[student_no], course_ids[course_code], term, score, "normal"))
        conn.executemany(
            "INSERT INTO scores (student_id, course_id, term, score, status) VALUES (?, ?, ?, ?, ?)",
            score_rows,
        )

        # 依据规则回填预警，保证初始数据自洽
        warning_count = 0
        pairs = conn.execute("SELECT DISTINCT student_id, term FROM scores").fetchall()
        for row in pairs:
            if recalculate_warning(conn, row["student_id"], row["term"]) is not None:
                warning_count += 1
        conn.commit()

        return {
            "database": db_path,
            "students": len(students),
            "courses": len(COURSES),
            "scores": len(score_rows),
            "warnings": warning_count,
        }
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="生成学生成绩模拟数据")
    parser.add_argument("--db", default=None, help="数据库路径，默认 var/school.db")
    parser.add_argument("--keep", action="store_true", help="保留已有数据")
    args = parser.parse_args()

    stats = seed_database(args.db, reset=not args.keep)
    print(f"数据库：{stats['database']}")
    print(f"学生 {stats['students']} 人 | 课程 {stats['courses']} 门 | "
          f"成绩 {stats['scores']} 条 | 预警 {stats['warnings']} 条")


if __name__ == "__main__":
    main()
