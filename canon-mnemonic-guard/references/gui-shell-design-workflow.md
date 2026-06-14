# GUI 壳子设计工作流 — 教训

> 来源: 2026-05-31 会话，GUI 客户端前端重做 3 次

## 核心教训

**永远不要手写 CSS 做 UI 设计。** 必须先用专业设计工具：

1. `popular-web-designs` — 加载真实设计系统的 tokens（颜色/字体/间距/圆角/阴影）
2. `claude-design` — 设计流程和品味（brief→context→tokens→build→verify）
3. 用设计 tokens 生成 HTML，不是从零手写
4. 呈现选项用视觉原型（4 种风格各一个 HTML），不是文字描述
5. 让用户选风格后再系统应用

## 失败的流程（本会话犯了）

```
手写 CSS → 用户说"太丑了" → 换一套手写 → 还是丑 →
用户说"你用专业设计的skill做这几个做的都好垃圾" →
加载 popular-web-designs → 拿 Linear tokens → 一次过
```

## 正确的流程

```
1. 加载 claude-design + popular-web-designs
2. 用户说风格偏好（如"OpenWebUI 那样"）→ 匹配设计系统
3. 或：提供 3-4 种不同风格的原型 HTML 让用户选
4. 用户选后 → 用该设计系统的 tokens 系统生成完整 UI
5. CSS 变量全来自 tokens，不自己编颜色/间距
```

## Hermes API 调试备忘（本次会话遇到）

- Hermes API server 端口: 8642（不是 11434，那是 Ollama）
- API Key: `HermesLocalKey0000`（找法: `source ~/.hermes/.env && echo $API_SERVER_KEY`）
- 流式响应格式: 第一个 chunk 只有 `{"role":"assistant"}` 无 content
- 解决客户端断开: 收到 WebSocket 消息后立刻发 `{"type":"started"}` 占位
- Hermes 不发 `thinking_content` 字段，不需要思考面板
