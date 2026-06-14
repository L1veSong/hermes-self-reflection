# CMG 未来路线图

## 近期（v5.5.5 → v5.5.6+）

### 拦截可见性增强
- 拦截提示：transform_llm_output 静默→明示（intercept_notice 开关 ✅ 已实现）
- 拦截后用户选择：重试/补充细节/停止（via clarify）
- 状态：已记录，待开发

### 钩子覆盖
- pre_tool_call 堵 SKILL.md 直接改 ✅ v1.3.0
- 17 钩子全注册，4 默认开 ✅ v1.3.0
- 智能缺口检测（记规则→检测所需钩子→提示） ✅ v5.5.5

## 中期

### CMG Dashboard (Web UI)
- 需求：可视化后台，直观改 CMG 配置
- 参考：Hermes Dashboard
- 场景：开关钩子、查看规则库、拦截日志、调整阈值
- 状态：创意阶段，未开始

### 拦截后闭环完善
- ralph-loop 自动重试
- 用户可选的修正路径（补充细节/停止/换方案）

## 长期

### 思考过程验证
- 不验证就开口 → 无解（AI 推理层）
- 自披露闭环缓解方式：回复必须带证据

### 跨平台 CMG
- Claude Code / Codex / Cursor 适配
- 插件层仅 Hermes 可用，Skill 层跨平台
