# sentinel v1.2.0

> Hermes 插件：CMG 规则系统级强制拦截。从"事后检查"升级为"事前拦截"——AI 跳步骤 → LLM 调用前直接阻断。

---

## 定位

sentinel 是 CMG（三省引擎）的**配套硬拦截插件**，不是 CMG 核心四线。

CMG 核心四线：
```
Canon v2.7.2        → 典则线（规则生产库）
Mnemonic v3.5.3     → 忆存线（状态记忆层）
Guard v4.8.3        → 护栏线（规则执行器）
canon-mnemonic-guard v5.6.0 → 外观层（四包索引 + 调度器）
```

配套插件：
```
skill-autoload → 自动加载 CMG Skill（加载辅助）
sentinel      → 系统级硬拦截（本插件）
```

和 CMG Skill 不同：Skill 层靠 AI 自觉遵守，可以被跳过。sentinel 在 Hermes 内核层拦截——AI 没有机会绕过去。

---

## 四层防护

```
用户输入
  │
  ▼
┌─────────────────────────────────────────────┐
│ pre_llm_call                                 │
│  ① 黑名单扫描 — 永久禁止的行为直接阻断        │
│  ② 哨兵检测   — 识别用户纠正意图              │
│  ③ 步骤完整性 — 该做的事没做就拦截             │
└─────────────────────────────────────────────┘
  │
  ▼
LLM 生成回复
  │
  ▼
┌─────────────────────────────────────────────┐
│ transform_llm_output                         │
│  ④ 关键词扫描 — ban 规则命中 → 替换为拦截消息  │
└─────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────┐
│ post_llm_call                                │
│  ⑤ 二次黑名单 — AI 回复后再扫一轮             │
└─────────────────────────────────────────────┘
```

---

## 步骤完整性检查（v1.2.0 新增）

AI 准备回复时，sentinel 先检查该做的事做没做：

| 规则 | 触发条件 | 拦截条件 |
|------|---------|---------|
| 链接完整阅读 | 会话中出现了 HTTP 链接 | 未调用 web_extract + vision_analyze 看完所有内容（含图片） |
| 文件覆盖度校验 | 刚创建/修改了持久化文件 | 未逐条核对后输出 N/N 确认 |
| Orchestrator clarify | 正在执行 IF/planning 等流程 | 每阶段结束未用 clarify() 让用户确认 |
| Skill workflow 执行 | 用户说"跑一遍/走一遍 XX" | 只读了文档未执行完整 workflow |

任一条不满足 → LLM 调用被阻断，system prompt 注入强制补完指令。

---

## 分阶段升级系统（v1.2.0 新增）

同一个错误不会立刻进黑名单。根据违规次数逐步升级：

| 次数 | 级别 | 行为 | 对应 CMG 规则级 |
|------|------|------|:--:|
| 第1次 | SENTINEL | 标记提醒，AI 注意即可 | monitor |
| 第2次(同会话) | SENTINEL-L2 | 警告拦截，必须纠正 | soft |
| 第3次(7天内) | SENTINEL-L3 | 建议固化规则，推 rule 草案 | hard |
| 第5次+ | BLACKLIST | 永久禁止，全链路拦截 | hard |

升级状态持久化到 `~/.hermes/self-reflection/escalation.json`，跨会话不丢失。

---

## 安装

```bash
cp -r sentinel ~/.hermes/plugins/
```

```yaml
# ~/.hermes/config.yaml
plugins:
  enabled:
    - sentinel

# 可选配置（均默认开启）
sentinel:
  lightweight_sentinel: true   # 哨兵：否定词正则扫描用户输入
  step_check: true             # 步骤完整性检查（v1.2.0）
```

安装后重启 Hermes 生效。启动日志中看到 `[sentinel] v1.2.0 registered` 即成功。

---

## 原理

### 规则加载
启动时读取 `~/.hermes/self-reflection/rules/ban/*.md`，提取每条规则的 frontmatter 中的 `keywords` 字段，构建关键词匹配库。

### 钩子执行流

**pre_llm_call**（每次 LLM 调用前）：
1. 扫描用户输入 → 匹配黑名单（level 4 才命中）
2. 扫描用户输入 → 哨兵正则匹配（否定词模式）→ 匹配则记录升级
3. 检查会话上下文 → 是否有未完成的步骤 → 有则阻断

**transform_llm_output**（每次 AI 回复后）：
1. 扫描 AI 输出全文 → 关键词匹配 ban 规则
2. 命中 → 输出替换为 `[CMG 拦截] 请遵守规则重新回答`
3. AI 下一轮看到拦截消息 → 自动修正

**post_llm_call**（v1.2.0 新增）：
1. 扫描 AI 回复 → 二次黑名单检查

### 哨兵模式
哨兵不直接拦截——它检测用户消息中的纠正意图（"你又犯了""别这样""记住"等），标记为 `suspected_correction`，注入 system prompt 提醒 AI 注意。

### 升级链
每次哨兵命中 → 提取用户消息前5个词作为 pattern key → `escalation.json` 中该 pattern 的计数 +1 → 根据计数返回对应级别的拦截消息。

---

## 配置参考

```yaml
sentinel:
  lightweight_sentinel: true    # 哨兵开关
  step_check: true              # 步骤完整性检查开关
```

关闭哨兵：`lightweight_sentinel: false`  
关闭步骤检查：`step_check: false`

---

## 依赖

- **Hermes Agent**（需支持 `pre_llm_call` / `transform_llm_output` / `post_llm_call` 钩子）
- **CMG Skill**（提供 `rules/ban/*.md` 规则库——canon + guard + mnemonic）

---

## 文件结构

```
sentinel/
├── __init__.py        # 插件主逻辑
├── plugin.yaml        # 插件元数据
├── README.md          # 本文件
├── CHANGELOG.md       # 版本历史
└── LICENSE            # MIT
```

运行时数据：
```
~/.hermes/self-reflection/
├── escalation.json     # 升级状态（新增 v1.2.0）
├── blacklist.json      # 永久黑名单（自动生成，level≥4）
└── rules/ban/*.md      # ban 规则库（由 CMG Skill 维护）
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.2.0 | 2026-05-28 | 步骤完整性检查 + 分阶段升级 + post_llm_call |
| v1.1.0 | 2026-05-25 | 轻量哨兵（否定词正则） |
| v1.0.0 | 2026-05-20 | 初始发布，transform_llm_output 关键词拦截 |

详见 [CHANGELOG.md](CHANGELOG.md)

---

## License

MIT © 2026 L1veSong
