#!/usr/bin/env python3
"""
CMG init script — Canon-Mnemonic-Guard 初始化
运行: python3 scripts/init.py
或: npx canon-mnemonic-guard init（安装后自动调用）
"""

import json
import os
import sys
import datetime
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")))
REF_DIR = HERMES_HOME / "self-reflection"
SKILLS_DIR = HERMES_HOME / "skills"
SOUL_PATH = HERMES_HOME / "SOUL.md"
CONFIG_YAML = HERMES_HOME / "config.yaml"


def print_header(text):
    print(f"\n{'='*50}")
    print(text)
    print("=" * 50)


def ask_yn(prompt, default="Y"):
    """Ask a Y/N question, return True for Y."""
    yn = input(f"{prompt} [Y/n]: ").strip().lower()
    if not yn:
        yn = default.lower()
    return yn in ("y", "yes")


def create_directories():
    """Create self-reflection directory structure."""
    dirs = [
        REF_DIR / "rules" / "ban",
        REF_DIR / "rules" / "gap",
        REF_DIR / "rules" / "lazy",
        REF_DIR / "checklists",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return True


def create_default_config():
    """Generate config.json with defaults."""
    config = {
        "match_mode": "layered",
        "load_mode": "full_preload",
        "semantic_match": "auto",
        "auto_solidify_threshold": 3,
        "solidify_threshold_mode": "adaptive",
        "auto_scan_interval_days": 7,
        "conflict_detection": {"cross_type": True},
        "scoring": {
            "enabled": True,
            "false_positive_threshold": 0.3,
            "expiry_days": 180,
        },
        "health_check": {"enabled": True},
        "scan_sources": {
            "builtin": {"soul": True, "memory": True, "skills": True},
            "obsidian": {
                "enabled": True,
                "vault_path": "~/obsidian",
                "rule_dirs": ["🔒 HERMES-全局铁则库"],
            },
            "plugins": {
                "enabled": True,
                "paths": ["~/.hermes/plugins/"],
                "entry_points": {
                    "enabled": True,
                    "group": "hermes_agent.plugins",
                },
            },
            "custom": [
                {
                    "name": "openclaw_memory",
                    "path": "~/.openclaw/memory/",
                    "file_pattern": "*.md",
                    "enabled": False,
                },
                {
                    "name": "plur_engrams",
                    "path": "~/.plur/",
                    "file_pattern": "engrams.yaml",
                    "enabled": False,
                },
            ],
        },
        "recommendations": {
            "version": "1.0.0",
            "auto_prompt": True,
            "items": [
                {
                    "name": "ralph-loop",
                    "type": "skill",
                    "detection_path": "~/.hermes/skills/software-development/ralph-loop/SKILL.md",
                    "integration": "Guard拦截违规后自动触发ralph-loop确保剩余步骤逐一闭环验证",
                    "category": "guard",
                    "configured": False,
                },
                {
                    "name": "verification-before-completion",
                    "type": "skill",
                    "detection_path": "~/.hermes/skills/software-development/verification-before-completion/SKILL.md",
                    "integration": "Guard拦截'声称完成但未验证'→自动调用",
                    "category": "guard",
                    "configured": False,
                },
                {
                    "name": "diagnose",
                    "type": "skill",
                    "detection_path": "~/.hermes/skills/software-development/diagnose/SKILL.md",
                    "integration": "Guard ban_check反复命中同一规则→自动触发diagnose分析根因",
                    "category": "guard",
                    "configured": False,
                },
                {
                    "name": "idea-foundry",
                    "type": "skill",
                    "detection_path": "~/.hermes/skills/software-development/idea-foundry/SKILL.md",
                    "integration": "CMG的rules/目录作为约束源注入IF代码生成阶段",
                    "category": "dispatch",
                    "configured": False,
                },
                {
                    "name": "rtk-rewrite",
                    "type": "plugin",
                    "detection_method": "entry_point",
                    "detection_group": "hermes_agent.plugins",
                    "detection_name": "rtk-rewrite",
                    "integration": "被动受益。rtk压缩所有Hermes终端输出→CMG的pre_action检查自然消耗更少token",
                    "category": "cost",
                    "configured": False,
                },
                {
                    "name": "plur",
                    "type": "mcp_server",
                    "detection_path": "~/.plur/",
                    "integration": "CMG扫盘纳入plur记忆作为额外规则来源",
                    "category": "rules",
                    "configured": False,
                },
                {
                    "name": "obsidian",
                    "type": "skill",
                    "detection_path": "~/.hermes/skills/note-taking/obsidian/SKILL.md",
                    "integration": "rules/可视化浏览+全文检索",
                    "category": "shared",
                    "configured": False,
                },
                {
                    "name": "karpathy-coding-guidelines",
                    "type": "skill",
                    "detection_path": "~/.hermes/skills/software-development/karpathy-coding-guidelines/SKILL.md",
                    "integration": "进攻型行为准则，Guard防守+Karpathy进攻=攻守兼备",
                    "category": "behavior",
                    "configured": False,
                },
                {
                    "name": "hermes-agent-skill-authoring",
                    "type": "skill",
                    "detection_path": "~/.hermes/skills/software-development/hermes-agent-skill-authoring/SKILL.md",
                    "integration": "13项发布自检清单+版本号全文件grep验证",
                    "category": "dev",
                    "configured": False,
                },
            ],
        },
    }
    config_path = REF_DIR / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return config


def create_state():
    """Initialize state.json."""
    now = datetime.datetime.now().isoformat()
    state = {
        "version": "2.7.2",
        "created_at": now,
        "last_modified": now,
        "last_solidify_at": None,
        "last_scan_at": now,
        "errors_since_solidify": 0,
        "total_errors": 0,
        "total_rules": 0,
        "sessions_since_start": 0,
        "last_activation": now,
        "engine_health": {
            "load_failures": 0,
            "intercept_count": 0,
            "false_positive_count": 0,
        },
    }
    with open(REF_DIR / "state.json", "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return state


def create_patterns():
    """Initialize patterns.json."""
    patterns = {"ban": {}, "gap": {}, "lazy": {}}
    with open(REF_DIR / "patterns.json", "w", encoding="utf-8") as f:
        json.dump(patterns, f, ensure_ascii=False, indent=2)


def create_index():
    """Generate initial _index.md."""
    index_content = "# CMG 规则索引\n\n暂无规则。使用 `!remember 禁止xxx` 记录第一条规则。\n"
    with open(REF_DIR / "rules" / "_index.md", "w", encoding="utf-8") as f:
        f.write(index_content)


def create_mnemonic_state():
    """Initialize mnemonic_state.json."""
    state = {
        "version": "3.5.3",
        "created_at": datetime.datetime.now().isoformat(),
        "data_source": "guard_intercept",
        "data_source_history": {"guard_intercept": 0, "none_sessions": 0},
        "recognized_patterns": 0,
        "draft_queue": [],
        "confidence_adjustments": {"auto": True},
        "intercept_count": 0,
        "last_pattern_push": None,
    }
    with open(REF_DIR / "mnemonic_state.json", "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def scan_recommendations(config):
    """Scan for installed recommendations, return (installed_configured, installed_unconfigured, not_installed)."""
    items = config["recommendations"]["items"]
    installed_configured = []
    installed_unconfigured = []
    not_installed = []

    for item in items:
        name = item["name"]
        installed = False
        configured = item.get("configured", False)

        if item["type"] == "skill":
            path = os.path.expanduser(item["detection_path"])
            installed = os.path.exists(path)
            configured = installed

        elif item["type"] == "plugin":
            try:
                import importlib.metadata as md

                eps = md.entry_points()
                if hasattr(eps, "select"):
                    group_eps = eps.select(group=item["detection_group"])
                else:
                    group_eps = [
                        ep
                        for ep in eps
                        if ep.group == item["detection_group"]
                    ]
                for ep in group_eps:
                    if ep.name == item["detection_name"]:
                        installed = True
                        break
                if installed and CONFIG_YAML.exists():
                    content = CONFIG_YAML.read_text()
                    configured = name in content and "enabled:" in content
            except Exception:
                pass

        elif item["type"] == "mcp_server":
            path = os.path.expanduser(item["detection_path"])
            installed = os.path.exists(path)
            configured = installed

        item["configured"] = configured

        if installed and configured:
            installed_configured.append(name)
        elif installed and not configured:
            installed_unconfigured.append(name)
        else:
            not_installed.append(name)

    config["recommendations"]["last_scan"] = datetime.datetime.now().isoformat()

    # Save updated config
    with open(REF_DIR / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    return installed_configured, installed_unconfigured, not_installed


def write_soul_activation():
    """Write one-line activation marker to SOUL.md."""
    if not SOUL_PATH.exists():
        print("  ⚠️ SOUL.md 不存在，跳过激活标记")
        return False

    marker = "[CMG v5.6.0] 加载 canon-mnemonic-guard 护栏规则\n"

    content = SOUL_PATH.read_text()
    if marker.strip() in content:
        print("  ℹ️ 激活标记已存在，跳过")
        return True

    # Append to end
    if not content.endswith("\n"):
        content += "\n"

    with open(SOUL_PATH, "w", encoding="utf-8") as f:
        f.write(content + "\n" + marker)

    return True


def check_soul_activation():
    """Check if activation marker exists in SOUL.md."""
    if not SOUL_PATH.exists():
        return None, "SOUL.md 不存在"

    content = SOUL_PATH.read_text()
    import re

    match = re.search(r"\[CMG v([\d.]+)\]", content)
    if not match:
        return False, "未找到激活标记"

    version = match.group(1)
    return version, f"v{version}"


def check_subpackages():

    """Check if guard/canon/mnemonic sub-packages are installed.
    Returns dict of {name: description} for missing packages."""
    sub_pkgs = {
        "guard": "Guard 护栏线 — 拦截执行 + 闭环重试",
        "canon": "Canon 典则线 — 规则生产 + 固化引擎",
        "mnemonic": "Mnemonic 忆存线 — 记忆存储 + 模式识别",
    }
    base = HERMES_HOME / "skills" / "software-development"
    missing = {}
    for pkg, desc in sub_pkgs.items():
        if not (base / pkg / "SKILL.md").exists():
            missing[pkg] = desc
    return missing


def install_subpackages(missing):
    """Prompt user to install missing sub-packages. Default: install all."""
    print(f"\n⚠️ 检测到 {len(missing)} 个子包未安装：")
    for pkg, desc in missing.items():
        print(f"  [✓] {pkg} — {desc}")

    print(f"\n默认全部安装。")
    print("输入要跳过的包名（逗号分隔），或直接回车全部安装：")
    skip_input = input("> ").strip()
    skip_list = [s.strip() for s in skip_input.split(",") if s.strip()] if skip_input else []

    for pkg in missing:
        if pkg in skip_list:
            print(f"  ⏭️ 跳过 {pkg}（后续补装: npx skills add {pkg} --yes --global）")
        else:
            print(f"  📦 安装 {pkg}...")
            ret = os.system(f"npx skills add {pkg} --yes --global 2>/dev/null")
            if ret == 0:
                print(f"  ✅ {pkg} 安装完成")
            else:
                print(f"  ❌ {pkg} 安装失败（错误码: {ret}），请手动执行: npx skills add {pkg} --yes --global")

    # Re-check after install
    still_missing = check_subpackages()
    if not still_missing:
        print("\n✅ 全部子包已就绪。")
    else:
        installed = [p for p in ["guard","canon","mnemonic"] if p not in still_missing]
        if installed:
            print(f"\n✅ 已安装: {', '.join(installed)}")
        print(f"⚠️ 仍缺失: {', '.join(still_missing.keys())}")
        print("  后续可随时补装：npx skills add <包名> --yes --global")
        print("  CMG 外观层会在此后每次启动时自动检测新安装的子包。")


def check_cmg_name_conflicts():
    """Check for CMG four-name conflicts with other installed skills."""
    import subprocess
    script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "check-name-conflicts.py"
    )
    if not os.path.exists(script):
        print("  ⚠️ check-name-conflicts.py 未找到，跳过冲突检测")
        return True

    result = subprocess.run(
        [sys.executable, script, "--quiet"],
        capture_output=True, text=True
    )
    output = result.stdout + result.stderr
    print(output.strip())
    
    if result.returncode != 0:
        print("\n⚠️ 检测到 CMG 四名冲突，进入交互修复...")
        subprocess.run([sys.executable, script, "--fix"])
        return False
    return True


def main():
    print_header("CMG 三省引擎 v5.6.0 初始化")

    # Phase 0: Check sub-packages
    missing = check_subpackages()
    if missing:
        install_subpackages(missing)
    else:
        print("✅ 子包检测: guard / canon / mnemonic 全部已安装")

    # Phase 0.5: Name conflict check
    print_header("🔍 四名冲突检测")
    check_cmg_name_conflicts()

    # Phase 1: Create directories
    create_directories()
    print("✅ rules/ 目录已创建（ban/gap/lazy）")

    # Phase 2: Generate config
    config = create_default_config()
    print("✅ config.json 已生成")

    # Phase 3: Initialize state
    create_state()
    print("✅ state.json 已初始化")

    # Phase 4: Initialize patterns
    create_patterns()
    print("✅ patterns.json 已初始化")

    # Phase 5: Create index
    create_index()
    print("✅ rules/_index.md 已生成")

    # Phase 6: Create mnemonic state
    create_mnemonic_state()
    print("✅ mnemonic_state.json 已创建")

    # Phase 7: Scan recommendations
    print_header("📋 推荐列表扫描")
    installed_ok, installed_bad, not_found = scan_recommendations(config)

    if installed_ok:
        print(f"✅ 已安装+已配置 ({len(installed_ok)} 个):")
        for n in installed_ok:
            item = next(i for i in config["recommendations"]["items"] if i["name"] == n)
            print(f"  [{item['category']}] {n} — {item['integration'][:50]}...")

    if installed_bad:
        print(f"\n⚠️ 已安装+未配置 ({len(installed_bad)} 个):")
        for n in installed_bad:
            item = next(i for i in config["recommendations"]["items"] if i["name"] == n)
            print(f"  [{item['category']}] {n}")
        print("\n  以上工具已安装但未启用。输入 !scan-recommendations 配置。")

    if not_found:
        print(f"\n❌ 未安装 ({len(not_found)} 个):")
        for n in not_found:
            item = next(i for i in config["recommendations"]["items"] if i["name"] == n)
            print(f"  [{item['category']}] {n} — {item['integration'][:50]}...")

    if not installed_ok and not installed_bad:
        print("  ℹ️ 当前无推荐工具已安装。CMG 核心功能（规则管理+护栏拦截）不受影响。")
        print("  之后安装推荐工具后，运行 !scan-recommendations 即可接入。")

    # Phase 8: SOUL activation
    print_header("⚡ 护栏自动激活")
    print("是否在 SOUL.md 中写入激活标记（一行），让护栏在每次对话自动生效？")
    print(f"  一行内容: [CMG v5.6.0] 加载 canon-mnemonic-guard 护栏规则")
    print()

    if ask_yn("写入激活标记"):
        success = write_soul_activation()
        if success:
            print("✅ 激活标记已写入 SOUL.md")
            print("   护栏规则将在下次新会话自动生效。")
            print("   如需停用，删除 SOUL.md 中 [CMG v...] 开头的行即可。")
    else:
        print("  已跳过。手动触发: /skill canon-mnemonic-guard 或 /skill guard")

    # Final summary
    print_header("初始化完成")
    print(f"规则目录: {REF_DIR}/rules/")
    print(f"配置:     {REF_DIR}/config.json")
    print(f"推荐:     {len(installed_ok)+len(installed_bad)}/{len(config['recommendations']['items'])} 个可用")
    print()
    print("快速上手:")
    print("  !remember 禁止xxx     → 记录规则")
    print("  !scan                 → 手动扫盘")
    print("  !scan-recommendations → 扫描推荐列表")
    print("  !log                  → 协调日志")
    print("  !diagnose             → 一键诊断")


if __name__ == "__main__":
    main()
