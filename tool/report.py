"""HTML 测试报告生成：单文件自包含，可直接用浏览器打开或截图。"""

import html
import json

PASS_BADGE = '<span class="badge pass">PASS</span>'
FAIL_BADGE = '<span class="badge fail">FAIL</span>'

STYLE = """
:root {
  --bg: #f4f6fb;
  --panel: #ffffff;
  --ink: #111827;
  --muted: #6b7280;
  --line: #e5e7eb;
  --accent: #4f46e5;
  --accent-soft: #eef2ff;
  --green: #0f9d58;
  --green-soft: #e8f7ee;
  --red: #dc2626;
  --red-soft: #fdecec;
  --amber: #b45309;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.6;
}
.hero {
  background: linear-gradient(120deg, #0f172a 0%, #1e293b 55%, #312e81 100%);
  color: #f8fafc;
  padding: 34px 48px 38px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
}
.eyebrow {
  font-size: 12px;
  letter-spacing: 2.4px;
  color: #a5b4fc;
  text-transform: uppercase;
  margin-bottom: 10px;
}
.hero h1 { font-size: 27px; margin: 0 0 8px; font-weight: 650; }
.hero .sub { color: #c7d2fe; margin: 0 0 18px; font-size: 13.5px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  background: rgba(255, 255, 255, 0.09);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  color: #e0e7ff;
}
.chip code { color: #fff; font-size: 12px; }
.score { text-align: center; min-width: 168px; }
.score .num { font-size: 54px; font-weight: 700; line-height: 1; color: #86efac; }
.score .label { color: #cbd5e1; font-size: 12.5px; margin-top: 8px; letter-spacing: 1px; }
main { padding: 28px 48px 40px; max-width: 1320px; margin: 0 auto; }
.kpis { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 22px; }
.kpi {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.kpi .label { color: var(--muted); font-size: 12px; }
.kpi .value { font-size: 26px; font-weight: 650; margin-top: 4px; font-variant-numeric: tabular-nums; }
.kpi .hint { font-size: 11.5px; color: var(--muted); margin-top: 2px; }
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 20px 22px 22px;
  margin-bottom: 20px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.panel h2 { font-size: 16px; margin: 0 0 4px; }
.panel .desc { color: var(--muted); font-size: 12.5px; margin: 0 0 16px; }
.methods { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.method {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 12px 14px;
  background: #fbfcff;
}
.method .name { font-size: 12.5px; color: var(--muted); }
.method .count { font-size: 22px; font-weight: 650; margin: 2px 0 8px; }
.bar { height: 6px; background: #eef1f8; border-radius: 999px; overflow: hidden; }
.bar > span { display: block; height: 100%; background: linear-gradient(90deg, #6366f1, #818cf8); }
table { width: 100%; border-collapse: collapse; font-size: 12.7px; }
table.fixed { table-layout: fixed; }
th {
  text-align: left;
  color: var(--muted);
  font-weight: 600;
  border-bottom: 1px solid var(--line);
  padding: 9px 10px;
  background: #fafbfe;
  white-space: nowrap;
}
td { border-bottom: 1px solid #f1f3f9; padding: 9px 10px; vertical-align: top; }
tr:last-child td { border-bottom: none; }
.badge {
  display: inline-block;
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.4px;
}
.badge.pass { background: var(--green-soft); color: var(--green); }
.badge.fail { background: var(--red-soft); color: var(--red); }
.tag {
  display: inline-block;
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 11px;
  white-space: nowrap;
}
code, .mono {
  font-family: Consolas, "Cascadia Mono", "Courier New", monospace;
  font-size: 11.8px;
  color: #334155;
  background: #f6f7fb;
  border: 1px solid #eceff5;
  border-radius: 5px;
  padding: 1px 6px;
}
td code { display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: bottom; }
.muted { color: var(--muted); }
.fail-detail { color: var(--red); font-size: 12px; margin: 4px 0 0; }
.grid2 { display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 20px; }
.kv { display: grid; grid-template-columns: 128px 1fr; gap: 6px 12px; font-size: 12.6px; }
.kv dt { color: var(--muted); }
.kv dd { margin: 0; }
.logbars { display: grid; gap: 9px; font-size: 12.6px; }
.logrow { display: grid; grid-template-columns: 92px 1fr 52px; align-items: center; gap: 10px; }
.logrow .track { height: 8px; background: #eef1f8; border-radius: 999px; overflow: hidden; }
.logrow .fill { height: 100%; background: #94a3b8; }
.logrow .fill.info { background: #60a5fa; }
.logrow .fill.warn { background: #f59e0b; }
.logrow .fill.err { background: #ef4444; }
footer { color: var(--muted); font-size: 12px; text-align: center; padding: 8px 0 32px; }
"""


def esc(value):
    return html.escape(str(value), quote=True)


def _snippet(value, limit=72):
    if value is None:
        return '<span class="muted">—</span>'
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    if len(text) > limit:
        text = text[:limit] + "…"
    return f"<code>{esc(text)}</code>"


def _request_cell(request):
    params = request.get("params") or {}
    if params:
        return _snippet(params)
    return _snippet(request.get("body"))


def _badge(passed):
    return PASS_BADGE if passed else FAIL_BADGE


def _cases_table(cases):
    rows = []
    for case in cases:
        detail = ""
        if case["failures"]:
            detail = "".join(
                f'<div class="fail-detail">✗ {esc(item)}</div>' for item in case["failures"]
            )
        checks = "、".join(esc(item["name"]) for item in case["checks"]) or "—"
        status = case.get("status")
        status_class = "muted"
        if status is not None:
            status_class = "" if status < 400 else "fail-detail"
        rows.append(
            "<tr>"
            f'<td class="mono">{esc(case["id"])}</td>'
            f"<td>{esc(case['title'])}{detail}</td>"
            f'<td><span class="tag">{esc(case["method_design"])}</span></td>'
            f'<td><code>{esc(case["request"]["method"])} {esc(case["request"]["path"])}</code><br>'
            f"{_request_cell(case['request'])}</td>"
            f'<td class="{status_class}">{esc(status if status is not None else "—")}</td>'
            f'<td class="mono">{esc(case["duration_ms"])} ms</td>'
            f"<td>{checks}</td>"
            f"<td>{_badge(case['passed'])}</td>"
            "</tr>"
        )
    return "".join(rows)


def _invariants_table(invariants):
    rows = []
    for item in invariants:
        rows.append(
            "<tr>"
            f'<td class="mono">{esc(item["id"])}</td>'
            f'<td>{esc(item["title"])}<br><span class="muted">{esc(item["sql_tech"])}</span></td>'
            f'<td><code>{esc(item["check"])}</code></td>'
            f'<td class="mono">{esc(item["actual"])}</td>'
            f'<td class="mono">{esc(item["expect"])}</td>'
            f"<td>{_badge(item['passed'])}</td>"
            "</tr>"
        )
    return "".join(rows)


def _method_cards(by_method, total):
    order = ["等价类-有效", "等价类-无效", "边界值", "场景法"]
    cards = []
    for name in order:
        count = by_method.get(name, 0)
        width = round(count / total * 100) if total else 0
        cards.append(
            '<div class="method">'
            f'<div class="name">{esc(name)}</div>'
            f'<div class="count">{count} 条</div>'
            f'<div class="bar"><span style="width:{width}%"></span></div>'
            "</div>"
        )
    return "".join(cards)


def _log_panel(log_stats):
    levels = log_stats.get("levels", {})
    rows = []
    for level, css in (("INFO", "info"), ("WARNING", "warn"), ("ERROR", "err")):
        count = levels.get(level, 0)
        total = max(log_stats.get("total_lines", 1), 1)
        width = round(count / total * 100)
        rows.append(
            '<div class="logrow">'
            f"<span>{level}</span>"
            f'<div class="track"><div class="fill {css}" style="width:{width}%"></div></div>'
            f"<span class=\"muted\">{count}</span>"
            "</div>"
        )
    statuses = log_stats.get("statuses", {})
    status_text = " · ".join(f"{key} {value}" for key, value in sorted(statuses.items())) or "无"
    rows.append(
        f'<div class="muted" style="margin-top:6px">状态码分布：{esc(status_text)}</div>'
    )
    rows.append(
        f'<div class="muted">慢请求（≥{esc(log_stats.get("slow_threshold_ms", 100))}ms）：'
        f'{esc(log_stats.get("slow_requests", 0))} 条，'
        f'接口请求合计 {esc(log_stats.get("requests", 0))} 次</div>'
    )
    return "".join(rows)


def render_report(result, result_name=""):
    summary = result["summary"]
    env = result["environment"]
    seed = env.get("seed", {})
    pass_rate = round(summary["pass_rate"] * 100, 1)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>测试报告 · {esc(result['suite'])}</title>
<style>{STYLE}</style>
</head>
<body>
<header class="hero">
  <div>
    <div class="eyebrow">API Test Report · SQL Data Validation</div>
    <h1>{esc(result['suite'])}</h1>
    <p class="sub">真实 HTTP 调用 → 数据库落库校验 → 全库一致性检查</p>
    <div class="chips">
      <span class="chip">执行时间 {esc(result['started_at'])}</span>
      <span class="chip">总耗时 {esc(round(result['duration_ms'] / 1000, 2))} s</span>
      <span class="chip">Python {esc(env['python'])}</span>
      <span class="chip">被测服务 <code>{esc(env['base_url'])}</code></span>
      <span class="chip">数据规模 {esc(seed.get('students', 0))} 名学生 / {esc(seed.get('scores', 0))} 条成绩</span>
    </div>
  </div>
  <div class="score">
    <div class="num">{pass_rate}%</div>
    <div class="label">用 例 通 过 率</div>
  </div>
</header>
<main>
  <section class="kpis">
    <div class="kpi">
      <div class="label">接口用例</div>
      <div class="value">{summary['total']}</div>
      <div class="hint">按顺序执行，覆盖 6 个接口</div>
    </div>
    <div class="kpi">
      <div class="label">通过</div>
      <div class="value" style="color:var(--green)">{summary['passed']}</div>
      <div class="hint">断言全部通过</div>
    </div>
    <div class="kpi">
      <div class="label">失败</div>
      <div class="value" style="color:{'var(--red)' if summary['failed'] else 'var(--muted)'}">{summary['failed']}</div>
      <div class="hint">{'存在失败用例' if summary['failed'] else '无失败用例'}</div>
    </div>
    <div class="kpi">
      <div class="label">SQL 不变量校验</div>
      <div class="value">{summary['invariants_passed']}/{summary['invariants_total']}</div>
      <div class="hint">多表联查 / 聚合 / 子查询</div>
    </div>
    <div class="kpi">
      <div class="label">接口请求 / 慢请求</div>
      <div class="value">{result['log_stats'].get('requests', 0)} / {result['log_stats'].get('slow_requests', 0)}</div>
      <div class="hint">来自 logs/app.log 实测</div>
    </div>
  </section>

  <section class="panel">
    <h2>用例设计方法分布</h2>
    <p class="desc">按等价类、边界值、场景法组织用例，覆盖正常流、异常流与业务规则边界。</p>
    <div class="methods">{_method_cards(summary['by_method'], summary['total'])}</div>
  </section>

  <section class="panel">
    <h2>接口用例明细</h2>
    <p class="desc">每条用例都通过 HTTP 调用真实服务，并用 SQL 从数据库反查结果（右侧为关联校验项）。</p>
    <table class="fixed">
      <colgroup>
        <col style="width:6%"><col style="width:25%"><col style="width:7%"><col style="width:36%">
        <col style="width:5%"><col style="width:6%"><col style="width:10%"><col style="width:5%">
      </colgroup>
      <thead><tr>
        <th>编号</th><th>用例</th><th>设计方法</th><th>请求</th>
        <th>状态码</th><th>耗时</th><th>SQL 校验</th><th>结果</th>
      </tr></thead>
      <tbody>{_cases_table(result['cases'])}</tbody>
    </table>
  </section>

  <section class="panel">
    <h2>SQL 数据一致性校验</h2>
    <p class="desc">全部用例执行完毕后，独立用 SQL 重算并比对，期望违例数恒为 0。</p>
    <table class="fixed">
      <colgroup>
        <col style="width:7%"><col style="width:43%"><col style="width:20%">
        <col style="width:10%"><col style="width:10%"><col style="width:10%">
      </colgroup>
      <thead><tr>
        <th>编号</th><th>校验项 / SQL 技术</th><th>校验函数</th><th>实际值</th><th>期望值</th><th>结果</th>
      </tr></thead>
      <tbody>{_invariants_table(result['invariants'])}</tbody>
    </table>
  </section>

  <section class="grid2">
    <div class="panel">
      <h2>接口日志分析</h2>
      <p class="desc">服务端访问日志由 logscan 解析，等价于 grep / awk 的排查链路。</p>
      <div class="logbars">{_log_panel(result['log_stats'])}</div>
    </div>
    <div class="panel">
      <h2>执行环境</h2>
      <p class="desc">数据由脚本按固定随机种子生成，结果可复现。</p>
      <dl class="kv">
        <dt>Python</dt><dd>{esc(env['python'])}</dd>
        <dt>运行平台</dt><dd>{esc(env['platform'])}</dd>
        <dt>数据库</dt><dd><code>{esc(env['database'])}</code></dd>
        <dt>用例文件</dt><dd><code>{esc(env['case_file'])}</code></dd>
        <dt>开始 / 结束</dt><dd>{esc(result['started_at'])} — {esc(result['finished_at'])}</dd>
        <dt>报告编号</dt><dd>{esc(result_name or 'latest')}</dd>
      </dl>
    </div>
  </section>
</main>
<footer>由 edu-api-testkit 自动生成 · python -m tool.cli run</footer>
</body>
</html>
"""
