# DeepSeek 外部评审对照 — 2026-06-09

> 来源：用户通过微信分享的 DeepSeek 对话截图（5张），Hermes 视觉模型提取。
> 评审对象：CMG v5.6.0 + Idea Foundry
> 方法：逐条建议对照 CMG 当前实际状态，判定完成/未完成/部分完成

---

## 评审一：CMG 开发方向（6大节）

| # | DeepSeek 建议 | CMG v5.6.0 现状 | 判定 |
|---|-------------|----------------|:--:|
| 1 | 30秒示例 + GIF 在 README | 未做。README 有功能描述但无可复制短示例 | ❌ |
| 2 | 规则数据结构设计（JSON/YAML） | rules/ 目录 + YAML frontmatter（ban/gap/lazy/meta） | ✅ |
| 3 | 规则冲突解决机制 | v2.3.1 冲突检测+裁决，优先级明确 | ✅ |
| 4 | v3 做情景感知非纯记忆 | Mnemonic v3.5.3，触发场景标签+上下文感知 | ✅ |
| 5 | v4 集成 ESLint/Prettier 等 lint | sentinel 是 Plugin 层拦截，未接外部 lint | ⚠️ 方向不同 |
| 6 | init 命令 | `scripts/init.py` + `--uninstall` | ✅ |
| 7 | 命令简化（!remember 等） | !remember/!solidify/!scan/!log/!diagnose 等 | ✅ |
| 8 | 规则可注释 | frontmatter 含 description/keywords/source_ids | ✅ |
| 9 | 傻瓜/专家模式 | P5 规划中，`!mode` 未实现 | ❌ |
| 10 | IF 联动（规则集注入代码生成阶段） | SSR 做 skill 匹配桥接，直接 IF-CMG 注入未做 | ⚠️ 间接 |

**核心结论：** 规则系统本体完工率 ~70%。缺口在「对外展示」和「模式切换」。

---

## 评审二：生态构建 8 项目

| # | 项目 | 难度 | CMG 现状 | 判定 |
|---|------|------|---------|:--:|
| 1 | Rule Bazaar 规则共享市场 | ★☆☆ | 无 | ❌ |
| 2 | Rule Linter 规则编译检查 | ★★☆ | check-frontmatter.py 部分覆盖，非独立 linter | ⚠️ |
| 3 | Skill Config Manager 统一配置 | ★★☆ | 无 | ❌ |
| 4 | Skill Logger 日志聚合 | ★☆☆ | `!log` 协调日志+intercept_log.jsonl，非跨 skill | ⚠️ |
| 5 | Skill Bootstrap 一键初始化 | ★☆☆ | ✅ init.py | ✅ |
| 6 | Example Hub 示例项目集 | ★★☆ | 无 | ❌ |
| 7 | Skill RPC 技能互调协议 | ★★☆ | 无（SSR 做匹配不做调用） | ❌ |
| 8 | Web UI 技能状态面板 | ★★☆ | ✅ Dashboard v1.0.0 | ✅ |

**核心结论：** 8 项目完成 2 个，部分覆盖 2 个，未做 4 个。基础设施类（Bootstrap/Dashboard）优先落地，对外生态类（Bazaar/Example Hub/RPC）全空。

---

## 评审三：IF 架构 11 问（5大类）

| 类别 | 问题数 | 说明 |
|------|--------|------|
| 核心编排逻辑 | 3 | 依赖预检查、循环依赖检测、数据格式兼容 |
| 安全与隐私 | 2 | 恶意 skill 注入、敏感信息泄露 |
| 容错与恢复 | 2 | 部分失败回滚、超时控制 |
| 扩展性与维护 | 2 | Skill 版本管理、配置热更新 |
| 用户体验 | 2 | 进度可视化、中断恢复 |

> 此部分属于 Idea Foundry 范畴，不作为 CMG 检查项。记录供 IF 开发时参考。

---

## 评审四：隐私 + 冲突两问

| 问题 | 现状 | 
|------|------|
| Excuse 全部扫描，隐私？ | CMG 扫盘有白名单制（config.json scan_sources），不扫全盘 |
| 不同 Skill 冲突，防冲突机制？ | CMG v2.3.1 有规则冲突检测，v5.5.5 有四名冲突检测。IF 层面冲突解决未独立实现 |

---

## 投入产出比排序（未完成项）

按「实现成本低 + 用户感知强」排序：

1. **30秒示例** — 改 README，10 分钟，最大感知提升
2. **P5 傻瓜/专家模式** — 已在路线图，下个 P 编号
3. **Example Hub** — 5-10 个场景示例，写文档为主
4. **Rule Linter 独立化** — check-frontmatter.py 基础上包装
5. **Rule Bazaar** — GitHub 仓库 + JSON 索引，2-3 天

---

## 视觉模型选择笔记

本次 OCR 使用 Hermes 内置视觉回退模型（非 SiliconFlow）。
- 图1/3/4/5 提取质量好
- 图2 连续两次失败（仅返回数字）
- 用户 memory 记录「SiliconFlow 仅 vision」——中文截图提取应优先走 SiliconFlow 视觉模型
