# CMG Plan 文件审计指南

> 创建: 2026-06-14 | 来源: 全系统 plan 文件审计 + master-status 重构

## 触发条件

用户问"CMG plan 都正确吗"、"整理计划文件"、"存储路径整齐吗"时执行。

## 审计清单

### 1. 散落文件检查

```bash
# CMG 相关文件不得散落在 plans/ 根目录
ls ~/.hermes/plans/*cmg* 2>/dev/null
# 有输出 → 移入 plans/cmg/
```

### 2. master-status 引用一致性

```bash
# 提取 master-status 引用的文件名
grep -oP '`([a-zA-Z0-9_\-]+\.md)`' ~/.hermes/plans/cmg/master-status.md | tr -d '`'

# 逐条验证文件存在
for f in <上述输出>; do
  ls ~/.hermes/plans/cmg/$f 2>/dev/null || echo "❌ 缺失: $f"
done
```

常见错误：master-status 引用的文件名带 `cmg-` 前缀，实际文件没有（或反之）。

### 3. 版本号一致性

```bash
# 检查所有 plan 文件中的版本号
grep -ohE 'v[0-9]+\.[0-9]+\.[0-9]+' ~/.hermes/plans/cmg/*.md | sort | uniq -c

# 基线版本应一致：CMG v5.6.0 + sentinel v1.4.0
# 计划版本（v1.5.0 / v2.0.0）是正常的
```

### 4. README.md 完整性

```bash
# README 应列出所有 .md 文件（不含自身）
ls ~/.hermes/plans/cmg/*.md | wc -l  # 实际数
grep -c '\.md' ~/.hermes/plans/cmg/README.md  # README 列出的数量
# 两数应一致
```

### 5. 规则数量

```bash
echo "ban:$(ls ~/.hermes/self-reflection/rules/ban/*.md 2>/dev/null | wc -l)"
echo "gap:$(ls ~/.hermes/self-reflection/rules/gap/*.md 2>/dev/null | wc -l)"
echo "lazy:$(ls ~/.hermes/self-reflection/rules/lazy/*.md 2>/dev/null | wc -l)"
echo "meta:$(ls ~/.hermes/self-reflection/rules/meta/*.md 2>/dev/null | wc -l)"
# 对比 master-status 中声明的数字
```

### 6. 过期计划检测

```bash
# 检查 plan 文件最后修改时间
ls -lt ~/.hermes/plans/cmg/*.md | head -10

# >14天无修改且未在 master-status "进行中"列的 → 标记过期
```

## 2026-06-14 审计实录

发现并修复的问题：

| # | 问题 | 修复 |
|:--:|------|------|
| 1 | `cmg-deepseek-review_plan.md` 散落在 plans/ 根目录 | 移入 cmg/，改名 `deepseek-review_plan.md` |
| 2 | master-status 引用 `cmg-antihallucination-*.md`，实际文件为 `antihallucination-*.md`（缺 cmg- 前缀） | 全部对齐实际文件名 |
| 3 | master-status 引用不存在的 `sentinel-v2.0_architecture.md` | 删除幻影引用 |
| 4 | README.md 只列 5 文件，实际 8 文件 | 补全，标注活跃/过期 |
| 5 | 规则数写 80（59+11+9+1），实际 82（60+12+9+1） | 修正 |
| 6 | sentinel 版本写 1.3.2，实际已部署 1.4.0 | 修正 |
| 7 | SSR plans/ 目录看起来空，实际文件在子目录下 | 教训：目录检查必须递归 |
| 8 | IF 文件散落在 plans/ 根目录（不属于 cmg/） | 标注，未移入 cmg（属 IF 项目） |

## 坑点：目录非空检查不能只看顶层

```bash
# ❌ 错误 — 只看顶层
ls ~/.hermes/plans/ssr/   # 输出: smart-skill-router → 看起来"只有一个子目录"
# → 误判为"空"或"少"

# ✅ 正确 — 递归
find ~/.hermes/plans/ssr -type f
# → 完整列出 9 个文件
```

此坑点在 2026-06-14 会话中触发：AI 说"SSR 目录是空的"，被用户纠正——文件在 `plans/ssr/smart-skill-router/`、`noise-reduction/`、`precision-upgrade/` 子目录下。
