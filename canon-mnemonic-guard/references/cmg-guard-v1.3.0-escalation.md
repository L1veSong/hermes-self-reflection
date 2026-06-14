# sentinel v1.3.0 升级链设计

> 配套插件 sentinel 的分阶段升级系统设计文档。v1.2.0 引入，v1.3.0 沿袭。2026-05-30。

## 设计原则

不搞一刀切黑名单。同一错误根据犯的次数逐步升级——给 AI 纠正机会，反复犯才永久禁止。

## 升级链

```
第1次 → SENTINEL       标记提醒（monitor级）
第2次 → SENTINEL-L2    警告拦截（soft级）
第3次 → SENTINEL-L3    建议固化规则（hard级）
第5次+ → BLACKLIST      永久禁止（hard级，进黑名单）
```

## 与 CMG 规则分级的关系

升级链跟踪"犯了多少次"（计数维度），CMG 规则分级定义"规则有多严"（严重维度）。两者配合：

| CMG规则级 | 升级链 | 行为 |
|:--:|:--:|------|
| monitor | L1 | 仅记录，不拦截 |
| soft | L2 | 提醒+警告 |
| hard | L3 | 推规则草案 |
| hard | L4 | 永久黑名单 |

## 技术实现

- 状态持久化：`~/.hermes/self-reflection/escalation.json`
- 每次哨兵命中 → 提取用户消息前5词作为 pattern key → 计数+1
- 根据 count 计算 level（`_calc_level` 函数）
- level≥4 → 自动加入 `blacklist.json`
- `pre_llm_call` 中优先扫描黑名单，命中直接阻断

## 位置

sentinel 是配套插件，不是 CMG 核心四线。离开 Hermes 平台不可用。核心四线（Canon/Guard/Mnemonic/外观层）是规则体系基石，换平台后适配的是核心，不是插件。
