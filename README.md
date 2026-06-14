# Canon-Mnemonic-Guard (CMG) — 三省引擎

> 取自「吾日三省吾身」。为 AI Agent 提供**错题本 + 免疫系统 + 监工**能力。
> 一次指出错误，永久记住并修正。

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Version](https://img.shields.io/badge/version-5.5.5-green)](CHANGELOG.md)

---

## 是什么

CMG 是一个**自进化护栏系统**。你用自然语言纠正 AI 的错误行为，CMG 自动记录、固化规则、永久拦截。

### 三层闭环

```
用户纠正 → CMG Skill（意图识别） → 三步走固化规则
                ↓
         sentinel Plugin（硬拦截） → 违规输出直接替换
                ↑
         skill-autoload Plugin     → 每次会话自动加载
```

**Layer 1 — skill-autoload Plugin**：会话首轮自动注入 MUST-LOAD 指令，确保 CMG 每次加载。

**Layer 2 — CMG Skill（四包）**：AI 读取规则库，意图识别用户纠正，自动执行三步走（errors.jsonl → rules/ → patterns.json）。

**Layer 3 — sentinel Plugin**：内核级输出拦截 + 步骤完整性检查。v1.4.0(活跃规则注入+URL检测+CoVe自检+平台检测)——直接 patch SKILL.md 被内核拦截、断言须附证据、步骤没做完禁止 LLM 回复。

### 双层哨兵 + 步骤检查

```
用户消息
  ├─ A 层哨兵（Plugin）: 否定词正则广撒网 → 标记「疑似纠正」
  ├─ 步骤完整性检查（v5.5.4）: 链接/文件/clarify/workflow 四重强制验证
  ├─ B 层判断（Skill）: LLM 语义理解 → 确认 → 三步走
  └─ 命中 sentinel 关键词 → 输出拦截
```

## 兼容性

### 平台
| Windows | macOS | Linux |
|:-------:|:-----:|:-----:|
| ✅ | ✅ | ✅ |

### AI Agent

| 能力 | Hermes | OpenClaw | Claude Code | Codex | 其他 |
|------|:------:|:--------:|:-----------:|:-----:|:----:|
| Skill 层（规则管理） | ✅ | ✅ | ✅ | ✅ | ✅ |
| Plugin 硬拦截 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 自动加载 | ✅ | ❌ | ❌ | ❌ | ❌ |

- **Hermes**：三层全开，硬拦截 + 步骤检查 + 自动加载
- **其他 Agent**：Skill 层可用（AI 自觉遵守规则），无硬拦截

## 快速安装

```bash
# 1. 克隆仓库
git clone https://github.com/L1veSong/Canon-Mnemonic-Guard.git
cd Canon-Mnemonic-Guard

# 2. 复制 Skill
cp -r canon ~/.hermes/skills/
cp -r guard ~/.hermes/skills/
cp -r mnemonic ~/.hermes/skills/
cp -r canon-mnemonic-guard ~/.hermes/skills/

# 3. 复制 Plugin（仅 Hermes）
cp -r skill-autoload ~/.hermes/plugins/
cp -r sentinel ~/.hermes/plugins/

# 4. 一键初始化（自动配置 config.yaml）
python3 ~/.hermes/skills/canon-mnemonic-guard/scripts/init.py

# 5. 重启 Hermes
```

> **init.py 会自动做什么？** 创建规则目录 → 写入默认配置 → 配置 config.yaml（启用插件 + 自动加载）→ 询问 SOUL.md 激活标记。零手动。

## 命令参考

| 命令 | 用途 |
|------|------|
| `!remember 禁止xxx` | 手动记录规则 |
| `!solidify` | 固化 errors.jsonl → rules/ |
| `!scan` | 扫盘提取准则 |
| `!log` | 三线协调日志 |
| `!diagnose` | 五阶段深度体检 |
| `!patterns` | 查看重复违规模式 |
| `!datasource` | 数据源健康状态 |
| `!export` / `!import` | 规则导入导出 |
| `!dashboard` | 可视化 Dashboard（`python3 ~/.hermes/dashboard/server.py`） |

## 卸载

```bash
# 普通卸载（保留用户规则数据）
python3 scripts/init.py --uninstall

# 彻底清除（含所有规则）
python3 scripts/init.py --uninstall --purge
```

卸载会恢复 config.yaml 到安装前状态，不碰其他插件和配置。

## 架构

```
canon/          v2.7.2   典则线 — 规则生产库
guard/          v4.8.3   护栏线 — 规则执行器（697→77行精炼版）
mnemonic/       v3.5.3   忆存线 — 模式识别
canon-mnemonic-guard/  v5.6.0   外观层 — 四包索引 + 微型调度器 + 四名冲突检测
skill-autoload/ v1.0.1   Plugin — 自动加载（适配 Hermes ≥v0.14.0）
sentinel/      v1.4.0   Plugin — 17hooks硬拦截 + 活跃规则注入 + URL检测 + CoVe自检
```

## 规则存储

```
~/.hermes/self-reflection/
├── rules/ban/        # 禁止项（.md + YAML frontmatter）
├── rules/gap/        # 缺失项
├── rules/lazy/       # 偷懒项
├── rules/_index.md   # 自动索引
├── errors.jsonl      # 原始错误记录
├── patterns.json     # 匹配模式库
├── state.json        # 跨会话状态
├── escalation.json   # 升级状态（v5.5.4 新增）
├── blacklist.json    # 永久黑名单（自动生成）
└── config.json       # 引擎配置
```

## License

MIT © 2026 L1veSong
