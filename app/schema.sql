-- 被测系统数据库结构：学生 / 课程 / 成绩 / 学业预警
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_no  TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    major       TEXT    NOT NULL,
    grade_year  INTEGER NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS courses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    credit      REAL    NOT NULL,
    teacher     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS scores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students (id) ON DELETE CASCADE,
    course_id   INTEGER NOT NULL REFERENCES courses (id) ON DELETE CASCADE,
    term        TEXT    NOT NULL,
    score       REAL,
    status      TEXT    NOT NULL DEFAULT 'normal'
                        CHECK (status IN ('normal', 'absent', 'exempt')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (student_id, course_id, term),
    -- 数据库层的兜底约束：成绩只允许为空或落在 0-100
    CHECK (score IS NULL OR (score >= 0 AND score <= 100))
);

CREATE TABLE IF NOT EXISTS warnings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students (id) ON DELETE CASCADE,
    term        TEXT    NOT NULL,
    level       TEXT    NOT NULL CHECK (level IN ('high', 'medium')),
    reason      TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (student_id, term)
);

CREATE INDEX IF NOT EXISTS idx_scores_student ON scores (student_id, term);
CREATE INDEX IF NOT EXISTS idx_scores_course ON scores (course_id, term);
CREATE INDEX IF NOT EXISTS idx_warnings_term ON warnings (term, level);
