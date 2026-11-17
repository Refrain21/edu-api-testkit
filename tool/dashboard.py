"""测试结果看板：读取 reports/latest_result.json，用浏览器展示最近一次执行情况。

启动：python -m tool.cli dashboard --port 5002
访问：http://127.0.0.1:5002
"""

import glob
import json
import os

from flask import Flask, render_template_string, send_file

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(ROOT, "reports")
LATEST_JSON = os.path.join(REPORTS_DIR, "latest_result.json")
LATEST_HTML = os.path.join(REPORTS_DIR, "latest_report.html")

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>测试结果看板 · edu-api-testkit</title>
<style>
:root {
  --bg:#0f1623; --panel:#161f2e; --panel2:#1b2536; --line:#26324a;
  --ink:#e8eefc; --muted:#8b9bb7; --accent:#7c8cff; --green:#34d399; --red:#f87171; --amber:#fbbf24;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif;font-size:14px}
a{color:#a5b4fc;text-decoration:none}
header{display:flex;align-items:center;justify-content:space-between;padding:22px 40px;border-bottom:1px solid var(--line);background:linear-gradient(90deg,#101827,#141d2f)}
.brand{font-weight:650;font-size:17px;letter-spacing:.3px}
.brand small{display:block;color:var(--muted);font-weight:400;font-size:12px;margin-top:3px;letter-spacing:0}
.btn{background:var(--accent);color:#0b1020;padding:8px 16px;border-radius:8px;font-size:12.5px;font-weight:650}
main{padding:26px 40px 40px;max-width:1400px;margin:0 auto}
.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:22px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:15px 17px}
.card .label{color:var(--muted);font-size:12px}
.card .value{font-size:26px;font-weight:700;margin-top:4px;font-variant-numeric:tabular-nums}
.card .hint{color:var(--muted);font-size:11.5px;margin-top:3px}
.grid{display:grid;grid-template-columns:1.55fr 1fr;gap:18px;align-items:start}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:18px}
.panel h2{font-size:14px;margin:0 0 12px;letter-spacing:.2px}
.meta{color:var(--muted);font-size:12px;margin:-6px 0 12px}
table{width:100%;border-collapse:collapse;font-size:12.3px}
th{text-align:left;color:var(--muted);font-weight:600;border-bottom:1px solid var(--line);padding:8px 8px;background:#131c2b}
td{border-bottom:1px solid #1e2940;padding:8px;vertical-align:top}
tr:last-child td{border-bottom:none}
code{font-family:Consolas,monospace;font-size:11.6px;background:#101827;border:1px solid #24314a;border-radius:5px;padding:1px 5px;color:#c7d2fe}
.pill{display:inline-block;border-radius:999px;padding:2px 9px;font-size:11px;font-weight:650}
.pill.pass{background:rgba(52,211,153,.12);color:var(--green)}
.pill.fail{background:rgba(248,113,113,.14);color:var(--red)}
.tag{display:inline-block;background:rgba(124,140,255,.13);color:#a5b4fc;border-radius:5px;padding:1px 7px;font-size:10.8px;white-space:nowrap}
.rows{display:grid;gap:9px;font-size:12.4px}
.row{display:grid;grid-template-columns:70px 1fr 44px;gap:10px;align-items:center}
.track{height:7px;background:#1d2740;border-radius:999px;overflow:hidden}
.fill{height:100%;background:#3b82f6}
.fill.warn{background:var(--amber)}
.fill.err{background:var(--red)}
.hist{display:grid;gap:8px;font-size:12.3px}
.hist .item{display:flex;justify-content:space-between;border:1px solid var(--line);border-radius:8px;padding:8px 11px;background:var(--panel2)}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px}
.kv{display:grid;grid-template-columns:96px 1fr;gap:6px 10px;font-size:12.2px}
.kv dt{color:var(--muted)} .kv dd{margin:0}
.empty{color:var(--muted);font-size:13px;padding:20px 0}
</style>
</head>
<body>
<header>
  <div class="brand">edu-api-testkit · 测试结果看板
    <small>学生成绩服务 · 接口自动化测试与 SQL 数据校验</small>
  </div>
  <div>
    <a class="btn" href="/report" target="_blank">打开完整 HTML 报告</a>
  </div>
</header>
<main>
{% if result %}
  <div class="cards">
    <div class="card"><div class="label">用例通过率</div>
      <div class="value" style="color:{{ '#34d399' if result.summary.failed == 0 else '#fbbf24' }}">{{ '%.1f'|format(result.summary.pass_rate * 100) }}%</div>
      <div class="hint">{{ result.summary.passed }}/{{ result.summary.total }} 通过</div></div>
    <div class="card"><div class="label">失败用例</div>
      <div class="value" style="color:{{ '#f87171' if result.summary.failed else '#8b9bb7' }}">{{ result.summary.failed }}</div>
      <div class="hint">断言失败数</div></div>
    <div class="card"><div class="label">SQL 不变量</div>
      <div class="value">{{ result.summary.invariants_passed }}/{{ result.summary.invariants_total }}</div>
      <div class="hint">一致性校验通过</div></div>
    <div class="card"><div class="label">接口请求</div>
      <div class="value">{{ result.log_stats.requests }}</div>
      <div class="hint">慢请求 {{ result.log_stats.slow_requests }} 条</div></div>
    <div class="card"><div class="label">执行耗时</div>
      <div class="value">{{ '%.2f'|format(result.duration_ms / 1000) }}s</div>
      <div class="hint">{{ result.started_at }}</div></div>
  </div>

  <div class="grid">
    <div>
      <div class="panel">
        <h2>用例执行明细</h2>
        <div class="meta">共 {{ result.summary.total }} 条 · {{ result.environment.case_file }} · 被测服务 {{ result.environment.base_url }}</div>
        <table>
          <thead><tr><th>编号</th><th>用例</th><th>方法</th><th>状态码</th><th>耗时</th><th>结果</th></tr></thead>
          <tbody>
          {% for case in result.cases %}
            <tr>
              <td><code>{{ case.id }}</code></td>
              <td>{{ case.title }}</td>
              <td><span class="tag">{{ case.method_design }}</span></td>
              <td>{{ case.status if case.status is not none else '—' }}</td>
              <td>{{ case.duration_ms }} ms</td>
              <td><span class="pill {{ 'pass' if case.passed else 'fail' }}">{{ 'PASS' if case.passed else 'FAIL' }}</span></td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
      </div>

      <div class="panel">
        <h2>SQL 数据一致性校验</h2>
        <table>
          <thead><tr><th>编号</th><th>校验项</th><th>实际 / 期望</th><th>结果</th></tr></thead>
          <tbody>
          {% for item in result.invariants %}
            <tr>
              <td><code>{{ item.id }}</code></td>
              <td>{{ item.title }}<br><span style="color:#8b9bb7;font-size:11px">{{ item.sql_tech }}</span></td>
              <td><code>{{ item.actual }}</code> / <code>{{ item.expect }}</code></td>
              <td><span class="pill {{ 'pass' if item.passed else 'fail' }}">{{ 'PASS' if item.passed else 'FAIL' }}</span></td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>

    <div>
      <div class="panel">
        <h2>日志级别分布</h2>
        <div class="meta">logs/app.log · 共 {{ result.log_stats.total_lines }} 行</div>
        <div class="rows">
        {% for level, css in [('INFO',''),('WARNING','warn'),('ERROR','err')] %}
          {% set count = result.log_stats.levels.get(level, 0) %}
          <div class="row">
            <span style="color:#8b9bb7">{{ level }}</span>
            <div class="track"><div class="fill {{ css }}" style="width:{{ (count / (result.log_stats.total_lines or 1) * 100)|round(1) }}%"></div></div>
            <span>{{ count }}</span>
          </div>
        {% endfor %}
        </div>
        <div class="kv" style="margin-top:14px">
          <dt>状态码</dt><dd>{{ result.log_stats.statuses }}</dd>
          <dt>慢请求阈值</dt><dd>≥ {{ result.log_stats.slow_threshold_ms }} ms</dd>
          <dt>请求总数</dt><dd>{{ result.log_stats.requests }}</dd>
        </div>
      </div>

      <div class="panel">
        <h2>历史执行</h2>
        <div class="hist">
        {% for run in history %}
          <div class="item">
            <span><span class="dot" style="background:{{ '#34d399' if run.failed == 0 else '#f87171' }}"></span>{{ run.name }}</span>
            <span style="color:#8b9bb7">{{ run.passed }}/{{ run.total }} · {{ '%.1f'|format(run.pass_rate * 100) }}%</span>
          </div>
        {% endfor %}
        </div>
      </div>

      <div class="panel">
        <h2>数据与环境</h2>
        <dl class="kv">
          <dt>Python</dt><dd>{{ result.environment.python }}</dd>
          <dt>数据库</dt><dd>{{ result.environment.database }}</dd>
          <dt>学生 / 成绩</dt><dd>{{ result.environment.seed.students }} / {{ result.environment.seed.scores }}</dd>
          <dt>预警记录</dt><dd>{{ result.environment.seed.warnings }}</dd>
          <dt>开始时间</dt><dd>{{ result.started_at }}</dd>
        </dl>
      </div>
    </div>
  </div>
{% else %}
  <div class="panel"><div class="empty">还没有执行记录，先运行 <code>python -m tool.cli run</code>。</div></div>
{% endif %}
</main>
</body>
</html>
"""


def _history():
    runs = []
    for path in sorted(glob.glob(os.path.join(REPORTS_DIR, "history", "run_*.json")), reverse=True)[:6]:
        try:
            with open(path, encoding="utf-8") as fp:
                data = json.load(fp)
            runs.append(
                {
                    "name": os.path.basename(path).replace("run_", "").replace(".json", ""),
                    "total": data["summary"]["total"],
                    "passed": data["summary"]["passed"],
                    "failed": data["summary"]["failed"],
                    "pass_rate": data["summary"]["pass_rate"],
                }
            )
        except (OSError, KeyError, ValueError):
            continue
    return runs


def create_dashboard():
    app = Flask(__name__)

    @app.get("/")
    def index():
        result = None
        if os.path.exists(LATEST_JSON):
            with open(LATEST_JSON, encoding="utf-8") as fp:
                result = json.load(fp)
        return render_template_string(PAGE, result=result, history=_history())

    @app.get("/report")
    def report():
        if not os.path.exists(LATEST_HTML):
            return "还没有生成报告，请先运行 python -m tool.cli run", 404
        return send_file(LATEST_HTML)

    return app


if __name__ == "__main__":
    create_dashboard().run(host="127.0.0.1", port=5002, debug=False)
