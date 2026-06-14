#!/usr/bin/env python3
"""Canon-Mnemonic-Guard Dashboard Server — serves dashboard + API on localhost.

Usage: python3 server.py [--port 8765]
Triggers: !dashboard in Hermes, or direct CLI call.
"""

import json, os, glob, yaml, sys, re, http.server, urllib.parse, webbrowser, threading, time
from datetime import datetime, timezone

SR = os.path.expanduser('~/.hermes/self-reflection')
CONFIG_PATH = os.path.expanduser('~/.hermes/config.yaml')
SKILLS_DIR = os.path.expanduser('~/.hermes/skills')
PORT = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == '--port' else 8765

# ── Companion skills: parsed from CMG SKILL.md ──

CMG_SKILL_PATH = os.path.expanduser('~/.hermes/skills/software-development/canon-mnemonic-guard/SKILL.md')

def _cmg_version():
    """Read CMG version from SKILL.md frontmatter."""
    try:
        with open(CMG_SKILL_PATH) as f:
            for line in f:
                if line.startswith("version:"):
                    return line.split(":",1)[1].strip()
    except: pass
    return "?.?.?"

def _sentinel_config_key():
    """Auto-detect sentinel plugin config key."""
    py = os.path.expanduser("~/.hermes/plugins/sentinel/plugin.yaml")
    if os.path.exists(py):
        try:
            with open(py) as f:
                d = yaml.safe_load(f) or {}
            return d.get("name", "sentinel")
        except: pass
    return "sentinel"

CMG_VERSION = _cmg_version()
SENTINEL_KEY = _sentinel_config_key()


def _parse_cmg_tables():
    """Parse companion skill tables from CMG SKILL.md. Returns [{id, desc}].
    Reads from '## 配套 Skill 生态' section, stops at next major heading."""
    skills = []
    seen = set()
    if not os.path.exists(CMG_SKILL_PATH):
        return skills
    with open(CMG_SKILL_PATH) as f:
        content = f.read()
    start = content.find('## 配套 Skill 生态')
    if start < 0:
        return skills
    # Find end: next '## ' heading that's NOT a subsection (### or ####)
    rest = content[start:]
    end_marker = None
    for m in re.finditer(r'\n## [^#]', rest):
        end_marker = m.start()
        break
    section = rest[:end_marker] if end_marker else rest
    # Parse markdown tables: | `skill-name` | description | ... |
    for line in section.split('\n'):
        m = re.match(r'\|\s*`([^`]+)`\s*\|\s*(.+?)\s*\|', line)
        if m:
            skill_id = m.group(1).strip()
            desc = m.group(2).strip()
            # Skip non-skill rows and internal plugins
            if skill_id in ('推荐', '------', 'canon-mnemonic-guard-dashboard', 'sentinel', 'skill-autoload',
                            'dashboard', 'cmg-dashboard',
                            'agent-s-deployment', 'hermes-agent-skill-authoring'):
                continue
            # Skip sub-references (contain /) and duplicates
            if '/' in skill_id or skill_id in seen:
                continue
            seen.add(skill_id)
            skills.append({'id': skill_id, 'desc': desc})
    return skills

def check_skill_installed(skill_id):
    """Check if a skill is installed by scanning all SKILL.md frontmatter names.
    Searches ~/.hermes/skills/, ~/.agents/skills/, and ~/.hermes/plugins/."""
    import glob as _glob
    alt_names = {'rtk-rewrite': 'rtk-hermes', 'plur': 'plur-memory'}
    ids = [skill_id] + ([alt_names[skill_id]] if skill_id in alt_names else [])
    search_dirs = [
        os.path.expanduser('~/.hermes/skills'),
        os.path.expanduser('~/.claude/skills'),
        os.path.expanduser('~/.agents/skills'),
        os.path.expanduser('~/.openclaw/skills'),
        os.path.expanduser('~/.codex/skills'),
    ]
    for sd in search_dirs:
        if not os.path.isdir(sd):
            continue
        for md in _glob.glob(os.path.join(sd, '**', 'SKILL.md'), recursive=True):
            try:
                with open(md) as f:
                    content = f.read()
                if not content.startswith('---'):
                    continue
                parts = content.split('---', 2)
                if len(parts) < 3:
                    continue
                # Extract name from frontmatter via regex (avoids YAML parse errors)
                m = re.search(r'^name:\s*(\S+)', parts[1], re.MULTILINE)
                if m and m.group(1).strip() in ids:
                    return True
            except:
                continue
    # Also check plugins/
    plugin_dir = os.path.expanduser('~/.hermes/plugins')
    for sid in ids:
        if os.path.isdir(os.path.join(plugin_dir, sid)):
            return True
    return False

def read_companion_skills():
    """Read companion skills with install status and toggle state from config.
    Skill list is parsed dynamically from CMG SKILL.md."""
    cfg_toggles = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            c = yaml.safe_load(f) or {}
        cfg_toggles = c.get(SENTINEL_KEY, {}).get('companion_skills', {})
    result = []
    for s in _parse_cmg_tables():
        installed = check_skill_installed(s['id'])
        enabled = cfg_toggles.get(s['id'], True)
        # English descriptions (CMG SKILL.md is Chinese-only)
        desc_en_map = {
            'ralph-loop': 'Close-loop verification',
            'verification-before-completion': 'Evidence before assertion',
            'diagnose': 'Root cause debugging',
            'karpathy-coding-guidelines': 'Proactive coding standards',
            'plur': 'Extended rule source',
            'obsidian': 'Visualize rules/*.md',
            'rtk-rewrite': 'Compress terminal output 60-90%',
            'hermes-agent-skill-authoring': 'Release checklist & versioning',
            'agent-s-deployment': 'Agent S deployment & config',
        }
        result.append({
            'id': s['id'],
            'name_zh': s['id'], 'name_en': s['id'],
            'desc_zh': s['desc'],
            'desc_en': desc_en_map.get(s['id'], s['desc']),
            'installed': installed,
            'enabled': enabled,
        })
    return result

# ── Data readers ──

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
    if not val:
        return None
    s = str(val).strip()
    for fmt in ['%Y-%m-%dT%H:%M:%S.%f%z','%Y-%m-%dT%H:%M:%S%z','%Y-%m-%dT%H:%M:%S.%f','%Y-%m-%dT%H:%M:%S','%Y-%m-%d']:
        try:
            cleaned = s.replace('Z', '+00:00')
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).days
        except:
            continue
    return None

def read_rules():
    rules = []
    for cat in ['ban', 'gap', 'lazy', 'meta']:
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
                'description': body.strip() if body else '',
                'source': fm.get('source_ids', ['—'])[0] if fm.get('source_ids') else '—',
            })
    rules.sort(key=lambda r: ({'ban':0,'gap':1,'lazy':2,'meta':3}.get(r['type'],4), -r['hit_count']))
    return rules

def read_stats():
    state = {}
    sp = os.path.join(SR, 'state.json')
    if os.path.exists(sp):
        state = json.load(open(sp))
    ilog = os.path.join(SR, 'intercept_log.jsonl')
    intercept_count = sum(1 for _ in open(ilog)) if os.path.exists(ilog) else 0
    elog = os.path.join(SR, 'errors.jsonl')
    error_count = sum(1 for _ in open(elog)) if os.path.exists(elog) else 0
    return {
        'intercept_count': intercept_count,
        'error_count': error_count,
        'sessions': state.get('sessions_since_start', 0),
        'last_solidify': str(state.get('last_solidify_at', '')),
    }

def read_intercept_trend():
    from collections import defaultdict
    import datetime as _dt
    ilog = os.path.join(SR, 'intercept_log.jsonl')
    if not os.path.exists(ilog):
        return {'days': [], 'counts': [], 'total': 0}
    now = _dt.datetime.now(_dt.timezone.utc)
    counts = defaultdict(int)
    total = 0
    with open(ilog) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                entry = json.loads(line)
                ts = entry.get('timestamp', '') or entry.get('ts', '')
                if ts:
                    dt = _dt.datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=_dt.timezone.utc)
                    days_ago = (now - dt).days
                    if 0 <= days_ago < 30: counts[days_ago] += 1
                total += 1
            except: total += 1
    days = list(range(29, -1, -1))
    return {'days': days, 'counts': [counts.get(d, 0) for d in days], 'total': total}

def read_config():
    """Read sentinel config section (auto-detected)."""
    if not os.path.exists(CONFIG_PATH):
        return {'intercept_notice': 'silent', 'hooks': {}}
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get(SENTINEL_KEY, {'intercept_notice': 'silent', 'hooks': {}})

def write_config(cmg_config: dict):
    """Write sentinel config section back (auto-detected)."""
    if not os.path.exists(CONFIG_PATH):
        return False
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f) or {}
    existing = cfg.get(SENTINEL_KEY, {})
    # Deep-merge: only overwrite fields that are present in the payload
    for key, val in cmg_config.items():
        if isinstance(val, dict) and isinstance(existing.get(key), dict):
            existing[key].update(val)
        else:
            existing[key] = val
    cfg[SENTINEL_KEY] = existing
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return True

def write_rule(data: dict):
    """Create a new rule .md file in rules/<type>/."""
    rule_id = data.get('id', '').strip()
    rule_type = data.get('type', 'ban')
    if not rule_id or rule_type not in ('ban', 'gap', 'lazy', 'meta'):
        return False, 'invalid id or type'
    keywords = data.get('keywords', [])
    description = data.get('description', '')
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    frontmatter = {
        'type': rule_type,
        'id': rule_id,
        'date': now_str,
        'last_triggered': '',
        'hit_count': 0,
        'false_positives': 0,
        'source_ids': ['dashboard'],
        'keywords': keywords,
        'tags': [],
        'level': 'soft',
    }
    md = '---\n' + yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False).strip() + '\n---\n\n'
    if description:
        md += f'# {rule_id}\n\n{description}\n'
    rule_dir = os.path.join(SR, 'rules', rule_type)
    os.makedirs(rule_dir, exist_ok=True)
    rule_path = os.path.join(rule_dir, f'{rule_id}.md')
    if os.path.exists(rule_path):
        return False, f'规则 {rule_id} 已存在'
    with open(rule_path, 'w') as f:
        f.write(md)
    # Update _index.md
    idx_path = os.path.join(SR, 'rules', '_index.md')
    if os.path.exists(idx_path):
        with open(idx_path, 'a') as f:
            f.write(f'| {rule_id} | {rule_type} | {now_str} | 0 | 0 | — |\n')
    return True, rule_path

def delete_rule(rule_id: str):
    """Delete a rule by searching all type directories."""
    if not rule_id:
        return False, 'no id provided'
    for cat in ['ban', 'gap', 'lazy', 'meta']:
        d = os.path.join(SR, 'rules', cat)
        if not os.path.isdir(d):
            continue
        for f in glob.glob(os.path.join(d, '*.md')):
            fm, _ = parse_frontmatter(f)
            if fm.get('id') == rule_id:
                os.remove(f)
                return True, f
    return False, f'规则 {rule_id} 不存在'

def update_rule(data: dict):
    """Update a rule's keywords, description, and optionally type."""
    rule_id = data.get('id', '').strip()
    if not rule_id:
        return False, 'no id provided'
    new_type = data.get('type', '').strip()
    if new_type and new_type not in ('ban', 'gap', 'lazy', 'meta'):
        new_type = ''
    for cat in ['ban', 'gap', 'lazy', 'meta']:
        d = os.path.join(SR, 'rules', cat)
        if not os.path.isdir(d): continue
        for f in glob.glob(os.path.join(d, '*.md')):
            fm, body = parse_frontmatter(f)
            if fm.get('id') == rule_id:
                if 'keywords' in data: fm['keywords'] = data['keywords']
                if 'description' in data:
                    d2 = data['description'].strip()
                    body = f'# {rule_id}\n\n{d2}\n' if d2 else ''
                if new_type: fm['type'] = new_type
                md = '---\n' + yaml.dump(fm, allow_unicode=True, default_flow_style=False).strip() + '\n---\n'
                if body: md += '\n' + body
                if new_type and new_type != cat:
                    nd = os.path.join(SR, 'rules', new_type)
                    os.makedirs(nd, exist_ok=True)
                    np = os.path.join(nd, os.path.basename(f))
                    with open(np, 'w') as fh: fh.write(md)
                    os.remove(f)
                    return True, np
                with open(f, 'w') as fh: fh.write(md)
                return True, f
    return False, f'规则 {rule_id} 不存在'

# ── HTML template ──

def DASHBOARD_HTML():
    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Canon-Mnemonic-Guard Dashboard · 三省引擎</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
[data-theme="dark"] {
  --bg-deep: #0d1117; --bg-panel: #161b22; --bg-surface: #21262d; --bg-elevated: #30363d;
  --text-primary: #e6edf3; --text-secondary: #c9d1d9; --text-tertiary: #8b949e; --text-muted: #6e7681;
  --accent: #7c7cff; --accent-bg: #5c5cff; --accent-hover: #9494ff;
  --border-subtle: rgba(255,255,255,0.06); --border-std: rgba(255,255,255,0.12);
  --green: #3fb950; --red: #f85149; --amber: #d2991d;
  --radius: 8px; --radius-sm: 6px;
}
[data-theme="light"] {
  --bg-deep: #fff; --bg-panel: #f6f8fa; --bg-surface: #f0f2f5; --bg-elevated: #e1e4e8;
  --text-primary: #1f2328; --text-secondary: #424a53; --text-tertiary: #656d76; --text-muted: #8c959f;
  --accent: #5c5cff; --accent-bg: #4949cc; --accent-hover: #3d3db3;
  --border-subtle: rgba(0,0,0,0.06); --border-std: rgba(0,0,0,0.12);
  --green: #1a7f37; --red: #cf222e; --amber: #9a6700;
  --radius: 8px; --radius-sm: 6px;
}
* { margin:0; padding:0; box-sizing:border-box; }
body {
  background: var(--bg-deep); color: var(--text-secondary);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  font-feature-settings: 'cv01','ss03'; font-size:15px; line-height:1.6;
  min-height:100vh; transition: background 0.2s, color 0.2s;
  animation: pageIn 0.3s ease;
}
@keyframes pageIn { from { opacity:0; } to { opacity:1; } }
.container { max-width:1400px; margin:0 auto; padding:16px 24px 40px; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration:0.01ms !important; transition-duration:0.01ms !important; }
}
header {
  background: var(--bg-panel); border-bottom:1px solid var(--border-std);
  padding:14px 24px; display:flex; align-items:center; justify-content:space-between;
  position:sticky; top:0; z-index:10; backdrop-filter:blur(12px); gap:12px; flex-wrap:wrap;
}
header h1 { font-size:22px; font-weight:600; color:var(--text-primary); letter-spacing:-0.3px; }
.badge { font-size:12px; font-weight:500; color:var(--text-muted); background:var(--bg-elevated); padding:3px 10px; border-radius:999px; border:1px solid var(--border-std); }
.theme-btn {
  background:var(--bg-elevated); border:1px solid var(--border-std); border-radius:999px;
  color:var(--text-secondary); padding:5px 14px; font-size:13px; cursor:pointer; font-weight:500;
  transition:all 0.2s;
}
.theme-btn:hover { color:var(--text-primary); border-color:var(--accent); }

/* Tabs */
.tabs { display:flex; gap:0; margin-bottom:20px; border-bottom:2px solid var(--border-std); }
.tab-btn {
  background:none; border:none; color:var(--text-muted); padding:10px 20px;
  font-size:13px; font-weight:500; cursor:pointer; font-family:inherit;
  border-bottom:2px solid transparent; margin-bottom:-2px; transition:all 0.2s ease;
  position:relative;
}
.tab-btn.active { color:var(--accent); border-bottom-color:var(--accent); }
.tab-btn:hover { color:var(--text-primary); }
.tab-btn::after {
  content:''; position:absolute; bottom:-2px; left:50%; width:0; height:2px;
  background:var(--accent); transition:all 0.2s ease; transform:translateX(-50%);
}
.tab-btn:hover::after { width:60%; }
.tab-btn.active::after { width:100%; }

.tab-panel { display:none; }
.tab-panel.active { display:block; animation:tabIn 0.2s ease; }
@keyframes tabIn { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }

.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; margin-bottom:20px; }
.stat-card {
  background:var(--bg-surface); border:1px solid var(--border-std); border-radius:var(--radius);
  padding:14px 16px; display:flex; flex-direction:column; gap:3px;
  transition:border-color 0.2s, transform 0.2s, box-shadow 0.2s;
  animation: cardIn 0.4s ease backwards;
}
.stat-card:nth-child(1) { animation-delay:0.05s; }
.stat-card:nth-child(2) { animation-delay:0.1s; }
.stat-card:nth-child(3) { animation-delay:0.15s; }
.stat-card:nth-child(4) { animation-delay:0.2s; }
.stat-card:nth-child(5) { animation-delay:0.25s; }
.stat-card:nth-child(6) { animation-delay:0.3s; }
@keyframes cardIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
.stat-card:hover { border-color:var(--accent); transform:translateY(-2px); box-shadow:0 4px 12px rgba(0,0,0,0.15); }
.stat-card .label { font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; }
.stat-card .value { font-size:30px; font-weight:600; color:var(--text-primary); letter-spacing:-0.8px; line-height:1.1; }
.stat-card .sub { font-size:12px; color:var(--text-tertiary); margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.stat-card.accent { border-color:rgba(92,92,255,0.3); }
.stat-card.accent .value { color:var(--accent); }
.stat-card.warn { border-color:rgba(248,81,73,0.3); }
.stat-card.warn .value { color:var(--red); }

.export-btn {
  background:var(--bg-elevated); border:1px solid var(--border-std); border-radius:var(--radius-sm);
  color:var(--text-secondary); font-size:12px; padding:5px 12px; cursor:pointer; font-family:inherit;
  transition:all 0.15s ease; margin-left:8px;
}
.export-btn:hover { border-color:var(--accent); color:var(--accent); }

.trend-card {
  background:var(--bg-surface); border:1px solid var(--border-std); border-radius:var(--radius);
  padding:12px 16px; margin-bottom:20px; animation: cardIn 0.4s 0.35s ease backwards;
}
.trend-card canvas { width:100%; height:160px; }

.toolbar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; padding-bottom:10px; }
.toolbar input, .toolbar select {
  background:var(--bg-surface); border:1px solid var(--border-std); border-radius:var(--radius-sm);
  color:var(--text-primary); padding:7px 12px; font-size:13px; font-family:inherit;
  transition:border-color 0.2s, box-shadow 0.2s;
}
.toolbar input:focus, .toolbar select:focus {
  outline:none; border-color:var(--accent); box-shadow:0 0 0 3px rgba(92,92,255,0.15);
}
.toolbar input { min-width:220px; }
.toolbar input::placeholder { color:var(--text-muted); }
.toolbar select { color:var(--text-secondary); cursor:pointer; }
.toolbar-input { background:var(--bg-surface); border:1px solid var(--border-std); border-radius:var(--radius-sm); color:var(--text-primary); padding:7px 12px; font-size:13px; font-family:inherit; }
.toolbar-input::placeholder { color:var(--text-muted); }

.table-wrap { overflow:auto; max-height:600px; border-radius:var(--radius); border:1px solid var(--border-std); transition:border-color 0.2s; }
.table-wrap:focus-within { border-color:var(--accent); }
table { width:100%; border-collapse:collapse; font-size:13px; table-layout:fixed; }
thead { background:var(--bg-panel); position:sticky; top:0; z-index:2; }
th {
  text-align:left; padding:11px 14px; font-weight:600; color:var(--text-tertiary);
  font-size:13px; text-transform:uppercase; letter-spacing:0.5px;
  border-bottom:2px solid var(--border-std); cursor:pointer; user-select:none; white-space:nowrap;
  position:relative;
}
th:hover { color:var(--accent); }
th.sort-asc::after, th.sort-desc::after {
  content:'▴'; display:inline-block; width:16px; text-align:center;
  margin-left:4px; font-size:14px; transition:transform 0.2s ease;
}
th.sort-asc::after { transform:rotate(0deg); }
th.sort-desc::after { transform:rotate(180deg); }
td { padding:9px 14px; border-bottom:1px solid var(--border-subtle); color:var(--text-secondary); transition:background 0.15s; }
tr:hover td { background:var(--bg-surface); }
tr:last-child td { border-bottom:none; }

.type-badge { display:inline-block; padding:2px 9px; border-radius:999px; font-size:11px; font-weight:600; }
.type-ban { background:rgba(248,81,73,0.15); color:var(--red); }
.type-gap { background:rgba(210,153,29,0.15); color:var(--amber); }
.type-lazy { background:rgba(92,92,255,0.15); color:var(--accent); }
.type-meta { background:rgba(45,212,191,0.15); color:#2dd4bf; }
.del-col { width:32px; text-align:center; padding:9px 6px !important; }
.del-btn {
  display:inline-block; width:20px; height:20px; line-height:18px; text-align:center;
  border-radius:4px; border:1px solid transparent; background:transparent;
  color:var(--text-muted); font-size:13px; cursor:pointer;
  font-family:inherit; padding:0; opacity:0; transition:opacity 0.15s ease,color 0.15s ease,background 0.15s ease;
  vertical-align:middle;
}
tr:hover .del-btn { opacity:1; }
.del-btn:hover { color:#fff; background:var(--red); border-color:var(--red); }
/* Rule detail expand */
tr.detail-row { display:none; }
tr.detail-row.show { display:table-row; animation: detailIn 0.25s ease; }
@keyframes detailIn { from { opacity:0; transform:translateY(-4px); } to { opacity:1; transform:translateY(0); } }
tr.detail-row td {
  background:rgba(92,92,255,0.04); padding:14px 24px; border-bottom:2px solid var(--border-std);
  font-size:13px; color:var(--text-secondary); line-height:1.7;
}
tr.detail-row .detail-label { font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.3px; }
tr.clickable { cursor:pointer; }
tr.clickable:hover { background:var(--bg-surface); }
.false-high { color:var(--red); font-weight:600; }
.stale { color:var(--text-muted); font-style:italic; }

/* Keyword tooltip with spring animation */
@keyframes tooltipIn {
  0% { opacity:0; transform:translateY(6px) scale(0.96); }
  100% { opacity:1; transform:translateY(0) scale(1); }
}
.keyword-cell { position:relative; cursor:default; }
.keyword-cell .kw-tip {
  visibility:hidden; opacity:0; position:absolute; bottom:calc(100% + 8px); left:0; max-width:380px;
  background:var(--bg-elevated); color:var(--text-primary); border:1px solid var(--accent);
  border-radius:var(--radius-sm); padding:8px 12px; font-size:12px; white-space:normal;
  max-width:380px; z-index:999; box-shadow:0 6px 20px rgba(0,0,0,0.5);
  pointer-events:none; line-height:1.6; transform-origin:bottom left;
}
.keyword-cell:hover .kw-tip {
  visibility:visible; opacity:1;
  animation: tooltipIn 0.25s cubic-bezier(0.16,1,0.3,1) forwards;
}
.keyword-cell:not(:hover) .kw-tip {
  animation: none;
  transition: opacity 0.12s ease, visibility 0.12s ease;
}

/* Config panel */
.config-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:12px; }
.config-card {
  background:var(--bg-surface); border:1px solid var(--border-std); border-radius:var(--radius); padding:16px;
  transition:border-color 0.2s;
}
.config-card:hover { border-color:var(--border-subtle); }
.config-card h3 { font-size:14px; font-weight:600; color:var(--text-primary); margin-bottom:12px; }
.hook-row {
  display:flex; justify-content:space-between; align-items:center; padding:8px 0;
  border-bottom:1px solid var(--border-subtle); font-size:13px;
  transition:background 0.15s; margin:0 -16px; padding-left:16px; padding-right:16px;
}
.hook-row:hover { background:var(--bg-elevated); }
.hook-row:last-child { border-bottom:none; }
.hook-row .name { color:var(--text-secondary); }
.hook-row .desc { font-size:11px; color:var(--text-muted); margin-top:2px; }
.toggle {
  width:44px; height:24px; border-radius:12px; border:none; cursor:pointer;
  background:var(--bg-elevated); position:relative; transition:background 0.2s, transform 0.1s; flex-shrink:0;
}
.toggle:active { transform:scale(0.92); }
.toggle.on { background:var(--accent-bg); }
.toggle::after {
  content:''; position:absolute; top:2px; left:2px; width:20px; height:20px;
  border-radius:50%; background:white; transition:transform 0.2s;
}
.toggle.on::after { transform:translateX(20px); }
.toggle.disabled { opacity:0.35; cursor:not-allowed; }

.notice-select {
  background:var(--bg-surface); border:1px solid var(--border-std); border-radius:var(--radius-sm);
  color:var(--text-primary); padding:6px 12px; font-size:13px; font-family:inherit; cursor:pointer;
  transition:border-color 0.2s, box-shadow 0.2s;
}
.notice-select:focus { outline:none; border-color:var(--accent); box-shadow:0 0 0 3px rgba(92,92,255,0.15); }

.save-btn {
  background:var(--accent-bg); color:white; border:none; border-radius:var(--radius-sm);
  padding:8px 20px; font-size:13px; font-weight:500; cursor:pointer; font-family:inherit;
  transition:background 0.2s, transform 0.15s;
}
.save-btn:hover { background:var(--accent-hover); }
.save-btn:active { transform:scale(0.97); }
.save-btn:disabled { opacity:0.5; cursor:not-allowed; transform:none; }

#toast {
  position:fixed; bottom:24px; right:24px; padding:10px 20px; border-radius:var(--radius);
  font-size:13px; font-weight:500; z-index:100;
  transition:opacity 0.3s, transform 0.3s; opacity:0; transform:translateY(10px);
  pointer-events:none;
}
#toast.show { opacity:1; transform:translateY(0); }
#toast.success { background:rgba(63,185,80,0.15); color:var(--green); border:1px solid var(--green); }
#toast.error { background:rgba(248,81,73,0.15); color:var(--red); border:1px solid var(--red); }

footer { text-align:center; padding:20px; color:var(--text-muted); font-size:12px; border-top:1px solid var(--border-std); margin-top:24px; }
.loading { text-align:center; padding:40px; color:var(--text-muted); font-size:14px; }

/* Modal / Edit popup */
.modal-overlay {
  display:none; position:fixed; top:0; left:0; width:100%; height:100%;
  background:rgba(0,0,0,0.55); z-index:1000; align-items:center; justify-content:center;
}
.modal-overlay.show { display:flex; animation:modalIn 0.2s ease; }
@keyframes modalIn { from { opacity:0; } to { opacity:1; } }
.modal-box {
  background:var(--bg-surface); border:1px solid var(--border-std); border-radius:var(--radius);
  padding:24px; max-width:520px; width:90%; box-shadow:0 12px 40px rgba(0,0,0,0.4);
}
.modal-box h2 { font-size:16px; font-weight:600; margin-bottom:16px; color:var(--text-primary); }
.modal-box label { font-size:12px; font-weight:500; color:var(--text-muted); display:block; margin-bottom:4px; margin-top:12px; }
.modal-box input, .modal-box textarea {
  width:100%; background:var(--bg-elevated); border:1px solid var(--border-std); border-radius:var(--radius-sm);
  color:var(--text-primary); padding:8px 12px; font-size:13px; font-family:inherit;
  box-sizing:border-box;
}
.modal-box textarea { min-height:80px; resize:vertical; }
.modal-actions { display:flex; gap:10px; justify-content:flex-end; margin-top:16px; }
.modal-actions button { padding:8px 18px; border-radius:var(--radius-sm); font-size:13px; cursor:pointer; font-family:inherit; border:none; }
.modal-actions .btn-cancel { background:var(--bg-elevated); color:var(--text-secondary); }
.modal-actions .btn-cancel:hover { background:var(--border-std); }
.modal-actions .btn-save { background:var(--accent-bg); color:white; }
.modal-actions .btn-save:hover { background:var(--accent-hover); }

.edit-rule-btn {
  background:transparent; border:1px solid var(--border-std); border-radius:var(--radius-sm);
  color:var(--accent); font-size:11px; padding:3px 10px; cursor:pointer; font-family:inherit;
  vertical-align:middle; transition:all 0.15s;
}
.edit-rule-btn:hover { background:var(--accent-bg); color:white; border-color:var(--accent-bg); }

/* Language switch */
.lang-switch {
  background:transparent; border:1px solid var(--border-std); border-radius:var(--radius-sm);
  color:var(--text-secondary); font-size:12px; padding:4px 10px; cursor:pointer; font-family:inherit;
}
.lang-switch:hover { border-color:var(--accent); color:var(--accent); }

.refresh-btn {
  background:transparent; border:1px solid var(--border-std); border-radius:var(--radius-sm);
  color:var(--text-muted); font-size:11px; padding:2px 8px; cursor:pointer; font-family:inherit;
}
.refresh-btn:hover { border-color:var(--accent); color:var(--accent); }
</style>
</head>
<body>

<header>
  <div style="display:flex;align-items:center;gap:10px;">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="4" y="3" width="16" height="18" rx="3" stroke="#7c7cff" stroke-width="1.5"/><line x1="8" y1="8" x2="16" y2="8" stroke="#7c7cff" stroke-width="1.5"/><line x1="8" y1="12" x2="16" y2="12" stroke="#7c7cff" stroke-width="1.5"/><line x1="8" y1="16" x2="13" y2="16" stroke="#7c7cff" stroke-width="1.5"/></svg>
    <h1 data-i18n="title">Canon-Mnemonic-Guard Dashboard</h1>
    <span class="badge">v''' + CMG_VERSION + '''</span>
  </div>
  <div style="display:flex;align-items:center;gap:12px;">
    <button class="lang-switch" onclick="switchLang()" id="langBtn" data-i18n="lang">English</button>
    <span class="badge" id="clock">—</span>
    <button class="theme-btn" onclick="toggleTheme()" id="themeBtn" data-i18n="theme_light">☀ 亮色</button>
  </div>
</header>

<div class="container">
  <div class="tabs">
    <button class="tab-btn active" data-tab="rules" onclick="switchTab('rules')">规则库</button>
    <button class="tab-btn" data-tab="config" onclick="switchTab('config')">引擎配置</button>
    <button class="tab-btn" data-tab="add" onclick="switchTab('add')">添加规则</button>
  </div>

  <!-- Rules Tab -->
  <div class="tab-panel active" id="tab-rules">
    <div class="stats" id="stats"></div>
    <div class="trend-card" id="trendCard" style="display:none">
      <canvas id="trendCanvas" height="160"></canvas>
    </div>
    <div class="toolbar">
      <input type="text" id="search" placeholder="搜索规则 ID 或关键词…" oninput="renderRules()">
      <select id="typeFilter" onchange="renderRules()">
        <option value="">全部类型</option>
        <option value="ban" data-i18n="ban_label">ban · 禁止项</option>
        <option value="gap" data-i18n="gap_label">gap · 缺失项</option>
        <option value="lazy" data-i18n="lazy_label">lazy · 偷懒项</option>
        <option value="meta" data-i18n="meta_label">meta · 元规则</option>
      </select>
      <span style="font-size:12px;color:var(--text-muted)" id="rowCount"></span>
      <button class="export-btn" onclick="exportRules()" data-i18n="export_btn">⬇ 导出</button>
      <button class="export-btn" id="batchToggle" onclick="toggleBatchMode()" data-i18n="batch_btn">☐ 批量</button>
      <span id="batchActions" style="display:none">
        <span class="export-btn" id="selectAllBtn" onclick="toggleSelectAllBtn()" style="cursor:pointer" data-i18n="select_all">☐ 全选</span>
        <button class="export-btn" onclick="batchDelete()" style="color:var(--red);border-color:var(--red);margin-left:8px">批量删除</button>
      </span>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th style="width:36px"></th>
          <th data-sort="id" onclick="sortRules('id')" style="width:32%">规则 ID</th>
          <th data-sort="type" onclick="sortRules('type')" style="width:8%">类型</th>
          <th data-sort="hit_count" onclick="sortRules('hit_count')" class="sort-desc" style="width:7%">命中</th>
          <th data-sort="false_rate" onclick="sortRules('false_rate')" style="width:8%">误报率</th>
          <th data-sort="days_since" onclick="sortRules('days_since')" style="width:9%">最后触发</th>
          <th data-i18n-col="col_keywords">关键词</th>
        </tr></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </div>

  <!-- Add Rule Tab -->
  <div class="tab-panel" id="tab-add">
    <div style="max-width:600px;margin:0 auto;">
      <div class="config-card" style="margin-bottom:0;">
        <h3 data-i18n="add_rule">添加新规则</h3>
        <div style="display:flex;flex-direction:column;gap:12px;margin-top:8px;">
          <div>
            <label data-i18n="add_type" style="font-size:12px;font-weight:500;color:var(--text-muted);display:block;margin-bottom:4px;">规则类型</label>
            <select id="newType" class="notice-select" style="width:100%;">
              <option value="ban" data-i18n="ban_label">ban · 禁止项</option>
              <option value="gap" data-i18n="gap_label">gap · 缺失项</option>
              <option value="lazy" data-i18n="lazy_label">lazy · 偷懒项</option>
              <option value="meta" data-i18n="meta_label">meta · 元规则</option>
            </select>
          </div>
          <div>
            <label data-i18n="add_id" style="font-size:12px;font-weight:500;color:var(--text-muted);display:block;margin-bottom:4px;">规则 ID</label>
            <input id="newId" type="text" class="toolbar-input" style="width:100%;" data-i18n-ph="add_id_ph" placeholder="rule_xxx（英文+下划线）">
          </div>
          <div>
            <label data-i18n="add_keywords" style="font-size:12px;font-weight:500;color:var(--text-muted);display:block;margin-bottom:4px;">关键词（逗号分隔）</label>
            <input id="newKeywords" type="text" class="toolbar-input" style="width:100%;" data-i18n-ph="modal_kw_ph" placeholder="关键词1, 关键词2, 关键词3">
          </div>
          <div>
            <label data-i18n="add_desc" style="font-size:12px;font-weight:500;color:var(--text-muted);display:block;margin-bottom:4px;">规则描述</label>
            <textarea id="newDesc" class="toolbar-input" style="width:100%;min-height:100px;resize:vertical;" data-i18n-ph="modal_desc_ph" placeholder="描述这条规则禁止/要求什么行为…"></textarea>
          </div>
        </div>
        <div style="margin-top:16px;display:flex;align-items:center;gap:12px;">
          <button class="save-btn" onclick="addRule()" data-i18n="add_btn">添加规则</button>
          <span style="font-size:12px;color:var(--text-muted);" id="addMsg"></span>
        </div>
      </div>
    </div>
  </div>

  <!-- Config Tab -->
  <div class="tab-panel" id="tab-config">
    <div class="config-grid">
      <div class="config-card">
        <h3>核心 Hook 开关</h3>
        <div id="core-hooks"></div>
      </div>
      <div class="config-card">
        <h3>扩展 Hook 开关</h3>
        <div id="extra-hooks"></div>
        <div style="margin-top:12px;">
          <button class="save-btn" id="saveBtn3" onclick="saveConfig()" disabled>保存配置</button>
          <span style="font-size:12px;color:var(--text-muted);margin-left:8px;display:none" id="dirtyHint3">有未保存的修改</span>
        </div>
      </div>
      <div class="config-card">
        <h3 data-i18n="companion_title">推荐配套 Skill</h3>
        <div style="padding:8px 0;">
          <div class="hook-row" style="margin-bottom:8px">
            <div><span class="name" data-i18n="task_rec_label">自动推荐配套工具</span><div class="desc" data-i18n="task_rec_desc" style="font-size:11px;color:var(--text-muted);margin-top:2px;">检测打包/写代码/调试等任务时自动建议 ralph-loop、TDD 等工具</div></div>
            <button class="toggle" id="taskRecToggle" data-hook="task_recommendations" onclick="toggleTaskRec()"></button>
          </div>
          <div style="border-top:1px solid var(--border-subtle);padding-top:8px;margin-bottom:4px;display:flex;justify-content:space-between;align-items:center">
            <span style="font-size:11px;color:var(--text-muted);font-weight:500" data-i18n="skill_list_label">已安装 Skill 状态</span>
            <button class="refresh-btn" onclick="refreshCompanion()" data-i18n="refresh" title="刷新扫描">↻ 刷新</button>
          </div>
          <div id="companion-list"></div>
        </div>
        <div style="margin-top:12px;">
          <button class="save-btn" id="saveBtn2" onclick="saveConfig()" disabled>保存配置</button>
          <span style="font-size:12px;color:var(--text-muted);margin-left:8px;display:none" id="dirtyHint2">有未保存的修改</span>
        </div>
      </div>
      <div class="config-card">
        <h3>拦截通知</h3>
        <div style="padding:8px 0;">
          <select class="notice-select" id="noticeMode" onchange="markDirty('notice')">
            <option value="silent" data-i18n="notice_silent">silent · 静默替换</option>
            <option value="visible" data-i18n="notice_visible">visible · 前置拦截说明</option>
          </select>
          <div data-i18n="intercept_desc" style="font-size:11px;color:var(--text-muted);margin-top:8px;">silent: 违规内容直接替换 · visible: 用户可见拦截详情</div>
        </div>
        <div style="margin-top:16px;">
          <button class="save-btn" id="saveBtn" onclick="saveConfig()" disabled>保存配置</button>
          <span style="font-size:12px;color:var(--text-muted);margin-left:8px;display:none" id="dirtyHint">有未保存的修改</span>
        </div>
      </div>
    </div>
  </div>
</div>

<div id="toast"></div>

<!-- Edit Rule Modal -->
<div class="modal-overlay" id="editModal">
  <div class="modal-box">
    <h2 id="modalTitle" data-i18n="edit_title">编辑规则</h2>
    <div><label data-i18n="modal_id">规则 ID</label><input id="modalId" disabled style="opacity:0.6;cursor:not-allowed"></div>
    <div><label data-i18n="add_type">规则类型</label><select id="modalType" class="notice-select" style="width:100%;">
      <option value="ban" data-i18n="ban_label">ban · 禁止项</option>
      <option value="gap" data-i18n="gap_label">gap · 缺失项</option>
      <option value="lazy" data-i18n="lazy_label">lazy · 偷懒项</option>
      <option value="meta" data-i18n="meta_label">meta · 元规则</option>
    </select></div>
    <div><label data-i18n="modal_keywords">关键词（逗号分隔）</label><input id="modalKeywords" data-i18n-ph="modal_kw_ph" placeholder="关键词1, 关键词2, 关键词3"></div>
    <div><label data-i18n="modal_desc">规则描述</label><textarea id="modalDesc" data-i18n-ph="modal_desc_ph" placeholder="描述这条规则禁止/要求什么行为…"></textarea></div>
    <div class="modal-actions">
      <button class="btn-cancel" onclick="closeModal()" data-i18n="cancel">取消</button>
      <button class="btn-save" onclick="saveEdit()" data-i18n="save">保存</button>
    </div>
  </div>
</div>

<footer><span data-i18n="footer">三省引擎</span> v''' + CMG_VERSION + ''' · localhost:''' + str(PORT) + '''</footer>

<script>
var rulesData = [];
var configData = {};
var origConfig = {};
var origHooks = {};
var origTaskRec = true;
var origNotice = 'silent';
var taskRecEnabled = true;
var companionData = [];
var origCompanion = {};
var sortKey = 'hit_count', sortDir = -1;

function falseRate(r) { return r.hit_count ? (r.false_positives/r.hit_count*100).toFixed(1) : '0.0'; }
function daysLabel(r) {
  if (r.days_since === null || r.days_since === undefined) return '—';
  if (r.days_since > 180) return '<span class="stale">'+r.days_since+'d</span>';
  return r.days_since+'d';
}

// ── Tab switching ──
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(function(b){
    b.classList.toggle('active', b.getAttribute('data-tab') === name);
  });
  document.getElementById('tab-rules').classList.toggle('active', name==='rules');
  document.getElementById('tab-config').classList.toggle('active', name==='config');
  document.getElementById('tab-add').classList.toggle('active', name==='add');
  if (name === 'config') { renderConfig(); renderCompanion(); }
 }

 function renderCompanion() {
   var html = '';
   companionData.forEach(function(s){
     var statusTxt = s.installed ? '✓' : '✗';
     var statusColor = s.installed ? 'background:rgba(63,185,80,0.15);color:var(--green)' : 'background:rgba(248,81,73,0.1);color:var(--red)';
     html += '<div class="hook-row">'+
       '<div style="flex:1;min-width:0">'+
         '<span class="name">'+ (currentLang==='en' ? s.name_en : s.name_zh) +'</span>'+
         '<div class="desc" style="font-size:11px;color:var(--text-muted);margin-top:2px">'+
           (currentLang==='en' ? s.desc_en : s.desc_zh)+'</div>'+
       '</div>'+
       '<span style="font-size:10px;padding:1px 8px;border-radius:999px;'+statusColor+';font-weight:500;flex-shrink:0;margin-left:8px">'+statusTxt+'</span>'+
     '</div>';
   });
   document.getElementById('companion-list').innerHTML = html;
 }

 function toggleCompanion(id) {
 var s = companionData.find(function(c){return c.id === id;});
 if (!s || !s.installed) return;
 s.enabled = !s.enabled;
 renderCompanion();
 markDirty('companion');
 }

// ── Rules rendering ──
function renderRules() {
  var q = (document.getElementById('search').value||'').toLowerCase();
  var tf = document.getElementById('typeFilter').value||'';
  var rows = rulesData.filter(function(r){
    if (tf && r.type !== tf) return false;
    if (q && !r.id.toLowerCase().includes(q) && !(r.keywords||[]).some(function(k){return k.toLowerCase().includes(q)})) return false;
    return true;
  });
  rows.sort(function(a,b){
    var va = a[sortKey], vb = b[sortKey];
    if (sortKey === 'days_since') { va = va != null ? va : 99999; vb = vb != null ? vb : 99999; }
    if (sortKey === 'false_rate') { va = parseFloat(falseRate(a)); vb = parseFloat(falseRate(b)); }
    if (va < vb) return -sortDir; if (va > vb) return sortDir; return 0;
  });
  var html = '';
  // Virtual scroll: only render visible rows
  var ROW_H = 37, BUF = 5;
  var wrap = document.querySelector('.table-wrap');
  var st = wrap ? wrap.scrollTop : 0;
  var vc = wrap ? Math.ceil(wrap.clientHeight / ROW_H) + BUF : rows.length;
  var start = Math.max(0, Math.floor(st / ROW_H) - BUF);
  var end = Math.min(rows.length, start + vc + BUF * 2);
  if (start > 0) html += '<tr style="height:'+(start*ROW_H)+'px"><td colspan="7"></td></tr>';
  for (var i = start; i < end; i++) {
    var r = rows[i], fr = parseFloat(falseRate(r));
    html += '<tr id="row-'+r.id+'" class="clickable" data-rid="'+r.id+'" onclick="toggleDetail(this.dataset.rid)">'+
      '<td class="del-col" style="text-align:center">'+
        '<button class="del-btn" data-rid="'+r.id+'" onclick="deleteRule(this.dataset.rid)" title="'+t('delete_title')+'">🗑</button>'+
        '<input type="checkbox" class="row-cb" data-rid="'+r.id+'" onclick="event.stopPropagation()" style="cursor:pointer;display:none">'+
      '</td>'+
      '<td style="font-family:JetBrains Mono,monospace;font-size:12px;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+r.id+'">'+r.id+'</td>'+
      '<td><span class="type-badge type-'+r.type+'">'+r.type+'</span></td>'+
      '<td>'+r.hit_count+'</td>'+
      '<td'+(fr>30?' class="false-high"':'')+'>'+falseRate(r)+'%</td>'+
      '<td>'+daysLabel(r)+'</td>'+
      '<td class="keyword-cell" style="color:var(--text-muted);font-size:12px;max-width:200px;overflow:visible;text-overflow:ellipsis;white-space:nowrap">'+(r.keywords||[]).slice(0,3).join(', ')+(r.keywords&&r.keywords.length>3?', …<span class="kw-tip">'+(r.keywords||[]).join(' · ')+'</span>':'')+'</td>'+\
    '</tr>'+
      '<tr class="detail-row" id="detail-'+r.id+'"><td colspan="7"><span class="detail-label">'+t('detail_date')+'</span> '+(r.date||'—')+' &nbsp;·&nbsp; <span class="detail-label">'+t('detail_last')+'</span> '+(r.last_triggered||'—')+' &nbsp;·&nbsp; <span class="detail-label">'+t('detail_fp')+'</span> '+r.false_positives+'/'+r.hit_count+' &nbsp;·&nbsp; <span class="detail-label">'+t('detail_source')+'</span> '+(r.source||'—')+' &nbsp; <button class="edit-rule-btn" onclick="event.stopPropagation();openEditModal(this.closest(&apos;tr&apos;).previousElementSibling.dataset.rid)" title="'+t('edit_title')+'">'+t('edit_btn')+'</button></td></tr>';
  }
  if (end < rows.length) html += '<tr style="height:'+((rows.length-end)*ROW_H)+'px"><td colspan="7"></td></tr>';
  document.getElementById('tbody').innerHTML = html;
  document.getElementById('rowCount').textContent = rows.length+' / '+rulesData.length+' '+t('row_unit');
  document.getElementById('clock').textContent = new Date().toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  if (batchMode) { applyBatchMode(true); document.querySelectorAll('.row-cb').forEach(function(cb){ cb.checked = !!selectedIds[cb.dataset.rid]; }); }
}

// Virtual scroll listener
document.addEventListener('DOMContentLoaded', function(){
  var w = document.querySelector('.table-wrap');
  if (w) w.addEventListener('scroll', function(){ renderRules(); });
});

function sortRules(key) {
  if (sortKey === key) sortDir *= -1; else { sortKey = key; sortDir = -1; }
  // Save expanded detail rows
  var expanded = [];
  document.querySelectorAll('.detail-row.show').forEach(function(r){ expanded.push(r.id.replace('detail-','')); });
  // Update sort indicator classes
  document.querySelectorAll('th').forEach(function(th){ th.classList.remove('sort-asc','sort-desc'); });
  var th = document.querySelector('th[data-sort="'+key+'"]');
  if (th) th.classList.add(sortDir===1?'sort-asc':'sort-desc');
  // Re-render rules
  renderRules();
  // Restore expanded details
  expanded.forEach(function(id){ var d = document.getElementById('detail-'+id); if(d) d.classList.add('show'); });
}

// ── Stats cards ──
function renderStats(s) {
  var ban = rulesData.filter(function(r){return r.type==='ban'}).length;
  var gap = rulesData.filter(function(r){return r.type==='gap'}).length;
  var lazy = rulesData.filter(function(r){return r.type==='lazy'}).length;
  var hits = rulesData.reduce(function(a,r){return a+r.hit_count;},0);
  var hf = rulesData.filter(function(r){return parseFloat(falseRate(r))>30;}).length;
  var st = rulesData.filter(function(r){return r.days_since!=null&&r.days_since>180;}).length;
  document.getElementById('stats').innerHTML =
    '<div class="stat-card"><span class="label">'+t('stats_total')+'</span><span class="value">'+rulesData.length+'</span><span class="sub" style="line-height:1.6"><span>'+t('type_ban')+' '+ban+' · '+t('type_gap')+' '+gap+' · '+t('type_lazy')+' '+lazy+'</span>'+(rulesData.some(function(r){return r.type==='meta'})?'<br><span>'+t('type_meta')+' '+(rulesData.filter(function(r){return r.type==='meta'}).length)+'</span>':'')+'</span></div>'+
    '<div class="stat-card"><span class="label">'+t('stats_hits')+'</span><span class="value">'+hits+'</span><span class="sub">'+t('stats_hits_sub')+'</span></div>'+
    '<div class="stat-card accent"><span class="label">'+t('stats_intercept')+'</span><span class="value">'+s.intercept_count+'</span><span class="sub">'+t('stats_intercept_sub')+'</span></div>'+
    '<div class="stat-card"><span class="label">'+t('stats_errors')+'</span><span class="value">'+s.error_count+'</span><span class="sub">'+t('stats_errors_sub')+'</span></div>'+
    '<div class="stat-card warn"><span class="label">'+t('stats_high_fp')+'</span><span class="value">'+hf+'</span><span class="sub">'+t('stats_high_fp_sub')+'</span></div>'+
    '<div class="stat-card"><span class="label">'+t('stats_stale')+'</span><span class="value">'+st+'</span><span class="sub">'+t('stats_stale_sub')+'</span></div>';
}

// ── Config rendering ──
function renderConfig() {
  if (!configData.hooks) return;
  var coreHooks = ['pre_tool_call','pre_llm_call','post_llm_call','transform_llm_output'];
  var coreHtml = '', extraHtml = '';
  Object.keys(configData.hooks).forEach(function(h){
    var row = '<div class="hook-row"><div><span class="name">'+h+'</span></div><button class="toggle'+(configData.hooks[h]?' on':'')+'" data-hook="'+h+'" onclick="toggleHook(this.dataset.hook)"></button></div>';
    if (coreHooks.indexOf(h) >= 0) coreHtml += row; else extraHtml += row;
  });
  document.getElementById('core-hooks').innerHTML = coreHtml || '<div style="color:var(--text-muted);font-size:12px">无</div>';
  document.getElementById('extra-hooks').innerHTML = extraHtml || '<div style="color:var(--text-muted);font-size:12px">无</div>';
  document.getElementById('noticeMode').value = configData.intercept_notice || 'silent';
  // Task recommendation toggle
  taskRecEnabled = configData.task_recommendations !== false;
  var tgl = document.getElementById('taskRecToggle');
  if (tgl) tgl.classList.toggle('on', taskRecEnabled);
  // Capture per-module originals on first load
  if (Object.keys(origHooks).length === 0) {
    origHooks = JSON.parse(JSON.stringify(configData.hooks));
    origTaskRec = taskRecEnabled;
    origNotice = configData.intercept_notice || 'silent';
  }
}

function toggleHook(name) {
  configData.hooks[name] = !configData.hooks[name];
  renderConfig();
  markDirty('hooks');
}

function refreshCompanion() {
  fetch('/api/companion').then(function(r){return r.json()}).then(function(d){
    companionData = d;
    renderCompanion();
  });
}

function toggleTaskRec() {
  taskRecEnabled = !taskRecEnabled;
  configData.task_recommendations = taskRecEnabled;
  var tgl = document.getElementById('taskRecToggle');
  if (tgl) tgl.classList.toggle('on', taskRecEnabled);
  markDirty('taskrec');
}

function markDirty(module) {
  // Sync current values
  if (module !== 'notice') configData.intercept_notice = origNotice;
  if (module !== 'taskrec') configData.task_recommendations = origTaskRec;
  if (module !== 'hooks') configData.hooks = JSON.parse(JSON.stringify(origHooks));

  if (module === 'notice') {
    configData.intercept_notice = document.getElementById('noticeMode').value;
  }
  if (module === 'taskrec') {
    configData.task_recommendations = taskRecEnabled;
  }

  var hooksChanged = JSON.stringify(configData.hooks) !== JSON.stringify(origHooks);
  var noticeChanged = configData.intercept_notice !== origNotice;
  var taskRecChanged = configData.task_recommendations !== origTaskRec;

  document.getElementById('saveBtn').disabled = !(noticeChanged);
  document.getElementById('saveBtn2').disabled = !(taskRecChanged);
  document.getElementById('saveBtn3').disabled = !(hooksChanged);
  document.getElementById('dirtyHint').style.display = (noticeChanged) ? 'inline' : 'none';
  document.getElementById('dirtyHint2').style.display = (taskRecChanged) ? 'inline' : 'none';
  document.getElementById('dirtyHint3').style.display = (hooksChanged) ? 'inline' : 'none';
}

function saveConfig() {
  var payload = {};
  var hooksChanged = JSON.stringify(configData.hooks) !== JSON.stringify(origHooks);
  var noticeChanged = configData.intercept_notice !== origNotice;
  var taskRecChanged = configData.task_recommendations !== origTaskRec;
  if (hooksChanged) payload.hooks = configData.hooks;
  if (noticeChanged) payload.intercept_notice = configData.intercept_notice;
  if (taskRecChanged) payload.task_recommendations = configData.task_recommendations;

  fetch('/api/config', {method:'POST', body:JSON.stringify(payload)})
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (d.ok) {
        origHooks = JSON.parse(JSON.stringify(configData.hooks));
        origNotice = configData.intercept_notice;
        origTaskRec = configData.task_recommendations;
        origCompanion = JSON.parse(JSON.stringify(configData.companion_skills||{}));
        markDirty('none');
        toast(t('config_saved'), 'success');
      }
      else { toast(t('save_failed')+': '+d.error, 'error'); }
    })
    .catch(function(e){ toast(t('net_error')+': '+e.message, 'error'); });
}

function toast(msg, type) {
  var t = document.getElementById('toast');
  t.textContent = msg; t.className = type+' show';
  setTimeout(function(){ t.classList.remove('show'); }, 2500);
}

// ── Add Rule ──
function addRule() {
  var data = {
    type: document.getElementById('newType').value,
    id: document.getElementById('newId').value.trim(),
    keywords: document.getElementById('newKeywords').value.split(',').map(function(k){return k.trim();}).filter(Boolean),
    description: document.getElementById('newDesc').value.trim()
  };
  if (!data.id || !data.keywords.length) {
    document.getElementById('addMsg').textContent = t('add_prompt');
    return;
  }
  fetch('/api/rules', {method:'POST', body:JSON.stringify(data)})
    .then(function(r){return r.json();})
    .then(function(d){
      var el = document.getElementById('addMsg');
      if (d.ok) {
        el.textContent = t('add_success') + ': ' + data.id;
        el.style.color = 'var(--green)';
        document.getElementById('newId').value = '';
        document.getElementById('newKeywords').value = '';
        document.getElementById('newDesc').value = '';
        // Reload rules
        fetch('/api/rules').then(function(r){return r.json()}).then(function(d2){ rulesData = d2; renderRules(); });
      } else {
        el.textContent = t('add_failed') + ': ' + (d.error||t('unknown'));
        el.style.color = 'var(--red)';
      }
    })
    .catch(function(e){
      document.getElementById('addMsg').textContent = t('net_error') + ': ' + e.message;
      document.getElementById('addMsg').style.color = 'var(--red)';
    });
}

// ── Delete Rule ──
function deleteRule(id) {
  if (!confirm(t('delete_title') + ': ' + id + ' ?')) return;
  var row = document.getElementById('row-'+id);
  if (row) {
    row.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
    row.style.opacity = '0';
    row.style.transform = 'translateX(-20px)';
  }
  fetch('/api/rules', {method:'DELETE', body:JSON.stringify({id:id})})
    .then(function(r){return r.json();})
    .then(function(d){
      if (d.ok) {
        if (row) setTimeout(function(){ row.remove(); }, 200);
        rulesData = rulesData.filter(function(r2){return r2.id !== id;});
        renderRules();
        toast(t('rule_deleted')+': '+id, 'success');
      } else {
        if (row) { row.style.opacity = '1'; row.style.transform = 'translateX(0)'; }
        toast(t('delete_failed')+': '+(d.error||t('unknown')), 'error');
      }
    })
    .catch(function(e){
      if (row) { row.style.opacity = '1'; row.style.transform = 'translateX(0)'; }
      toast(t('net_error')+': '+e.message, 'error');
    });
}

// ── Detail expand ──
function toggleDetail(id) {
  var row = document.getElementById('detail-'+id);
  if (row) row.classList.toggle('show');
}

// ── Rule Edit Modal ──
var editingRuleId = null;

function openEditModal(id) {
  var r = rulesData.find(function(r2){return r2.id === id;});
  if (!r) return;
  editingRuleId = id;
  document.getElementById('modalId').value = id;
  document.getElementById('modalType').value = r.type || 'ban';
  document.getElementById('modalKeywords').value = (r.keywords||[]).join(', ');
  document.getElementById('modalDesc').value = r.description || '';
  document.getElementById('editModal').classList.add('show');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('editModal').classList.remove('show');
  document.body.style.overflow = '';
  editingRuleId = null;
}

function saveEdit() {
  if (!editingRuleId) return;
  var kwRaw = document.getElementById('modalKeywords').value;
  var keywords = kwRaw.split(',').map(function(k){return k.trim();}).filter(Boolean);
  var desc = document.getElementById('modalDesc').value.trim();
  var newType = document.getElementById('modalType').value;
  fetch('/api/rules', {
    method:'PUT',
    body:JSON.stringify({id:editingRuleId, keywords:keywords, description:desc, type:newType})
  })
  .then(function(r){return r.json();})
  .then(function(d){
    if (d.ok) {
      closeModal();
      // Refresh rules
      fetch('/api/rules').then(function(r){return r.json();}).then(function(d2){
        rulesData = d2;
        renderRules();
      });
      toast(t('rule_updated')+': '+editingRuleId, 'success');
    } else {
      toast(t('update_failed')+': '+(d.error||t('unknown')), 'error');
    }
  })
  .catch(function(e){ toast(t('net_error')+': '+e.message, 'error'); });
}

// Close modal on overlay click
document.getElementById('editModal').addEventListener('click', function(e){
  if (e.target === this) closeModal();
});

// ── Language Switching ──
// Keys use Chinese text as-is. New UI text = new key auto-works in zh.
// Only add English translation. Audit runs after switch — CJK in en mode = red outline.
var I18N = {
  zh: {
    title:'三省引擎仪表盘', lang:'English', rules_tab:'规则库', config_tab:'引擎配置', add_tab:'添加规则',
    add_rule:'添加新规则', add_type:'规则类型', add_id:'规则 ID', add_keywords:'关键词（逗号分隔）',
    add_desc:'规则描述', add_btn:'添加规则', add_id_ph:'rule_xxx（英文+下划线）',
    modal_id:'规则 ID', modal_keywords:'关键词（逗号分隔）', modal_desc:'规则描述',
    cancel:'取消', save:'保存', edit_title:'编辑规则',
    search_placeholder:'搜索规则 ID 或关键词…', all_types:'全部类型',
    ban_label:'ban · 禁止项', gap_label:'gap · 缺失项', lazy_label:'lazy · 偷懒项', meta_label:'meta · 元规则',
    type_ban:'禁止', type_gap:'缺失', type_lazy:'偷懒', type_meta:'元规则',
    stats_total:'规则总数', stats_hits:'累计命中', stats_intercept:'系统拦截',
    stats_errors:'错误记录', stats_high_fp:'高误报', stats_stale:'长期未触发',
    stats_hits_sub:'规则触发总次数', stats_intercept_sub:'intercept_log.jsonl',
    stats_errors_sub:'errors.jsonl', stats_high_fp_sub:'误报率 >30%', stats_stale_sub:'>180 天',
    col_id:'规则 ID', col_type:'类型', col_hits:'命中', col_false:'误报率',
    col_days:'最后触发', col_keywords:'关键词',
    delete_title:'删除规则', core_hooks:'核心 Hook 开关', extra_hooks:'扩展 Hook 开关',
    task_rec:'任务推荐', task_rec_desc:'检测打包/写代码/调试等任务时自动建议 ralph-loop、TDD 等工具',
    task_rec_label:'自动推荐配套工具', intercept_notice:'拦截通知',
    companion_title:'推荐配套 Skill',
    skill_list_label:'已安装 Skill 状态', refresh:'↻ 刷新',
    notice_silent:'silent · 静默替换', notice_visible:'visible · 前置拦截说明',
    notice_silent_desc:'silent: 违规内容直接替换', notice_visible_desc:'visible: 用户可见拦截详情',
    intercept_desc:'silent: 违规内容直接替换 · visible: 用户可见拦截详情',
    save_config:'保存配置', dirty_hint:'有未保存的修改',
    add_success:'规则已添加', add_prompt:'请填写规则 ID 和关键词',
    config_saved:'配置已保存，重启 Hermes 生效',
    detail_date:'创建日期', detail_last:'最后触发', detail_fp:'误报', detail_source:'来源',
    edit_btn:'✏ 编辑', footer:'三省引擎', row_unit:'条',
    modal_kw_ph:'关键词1, 关键词2, 关键词3', modal_desc_ph:'描述这条规则禁止/要求什么行为…',
    rule_deleted:'已删除', rule_updated:'已更新', save_failed:'保存失败',
    delete_failed:'删除失败', update_failed:'更新失败', net_error:'网络错误',
    unknown:'未知', add_failed:'添加失败', no_recent_intercepts:'近30天无拦截记录', theme_light:'☀ 亮色', theme_dark:'🌙 暗色', export_btn:'⬇ 导出', batch_btn:'☐ 批量', select_all:'☐ 全选', deselect_all:'取消全选',
  },
  en: {
    title:'Canon-Mnemonic-Guard Dashboard', lang:'中文', rules_tab:'Rules', config_tab:'Config', add_tab:'Add Rule',
    add_rule:'Add New Rule', add_type:'Rule Type', add_id:'Rule ID', add_keywords:'Keywords (comma-separated)',
    add_desc:'Description', add_btn:'Add Rule', add_id_ph:'rule_xxx (letters+underscore)',
    modal_id:'Rule ID', modal_keywords:'Keywords (comma-separated)', modal_desc:'Description',
    cancel:'Cancel', save:'Save', edit_title:'Edit Rule',
    search_placeholder:'Search rule ID or keywords…', all_types:'All Types',
    ban_label:'ban · Prohibited', gap_label:'gap · Missing', lazy_label:'lazy · Lazy', meta_label:'meta · Meta-Rule',
    type_ban:'Prohibited', type_gap:'Missing', type_lazy:'Lazy', type_meta:'Meta',
    stats_total:'Total Rules', stats_hits:'Total Hits', stats_intercept:'Intercepts',
    stats_errors:'Error Records', stats_high_fp:'High False Pos.', stats_stale:'Stale (>180d)',
    stats_hits_sub:'Rule trigger count', stats_intercept_sub:'intercept_log.jsonl',
    stats_errors_sub:'errors.jsonl', stats_high_fp_sub:'False rate >30%', stats_stale_sub:'>180 days',
    col_id:'Rule ID', col_type:'Type', col_hits:'Hits', col_false:'False Rate',
    col_days:'Last Hit', col_keywords:'Keywords',
    delete_title:'Delete Rule', core_hooks:'Core Hooks', extra_hooks:'Extended Hooks',
    task_rec:'Task Recs', task_rec_desc:'Auto-suggest ralph-loop, TDD etc. on build/code/debug tasks',
    task_rec_label:'Auto-recommend tools', intercept_notice:'Intercept Notice',
    companion_title:'Companion Skills',
    skill_list_label:'Installed Skills', refresh:'↻ Refresh',
    notice_silent:'silent · Silent Replace', notice_visible:'visible · Show Detail',
    notice_silent_desc:'silent: Replace offending content directly', notice_visible_desc:'visible: User sees intercept detail',
    intercept_desc:'silent: Replace offending content directly · visible: User sees intercept detail',
    save_config:'Save Config', dirty_hint:'Unsaved changes',
    add_success:'Rule added', add_prompt:'Please fill rule ID and keywords',
    config_saved:'Config saved, restart Hermes to apply',
    detail_date:'Created', detail_last:'Last Hit', detail_fp:'False Pos.', detail_source:'Source',
    edit_btn:'✏ Edit', footer:'Canon-Mnemonic-Guard', row_unit:'rules',
    modal_kw_ph:'keyword1, keyword2, keyword3', modal_desc_ph:'Describe what this rule prohibits or requires…',
    rule_deleted:'deleted', rule_updated:'updated', save_failed:'Save failed',
    delete_failed:'Delete failed', update_failed:'Update failed', net_error:'Network error',
    unknown:'unknown', add_failed:'Add failed', no_recent_intercepts:'No intercepts in 30 days', theme_light:'☀ Light', theme_dark:'🌙 Dark', export_btn:'⬇ Export', batch_btn:'☐ Batch', select_all:'☐ Select All', deselect_all:'Deselect All',
  }
};
var currentLang = localStorage.getItem('dashboard-lang') || 'zh';

function t(key) { return (I18N[currentLang]||I18N.zh)[key] || key; }

function applyLang() {
  document.querySelectorAll('[data-i18n]').forEach(function(el){
    var key = el.getAttribute('data-i18n');
    var txt = t(key);
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
      el.placeholder = txt;
    } else {
      el.textContent = txt;
    }
  });
  // Handle data-i18n-ph for placeholder-only elements
  document.querySelectorAll('[data-i18n-ph]').forEach(function(el){
    el.placeholder = t(el.getAttribute('data-i18n-ph'));
  });
  // Update tab buttons
  document.querySelectorAll('.tab-btn').forEach(function(b){
    var tab = b.getAttribute('data-tab');
    if (tab === 'rules') b.textContent = t('rules_tab');
    else if (tab === 'config') b.textContent = t('config_tab');
    else if (tab === 'add') b.textContent = t('add_tab');
  });
  // Update search placeholder
  var s = document.getElementById('search');
  if (s) s.placeholder = t('search_placeholder');
  // Update type filter
  var tf = document.getElementById('typeFilter');
  if (tf) {
    tf.options[0].textContent = t('all_types');
    tf.options[1].textContent = t('ban_label');
    tf.options[2].textContent = t('gap_label');
    tf.options[3].textContent = t('lazy_label');
    tf.options[4].textContent = t('meta_label');
  }
  // Update stats (re-render)
  if (rulesData.length) {
    fetch('/api/stats').then(function(r){return r.json();}).then(function(s){ renderStats(s); });
  }
  // Update table headers
  var ths = document.querySelectorAll('th[data-sort]');
  var colMap = {id:'col_id', type:'col_type', hit_count:'col_hits', false_rate:'col_false', days_since:'col_days'};
  ths.forEach(function(th){
    var k = th.getAttribute('data-sort');
    if (colMap[k]) th.childNodes[0] && (th.childNodes[0].textContent = t(colMap[k]));
  });
  // Update non-sortable column headers
  document.querySelectorAll('th[data-i18n-col]').forEach(function(th){
    th.childNodes[0] && (th.childNodes[0].textContent = t(th.getAttribute('data-i18n-col')));
  });
  // Update lang button
  document.getElementById('langBtn').textContent = t('lang');
  // Update add form
  var at = document.getElementById('newType');
  if (at) {
    at.options[0].textContent = t('ban_label');
    at.options[1].textContent = t('gap_label');
    at.options[2].textContent = t('lazy_label');
    at.options[3].textContent = t('meta_label');
  }
  // Update config tab titles if open
  var cards = document.querySelectorAll('#tab-config .config-card h3');
  var cardLabels = [t('core_hooks'), t('extra_hooks'), t('companion_title'), t('intercept_notice')];
  cards.forEach(function(c, i){ if (cardLabels[i]) c.textContent = cardLabels[i]; });
  // Update notice mode select
  var nm = document.getElementById('noticeMode');
  if (nm) {
    nm.options[0].textContent = t('notice_silent');
    nm.options[1].textContent = t('notice_visible');
    var descEl = nm.nextElementSibling;
    if (descEl) descEl.textContent = t('notice_silent_desc');
  }
  // Update task rec label
  var trl = document.querySelector('#tab-config .hook-row .name');
  if (trl) trl.textContent = t('task_rec_label');
  var trd = document.querySelector('#tab-config .hook-row .desc');
  if (trd) trd.textContent = t('task_rec_desc');
  // Update save buttons
  var sbs = document.querySelectorAll('.save-btn');
  sbs.forEach(function(b){ b.textContent = t('save_config'); });
  // Update dirty hints
  var dhs = document.querySelectorAll('[id^=\"dirtyHint\"]');
  dhs.forEach(function(d){ d.textContent = t('dirty_hint'); });
  // Re-render rules + companion to update text
  renderRules();
  renderCompanion();
  localStorage.setItem('dashboard-lang', currentLang);
}

function auditI18n() {
  // Scan for untranslated CJK text in non-data elements
  document.querySelectorAll('[data-i18n]').forEach(function(el){
    if (el.dataset.i18nAudited) return;
    var txt = el.textContent.trim();
    if (txt && /[\u4e00-\u9fff]/.test(txt) && currentLang === 'en') {
      el.style.outline = '2px dashed #f85149';
      el.title = '⚠ Untranslated: ' + el.getAttribute('data-i18n');
      el.dataset.i18nAudited = '1';
    }
  });
}

function switchLang() {
  currentLang = currentLang === 'zh' ? 'en' : 'zh';
  applyLang();
}

// ── Trend Chart ──
function renderTrend(d) {
  var card = document.getElementById('trendCard');
  card.style.display = 'block';
  var maxVal = Math.max.apply(null, d.counts) || 1;
  if (d.counts.every(function(c){return c===0;})) {
    card.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:20px;font-size:13px">'+t('no_recent_intercepts')+'</div>';
    return;
  }
  var canvas = document.getElementById('trendCanvas');
  var ctx = canvas.getContext('2d');
  var dpr = window.devicePixelRatio || 1;
  var w = canvas.parentElement.clientWidth - 32;
  canvas.width = w * dpr; canvas.height = 160 * dpr;
  canvas.style.width = w + 'px'; canvas.style.height = '160px';
  ctx.scale(dpr, dpr);
  var barW = Math.max(4, (w - 60) / d.days.length - 2);
  ctx.strokeStyle = '#30363d'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(40, 20); ctx.lineTo(40, 140); ctx.lineTo(w - 10, 140); ctx.stroke();
  d.counts.forEach(function(c, i){
    var x = 42 + i * (barW + 2), h = Math.max(2, (c / maxVal) * 115);
    var dark = document.documentElement.getAttribute('data-theme') === 'dark';
    ctx.fillStyle = c > 0 ? (dark ? '#7c7cff' : '#5c5cff') : (dark ? '#30363d' : '#e1e4e8');
    ctx.fillRect(x, 140 - h, barW, h);
    if (i % 5 === 0) { ctx.fillStyle = dark ? '#8b949e' : '#656d76'; ctx.font = '9px Inter'; ctx.textAlign = 'center'; ctx.fillText('-' + d.days[i] + 'd', x + barW/2, 155); }
  });
  var dark = document.documentElement.getAttribute('data-theme') === 'dark';
  ctx.fillStyle = dark ? '#8b949e' : '#656d76'; ctx.font = '9px Inter'; ctx.textAlign = 'right';
  ctx.fillText(maxVal, 35, 25);
}

// ── Rule Export ──
function exportRules() {
  var a = document.createElement('a');
  a.href = '/api/rules/export';
  a.download = 'cmg-rules-export.zip';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ── Batch Operations ──
var batchMode = false, selectedIds = {}, selectAllOn = false;
function applyBatchMode(show) {
  document.querySelectorAll('.del-btn').forEach(function(b){ b.style.display = show ? 'none' : ''; });
  document.querySelectorAll('.row-cb').forEach(function(cb){ cb.style.display = show ? '' : 'none'; });
}
function toggleBatchMode() {
  batchMode = !batchMode;
  document.getElementById('batchToggle').textContent = batchMode ? '☑ '+t('cancel') : t('batch_btn');
  document.getElementById('batchActions').style.display = batchMode ? 'inline' : 'none';
  if (!batchMode) { selectAllOn = false; selectedIds = {}; document.querySelectorAll('.row-cb').forEach(function(cb){ cb.checked = false; }); }
  applyBatchMode(batchMode);
  renderRules();
}
function toggleSelectAllBtn() {
  selectAllOn = !selectAllOn;
  document.getElementById('selectAllBtn').textContent = selectAllOn ? '☑ 全选' : '☐ 全选';
  var list = window._vrows || rulesData;
  if (selectAllOn) { list.forEach(function(r){ selectedIds[r.id] = true; }); }
  else { selectedIds = {}; }
  document.querySelectorAll('.row-cb').forEach(function(cb){ cb.checked = selectAllOn; });
}
function toggleRowCb(tr) {
  var cb = tr.querySelector('.row-cb');
  if (!cb) return;
  if (window.event && window.event.shiftKey && window._lastBatchIdx >= 0) {
    var cbs = document.querySelectorAll('.row-cb');
    var idx = Array.from(cbs).indexOf(cb);
    var lo = Math.min(window._lastBatchIdx, idx), hi = Math.max(window._lastBatchIdx, idx);
    var state = !cb.checked;
    for (var i = lo; i <= hi; i++) {
      if (cbs[i]) { cbs[i].checked = state; if (state) selectedIds[cbs[i].dataset.rid] = true; else delete selectedIds[cbs[i].dataset.rid]; }
    }
  } else {
    cb.checked = !cb.checked;
    if (cb.checked) selectedIds[cb.dataset.rid] = true; else delete selectedIds[cb.dataset.rid];
  }
  window._lastBatchIdx = Array.from(document.querySelectorAll('.row-cb')).indexOf(cb);
  updateBatchCount();
}
function updateBatchCount() {
  var n = Object.keys(selectedIds).length;
  var btn = document.getElementById('selectAllBtn');
  btn.textContent = n > 0 ? (currentLang==='en'?'Sel ':'已选 ')+n : (selectAllOn?'☑ 全选':'☐ 全选');
}
function batchDelete() {
  var ids = Object.keys(selectedIds);
  if (!ids.length) return;
  if (!confirm(ids.length + ' 条规则将被删除，不可恢复。继续？')) return;
  var done = 0;
  ids.forEach(function(id){
    fetch('/api/rules', {method:'DELETE', body:JSON.stringify({id:id})})
      .then(function(r){return r.json()})
      .then(function(d){ done++; if (done === ids.length) { fetch('/api/rules').then(function(r){return r.json()}).then(function(d2){ rulesData = d2; renderRules(); }); } });
  });
}

// ── Theme ──
function toggleTheme() {
  var html = document.documentElement;
  var isDark = html.getAttribute('data-theme') === 'dark';
  html.setAttribute('data-theme', isDark ? 'light' : 'dark');
  document.getElementById('themeBtn').textContent = isDark ? '☾ 暗色' : '☀ 亮色';
  try { localStorage.setItem('dashboard-theme', isDark ? 'light' : 'dark'); } catch(e) {}
}

// ── Init ──
function loadTheme() {
  try {
    var saved = localStorage.getItem('dashboard-theme');
    if (saved) {
      document.documentElement.setAttribute('data-theme', saved);
      document.getElementById('themeBtn').textContent = saved==='light'?'☾ 暗色':'☀ 亮色';
    } else {
      var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
      document.getElementById('themeBtn').textContent = prefersDark ? '☀ 亮色' : '☾ 暗色';
    }
    // Listen for system theme changes
    if (window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e){
        if (!localStorage.getItem('dashboard-theme')) {
          document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
          document.getElementById('themeBtn').textContent = e.matches ? '☀ 亮色' : '☾ 暗色';
        }
      });
    }
  } catch(e) {}
}

function loadAll() {
  loadTheme();
  fetch('/api/rules').then(function(r){return r.json()}).then(function(d){
    rulesData = d;
    fetch('/api/stats').then(function(r){return r.json()}).then(function(s){
      renderStats(s);
      renderRules();
      applyLang();
    });
  });
  fetch('/api/config').then(function(r){return r.json()}).then(function(d){
    configData = d;
    origConfig = JSON.parse(JSON.stringify(d));
    origHooks = JSON.parse(JSON.stringify(d.hooks||{}));
    origNotice = d.intercept_notice || 'silent';
    origTaskRec = d.task_recommendations !== false;
  });
  fetch('/api/companion').then(function(r){return r.json()}).then(function(d){
    companionData = d;
    origCompanion = {};
    d.forEach(function(s){ origCompanion[s.id] = s.enabled; });
    configData.companion_skills = JSON.parse(JSON.stringify(origCompanion));
  });
  fetch('/api/trend').then(function(r){return r.json()}).then(function(d){
    if (d.days && d.days.length) renderTrend(d);
  });
  setInterval(function(){
    document.getElementById('clock').textContent = new Date().toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  }, 1000);
}
loadAll();
</script>
</body>
</html>'''


# ── HTTP Server ──

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silent

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path == '/':
            self._serve_html(DASHBOARD_HTML())
        elif path == '/api/rules':
            self._serve_json(read_rules())
        elif path == '/api/stats':
            self._serve_json(read_stats())
        elif path == '/api/config':
            self._serve_json(read_config())
        elif path == '/api/companion':
            self._serve_json(read_companion_skills())
        elif path == '/api/rules/export':
            self._serve_zip_export()
        elif path == '/api/trend':
            self._serve_json(read_intercept_trend())
        else:
            self.send_error(404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path == '/api/config':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                new_cfg = json.loads(body)
                ok = write_config(new_cfg)
                self._serve_json({'ok': ok, 'error': None if ok else '写入 config.yaml 失败'})
            except Exception as e:
                self._serve_json({'ok': False, 'error': str(e)})
        elif path == '/api/rules':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                data = json.loads(body)
                ok, msg = write_rule(data)
                self._serve_json({'ok': ok, 'error': None if ok else msg, 'path': msg if ok else None})
            except Exception as e:
                self._serve_json({'ok': False, 'error': str(e)})
        else:
            self.send_error(404)

    def _serve_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def _serve_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _serve_zip_export(self):
        import io, zipfile
        buf = io.BytesIO()
        rules_dir = os.path.join(SR, 'rules')
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            if os.path.isdir(rules_dir):
                for f in glob.glob(os.path.join(rules_dir, '**', '*.md'), recursive=True):
                    zf.write(f, os.path.relpath(f, rules_dir))
        buf.seek(0)
        self.send_response(200)
        self.send_header('Content-Type', 'application/zip')
        self.send_header('Content-Disposition', 'attachment; filename="cmg-rules-export.zip"')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(buf.read())

    def do_PUT(self):
        path = urllib.parse.urlparse(self.path).path
        if path == '/api/rules':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                data = json.loads(body)
                ok, msg = update_rule(data)
                self._serve_json({'ok': ok, 'error': None if ok else msg})
            except Exception as e:
                self._serve_json({'ok': False, 'error': str(e)})
        else:
            self.send_error(404)

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        if path == '/api/rules':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                data = json.loads(body)
                ok, msg = delete_rule(data.get('id', ''))
                self._serve_json({'ok': ok, 'error': None if ok else msg})
            except Exception as e:
                self._serve_json({'ok': False, 'error': str(e)})
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def start():
    server = http.server.HTTPServer(('127.0.0.1', PORT), DashboardHandler)
    print(f'Canon-Mnemonic-Guard Dashboard → http://localhost:{PORT}')
    print(f'按 Ctrl+C 停止')
    # Only auto-open browser in interactive terminal
    if sys.stdout.isatty():
        def _open():
            time.sleep(0.5)
            webbrowser.open(f'http://localhost:{PORT}')
        threading.Thread(target=_open, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')
        server.server_close()


if __name__ == '__main__':
    start()
