#!/usr/bin/env python3
"""Canon-Mnemonic-Guard Dashboard Generator — standalone HTML with data embedded.

Usage: python3 generate.py [--output path.html]
"""

import json, os, glob, yaml, sys, re
from datetime import datetime, timezone, timedelta

SR = os.path.expanduser('~/.hermes/self-reflection')
OUTPUT = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == '--output' else os.path.expanduser('~/Desktop/canon-mnemonic-guard-dashboard.html')

def parse_frontmatter(path):
    content = open(path).read()
    if not content.startswith('---'):
        return {}, ''
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, ''
    body = parts[2].strip()
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except:
        fm = {}
    return fm, body

def parse_days_since(val):
    """Parse a date/datetime string robustly, return days since or None."""
    if not val:
        return None
    s = str(val).strip()
    # Try ISO format variants
    for fmt in [
        '%Y-%m-%dT%H:%M:%S.%f%z',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d',
    ]:
        try:
            # Replace Z with +00:00 for fromisoformat compat
            cleaned = s.replace('Z', '+00:00')
            dt = datetime.fromisoformat(cleaned)
            # Ensure timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return (now - dt).days
        except:
            continue
    return None

def read_rules():
    rules = []
    for cat in ['ban', 'gap', 'lazy']:
        d = os.path.join(SR, 'rules', cat)
        if not os.path.isdir(d):
            continue
        for f in glob.glob(os.path.join(d, '*.md')):
            fm, body = parse_frontmatter(f)
            last = fm.get('last_triggered', '')
            rules.append({
                'id': fm.get('id', os.path.basename(f).replace('.md','')),
                'type': fm.get('type', cat),
                'date': str(fm.get('date', '')),
                'last_triggered': str(last),
                'days_since': parse_days_since(last),
                'hit_count': int(fm.get('hit_count', 0)),
                'false_positives': int(fm.get('false_positives', 0)),
                'keywords': fm.get('keywords', []) or [],
                'tags': fm.get('tags', []) or [],
            })
    return rules

def false_rate(r):
    if r['hit_count'] == 0:
        return 0
    return round(r['false_positives'] / r['hit_count'] * 100, 1)

rules = read_rules()
ban_count = sum(1 for r in rules if r['type'] == 'ban')
gap_count = sum(1 for r in rules if r['type'] == 'gap')
lazy_count = sum(1 for r in rules if r['type'] == 'lazy')

state = {}
sp = os.path.join(SR, 'state.json')
if os.path.exists(sp):
    state = json.load(open(sp))

ilog = os.path.join(SR, 'intercept_log.jsonl')
intercept_count = sum(1 for _ in open(ilog)) if os.path.exists(ilog) else 0

elog = os.path.join(SR, 'errors.jsonl')
error_count = sum(1 for _ in open(elog)) if os.path.exists(elog) else 0

# Sort rules: ban first, then gap, then lazy; within each by hit_count desc
rules.sort(key=lambda r: ({'ban':0,'gap':1,'lazy':2}.get(r['type'],3), -r['hit_count']))

top_hit = sorted(rules, key=lambda r: r['hit_count'], reverse=True)[:5]
bottom_hit = sorted(rules, key=lambda r: r['hit_count'])[:5]
high_false = [r for r in rules if false_rate(r) > 30]
total_hits = sum(r['hit_count'] for r in rules)

# Build rules JSON carefully — escape </script> just in case
rules_json = json.dumps(rules, ensure_ascii=False)
if '</script>' in rules_json:
    rules_json = rules_json.replace('</script>', '<\\/script>')

# Build HTML
# Using template approach to avoid f-string complexity with curly braces
CSS = open(__file__).read()  # We'll embed CSS directly

HTML = f'''<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Canon-Mnemonic-Guard Dashboard · 三省引擎</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
[data-theme="dark"] {{
  --bg-deep: #0d1117; --bg-panel: #161b22; --bg-surface: #21262d; --bg-elevated: #30363d;
  --text-primary: #e6edf3; --text-secondary: #c9d1d9; --text-tertiary: #8b949e; --text-muted: #6e7681;
  --accent: #7c7cff; --accent-bg: #5c5cff; --accent-hover: #9494ff;
  --border-subtle: rgba(255,255,255,0.06); --border-std: rgba(255,255,255,0.12);
  --green: #3fb950; --red: #f85149; --amber: #d2991d;
  --radius: 8px; --radius-sm: 6px;
}}
[data-theme="light"] {{
  --bg-deep: #ffffff; --bg-panel: #f6f8fa; --bg-surface: #f0f2f5; --bg-elevated: #e1e4e8;
  --text-primary: #1f2328; --text-secondary: #424a53; --text-tertiary: #656d76; --text-muted: #8c959f;
  --accent: #5c5cff; --accent-bg: #4949cc; --accent-hover: #3d3db3;
  --border-subtle: rgba(0,0,0,0.06); --border-std: rgba(0,0,0,0.12);
  --green: #1a7f37; --red: #cf222e; --amber: #9a6700;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  background: var(--bg-deep); color: var(--text-secondary);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  font-feature-settings: 'cv01','ss03'; font-size:15px; line-height:1.6;
  min-height:100vh; transition: background 0.2s, color 0.2s;
}}
.container {{ max-width:1400px; margin:0 auto; padding:16px 24px 40px; }}
header {{
  background: var(--bg-panel); border-bottom:1px solid var(--border-std);
  padding:14px 24px; display:flex; align-items:center; justify-content:space-between;
  position:sticky; top:0; z-index:10; backdrop-filter:blur(12px);
}}
header h1 {{ font-size:17px; font-weight:600; color:var(--text-primary); letter-spacing:-0.2px; display:flex; align-items:center; gap:10px; }}
.badge {{ font-size:12px; font-weight:500; color:var(--text-muted); background:var(--bg-elevated); padding:3px 10px; border-radius:999px; border:1px solid var(--border-std); }}
.theme-btn {{
  background:var(--bg-elevated); border:1px solid var(--border-std); border-radius:999px;
  color:var(--text-secondary); padding:5px 14px; font-size:13px; font-family:inherit;
  cursor:pointer; font-weight:500;
}}
.theme-btn:hover {{ color:var(--text-primary); border-color:var(--accent); }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; margin-bottom:20px; }}
.stat-card {{
  background:var(--bg-surface); border:1px solid var(--border-std); border-radius:var(--radius);
  padding:14px 16px; display:flex; flex-direction:column; gap:3px; transition:border-color 0.2s;
}}
.stat-card:hover {{ border-color:var(--accent); }}
.stat-card .label {{ font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; }}
.stat-card .value {{ font-size:30px; font-weight:600; color:var(--text-primary); letter-spacing:-0.8px; line-height:1.1; }}
.stat-card .sub {{ font-size:12px; color:var(--text-tertiary); margin-top:2px; }}
.stat-card.accent {{ border-color:rgba(92,92,255,0.3); }}
.stat-card.accent .value {{ color:var(--accent); }}
.stat-card.warn {{ border-color:rgba(248,81,73,0.3); }}
.stat-card.warn .value {{ color:var(--red); }}
.section-title {{
  font-size:14px; font-weight:600; color:var(--text-primary);
  padding:20px 0 10px; display:flex; align-items:center; gap:8px;
}}
.section-title .count {{ font-size:12px; font-weight:400; color:var(--text-muted); }}
.toolbar {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; padding-bottom:10px; }}
.toolbar input, .toolbar select {{
  background:var(--bg-surface); border:1px solid var(--border-std); border-radius:var(--radius-sm);
  color:var(--text-primary); padding:7px 12px; font-size:13px; font-family:inherit;
}}
.toolbar input {{ min-width:220px; }}
.toolbar input::placeholder {{ color:var(--text-muted); }}
.toolbar select {{ color:var(--text-secondary); cursor:pointer; }}
.table-wrap {{ overflow-x:auto; border-radius:var(--radius); border:1px solid var(--border-std); }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
thead {{ background:var(--bg-panel); }}
th {{
  text-align:left; padding:10px 14px; font-weight:600; color:var(--text-tertiary);
  font-size:11px; text-transform:uppercase; letter-spacing:0.4px;
  border-bottom:2px solid var(--border-std); cursor:pointer; user-select:none; white-space:nowrap;
}}
th:hover {{ color:var(--accent); }}
td {{ padding:9px 14px; border-bottom:1px solid var(--border-subtle); color:var(--text-secondary); }}
tr:hover td {{ background:var(--bg-surface); }}
tr:last-child td {{ border-bottom:none; }}
.type-badge {{
  display:inline-block; padding:2px 9px; border-radius:999px; font-size:11px; font-weight:600; letter-spacing:0.3px;
}}
.type-ban {{ background:rgba(248,81,73,0.15); color:var(--red); }}
.type-gap {{ background:rgba(210,153,29,0.15); color:var(--amber); }}
.type-lazy {{ background:rgba(92,92,255,0.15); color:var(--accent); }}
.false-high {{ color:var(--red); font-weight:600; }}
.stale {{ color:var(--text-muted); font-style:italic; }}
.panels {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:20px; }}
@media(max-width:768px){{ .panels{{grid-template-columns:1fr;}} }}
.panel {{
  background:var(--bg-surface); border:1px solid var(--border-std); border-radius:var(--radius); padding:16px;
}}
.panel h3 {{ font-size:14px; font-weight:600; color:var(--text-primary); margin-bottom:10px; }}
.rule-row {{
  display:flex; justify-content:space-between; align-items:center; padding:7px 0;
  border-bottom:1px solid var(--border-subtle); font-size:13px;
}}
.rule-row:last-child {{ border-bottom:none; }}
.rule-row .name {{ color:var(--text-secondary); flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-family:'JetBrains Mono',monospace; font-size:12px; }}
.rule-row .meta {{ color:var(--text-muted); font-size:12px; margin-left:12px; white-space:nowrap; }}
.empty {{ text-align:center; color:var(--text-muted); padding:32px; font-size:14px; }}
footer {{
  text-align:center; padding:20px; color:var(--text-muted); font-size:12px;
  border-top:1px solid var(--border-std); margin-top:24px;
}}
#error-msg {{ display:none; background:rgba(248,81,73,0.1); border:1px solid var(--red); color:var(--red); padding:12px 16px; border-radius:var(--radius); margin-bottom:16px; font-size:13px; font-family:'JetBrains Mono',monospace; }}
</style>
</head>
<body>

<header>
  <div style="display:flex;align-items:center;gap:10px;">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="4" y="3" width="16" height="18" rx="3" stroke="#7c7cff" stroke-width="1.5"/><line x1="8" y1="8" x2="16" y2="8" stroke="#7c7cff" stroke-width="1.5"/><line x1="8" y1="12" x2="16" y2="12" stroke="#7c7cff" stroke-width="1.5"/><line x1="8" y1="16" x2="13" y2="16" stroke="#7c7cff" stroke-width="1.5"/></svg>
    <h1>Canon-Mnemonic-Guard Dashboard</h1>
    <span class="badge">三省引擎 v5.5.5</span>
  </div>
  <div style="display:flex;align-items:center;gap:12px;">
    <span class="badge" id="updated">—</span>
    <button class="theme-btn" onclick="toggleTheme()" id="themeBtn">☀ 亮色</button>
  </div>
</header>

<div class="container">
  <div id="error-msg"></div>

  <div class="stats">
    <div class="stat-card">
      <span class="label">规则总数</span>
      <span class="value">{len(rules)}</span>
      <span class="sub">ban {ban_count} · gap {gap_count} · lazy {lazy_count}</span>
    </div>
    <div class="stat-card">
      <span class="label">累计命中</span>
      <span class="value">{total_hits}</span>
      <span class="sub">规则触发总次数</span>
    </div>
    <div class="stat-card accent">
      <span class="label">系统拦截</span>
      <span class="value">{intercept_count}</span>
      <span class="sub">intercept_log.jsonl</span>
    </div>
    <div class="stat-card">
      <span class="label">错误记录</span>
      <span class="value">{error_count}</span>
      <span class="sub">errors.jsonl</span>
    </div>
    <div class="stat-card warn">
      <span class="label">高误报</span>
      <span class="value">{len(high_false)}</span>
      <span class="sub">误报率 &gt;30%</span>
    </div>
  </div>

  <div class="panels">
    <div class="panel">
      <h3>高频规则 Top 5</h3>
      {''.join(f'<div class="rule-row"><span class="name">{r["id"]}</span><span class="meta">{r["hit_count"]} 次</span></div>' for r in top_hit) if top_hit else '<div class="empty">暂无数据</div>'}
    </div>
    <div class="panel">
      <h3>低频规则 Bottom 5</h3>
      {''.join(f'<div class="rule-row"><span class="name">{r["id"]}</span><span class="meta">{r["hit_count"]} 次</span></div>' for r in bottom_hit) if bottom_hit else '<div class="empty">暂无数据</div>'}
    </div>
  </div>

  <div class="section-title">全部规则 <span class="count">({len(rules)})</span></div>
  <div class="toolbar">
    <input type="text" id="search" placeholder="搜索规则 ID 或关键词…" oninput="render()">
    <select id="typeFilter" onchange="render()">
      <option value="">全部类型</option>
      <option value="ban">ban · 禁止项</option>
      <option value="gap">gap · 缺失项</option>
      <option value="lazy">lazy · 偷懒项</option>
    </select>
    <span style="font-size:12px;color:var(--text-muted);" id="rowCount"></span>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th data-sort="id" onclick="sort('id')">规则 ID ▾</th>
          <th data-sort="type" onclick="sort('type')">类型</th>
          <th data-sort="hit_count" onclick="sort('hit_count')">命中 ▾</th>
          <th data-sort="false_rate" onclick="sort('false_rate')">误报率</th>
          <th>关键词</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</div>

<footer>Canon-Mnemonic-Guard · 三省引擎 v5.5.5 · 数据源 ~/.hermes/self-reflection/</footer>

<script>
const DATA = {rules_json};

let sortKey = 'hit_count';
let sortDir = -1;

function falseRate(r) {{ return r.hit_count ? (r.false_positives/r.hit_count*100).toFixed(1) : '0.0'; }}

function render() {{
  try {{
    const q = (document.getElementById('search')?.value||'').toLowerCase();
    const tf = document.getElementById('typeFilter')?.value||'';
    let rows = DATA.filter(function(r) {{
      if (tf && r.type !== tf) return false;
      if (q && !r.id.toLowerCase().includes(q) && !(r.keywords||[]).some(function(k){{return k.toLowerCase().includes(q)}})) return false;
      return true;
    }});
    rows.sort(function(a,b) {{
      var va = a[sortKey], vb = b[sortKey];
      if (sortKey === 'false_rate') {{ va = parseFloat(falseRate(a)); vb = parseFloat(falseRate(b)); }}
      if (va < vb) return -sortDir; if (va > vb) return sortDir; return 0;
    }});

    var html = '';
    for (var i = 0; i < rows.length; i++) {{
      var r = rows[i];
      var fr = parseFloat(falseRate(r));
      html += '<tr>'+
        '<td style="font-family:JetBrains Mono,monospace;font-size:12px;max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+r.id+'">'+r.id+'</td>'+
        '<td><span class="type-badge type-'+r.type+'">'+r.type+'</span></td>'+
        '<td>'+r.hit_count+'</td>'+
        '<td'+(fr>30?' class="false-high"':'')+'>'+falseRate(r)+'%</td>'+
        '<td style="color:var(--text-muted);font-size:12px;max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+(r.keywords||[]).join(', ')+'</td>'+
      '</tr>';
    }}
    document.getElementById('tbody').innerHTML = html;
    document.getElementById('rowCount').textContent = rows.length+' / '+DATA.length+' 条';
    document.getElementById('updated').textContent = new Date().toLocaleTimeString('zh-CN',{{hour:'2-digit',minute:'2-digit',second:'2-digit'}});
    document.getElementById('error-msg').style.display = 'none';
  }} catch(e) {{
    document.getElementById('error-msg').style.display = 'block';
    document.getElementById('error-msg').textContent = 'JS Error: ' + e.message + ' (line ' + e.lineNumber + ')';
  }}
}}

function sort(key) {{
  if (sortKey === key) sortDir *= -1; else {{ sortKey = key; sortDir = -1; }}
  render();
}}

function toggleTheme() {{
  var html = document.documentElement;
  var isDark = html.getAttribute('data-theme') === 'dark';
  html.setAttribute('data-theme', isDark ? 'light' : 'dark');
  document.getElementById('themeBtn').textContent = isDark ? '☾ 暗色' : '☀ 亮色';
  try {{ localStorage.setItem('dashboard-theme', isDark ? 'light' : 'dark'); }} catch(e) {{}}
}}

(function() {{
  try {{
    var saved = localStorage.getItem('dashboard-theme');
    if (saved) {{
      document.documentElement.setAttribute('data-theme', saved);
      document.getElementById('themeBtn').textContent = saved === 'light' ? '☾ 暗色' : '☀ 亮色';
    }} else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {{
      document.documentElement.setAttribute('data-theme', 'light');
      document.getElementById('themeBtn').textContent = '☾ 暗色';
    }}
  }} catch(e) {{}}
  render();
}})();
</script>
</body>
</html>'''

# Validate JSON is parseable
json.loads(rules_json)

with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(HTML)

print(f"Dashboard: {OUTPUT}")
print(f"Size: {len(HTML):,} bytes · Rules: {len(rules)} (ban:{ban_count} gap:{gap_count} lazy:{lazy_count})")
print(f"Total hits: {total_hits} · Intercepts: {intercept_count} · Errors: {error_count}")

# Verify days_since computation
with_days = sum(1 for r in rules if r['days_since'] is not None)
print(f"Rules with valid days_since: {with_days}/{len(rules)}")
if with_days > 0:
    sample = [r for r in rules if r['days_since'] is not None][:3]
    for r in sample:
        print(f"  {r['id']}: last_triggered={r['last_triggered']} → {r['days_since']}d ago")
