"""用例执行引擎。

流程：
1. 用固定随机种子重建数据库（保证可复现）
2. 清空接口日志，启动被测服务（真实 HTTP，而不是测试桩）
3. 按顺序执行 cases/score_api_cases.json 中的接口用例，并用 SQL 校验落库结果
4. 执行全库不变量校验 cases/sql_suite.json
5. 汇总日志统计，输出 JSON 结果与 HTML 报告
"""

import json
import os
import platform
import sqlite3
import threading
import time
from collections import Counter
from datetime import datetime

import requests
from werkzeug.serving import make_server

from app.server import create_app
from data.generate_data import seed_database
from tool.checks import REGISTRY
from tool.logscan import read_records, summarize
from tool.report import render_report

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(ROOT, "var", "school.db")
DEFAULT_LOG = os.path.join(ROOT, "logs", "app.log")
CASES_FILE = os.path.join(ROOT, "cases", "score_api_cases.json")
SQL_FILE = os.path.join(ROOT, "cases", "sql_suite.json")
REPORTS_DIR = os.path.join(ROOT, "reports")
HISTORY_DIR = os.path.join(REPORTS_DIR, "history")


def diff(actual, expected, path="响应"):
    """深度比对：expected 是子集，允许 actual 比 expected 多字段。"""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path} 期望为对象，实际为 {type(actual).__name__}"]
        issues = []
        for key, value in expected.items():
            if key not in actual:
                issues.append(f"{path}.{key} 缺失")
            else:
                issues.extend(diff(actual[key], value, f"{path}.{key}"))
        return issues
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path} 期望为数组，实际为 {type(actual).__name__}"]
        if len(actual) != len(expected):
            return [f"{path} 长度 {len(actual)} != 期望 {len(expected)}"]
        issues = []
        for index, (item_actual, item_expected) in enumerate(zip(actual, expected)):
            issues.extend(diff(item_actual, item_expected, f"{path}[{index}]"))
        return issues
    if isinstance(expected, bool):
        return [] if actual is expected else [f"{path} 期望 {expected}，实际 {actual}"]
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return [] if abs(float(actual) - float(expected)) < 1e-6 else [
            f"{path} 期望 {expected}，实际 {actual}"
        ]
    return [] if actual == expected else [f"{path} 期望 {expected!r}，实际 {actual!r}"]


def run_checks(conn, checks):
    results = []
    for item in checks or []:
        name = item["name"]
        func = REGISTRY.get(name)
        if func is None:
            results.append(
                {"name": name, "expect": item.get("expect"), "actual": None,
                 "passed": False, "note": "未注册的校验项"}
            )
            continue
        actual = func(conn, **item.get("params", {}))
        issues = diff(actual, item["expect"], "实际值")
        results.append(
            {
                "name": name,
                "params": item.get("params", {}),
                "expect": item["expect"],
                "actual": actual,
                "passed": not issues,
                "note": (func.__doc__ or "").strip().splitlines()[0] if func.__doc__ else "",
                "issues": issues,
            }
        )
    return results


def run_case(session, base_url, case, db_path):
    request = case["request"]
    expect = case.get("expect", {})
    started = time.perf_counter()
    failures = []
    status = None
    body = None

    kwargs = {}
    if "json" in request:
        kwargs["json"] = request["json"]
    if "params" in request:
        kwargs["params"] = request["params"]

    try:
        response = session.request(
            request["method"], base_url + request["path"], timeout=10, **kwargs
        )
        status = response.status_code
        try:
            body = response.json() if response.text else None
        except ValueError:
            body = response.text[:200]
    except requests.RequestException as exc:
        failures.append(f"请求异常：{exc}")

    if status is not None and expect.get("status") is not None and status != expect["status"]:
        failures.append(f"状态码 期望 {expect['status']}，实际 {status}")
    if "json" in expect:
        failures.extend(diff(body, expect["json"]))
    if "error_contains" in expect:
        message = body.get("error", "") if isinstance(body, dict) else str(body)
        if expect["error_contains"] not in message:
            failures.append(f"错误信息未包含「{expect['error_contains']}」：{message}")

    conn = sqlite3.connect(db_path)
    try:
        checks = run_checks(conn, case.get("checks"))
    finally:
        conn.close()
    for item in checks:
        failures.extend(item.get("issues", []))

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "id": case["id"],
        "title": case["title"],
        "method_design": case.get("method_design", ""),
        "request": {
            "method": request["method"],
            "path": request["path"],
            "params": request.get("params"),
            "body": request.get("json"),
        },
        "status": status,
        "expected_status": expect.get("status"),
        "duration_ms": duration_ms,
        "passed": not failures,
        "failures": failures,
        "response_excerpt": body,
        "checks": checks,
    }


def _wait_until_ready(base_url, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(base_url + "/health", timeout=0.5).status_code == 200:
                return
        except requests.RequestException:
            time.sleep(0.1)
    raise RuntimeError("被测服务在限定时间内未启动")


def run_suite(db_path=None, log_path=None, port=5011, cases_file=None, sql_file=None, verbose=False):
    """执行整套用例，返回结果字典，并写出 JSON / HTML 报告。"""
    db_path = db_path or DEFAULT_DB
    log_path = log_path or DEFAULT_LOG
    cases_file = cases_file or CASES_FILE
    sql_file = sql_file or SQL_FILE

    started_at = datetime.now()
    start_ts = time.perf_counter()

    seed_stats = seed_database(db_path)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8"):
        pass

    app = create_app(db_path=db_path, log_path=log_path)
    server = make_server("127.0.0.1", port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"

    try:
        _wait_until_ready(base_url)
        with open(cases_file, encoding="utf-8") as fp:
            case_data = json.load(fp)
        with open(sql_file, encoding="utf-8") as fp:
            sql_data = json.load(fp)

        session = requests.Session()
        case_results = []
        total_cases = len(case_data["cases"])
        for index, case in enumerate(case_data["cases"], start=1):
            outcome = run_case(session, base_url, case, db_path)
            case_results.append(outcome)
            if verbose:
                mark = "PASS" if outcome["passed"] else "FAIL"
                print(
                    f'[{index:02d}/{total_cases}] {mark}  {outcome["id"]}  '
                    f'{outcome["title"]}  ({outcome["duration_ms"]} ms)'
                )
                for failure in outcome["failures"]:
                    print(f'          ✗ {failure}')
        session.close()
    finally:
        server.shutdown()

    conn = sqlite3.connect(db_path)
    try:
        invariant_results = []
        for entry in sql_data["checks"]:
            func = REGISTRY[entry["check"]]
            actual = func(conn, **entry.get("params", {}))
            issues = diff(actual, entry["expect"], "实际值")
            invariant_results.append(
                {
                    "id": entry["id"],
                    "title": entry["title"],
                    "check": entry["check"],
                    "sql_tech": entry.get("sql_tech", ""),
                    "expect": entry["expect"],
                    "actual": actual,
                    "passed": not issues,
                    "note": (func.__doc__ or "").strip().splitlines()[0] if func.__doc__ else "",
                    "issues": issues,
                }
            )
    finally:
        conn.close()

    finished_at = datetime.now()
    passed = sum(1 for item in case_results if item["passed"])
    invariant_passed = sum(1 for item in invariant_results if item["passed"])
    method_counter = Counter(item["method_design"] for item in case_results)
    log_stats = summarize(read_records(log_path))

    result = {
        "suite": case_data.get("suite", "接口自动化测试"),
        "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": finished_at.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_ms": round((time.perf_counter() - start_ts) * 1000, 1),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "base_url": base_url,
            "database": os.path.relpath(db_path, ROOT).replace("\\", "/"),
            "log": os.path.relpath(log_path, ROOT).replace("\\", "/"),
            "seed": seed_stats,
            "case_file": os.path.relpath(cases_file, ROOT).replace("\\", "/"),
        },
        "summary": {
            "total": len(case_results),
            "passed": passed,
            "failed": len(case_results) - passed,
            "pass_rate": round(passed / len(case_results), 4) if case_results else 0,
            "by_method": dict(method_counter),
            "invariants_total": len(invariant_results),
            "invariants_passed": invariant_passed,
        },
        "cases": case_results,
        "invariants": invariant_results,
        "log_stats": log_stats,
    }

    os.makedirs(HISTORY_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    stamp = started_at.strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(REPORTS_DIR, "latest_result.json"), "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=2)
    with open(os.path.join(HISTORY_DIR, f"run_{stamp}.json"), "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=2)
    with open(os.path.join(REPORTS_DIR, "latest_report.html"), "w", encoding="utf-8") as fp:
        fp.write(render_report(result, result_name=f"{stamp}"))

    return result
