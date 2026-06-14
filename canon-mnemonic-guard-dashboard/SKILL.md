---
name: canon-mnemonic-guard-dashboard
description: Use when the user says "dashboard", "仪表盘", "!dashboard", or wants to view/manage Canon-Mnemonic-Guard rules, config, or companion skills. Launches a local web dashboard at localhost:8765 with rule browsing, config management, companion skill monitoring, trend charts, ZIP export, batch operations, and type conversion.
version: 1.1.1
author: L1veSong
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [dashboard, cmg, web, rules, config, companion]
    related_skills: [canon-mnemonic-guard]
---

# Canon-Mnemonic-Guard Dashboard

Web dashboard for Canon-Mnemonic-Guard. Single-file Python HTTP server with embedded HTML/CSS/JS. Zero external web dependencies.

## Quick Start

```bash
pip install pyyaml
python3 server.py
# http://localhost:8765
```

Or `cmg dashboard` or `!dashboard` in Hermes.

## Features

**Rules Tab** — 77+ rules searchable, filterable (ban/gap/lazy/meta), sortable. Expand rows for metadata. Edit keywords/description/type via modal. Delete single or batch.

**Engine Config** — 17 hook toggles + intercept notice + auto-recommend master switch. Companion skills list with real-time install status (✓/✗). Per-module save buttons.

**Trend Chart** — 30-day intercept bar chart below stats cards. Shows empty state when no recent data.

**Export** — Download all rules as ZIP (button in toolbar).

**Batch Operations** — Checkbox select + select-all + batch delete.

**Add Rule** — Form with type selector (ban/gap/lazy/meta).

**Theme & i18n** — Dark/light with system detection. Full zh/en coverage.

**Virtual Scroll** — Table limited to 600px height with sticky header. Only visible rows rendered.

## Architecture

Single-file `server.py`: HTTP server + HTML template + CSS + JS. API endpoints serve JSON to the frontend JS. Rules read/write directly to `~/.hermes/self-reflection/rules/`. Config deep-merges to `~/.hermes/config.yaml`.

## Development Rules

1. Use `patch` for code edits, NEVER `sed` for JS insertion (sed eats closing braces, nests functions inside applyLang).
2. **Backup before every feature** — `cp server.py server.py.bak{N}` before each change.
3. One feature at a time; test each before continuing.
4. If broken, roll back to `.bak` — don't debug forward into corrupted code.
5. JS in Python `'''` strings: use `&apos;` for single quotes, never `\'`.
6. Virtual scroll + DOM rebuild resets state — use data-driven tracking (`selectedIds` object), never DOM-based selection (`querySelectorAll('.row-cb:checked')`).
7. `table-layout:fixed` + new columns breaks layout — consolidate into existing columns.
8. All new i18n strings need BOTH `zh` AND `en` entries.
9. **🔴 `replace_all: true` can eat unrelated CSS** — when the same selector pattern appears twice (`.export-btn { ... }` duplicated), replace_all replaces BOTH including the wrong one. Always use unique surrounding context.
9. **`<label>` causes click propagation** — wrapping buttons in `<label>` causes sibling button handlers to fire. Use `<span>` for neutral containers.
10. **CSS transitions break on DOM rebuild** — `renderRules()` does `innerHTML = html` which destroys in-progress transitions. Schedule DOM cleanup AFTER transition completes (use `setTimeout` matching transition duration). Fade-out → wait → then rebuild.
11. **Companion toggles are read-only** — per-skill enable/disable toggles were removed in v1.0.1 because cmg-guard plugin never reads `companion_skills` from config.yaml. The Dashboard's toggles had no effect on actual behavior. The companion list now shows only install status (✓/✗).
12. **🔴 硬编码版本号/配置 key 必须自适应** — 不要写死 `v5.6.0` 或 `'cmg_guard'`。版本从 CMG SKILL.md frontmatter 读取，配置 key 从 sentinel plugin.yaml 自动检测。用 `CMG_VERSION = _cmg_version()` 和 `SENTINEL_KEY = _sentinel_config_key()` 在服务启动时注入 HTML 模板。
13. **🔴 Canvas 必须 devicePixelRatio 缩放** — Retina 屏上 Canvas 默认分辨率极糊。`canvas.width = w * dpr; canvas.height = h * dpr; canvas.style.width = w + 'px'; canvas.style.height = h + 'px'; ctx.scale(dpr, dpr)`。
14. **🔴 JS 动态 textContent 覆写会绕过 i18n** — `toggleBatchMode()` 之类的函数用 `textContent = '☐ 批量'` 绕过 `applyLang()`。所有动态按钮文本必须用 `t('key')`。
15. **🔴 naive datetime vs UTC-aware 导致静默故障** — `datetime.now(timezone.utc)` 与 `datetime.fromisoformat(ts)` (naive) 相减抛 TypeError，被 `except: pass` 吞掉。必须 `dt.replace(tzinfo=timezone.utc)` 统一时区后再相减。
16. **🔴 execute_code 多次调用会互踩** — 每次 execute_code 是独立沙箱，重复 `read→modify→write` 同一个文件会互相覆盖。改同一文件时必须在一次 execute_code 中完成所有修改，或在每次修改前重新 read_file。

## Companion Detection

Scans `~/.hermes/skills/`, `~/.claude/skills/`, `~/.agents/skills/`, `~/.openclaw/skills/`, `~/.codex/skills/`, and `~/.hermes/plugins/`. Matches by `name:` regex in SKILL.md frontmatter (never YAML-parse to avoid crashes).

## Dependencies

Python 3.7+, PyYAML.
