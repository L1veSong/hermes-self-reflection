"""
sentinel v1.4.0: + pre_llm_call 活跃规则注入 + URL 检测提示 + post_llm_call CoVe 自检薄层。

v1.4.0: + _inject_active_rules (CLI+GUI: 按任务匹配 5-10 条最相关 ban 规则注入上下文)
        + _detect_urls (CLI+GUI: 检测用户消息中的 URL，提示使用 web_extract)
        + _add_cove_check (CLI: post_llm_call 追加自检提示)
v1.3.2: pre_tool_call SKILL.md gate now distinguishes read vs write:
        read_file → always allowed; terminal grep/cat/ls → allowed;
        terminal sed/>/tee, execute_code write_file/patch → blocked
v1.3.0: + pre_tool_call SKILL.md edit gate (default ON)
        + post_llm_call completion-without-evidence check (default ON)
        + session state tracking for authoring skill detection
        + configurable hook system (17 hooks, 4 core ON, 13 opt-in)
        + hook-enable check via config.yaml sentinel.hooks.*

v1.2.0: + pre_llm_call step-completeness checker + global blacklist.
v1.1.0: + sentinel regex + escalation system.
v1.0.0: + transform_llm_output ban keyword scanner.

Unlike the CMG skill (AI reads rules and self-polices), this plugin runs
inside Hermes — the AI has no opportunity to skip or rationalise past it.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

_CONFIG_CACHE: Optional[dict] = None
_SESSION_FLAGS: Dict[str, dict] = {}
_BLACKLIST_CACHE: Optional[Set[str]] = None


def _load_cmg_config() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    try:
        from hermes_cli.config import load_config
        raw = load_config()
        cfg: dict = raw.get("sentinel", {})
    except Exception:
        cfg = {}
    _CONFIG_CACHE = cfg
    return _CONFIG_CACHE


def _hook_enabled(hook_name: str) -> bool:
    """Check if a specific hook is enabled. CORE hooks default ON, others OFF.
    
    Platform-aware: output-modifying hooks (pre_llm_call, post_llm_call,
    transform_llm_output) are auto-disabled on non-CLI platforms where the
    AI can't self-correct after interception.
    """
    cfg = _load_cmg_config()
    hooks_cfg = cfg.get("hooks", {})
    core_defaults = {
        "pre_tool_call": True,
        "pre_llm_call": True,
        "post_llm_call": True,
        "transform_llm_output": True,
    }
    if hook_name in core_defaults:
        enabled = hooks_cfg.get(hook_name, core_defaults[hook_name])
    else:
        enabled = hooks_cfg.get(hook_name, False)

    # Platform gate: output-modifying hooks only work on CLI
    # pre_llm_call is EXEMPT — its context-injection sub-hooks
    # (_inject_active_rules, _detect_urls) are designed cross-platform.
    if enabled and hook_name in ("post_llm_call", "transform_llm_output"):
        plat = _detect_platform()
        if plat != "cli":
            logger.debug("[sentinel] hook '%s' disabled on platform '%s' (no AI self-correct loop)", hook_name, plat)
            return False
    return enabled


def _detect_platform() -> str:
    """Detect the current Hermes platform (cli, desktop, web, etc.)."""
    try:
        for env_var in ("HERMES_PLATFORM", "HERMES_CLI_PLATFORM"):
            val = os.environ.get(env_var, "")
            if val:
                return val.lower()
        if os.environ.get("HERMES_DESKTOP_CHILD_PID"):
            return "desktop"
        if os.environ.get("ELECTRON_RUN_AS_NODE"):
            return "desktop"
        return "cli"
    except Exception:
        return "cli"


def _intercept_notice_mode() -> str:
    """silent (default) or visible — how to display interception notices."""
    cfg = _load_cmg_config()
    return cfg.get("intercept_notice", "silent")


def _sentinel_enabled() -> bool:
    cfg = _load_cmg_config()
    if "lightweight_sentinel" not in cfg:
        return True
    return bool(cfg["lightweight_sentinel"])


def _step_check_enabled() -> bool:
    cfg = _load_cmg_config()
    if "step_check" not in cfg:
        return True
    return bool(cfg["step_check"])


def _task_recommendations_enabled() -> bool:
    cfg = _load_cmg_config()
    if "task_recommendations" not in cfg:
        return True
    return bool(cfg["task_recommendations"])


# ---------------------------------------------------------------------------
# Session state tracking
# ---------------------------------------------------------------------------

def _get_session(session_id: str) -> dict:
    """Get or create per-session state dict."""
    if session_id not in _SESSION_FLAGS:
        _SESSION_FLAGS[session_id] = {
            "authoring_seen": False,
            "writing_seen": False,
            "authoring_loaded": False,
        }
    return _SESSION_FLAGS[session_id]


# ---------------------------------------------------------------------------
# Escalation system
# ---------------------------------------------------------------------------

ESCALATION_FILE = os.path.expanduser("~/.hermes/self-reflection/escalation.json")
BLACKLIST_FILE = os.path.expanduser("~/.hermes/self-reflection/blacklist.json")


def _load_escalation() -> dict:
    try:
        if os.path.exists(ESCALATION_FILE):
            with open(ESCALATION_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {"patterns": {}, "last_updated": ""}


def _save_escalation(data: dict) -> None:
    data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        os.makedirs(os.path.dirname(ESCALATION_FILE), exist_ok=True)
        with open(ESCALATION_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.warning("[sentinel] failed to save escalation: %s", e)


def _record_correction(pattern: str) -> int:
    data = _load_escalation()
    now = time.time()
    entry = data["patterns"].get(pattern, {"count": 0, "first_seen": now, "last_seen": now, "level": 0})
    entry["count"] += 1
    entry["last_seen"] = now
    entry["level"] = _calc_level(entry["count"])
    data["patterns"][pattern] = entry
    _save_escalation(data)
    logger.info("[sentinel] escalation: '%s' count=%d level=%d", pattern[:80], entry["count"], entry["level"])
    return entry["level"]


def _calc_level(count: int) -> int:
    if count <= 1:
        return 1
    elif count == 2:
        return 2
    elif count <= 4:
        return 3
    else:
        return 4


def _load_blacklist() -> Set[str]:
    global _BLACKLIST_CACHE
    if _BLACKLIST_CACHE is not None:
        return _BLACKLIST_CACHE
    try:
        if os.path.exists(BLACKLIST_FILE):
            with open(BLACKLIST_FILE) as f:
                data = json.load(f)
            _BLACKLIST_CACHE = set(data.get("permanent_errors", []))
        else:
            _BLACKLIST_CACHE = set()
    except Exception:
        _BLACKLIST_CACHE = set()
    return _BLACKLIST_CACHE


def _maybe_add_to_blacklist(pattern: str, level: int) -> None:
    if level < 4:
        return
    bl = _load_blacklist()
    bl.add(pattern)
    data = {"permanent_errors": list(bl), "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    try:
        os.makedirs(os.path.dirname(BLACKLIST_FILE), exist_ok=True)
        with open(BLACKLIST_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.warning("[sentinel] failed to save blacklist: %s", e)
        return
    global _BLACKLIST_CACHE
    _BLACKLIST_CACHE = bl
    logger.warning("[sentinel] BLACKLISTED permanently: '%s' (level 4)", pattern[:80])


def _scan_blacklist(message: str) -> Optional[str]:
    bl = _load_blacklist()
    if not bl:
        return None
    lower = message.lower()
    for pattern in bl:
        if pattern.lower() in lower:
            logger.warning("[sentinel] blacklist hit: '%s'", pattern[:80])
            return f"[CMG-BLACKLIST] 此行为已被永久禁止: {pattern}"
    return None


# ---------------------------------------------------------------------------
# Ban rule loading (v1.3.0 legacy path — used by _scan_text / transform_llm_output)
# ---------------------------------------------------------------------------

_BAN_KEYWORDS: Optional[Dict[str, Tuple[str, List[str]]]] = None


def _load_ban_keywords() -> Dict[str, Tuple[str, List[str]]]:
    global _BAN_KEYWORDS
    if _BAN_KEYWORDS is not None:
        return _BAN_KEYWORDS
    rules_dir = Path(os.path.expanduser("~/.hermes/self-reflection/rules/ban"))
    if not rules_dir.is_dir():
        _BAN_KEYWORDS = {}
        return _BAN_KEYWORDS
    result: Dict[str, Tuple[str, List[str]]] = {}
    for md_file in sorted(rules_dir.glob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
            m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
            if not m:
                continue
            fm_text = m.group(1)
            rule_id = md_file.stem
            keywords: List[str] = []
            in_kw = False
            buf = ""
            for line in fm_text.split("\n"):
                s = line.strip()
                if s.startswith("id:"):
                    rule_id = s[3:].strip().strip('"').strip("'")
                elif s.startswith("keywords:"):
                    in_kw = True
                    buf = s[9:].strip()
                    if buf.endswith("]"):
                        in_kw = False
                        buf = buf[:-1]
                elif in_kw:
                    buf += " " + s
                    if s.endswith("]"):
                        in_kw = False
                        buf = buf.rstrip("]")
            if buf:
                raw = buf.strip().lstrip("[").rstrip("]")
                for p in raw.split(","):
                    kw = p.strip().strip("'").strip('"').lower()
                    if kw and len(kw) >= 2:
                        keywords.append(kw)
            if keywords:
                result[rule_id] = (md_file.stem, keywords)
        except Exception:
            pass
    _BAN_KEYWORDS = result
    logger.info("[sentinel] loaded %d ban rules", len(result))
    return _BAN_KEYWORDS


def _scan_text(text: str) -> Optional[str]:
    rules = _load_ban_keywords()
    if not rules:
        return None
    lower = text.lower()
    for rule_id, (stem, keywords) in rules.items():
        for kw in keywords:
            if kw in lower:
                logger.warning("[sentinel] rule %s hit: '%s'", rule_id, kw)
                return (
                    f"[CMG 拦截] 你的回答命中了规则 \"{stem}\"（关键词: \"{kw}\"）。"
                    f"请遵守 CMG 规则重新回答。"
                )
    return None


# ---------------------------------------------------------------------------
# Sentinel — negation regex scanner
# ---------------------------------------------------------------------------

_SENTINEL_PATTERN_1 = re.compile(
    r"(不|别|不能|别再|不要|不该|不许|怎么又|又忘了|又犯|又偷|又懒|"
    r"你总[是说]|你咋|你又|别再|不准)"
    r".{0,15}"
    r"(你|我|这么|这样|那么|那|这|还|再|老|了|啦|吧|啊)"
)
_SENTINEL_PATTERN_2 = re.compile(r"^(别|不要|不能|不许|不该|别再|不准)")
_SENTINEL_PATTERN_3 = re.compile(
    r"(记住[了没]?|明白[了没]|懂[了没]|"
    r"下次还|以后还|还敢|还能不能|"
    r"说了多少次|能不能|好了再说|"
    r"长点记性|长记性)"
)


def _scan_user_message(user_message: str) -> Optional[str]:
    if not user_message or len(user_message) < 2:
        return None
    if (_SENTINEL_PATTERN_1.search(user_message) or
            _SENTINEL_PATTERN_2.search(user_message) or
            _SENTINEL_PATTERN_3.search(user_message)):
        logger.debug("[sentinel] sentinel matched: %s", user_message[:80])
        words = re.findall(r"[\u4e00-\u9fff\w]+", user_message)
        pattern_key = " ".join(words[:5]) if words else user_message[:30]
        level = _record_correction(pattern_key)
        _maybe_add_to_blacklist(pattern_key, level)
        if level >= 4:
            return f"[CMG-BLACKLIST-PERMANENT] 此错误已反复出现{level}次，永久禁止"
        elif level >= 3:
            return f"[CMG-SENTINEL-L3] 此错误已出现{level}次，建议固化规则"
        elif level >= 2:
            return f"[CMG-SENTINEL-L2] 此错误已出现{level}次，警告拦截"
        else:
            return "[CMG-SENTINEL] suspected_correction"
    return None


# ---------------------------------------------------------------------------
# Step-completeness checker
# ---------------------------------------------------------------------------

_STEP_RULES = [
    {
        "id": "link_complete_reading",
        "trigger": re.compile(r"https?://[^\s]+"),
        "description": "链接必须完整阅读（含图片、附件、代码块）",
        "required_tools": ["web_extract", "vision_analyze"],
    },
    {
        "id": "file_coverage_check",
        "trigger": re.compile(r"(write_file|write_to_file|创建了.*文件|写入了.*文件)"),
        "description": "创建文件后必须做覆盖度校验（逐条核对）",
        "required_pattern": r"(覆盖度|逐条核对|N/N|全部覆盖)",
    },
    {
        "id": "orchestrator_clarify",
        "trigger": re.compile(r"(IF|idea-foundry|orchestrator|Phase -[0-9])"),
        "description": "Orchestrator流程每阶段必须用clarify()确认",
        "required_tools": ["clarify"],
    },
    {
        "id": "skill_workflow_execution",
        "trigger": re.compile(r"(跑|走|过).{0,5}(一遍|一下).{0,10}(IF|idea-foundry|brainstorming|planning)"),
        "description": "说'跑Skill'必须执行完整workflow，不能只读文档",
        "required_pattern": r"(Phase -[0-9].*完成|质量预检|策略选择)",
    },
    {
        "id": "evidence_for_claims",
        "trigger": re.compile(r"(通过|完成|成功|已安装|存在|无冲突|全部.*[过绿]|✅|PASS|生效|可用|已修复|已解决|没问题)"),
        "description": "断言性结论必须附带验证证据（终端输出/文件列表/命令结果）",
        "required_pattern": r"(验证|实测|输出|grep|wc -l|ls |cat |curl|exit_code|diff|find.*SKILL|python3.*check)",
    },
]


def _get_recent_context() -> str:
    try:
        from hermes_cli.session import get_current_session
        session = get_current_session()
        if session and hasattr(session, "messages"):
            messages = getattr(session, "messages", [])
            recent = messages[-10:] if len(messages) > 10 else messages
            parts = []
            for msg in recent:
                content = getattr(msg, "content", "") or str(msg)
                if content and len(str(content)) < 2000:
                    parts.append(str(content)[:500])
            return " ".join(parts)
    except Exception:
        pass
    return ""


def _check_step_completeness(user_message: str, **kwargs) -> Optional[str]:
    if not _step_check_enabled():
        return None
    if not user_message:
        return None
    recent_context = _get_recent_context()
    combined = f"{recent_context} {user_message}"
    violations = []
    for rule in _STEP_RULES:
        if not rule["trigger"].search(combined):
            continue
        if "required_tools" in rule:
            tools_called = all(tool in recent_context for tool in rule["required_tools"])
            if not tools_called:
                violations.append(rule["description"])
                continue
        if "required_pattern" in rule:
            if not re.search(rule["required_pattern"], combined, re.IGNORECASE):
                violations.append(rule["description"])
    if violations:
        msg = (
            "[CMG-STEP-CHECK] 以下步骤未完成，禁止回复：\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\n请先完成上述步骤后再回复。"
        )
        logger.warning("[sentinel] step check failed: %s", violations)
        return msg
    return None


# ===========================================================================
#  HOOK HANDLERS
# ===========================================================================

# ── Core: transform_llm_output ───────────────────────────────────────────

def _is_subagent_relay(text: str) -> bool:
    """检测是否为子agent输出的中继文本，这些文本应豁免ban关键词扫描。"""
    if not text:
        return False
    markers = [
        '"task_index"', '"subagent"', 'Copilot ACP', 'Reasonix',
        'delegate_task', '子agent', '子 agent', 'subagent output',
        '"status":', '"summary":', '"results":', '"api_calls":',
        '"duration_seconds":', '"model":', '"exit_reason":',
        'Results from delegate', '[CMG 拦截]', '⚠️ [CMG拦截]',
    ]
    lower = text.lower()
    for m in markers:
        if m.lower() in lower:
            return True
    return False


def _transform_llm_output(response_text: str = "", **kwargs) -> Optional[str]:
    if not _hook_enabled("transform_llm_output"):
        return None
    if not _is_subagent_relay(response_text):
        block_msg = _scan_text(response_text)
        if block_msg:
            if _intercept_notice_mode() == "visible":
                return f"⚠️ [CMG拦截] {block_msg}"
            return block_msg
    bl_msg = _scan_blacklist(response_text)
    if bl_msg:
        if _intercept_notice_mode() == "visible":
            return f"⚠️ [CMG拦截] {bl_msg}"
        return bl_msg
    return None


# ── Core: pre_llm_call ───────────────────────────────────────────────────

_TASK_RECOMMENDATIONS = {
    "打包|发布|部署|zip|上传|release|桌面": [
        "ralph-loop（闭环验证，逐项核对不漏组件）",
        "verification-before-completion（证据先于断言）",
        "hermes-agent-skill-authoring（发布自检清单）",
    ],
    "写代码|开发|实现|重构|build|新建|创建.*项目": [
        "tdd / test-driven-development（先写测试）",
        "brainstorming（先想清楚再动手）",
        "planning-with-files（文件持久化进度）",
    ],
    "调试|修复|bug|报错|不工作": [
        "diagnose（四阶段根因调试）",
        "systematic-debugging（理解bug再修复）",
    ],
    "测试|验证|test": [
        "tdd / test-driven-development（RED-GREEN-REFACTOR）",
        "verification-before-completion（完成前必须验证）",
    ],
    "写.*(文章|论文|文档|报告)": [
        "planning-with-files（大纲持久化）",
        "verification-before-completion（字数/格式校验）",
    ],
}

_REC_SESSION_CACHE: Dict[str, set] = {}


def _check_task_recommendations(user_message: str, session_id: str = "") -> Optional[str]:
    """Scan user message for task keywords, suggest CMG companion tools.
    Only fires once per session per task type to avoid spam.
    """
    if not user_message or len(user_message) < 5:
        return None

    cache = _REC_SESSION_CACHE.setdefault(session_id, set())

    suggestions = []
    for pattern, tools in _TASK_RECOMMENDATIONS.items():
        if re.search(pattern, user_message, re.IGNORECASE):
            task_key = pattern[:20]
            if task_key in cache:
                continue
            cache.add(task_key)
            suggestions.extend(tools)

    if not suggestions:
        return None

    tool_list = "\n".join(f"  • {t}" for t in suggestions)
    msg = (
        "[CMG 配套工具建议]\n"
        "检测到任务类型，推荐启用以下 CMG 配套工具以确保质量：\n"
        f"{tool_list}\n"
        "以上为一次性提示，本会话内不再重复。"
    )
    logger.info("[sentinel] task recommendation: %d tools suggested", len(suggestions))
    return msg


# ── v1.4.0: 活跃规则注入 ─────────────────────────────────────────────────

_BAN_RULES_CACHE: Optional[List[dict]] = None
_BAN_RULE_MTIMES: Dict[str, float] = {}  # per-file mtime tracking


def _parse_fm(text: str) -> dict:
    """Parse simple YAML frontmatter: key: value (no nested structures).
    Supports inline list [...], block scalar | for multi-line values,
    numeric string→int conversion, and negative numbers.

    Block scalar preserves empty lines within the value — only a
    non-indented key:value line or end-of-frontmatter terminates it.
    """
    fm: Dict[str, object] = {}
    block_key: Optional[str] = None
    block_buf: Optional[List[str]] = None
    block_indent: Optional[int] = None
    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        is_indented = bool(line) and line[0] in (" ", "\t")

        # ── Block scalar mode: all indented lines are content ──
        if block_key is not None:
            if not stripped:
                # Empty line inside block scalar → preserve
                block_buf.append("")
                continue
            if is_indented:
                # Indented content line → part of block scalar
                block_buf.append(stripped)
                continue
            # Non-indented, non-empty → block scalar ends
            fm[block_key] = "\n".join(block_buf)
            block_key = None
            block_buf = None
            block_indent = None
            # Fall through to process this line as normal

        if not stripped or stripped.startswith("#"):
            continue

        if ":" not in stripped:
            continue

        key, _, val = stripped.partition(":")
        key = key.strip()
        val_stripped = val.strip()

        # Detect block scalar: | or |+
        if val_stripped == "|" or val_stripped.startswith("|+"):
            block_key = key
            block_buf = []
            block_indent = None
            continue

        # Normal value
        val_clean = val_stripped.strip('"').strip("'")

        # Parse inline list: [a, b, c]
        if val_clean.startswith("[") and val_clean.endswith("]"):
            items = re.findall(r'"([^"]*)"', val_clean)
            if items:
                fm[key] = items
            else:
                items_raw = [v.strip().strip('"').strip("'") for v in val_clean[1:-1].split(",")]
                fm[key] = [i for i in items_raw if i]
        # Parse numeric values (including negatives)
        elif val_clean.lstrip("-").replace(".", "", 1).isdigit():
            if "." in val_clean:
                fm[key] = float(val_clean)
            else:
                fm[key] = int(val_clean)
        else:
            fm[key] = val_clean

    # Flush block scalar if file ended without closing blank line
    if block_key is not None and block_buf:
        fm[block_key] = "\n".join(block_buf).rstrip("\n")

    return fm


def _load_ban_rules() -> List[dict]:
    """Load ban rules from rules/ban/ directory with per-file mtime tracking.
    Uses individual file mtimes so edits to existing files invalidate the cache.
    """
    global _BAN_RULES_CACHE, _BAN_RULE_MTIMES
    rules_dir = Path(os.path.expanduser("~/.hermes/self-reflection/rules/ban"))
    if not rules_dir.is_dir():
        _BAN_RULES_CACHE = []
        _BAN_RULE_MTIMES = {}
        return []

    # Scan current mtimes once (shared by cache-valid check and cache-miss path)
    current_mtimes: Dict[str, float] = {}
    for rule_file in rules_dir.glob("*.md"):
        try:
            current_mtimes[rule_file.name] = rule_file.stat().st_mtime
        except OSError:
            current_mtimes[rule_file.name] = 0

    # Cache valid if file set and mtimes match
    if _BAN_RULES_CACHE is not None:
        cache_valid = (
            current_mtimes.keys() == _BAN_RULE_MTIMES.keys()
            and all(
                _BAN_RULE_MTIMES.get(name) == mtime
                for name, mtime in current_mtimes.items()
            )
        )
        if cache_valid:
            return _BAN_RULES_CACHE

    rules = []
    for rule_file in sorted(rules_dir.glob("*.md")):
        try:
            content = rule_file.read_text(encoding="utf-8")
        except Exception:
            continue
        fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not fm_match:
            continue
        try:
            fm = _parse_fm(fm_match.group(1))
        except Exception:
            logger.debug("[sentinel] failed to parse frontmatter in %s", rule_file.name)
            continue
        keywords = fm.get("keywords", [])
        if not keywords:
            continue
        if isinstance(keywords, str):
            keywords = [keywords]
        # Pre-lowercase keywords for faster matching
        keywords_lowered = [kw.lower() for kw in keywords if isinstance(kw, str)]
        keywords_lowered = [kw for kw in keywords_lowered if len(kw) >= 2]
        if not keywords_lowered:
            continue
        title_match = re.search(r"\n#\s+(.+?)\n", content[fm_match.end():])
        title = title_match.group(1).strip() if title_match else rule_file.stem
        rules.append({
            "id": fm.get("id", rule_file.stem),
            "title": title,
            "type": str(fm.get("type", "ban")),
            "keywords": keywords_lowered,
            "hit_count": int(fm.get("hit_count") or 0),
            "correction_template": str(fm.get("correction_template", "")),
        })
    _BAN_RULES_CACHE = rules
    _BAN_RULE_MTIMES = current_mtimes
    logger.debug("[sentinel] loaded %d ban rules with keywords (per-file mtime cache)", len(rules))
    return rules


# Session cache for active rules injection (avoid duplicate injection)
_INJECT_SESSION_CACHE: Dict[str, frozenset] = {}


def _inject_active_rules(user_message: str, session_id: str = "") -> Optional[str]:
    """Match user message against ban rules, inject top-10 most relevant.

    Works on ALL platforms (CLI + GUI) since it only injects context.
    Deduplicates: same rule set within same session is only injected once.
    """
    if not user_message or len(user_message) < 5:
        return None

    rules = _load_ban_rules()
    if not rules:
        return None

    scored: List[Tuple[int, dict]] = []
    msg_lower = user_message.lower()
    for rule in rules:
        score = 0
        for kw in rule["keywords"]:
            if kw in msg_lower:
                score += 1
        if score > 0:
            scored.append((score, rule))

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:10]

    # Deduplicate: same session + same rule IDs → skip injection
    cache = _INJECT_SESSION_CACHE.setdefault(session_id, frozenset())
    rule_ids = frozenset(r["id"] for _, r in top)
    if rule_ids.issubset(cache):
        return None  # Already injected this exact rule set
    _INJECT_SESSION_CACHE[session_id] = cache | rule_ids

    lines = ["[CMG 活跃约束] 检测到以下相关规则，请注意遵守："]
    for _, rule in top:
        hint = ""
        if rule.get("correction_template"):
            tmpl = rule["correction_template"]
            if len(tmpl) > 120:
                tmpl = tmpl[:117] + "..."
            hint = f"\n  修正: {tmpl}"
        lines.append(f"  [{rule['type']}] {rule['title']}{hint}")

    logger.info("[sentinel] active rules injected: %d rules matched", len(top))
    return "\n".join(lines)


# ── v1.4.0: URL 检测 ──────────────────────────────────────────────────────

# Strip trailing punctuation from URLs to avoid matching "https://example.com)."
_URL_PATTERN = re.compile(
    r"https?://[^\s<>\"'\)\]\[]+(?<![,\.;:!?\)\]}>])",
    re.IGNORECASE,
)


def _detect_urls(user_message: str) -> Optional[str]:
    """Detect URLs in user message, hint the agent to fetch them.
    Works on ALL platforms. The hook can't call web tools directly.
    """
    if not user_message:
        return None
    urls = _URL_PATTERN.findall(user_message)
    if not urls:
        return None

    unique = list(dict.fromkeys(urls))
    if len(unique) == 1:
        hint = f"[CMG 素材提示] 检测到链接: {unique[0]}\n请使用 web_extract 读取内容后再回答。"
    else:
        url_list = "\n".join(f"  • {u}" for u in unique[:5])
        more = f"\n  ... 等 {len(unique)} 个链接" if len(unique) > 5 else ""
        hint = (
            f"[CMG 素材提示] 检测到 {len(unique)} 个链接:\n"
            f"{url_list}{more}\n"
            "请使用 web_extract 读取链接内容后再回答。"
        )
    logger.info("[sentinel] URL hint: %d URLs detected", len(unique))
    return hint


def _pre_llm_call(user_message: str = "", session_id: str = "", **kwargs) -> Optional[dict]:
    """pre_llm_call hook: collect all context injections into a single block.
    Returns {'context': '...'} with pieces joined by blank lines.
    Empty context pieces are skipped — only non-None results are included.
    """
    if not _hook_enabled("pre_llm_call"):
        return None

    plat = _detect_platform()
    is_cli = (plat == "cli")

    # Collect all context pieces (non-CLI platforms get reduced set)
    contexts: List[str] = []

    # v1.4.0: Active rule injection (ALL platforms)
    rule_ctx = _inject_active_rules(user_message, session_id)
    if rule_ctx:
        contexts.append(rule_ctx)

    # v1.4.0: URL detection (ALL platforms)
    url_ctx = _detect_urls(user_message)
    if url_ctx:
        contexts.append(url_ctx)

    # Blacklist scan (ALL platforms — always warn, but only CLI blocks)
    bl_msg = _scan_blacklist(user_message)
    if bl_msg:
        logger.info("[sentinel] blacklist intercept")
        if is_cli:
            contexts.append(f"[CMG-BLACKLIST-BLOCK] {bl_msg}")

    # Sentinel (ALL platforms — non-CLI just logs, CLI adds context)
    if _sentinel_enabled():
        flag = _scan_user_message(user_message)
        if flag:
            logger.info("[sentinel] sentinel: flagged suspected correction (platform=%s)", plat)
            if is_cli:
                contexts.append(flag)

    # Task recommendations (CLI only)
    if is_cli and _task_recommendations_enabled():
        rec_msg = _check_task_recommendations(user_message, session_id)
        if rec_msg:
            contexts.append(rec_msg)

    # Step completeness check (CLI only)
    if is_cli:
        step_fail = _check_step_completeness(user_message)
        if step_fail:
            logger.info("[sentinel] step check: blocking LLM call")
            contexts.append(step_fail)

    if contexts:
        return {"context": "\n\n".join(contexts)}
    return None


# ── Core: post_llm_call ──────────────────────────────────────────────────

# Completion-claim patterns
_COMPLETION_CLAIM = re.compile(
    r"(完成[了啦]?|好了|搞定|做完了|已创建|已写入|已更新"
    r"|已修复|已打包|已发布|已部署|就绪|全部.*[过绿]"
    r"|一切.*正常|到此.*结束|以上.*就是)",
    re.IGNORECASE,
)
# Minimal data token: any digit, emoji marker, or path separator
_DATA_TOKEN = re.compile(r"[\d✅❌⏳⚠️/~]")


def _check_completion_evidence(response_text: str) -> Optional[str]:
    """Detect task-completion claims with nothing substantive following them.

    Abstract rule: after declaring something done, what's left?
    If the reply ends right after the claim (or fills the rest with
    vague words only), there's no evidence. If there's substance —
    numbers, paths, markers, anything specific — it passes.
    """
    # Find the last completion claim position
    last_match = None
    for m in _COMPLETION_CLAIM.finditer(response_text):
        last_match = m

    if not last_match:
        return None

    # If there's nothing substantive after the claim, flag it
    # A substantive token is a digit, emoji, path char, or longer word
    after = response_text[last_match.end():].strip()
    if not after or len(after) < 5:
        return None  # too short to judge, skip
    # Check if the text after the claim has any data tokens
    if _DATA_TOKEN.search(after):
        return None
    # Also check for code blocks, paths, or file references after the claim
    if re.search(r"```|[/~\\]|MEDIA:|file:|path:", after):
        return None
    # Check for substantive content: words with 3+ chars
    words_after = after.split()
    substantial = sum(1 for w in words_after if len(w) >= 3)
    if substantial >= 2:
        return None

    logger.warning("[sentinel] completion without evidence detected")
    return (
        "[CMG-EVIDENCE] 检测到完成声明但缺少验证证据。\n"
        "请在回答中包含以下信息：\n"
        "  - 关键操作的具体结果（终端输出、文件列表、命令返回码）\n"
        "  - 验证步骤的执行证据\n"
        "  - 任何可复现的、可查证的数据"
    )


# ── v1.4.0: CoVe 自检 ────────────────────────────────────────────────────

def _add_cove_check(response_text: str) -> Optional[str]:
    """Add CoVe (Chain of Verification) self-check prompt to CLI responses.
    Only fires when the response is long enough to benefit from self-verification.
    """
    if not response_text or len(response_text) < 200:
        return None

    # Check for evidence patterns — if already present, skip CoVe
    has_evidence = bool(
        _DATA_TOKEN.search(response_text)
        or re.search(r"```|[/~\\]|验证|实测|输出|exit_code", response_text)
    )
    if has_evidence:
        return None

    logger.debug("[sentinel] cove check appended")
    return (
        "\n\n[CMG-CoVe 自检] 请在上方回复中检查：\n"
        "1. 所有断言性结论是否有可验证的证据支持？\n"
        "2. 代码/配置变更是否经过测试或编译验证？\n"
        "3. 如果有 `write_file` 或 `patch` 操作，是否确认内容正确？\n"
        "4. 如果有依赖安装或系统修改，是否验证了可用性？\n"
        "请补充缺失的验证证据后再回复。"
    )


def _post_llm_call(response_text: str = "", session_id: str = "", **kwargs) -> Optional[dict]:
    """post_llm_call hook: apply evidence checking and CoVe self-check.

    Returns {'alteration': new_text_with_appended_check} if any check fires,
    or None to pass through unchanged.

    Only fires on CLI platform (platform gate via _hook_enabled).
    Skips CoVe if completion-evidence already fires to avoid redundant prompts.
    """
    if not _hook_enabled("post_llm_call"):
        return None
    if not response_text:
        return None

    suffix_parts: List[str] = []

    # Check for completion without evidence
    ev_check = _check_completion_evidence(response_text)
    has_ev_violation = bool(ev_check)
    if ev_check:
        suffix_parts.append(ev_check)

    # CoVe self-check (v1.4.0) — skip if completion-evidence already fired
    if not has_ev_violation:
        cove_check = _add_cove_check(response_text)
        if cove_check:
            suffix_parts.append(cove_check)

    if not suffix_parts:
        return None

    altered = response_text.rstrip() + "\n\n" + "\n\n".join(suffix_parts)
    logger.debug("[sentinel] post_llm_call: appended %d checks", len(suffix_parts))
    return {"alteration": altered}


# ── Core: pre_tool_call ──────────────────────────────────────────────────

_SUBAGENT_TOOLS = frozenset({
    "delegate_task", "run_skill", "explore", "research", "review", "security_review",
})


def _pre_tool_call(tool_name: str = "", tool_args: Optional[dict] = None, session_id: str = "", **kwargs) -> Optional[dict]:
    """pre_tool_call gate for SKILL.md editing and subagent relay.

    GUARD_ROLE: Determines whether a tool call is a "read" or "write" operation
    for SKILL.md editing:
      - read_file → always allowed
      - terminal with grep/cat/ls → allowed
      - terminal with sed/>/tee, write_file, patch → blocked
    """
    if not _hook_enabled("pre_tool_call"):
        return None

    # ── Subagent relay tracking ──────────────────────────────────────
    if tool_name in _SUBAGENT_TOOLS:
        sess = _get_session(session_id)
        sess["last_subagent_relay"] = True
        return None

    # ── SKILL.md edit gate ───────────────────────────────────────────
    if tool_name in ("write_file", "patch"):
        args = tool_args or {}
        file_path = args.get("path", "")
        if file_path and "skill" in file_path.lower():
            logger.warning("[sentinel] blocked skill write: %s %s", tool_name, file_path)
            return {
                "block": True,
                "reason": "[CMG-GATE] 禁止直接写入 skill 文件。请使用 skill_manage(action='create'|'patch') 操作 skill。",
            }

    if tool_name == "terminal":
        args = tool_args or {}
        cmd = args.get("command", "")
        if _is_skill_write_via_terminal(cmd):
            logger.warning("[sentinel] blocked terminal skill write: %s", cmd[:80])
            return {
                "block": True,
                "reason": "[CMG-GATE] 禁止通过终端写入 skill 文件。请使用 skill_manage(action='create'|'patch') 操作 skill。",
            }

    return None


def _is_skill_write_via_terminal(cmd: str) -> bool:
    """Check if a terminal command writes to a skill file path."""
    skill_pattern = re.compile(
        r"(sed|tee|>>|>)\s+.*skill",
        re.IGNORECASE,
    )
    return bool(skill_pattern.search(cmd))


# ===========================================================================
#  Plugin registration
# ===========================================================================

def register(ctx) -> None:
    """Register sentinel hooks with Hermes (v1.4.0 + new plugin API)."""
    sentinel = _sentinel_enabled()
    step_check = _step_check_enabled()
    bl_size = len(_load_blacklist())
    rules = _load_ban_keywords()

    # Register hooks via new ctx API (Hermes v0.14+)
    # Core hooks — always have implementations
    core_hooks = {
        "pre_tool_call": _pre_tool_call,
        "pre_llm_call": _pre_llm_call,
        "post_llm_call": _post_llm_call,
        "transform_llm_output": _transform_llm_output,
    }

    # Optional hooks — registered only if implementation exists (reserved extension points)
    _optional_hook_names = [
        "post_tool_call", "transform_tool_result", "transform_terminal_output",
        "pre_api_request", "post_api_request", "on_session_start", "on_session_end",
        "on_session_finalize", "on_session_reset", "pre_gateway_dispatch",
        "pre_approval_request", "post_approval_response", "subagent_stop",
    ]
    for hn in _optional_hook_names:
        fn = globals().get(f"_{hn}")
        if fn is not None:
            core_hooks[hn] = fn

    active = []
    for hook_name, hook_fn in core_hooks.items():
        if _hook_enabled(hook_name):
            ctx.register_hook(hook_name, hook_fn)
            active.append(hook_name)

    logger.info(
        "[sentinel] v1.4.0 registered (%d rules, sentinel=%s, step-check=%s, blacklist=%d, hooks=%s)",
        len(rules),
        "ON" if sentinel else "OFF",
        "ON" if step_check else "OFF",
        bl_size,
        "+".join(h.split("_")[-1][:4] for h in active) if active else "none",
    )
