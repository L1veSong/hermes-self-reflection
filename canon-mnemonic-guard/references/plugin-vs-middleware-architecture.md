# CMG 架构：插件模式 vs 中间件模式

> 2026-05-31 | 来源：CMG ↔ Marvis 平台联动讨论

## 两种架构对比

### 插件模式（当前，Hermes 内）

```
Hermes 内核
  → pre_llm_call hook → sentinel 注入事实/推荐/预拉取
  → LLM 推理
  → post_llm_call hook → sentinel 证据校验/ban扫描
  → pre_tool_call hook → sentinel 读写分流拦截
  → transform_llm_output hook → sentinel 输出替换
  → 用户
```

特性：
- 寄生在 Hermes 内，依赖 hook 机制
- 17 个 hook 注册，4 个核心启用
- 需要区分读/写操作（read_file vs sed）
- 需要三路径降级（hermes API → requests → 失败）
- 受 Hermes 版本升级影响（hook 名可能变）

### 中间件模式（未来，平台内）

```
平台 scheduler
  → cmg.pre_check(task) → 注入事实 + 预拉取
  → agent.run()
  → cmg.post_check(output) → ban扫描 + 证据校验
  → 用户
```

特性：
- 独立模块，平台 import 即可
- 两个函数调用：pre_check + post_check
- 不需要区分读/写（平台层不碰文件）
- 直接用 requests，不走 Hermes 内部 API
- 不受 Hermes 版本升级影响
- 所有接入 agent 自动覆盖（不只是 Hermes）

## 成本对比

| 维度 | 插件模式 | 中间件模式 |
|------|:--:|:--:|
| 接入代码 | 17 个 hook 注册 | `import cmg_middleware` |
| 读/写分流 | 需要正则判断 | 不需要 |
| API 降级 | 三路径 | 直接用 requests |
| 版本兼容 | 依赖 Hermes hook 名 | 零依赖 |
| 覆盖范围 | 仅 Hermes | 所有 agent |
| 规则更新 | 重启 Hermes | 热加载 |

## 结论

插件是"挤进别人的管道"——适配成本高、覆盖窄。中间件是"站在自己的管道里"——平台是自己写的，CMG 直接 import。多 agent 平台做出来之后，防幻觉不是更难的扩展问题，反而是更简单的架构问题。

## 相关

- 联动计划：`~/Desktop/marvis-like-agent-platform/cmg-integration-plan.md`
- sentinel 插件：`~/.hermes/plugins/sentinel/__init__.py`
