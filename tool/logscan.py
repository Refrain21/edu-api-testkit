"""接口日志分析工具：模拟 Linux 下 grep / awk 的排查流程。

日志行格式：
    2026-11-17 11:35:02 | INFO    | api | GET /api/scores -> 200 (3ms)

对应关系（README 中也有对照表）：
    grep '| ERROR' logs/app.log        ->  python -m tool.logscan --level ERROR
    grep '-> 4' logs/app.log           ->  python -m tool.logscan --status 4xx
    awk 统计状态码分布                  ->  python -m tool.logscan --summary
"""

import argparse
import re
import sys
from collections import Counter

LINE_RE = re.compile(
    r"^(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \|\s*(?P<level>[A-Z]+)\s*\|"
    r"\s*(?P<logger>\w+)\s*\|\s*(?P<message>.*)$"
)
REQUEST_RE = re.compile(
    r"^(?P<method>[A-Z]+) (?P<path>\S+) -> (?P<status>\d{3}) \((?P<ms>\d+)ms\)$"
)


def parse_line(line):
    match = LINE_RE.match(line.rstrip("\n"))
    if not match:
        return None
    record = match.groupdict()
    request = REQUEST_RE.match(record["message"])
    if request:
        record.update(
            method=request["method"],
            path=request["path"],
            status=int(request["status"]),
            ms=int(request["ms"]),
        )
    return record


def read_records(path):
    records = []
    try:
        with open(path, encoding="utf-8") as fp:
            for line in fp:
                record = parse_line(line)
                if record:
                    records.append(record)
    except FileNotFoundError:
        pass
    return records


def _status_band(status):
    return f"{status // 100}xx"


def summarize(records, slow_ms=100):
    levels = Counter(item["level"] for item in records)
    statuses = Counter(_status_band(item["status"]) for item in records if "status" in item)
    requests = [item for item in records if "status" in item]
    slow = [item for item in requests if item["ms"] >= slow_ms]
    slow_paths = Counter(f'{item["method"]} {item["path"]}' for item in slow)
    error_paths = Counter(
        f'{item["method"]} {item["path"]}' for item in requests if item["status"] >= 400
    )
    return {
        "total_lines": len(records),
        "levels": dict(levels),
        "statuses": dict(statuses),
        "requests": len(requests),
        "slow_requests": len(slow),
        "slow_threshold_ms": slow_ms,
        "top_slow_paths": slow_paths.most_common(3),
        "top_error_paths": error_paths.most_common(3),
    }


def apply_filters(records, args):
    result = []
    for item in records:
        if args.level and item["level"] != args.level.upper():
            continue
        if args.status:
            target = args.status.lower()
            actual = str(item.get("status", ""))
            if target.endswith("xx"):
                if not actual.startswith(target[0]):
                    continue
            elif actual != target:
                continue
        if args.path and args.path not in item.get("path", ""):
            continue
        if args.min_ms is not None and item.get("ms", 0) < args.min_ms:
            continue
        if args.grep and args.grep.lower() not in item["message"].lower():
            continue
        result.append(item)
    return result


def print_records(records, limit=None):
    shown = records[-limit:] if limit else records
    for item in shown:
        print(f'{item["time"]}  {item["level"]:<7}  {item["message"]}')
    if limit and len(records) > limit:
        print(f"... 共 {len(records)} 条，仅显示最近 {limit} 条")


def print_summary(records):
    stats = summarize(records)
    print("=" * 60)
    print(f'日志总行数：{stats["total_lines"]}    接口请求：{stats["requests"]}')
    print(f'级别分布：{stats["levels"] or "无"}')
    print(f'状态码分布：{stats["statuses"] or "无"}')
    print(f'慢请求（>={stats["slow_threshold_ms"]}ms）：{stats["slow_requests"]} 条')
    if stats["top_error_paths"]:
        print("错误请求 TOP：")
        for path, count in stats["top_error_paths"]:
            print(f"  {path}  x{count}")
    if stats["top_slow_paths"]:
        print("慢请求 TOP：")
        for path, count in stats["top_slow_paths"]:
            print(f"  {path}  x{count}")
    print("=" * 60)


def main(argv=None):
    parser = argparse.ArgumentParser(description="接口日志分析（grep/awk 风格）")
    parser.add_argument("--file", default="logs/app.log", help="日志文件路径")
    parser.add_argument("--level", help="按级别过滤，如 ERROR / WARNING / INFO")
    parser.add_argument("--status", help="按状态码过滤，支持 4xx 或 404")
    parser.add_argument("--path", help="按接口路径包含的关键字过滤")
    parser.add_argument("--min-ms", type=int, dest="min_ms", help="只看耗时不低于该值的请求")
    parser.add_argument("--grep", help="按日志正文关键字过滤")
    parser.add_argument("--limit", type=int, help="仅显示最近 N 条匹配记录")
    parser.add_argument("--summary", action="store_true", help="输出统计摘要")
    args = parser.parse_args(argv)

    records = read_records(args.file)
    if not records:
        print(f"未找到日志文件或无有效记录：{args.file}")
        return 0

    matched = apply_filters(records, args)
    if args.summary:
        print_summary(records)
    if matched:
        print_records(matched, args.limit)
    elif not args.summary:
        print("无匹配记录")
    return 0


if __name__ == "__main__":
    sys.exit(main())
