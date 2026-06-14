# Hermes 升级适配指南

## v0.13 → v0.14.0 变更

### 移除的 Hook

`pre_system_prompt` — Hermes v0.14.0 不再支持此 hook。

### 新增的 Hook

替代方案：`pre_llm_call`。在 LLM 调用前触发，可注入 context 到用户消息。

有效 hooks (v0.14.0)：
on_session_end, on_session_finalize, on_session_reset, on_session_start,
post_api_request, post_approval_response, post_llm_call, post_tool_call,
pre_api_request, pre_approval_request, pre_gateway_dispatch, pre_llm_call,
pre_tool_call, subagent_stop, transform_llm_output, transform_terminal_output,
transform_tool_result

## 影响范围

### skill-autoload Plugin

**v1.0.0** (pre_system_prompt) → **v1.0.1** (pre_llm_call)

变更：
- `plugin.yaml`: `provides_hooks: [pre_llm_call]`
- `__init__.py`: 替换 hook 函数签名，新增 `is_first_turn` 参数，跟踪已注入会话避免重复
- Context 注入到用户消息而非 system prompt（保护 prompt 缓存）

### sentinel Plugin

**v1.0.0** → **v1.1.0**

新增：
- `pre_llm_call` hook（sentinel 哨兵扫描用户输入）
- `plugin.yaml`: `provides_hooks: [transform_llm_output, pre_llm_call]`

## CMG Skill 恢复流程

Hermes 升级可能清空 `~/.hermes/skills/` 下的文件。恢复步骤：

1. 从 GitHub/备份恢复四包 SKILL.md：
   ```bash
   git clone https://github.com/L1veSong/Canon-Mnemonic-Guard /tmp/cmg
   cp -r /tmp/cmg/canon ~/.hermes/skills/
   cp -r /tmp/cmg/guard ~/.hermes/skills/
   cp -r /tmp/cmg/mnemonic ~/.hermes/skills/
   cp -r /tmp/cmg/canon-mnemonic-guard ~/.hermes/skills/
   ```

2. 更新插件版本：
   ```bash
   cp -r /tmp/cmg/skill-autoload ~/.hermes/plugins/
   cp -r /tmp/cmg/sentinel ~/.hermes/plugins/
   ```

3. 运行 init.py 重新配置

4. 重启 Hermes 并检查日志：
   ```bash
   grep 'unknown hook' ~/.hermes/logs/agent.log  # 应无输出
   grep 'sentinel' ~/.hermes/logs/agent.log      # 应显示 registered
   ```
