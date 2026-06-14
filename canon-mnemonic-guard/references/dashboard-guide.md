# Canon-Mnemonic-Guard Dashboard — 实现指南

> 2026-05-30 | Phase 1+3 完成 | server.py 零依赖

## 架构

```
~/.hermes/dashboard/
├── server.py        ← HTTP 服务器（localhost:8765），API + 嵌入式 HTML
└── generate.py      ← 静态 HTML 生成器（备用，无需服务器）
```

## 启动

```
!dashboard           ← Hermes 对话中触发
python3 ~/.hermes/dashboard/server.py          ← CLI 直接启动
python3 ~/.hermes/dashboard/server.py --port 8766  ← 自定义端口
```

## API 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/` | 服务完整 Dashboard HTML |
| GET | `/api/rules` | 返回所有规则 JSON |
| GET | `/api/stats` | 返回拦截/错误/会话统计 |
| GET | `/api/config` | 返回 sentinel 配置 |
| POST | `/api/config` | 写入 sentinel 配置到 config.yaml |
| POST | `/api/rules` | 创建新规则 .md 文件 |
| DELETE | `/api/rules` | 删除规则 .md 文件 |

## 前端功能

### Tab 1: 规则库
- 6 张统计卡片（总数/命中/拦截/错误/高误报/长期未触发）
- 全部规则可排序/筛选表格（按 ID/类型/命中/误报率/最后触发）
- 关键词气泡：hover 显示完整列表，`@keyframes tooltipIn` 动画
- 每行删除按钮（×），右滑淡出动画后移除文件

### Tab 2: 引擎配置
- 17 个 Hook 可视化 toggle（核心 4 个 + 扩展 13 个）
- 拦截通知模式切换（silent/visible）
- 保存按钮 → POST /api/config → 重启 Hermes 生效

### Tab 3: 添加规则
- 表单：类型（ban/gap/lazy）+ ID + 关键词 + 描述
- 提交 → POST /api/rules → 生成 .md 文件

## 设计原则

- Linear 暗色风格（`#0d1117` 背景 + `#7c7cff` 强调色）
- 亮色/暗色一键切换，自动跟随系统 `prefers-color-scheme`
- `prefers-reduced-motion` 支持（无障碍）
- 禁止 "CMG" 缩写，统一使用 "Canon-Mnemonic-Guard" / "三省引擎"

## 常见坑点

1. **JS 中的引号转义**：Python 三重引号内嵌 JavaScript 时，`\'` 会被 Python 吃掉。避免 `onclick="fn(''+var+'')"` 模式，改用 `data-*` 属性 + `this.dataset.xxx`。
2. **配置写入后需重启**：config.yaml 由 Hermes 启动时加载，Dashboard 写入后不会热更新。页面有明确提示。
3. **规则文件冲突**：添加规则时若 ID 已存在，API 返回 409。
4. **静态 HTML 文件无法写回**：`generate.py` 生成的 HTML 只能查看，不能修改配置或添加规则。交互功能必须通过 server.py。
5. **JS 语法验证**：每次修改 embedded JavaScript 后必须 `node --check` 验证，Python 编译通过不代表 JS 正确。
