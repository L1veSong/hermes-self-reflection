# 配套组件版本同步教训

> 来源：CMG v5.5.5 发布（2026-05-30）

## 问题

sentinel 已升级到 v1.3.0（17 hooks + pre_tool_call 阻断 + 自披露闭环），但 CMG 生态包中 7 处仍写 v1.2.0：

| 文件 | 行内容 | 旧值 |
|------|--------|------|
| CMG SKILL.md L3 | description | `sentinel v1.2.0步骤完整性检查...` |
| CMG SKILL.md L31 | 版本变更表 | `+sentinel v1.2.0：pre_llm_call...` |
| CMG SKILL.md L993 | 配套Skill表 | `v1.2.0: 硬拦截 + 步骤完整性检查...` |
| CMG README.md L29 | 三层闭环说明 | `v1.2.0 新增 pre_llm_call 阻断` |
| CMG README.md L117 | 架构版本表 | `sentinel/ v1.2.0 Plugin — 硬拦截...` |
| CMG CHANGELOG.md L3 | v5.5.5 标题 | `四名冲突检测`（未提及 sentinel） |
| CMG CHANGELOG.md L13 | 子包版本行 | `sentinel v1.2.0（无变更）` |

## 根因

主包版本号（v5.5.5）没变，但配套插件版本从 v1.2.0 升到 v1.3.0。标准 version grep（`grep 'v[0-9]\.[0-9]\.[0-9]'`）关注的是主包版本号（5.5.5），不会标记配套组件版本不一致——因为 v1.2.0 和 v1.3.0 都是合法的版本号格式。

## 修复列表

1. 全文件 sentinel 版本号同步：7 处 v1.2.0 → v1.3.0
2. 引用文件重命名：`references/sentinel-v1.2.0-escalation.md` → `v1.3.0`
3. CHANGELOG 补充 sentinel v1.3.0 变更详情

## 预防

多组件发布时，version grep 需额外扫描配套组件的版本号：

```bash
# 标准步骤（检查主包）
grep -rn 'v[0-9]\.[0-9]\.[0-9]' SKILL.md README.md CHANGELOG.md

# 额外步骤（检查配套组件版本）
grep -rn 'sentinel v[0-9]' README.md CHANGELOG.md SKILL.md
grep -rn 'skill-autoload v[0-9]' README.md CHANGELOG.md SKILL.md
```
