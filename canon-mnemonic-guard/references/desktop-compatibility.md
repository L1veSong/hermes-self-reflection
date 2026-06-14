# sentinel 跨平台兼容性

## 问题

sentinel 插件有三个钩子在非 CLI 平台（Desktop/Web/API）上不兼容：

| 钩子 | CLI 行为 | Desktop 行为 | 问题 |
|------|---------|-------------|------|
| `transform_llm_output` | 替换输出 → AI 看到拦截 → 自我修正 → 重试 | 替换文本直接渲染到聊天 UI | 无重试机制，用户看到拦截消息就卡死 |
| `pre_llm_call` | 哨兵检测 → 注入 `[CMG-SENTINEL]` 上下文 → AI 处理 | 上下文注入到 Desktop 消息流 | 劫持用户消息，Desktop UI 异常 |
| `post_llm_call` | 完成证据校验 → 注入提示 | 同 Desktop | 不兼容 Desktop 的消息处理 |

只有 `pre_tool_call`（工具调用拦截）是跨平台兼容的——它在 Hermes 内核层执行，不涉及 UI 消息流。

## 根因

**CLI 和 Desktop 的关键差异不在规则，在下游处理：**

- **CLI**：同一个 Python 进程内完成「生成 → 拦截 → 重试 → 输出」。用户看不到拦截中间态。
- **Desktop**：Python 后端 + Electron 前端分离。拦截消息直接推到 UI，没有重试循环。

## 修复方案（sentinel v1.4.0+）

在 `_hook_enabled()` 中加入平台检测：

```python
def _detect_platform() -> str:
    """通过 HERMES_PLATFORM / ELECTRON_RUN_AS_NODE 环境变量检测平台"""
    ...

def _hook_enabled(hook_name: str) -> bool:
    ...
    # 输出修改类钩子仅在 CLI 平台生效
    if hook_name in ("pre_llm_call", "post_llm_call", "transform_llm_output"):
        if _detect_platform() != "cli":
            return False
    ...
```

哨兵在非 CLI 平台上**仍然运行但静默**——检测用户纠正、写 errors.jsonl，但不注入 `{"context": flag}` 到对话流。

## 各平台最终行为

| 功能 | CLI | Desktop |
|------|:--:|:--:|
| pre_tool_call（防改 SKILL.md） | ✅ | ✅ |
| transform_llm_output（ban 关键词替换） | ✅ | 自动关 |
| pre_llm_call 哨兵（纠正自动感知） | ✅ 注入上下文 | ✅ 静默记录 |
| pre_llm_call 任务推荐 | ✅ | 自动关 |
| post_llm_call（完成证据校验） | ✅ | 自动关 |

## 重启验证清单

sentinel 代码变更后（修改 `__init__.py`、更新 ban 规则关键词、调整 config.yaml hooks），重启 Hermes 后必须逐项验证。**凭感觉说「应该生效了」不可接受——每项都要有可追溯证据。**

### 验证步骤

```bash
# 1. 平台检测确认
grep "platform=" ~/.hermes/logs/agent.log | tail -3
# 预期：CLI 会话显示 platform=cli，Desktop 显示 platform=desktop

# 2. config.yaml 钩子状态
grep -A 8 'sentinel:' ~/.hermes/config.yaml
# CLI: pre_llm_call/post_llm_call/transform_llm_output=true
# Desktop: 以上三项=false, 只保留 pre_tool_call=true

# 3. sentinel 插件文件确认
head -5 ~/.hermes/plugins/sentinel/__init__.py
# 确认版本号和修改时间（注意：代码头注释可能滞后于实际功能）

# 4. ban 规则关键词审计（防自噬）
grep "keywords:" ~/.hermes/self-reflection/rules/ban/*cmg-declaration* 2>/dev/null
# 预期：完整短语，不含「激活」「CMG」等 CMG 自身输出高频词

# 5. 规则数统计（从实际文件，不凭记忆）
echo "ban:$(ls ~/.hermes/self-reflection/rules/ban/*.md 2>/dev/null | wc -l) gap:$(ls ~/.hermes/self-reflection/rules/gap/*.md 2>/dev/null | wc -l) lazy:$(ls ~/.hermes/self-reflection/rules/lazy/*.md 2>/dev/null | wc -l) meta:$(ls ~/.hermes/self-reflection/rules/meta/*.md 2>/dev/null | wc -l)"

# 6. 哨兵行为确认
grep "sentinel" ~/.hermes/logs/agent.log | tail -5
# CLI: 看到 "flagged suspected correction (platform=cli)" → 注入上下文
# Desktop: 看到 "flagged suspected correction (platform=desktop)" 但不注入

# 7. CMG 自动加载确认
grep "skill-autoload.*canon-mnemonic-guard" ~/.hermes/logs/agent.log | tail -2
```

### 验证报告模板

| 检查项 | 状态 | 证据 |
|--------|:--:|------|
| 平台检测 | ✅/❌ | log: `platform=xxx` |
| 钩子配置 | ✅/❌ | config.yaml sentinel.hooks |
| 插件版本 | ✅/❌ | `__init__.py` 头注释 + mtime |
| ban 关键词 | ✅/❌ | 精确短语 / 无自噬风险 |
| 规则数 | N/M/K/L | 从 `ls | wc -l` 实际统计 |
| 哨兵 | ✅/❌ | agent.log sentinel 行 |
| CMG 加载 | ✅/❌ | skill-autoload 注入确认 |

**反模式：** 说「应该生效了」「看起来正常」「可能没问题」→ 没有 `grep`/`ls` 证据就是没验证。2026-05-22 SOUL 铁则已固化此条。

## ban 规则自噬问题

两条 ban 规则的关键词含 CMG 自身输出中的词：

1. **cmg-declaration-without-load** — 关键词 `激活` 命中 CMG 的「三省引擎已激活」→ 自噬循环
2. **ban_no_cmg_abbreviation** — 关键词 `CMG` 命中任何内部对话 → 全部替换

**教训：**
- ban 规则关键词必须是完整短语，不能是 2 字以下的中文词
- 必须区分「内部对话许可」和「对外文档禁止」
- 2 字关键词的误伤率极高，正常对话中几乎必中
