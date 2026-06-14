# CMG Desktop 试用暴露的跨平台缺陷

> 2026-06-04 | 来源：Hermes Desktop v0.15.1 试用 | 三 AI 交叉验证（Hermes + DeepSeek + 豆包）

## 核心发现

sentinel Plugin 有三个钩子在 CLI 上"能用"但实际依赖 AI 自我修正循环：
- `transform_llm_output` — 输出替换后 AI 看到拦截 → 自我修正 → 用户无感
- `pre_llm_call` sentinel — 注入 `[CMG-SENTINEL]` 后 AI 自动处理
- `post_llm_call` — 证据校验后 AI 重试

**任何没有 AI 重试循环的平台（Desktop/Web/API/Gateway），这三个钩子都会导致输出死锁。**

## 四个具体问题

| # | 问题 | 根因 | 修法 |
|---|------|------|------|
| 1 | CMG 自噬循环 | ban 规则关键词"激活"匹配 CMG 自己的激活消息 | 关键词改为完整短语 |
| 2 | Desktop 输出死锁 | `transform_llm_output` 替换输出直接渲染 → 无重试 | sentinel 加平台检测 |
| 3 | 哨兵劫持消息流 | sentinel 注入 `[CMG-SENTINEL]` → Desktop UI 异常 | 非 CLI 平台静默记录 |
| 4 | 59 条 ban 规则宽泛词 | "激活""CMG""打包""发布"等 2 字日常高频词 | 不改规则本身，改执行方式 |

## 设计教训

1. 不能假设所有平台都有 AI 自愈循环
2. ban 规则关键词不能包含 CMG 自身输出中的高频词
3. 输出替换模式仅在 Agent 能自我修正的交互环境里安全
4. sentinel 的 Plugin 层需要平台感知，不能一刀切

## sentinel v1.4.0 平台检测

已落地：通过 `HERMES_DESKTOP_CHILD_PID` 环境变量检测 Desktop 平台，自动跳过不兼容的钩子。

详见 `~/.hermes/plans/cmg-platform-adaptation_task_plan.md`
