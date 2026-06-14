---
name: guard
description: 三省引擎(Canon-Mnemonic-Guard)护栏线 (Guard) — 规则执行器。读取 Canon 规则库，执行五层前置拦截。Hermes 平台搭配 cmg-guard 插件实现内核级硬拦截，其他平台靠 Skill 层自觉。v4.8.3 文档精简。
version: 4.8.3
role: guard
stage: pre_action
dependencies: []
min_hermes_version: any
platforms: [linux, macos, windows]
author: L1veSong
license: MIT
metadata:
  hermes:
    tags: [cmg, guard, interception, pre-action]
    related_skills: [canon, mnemonic, canon-mnemonic-guard]
---

# Guard 护栏线 v4.8.3

> **角色**: guard | **阶段**: pre_action | **职责**: 读取 Canon 规则库，执行拦截
> Hermes 用户搭配 `cmg-guard` 插件获得内核级硬拦截；其他平台通过 Skill 层自觉遵守。

---

## 能力

| 拦截层 | 检查内容 | Hermes 硬拦截 | 其他平台 |
|--------|---------|:------------:|:-------:|
| Ban | 精确匹配规则关键词 | ✅ 插件 | Skill 自觉 |
| Fabrication | 防幻觉声称（"已创建/已验证"） | ✅ 插件 | Skill 自觉 |
| StepCompleteness | 防跳步骤（链接未读/文件未校验） | ✅ 插件 | Skill 自觉 |
| SkillLoad | 防偷懒（领域 Skill 未加载） | ❌ | Skill 自觉 |
| Clarify | 防瞎猜（多选项未 clarify） | ❌ | Skill 自觉 |

> **注意**：SkillLoad 和 Clarify 需要语义理解，正则做不到，只能在 Skill 层引导。其余三层 cmg-guard 插件全包。

## cmg-guard 插件（Hermes 专属）

配套插件 `cmg-guard` 提供内核级硬拦截，AI 无法跳过：

| Hook | 检查内容 |
|------|---------|
| `pre_tool_call` | 直接 patch/write SKILL.md → 阻断，要求先加载 authoring。v1.3.2: 读写感知——read_file/grep 放行，sed/>/write_file 拦截 |
| `pre_llm_call` | 哨兵扫描 + 步骤完整性 + 黑名单 |
| `post_llm_call` | 任务完成证据校验 + 外部来源主张验证 |
| `transform_llm_output` | 关键词黑名单替换 |

17 个 hook 全阶段覆盖，4 个核心默认开启，其余按需配置。

## 安装（Hermes）

```bash
# Skill 层
cp -r guard ~/.hermes/skills/software-development/

# Plugin 层（硬拦截）
cp -r cmg-guard ~/.hermes/plugins/

# 一键配置
python3 ~/.hermes/skills/software-development/canon-mnemonic-guard/scripts/init.py
```

**非 Hermes 平台**：只复制 Skill 目录，Plugin 层不可用，依赖 AI 自觉遵守规则。

## 常见坑点

1. **Guard 不会自动加载** — Hermes 技能系统靠任务匹配。需要 SOUL 激活标记或手动 `/skill guard`。
2. **不要给模糊结论** — 「应该已激活」本身就会被拦截。验证到确定为止。
3. **intercept_log 需要有效时间戳** — 手工填充会导致效能分析失败。
4. **输出层拦截不覆盖执行层偷懒** — AI 跳过中间步骤不产生违规关键词→拦截器不触发。这是架构边界，非 Bug。
5. **Skill 层规则不是硬拦截** — 非 Hermes 平台上 Guard 完全靠 AI 自觉。要强制必须用 Plugin。
6. **cmg-guard 插件在非 CLI 平台需特殊配置** — Desktop/Web/API 没有 AI 自我修正循环，`transform_llm_output`/`pre_llm_call`/`post_llm_call` 三个钩子会导致输出死锁。Desktop 端必须关掉这三项，只保留 `pre_tool_call: true`。详见 CMG 外观层 `references/desktop-compatibility.md`。
7. **cmg-guard 代码变更后必须重启验证** — 不能凭感觉说「应该生效了」。需逐项 `grep` agent.log + 统计规则数 + 确认钩子配置。详见 CMG 外观层 `references/desktop-compatibility.md` 的「重启验证清单」。

## 参考文件

- [CHANGELOG.md](CHANGELOG.md) — 完整版本历史
- [README.md](README.md) — 快速上手
- [CMG 外观层](../canon-mnemonic-guard/SKILL.md) — 三线协作全貌
