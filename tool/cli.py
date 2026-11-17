"""统一命令行入口。

    python -m tool.cli seed          重建模拟数据
    python -m tool.cli run           执行全部测试用例并生成报告
    python -m tool.cli serve         启动被测服务（默认 5001 端口）
    python -m tool.cli dashboard     启动测试结果看板（默认 5002 端口）
"""

import argparse
import os
import sys

from app.server import create_app
from data.generate_data import seed_database
from tool.runner import REPORTS_DIR, run_suite


def _print_result(result):
    summary = result["summary"]
    print("=" * 72)
    print(f"执行完成：{summary['passed']}/{summary['total']} 用例通过，"
          f"SQL 校验 {summary['invariants_passed']}/{summary['invariants_total']} 通过，"
          f"总耗时 {round(result['duration_ms'] / 1000, 2)}s")
    if summary["failed"]:
        print("失败用例：")
        for case in result["cases"]:
            if not case["passed"]:
                print(f"  - {case['id']} {case['title']}")
                for failure in case["failures"]:
                    print(f"      ✗ {failure}")
    print(f"JSON 结果：{os.path.join(REPORTS_DIR, 'latest_result.json')}")
    print(f"HTML 报告：{os.path.join(REPORTS_DIR, 'latest_report.html')}")
    print("查看看板：python -m tool.cli dashboard")
    print("=" * 72)


def main(argv=None):
    parser = argparse.ArgumentParser(description="学生成绩服务测试工具")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="重建模拟数据")

    run_parser = sub.add_parser("run", help="执行测试用例")
    run_parser.add_argument("--port", type=int, default=5011, help="被测服务监听端口")
    run_parser.add_argument("--quiet", action="store_true", help="只输出汇总，不逐条打印")

    serve_parser = sub.add_parser("serve", help="启动被测服务")
    serve_parser.add_argument("--port", type=int, default=5001)

    dash_parser = sub.add_parser("dashboard", help="启动测试结果看板")
    dash_parser.add_argument("--port", type=int, default=5002)

    args = parser.parse_args(argv)

    if args.command == "seed":
        stats = seed_database()
        print(f"数据已重建：{stats}")
        return 0

    if args.command == "run":
        print("正在重建模拟数据并启动被测服务 ...")
        result = run_suite(port=args.port, verbose=not args.quiet)
        _print_result(result)
        return 0 if result["summary"]["failed"] == 0 else 1

    if args.command == "serve":
        app = create_app()
        print(f"被测服务已启动：http://127.0.0.1:{args.port}")
        app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
        return 0

    if args.command == "dashboard":
        from tool.dashboard import create_dashboard

        app = create_dashboard()
        print(f"测试结果看板：http://127.0.0.1:{args.port}")
        app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
