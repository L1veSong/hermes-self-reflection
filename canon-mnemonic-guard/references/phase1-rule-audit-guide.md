# Phase 1 规则审计指南

> v1.0.0 — 2026-06-14 | 用于 CMG 规则治理的 Phase 1 审计流程

## 目的

定期评估 gap(缺失)和 lazy(偷懒)规则是否可以升级为 ban(硬拦截)，同时识别死规则供归档。

## 审计步骤

### Step 1: 运行 !diagnose

获取全貌：
- 文件完整性（5 文件）
- 规则有效性（frontmatter 覆盖率、_index.md 匹配）
- 跨模块引用一致性
- 数据源健康
- 子包版本

**注意**：!diagnose 的输出直接作为审计基础数据。Phase 2 会检测 `_index.md` 表格行数 vs 实际文件数的漂移。

### Step 2: 读取所有 gap/lazy 规则 frontmatter

```bash
# 统计文件数（sentinel 可能拦截 terminal，改用 read_file 逐个读）
ls ~/.hermes/self-reflection/rules/gap/*.md | wc -l
ls ~/.hermes/self-reflection/rules/lazy/*.md | wc -l
```

逐条提取：
- `hit_count` — 命中次数
- `last_triggered` — 最后命中日期（判断死规则的关键字段）
- `keywords` — 当前关键词列表
- `level` — hard/soft/monitor
- `date` — 创建日期
- `source` — session/disk_scan/user_correction

**坑点**：很多 session 来源规则缺少 `last_triggered` 字段 —— 用 `date` 作为 fallback。

### Step 3: 查 errors.jsonl 找违反记录

搜索 type: gap 和 type: lazy 的记录：

```bash
grep '"type":\s*"gap"' errors.jsonl
grep '"type":\s*"lazy"' errors.jsonl
```

区分真实违反 vs 扫盘提取：
- `trigger: "扫盘提取:*"` → 初始规则创建，非真实违反
- `source: "session"` 或 `"user_correction"` → 真实违反

### Step 4: 评估升级可行性（三维检查）

每条规则评估三个维度：

#### 维度 1: 有违反记录
- ✅ 有真实违反记录（非扫盘提取）
- ⚠️ 仅有扫盘提取记录
- ❌ 无任何记录

#### 维度 2: 可转关键词匹配
gap/lazy 规则本质是行为缺口（"AI 没做什么"），不是文本输出违规（"AI 说了不该说的词"）。只有能通过 AI 输出文本检测到的规则才能转为 ban。

**可转的**（AI 输出中有可检测的文本模式）：
- "跳过这一步"、"省略掉" → 偷懒摆烂
- "建议安装 X skill" → 推荐前未验证
- "自己写一个" → 不搜直接建
- "直接用 write_file" → 覆盖前不读

**不可转的**（行为缺口，无文本信号）：
- "没加载 writing-skills" → 不加载是 absence，输出中无信号
- "不跑 TDD" → 不跑测试是 absence
- "不跑 checklist" → 不跑是 absence

#### 维度 3: 不会自噬（不自匹配 CMG 自身输出）

这是最关键的安全检查。ban 规则的关键词会被 sentinel 扫描 AI 输出。如果关键词匹配了 CMG 自己的正常输出（激活消息、!log、!diagnose 报告），会导致 CMG 拦截自己 → 死循环。

**自噬检查清单**（逐项对照 CMG 的正常输出）：

| CMG 输出 | 含有的词（需排除） | 不含的词（安全） |
|----------|-------------------|-----------------|
| 激活消息 | `激活`、`偷懒`、`缺失`、`禁止` | "跳过这一步"、"建议安装"、"write_file" |
| !log 输出 | `推荐`、`规则`、`拦截`、`条` | "装一个 skill"、"造轮子"、"覆盖就行" |
| !diagnose 报告 | `建议`、`规则`、`条`、`新建` | "糊弄过去"、"马虎了事"、"自己写一个" |
| !patterns 输出 | `模式`、`识别` | (较少风险词) |

**自噬检查步骤**：
1. 列出候选 keywords
2. 逐个检查：这个词/短语是否出现在 CMG 的激活消息中？
3. 检查 !log 输出格式
4. 检查 !diagnose 输出格式
5. 检查 CMG SKILL.md 自身的描述文本（预加载后上下文）
6. 发现重叠 → 替换为更精确的短语，或加上下文约束

### Step 5: 识别死规则

**严格死规则**：`hit_count = 0` 且 `last_triggered > 30天前`

**准死规则**：`hit_count = 0` 但不足 30 天（标记提醒，下次审计复核）

**占位死规则**：`rule_*_unknown` 类，无 keywords 或无实际内容

### Step 6: 输出审计报告

格式：
1. !diagnose 摘要
2. gap/lazy 规则统计表（hit_count / last_triggered / keywords）
3. errors.jsonl 违反记录分类（真实 vs 扫盘）
4. 死规则清单（严格死 + 准死 + 占位死）
5. 升级候选评估矩阵（三维 × 每条规则）
6. 最终推荐升级列表（含安全版 keywords）
7. 附加发现（_index.md 漂移、patterns.json 空、字段缺失等）

## 升级规则的安全 keywords 设计

### 原则

1. **精确短语优于宽泛词**：`"跳过这一步"` 优于 `"跳过"`
2. **上下文约束优于裸词**：`"建议安装.*skill"` 优于 `"推荐"`
3. **排除 CMG 自噬词**：先查 CMG 激活消息/!log/!diagnose 输出，排除重叠词
4. **behavior 缺口不可转**：不加载 skill、不跑 TDD、不跑 checklist 是行为 absence，关键词扫不到

### 自噬排除词表（2026-06-14 已验证）

以下词/模式出现在 CMG 自身输出中，**不得**作为 ban 规则关键词：

| 排除词 | 出现位置 |
|--------|---------|
| `激活` | CMG 激活消息 "三省引擎已激活" |
| `偷懒` | 激活消息 "9 条偷懒" |
| `缺失` | 激活消息 "12 条缺失" |
| `推荐` | !log 输出 "推荐: ralph-loop/VBC/..." |
| `简化` | CMG 文档 "简化触发词" |
| `CMG` | 对外缩写，ban_rule 已禁止 |
| `新建` / `创建` | !diagnose 报告、通用语境（false positive 极高） |
| `规则` | 全 CMG 输出通用词 |
| `skill` | 全 CMG 输出通用词（除非在上下文中与 `安装`/`装` 共现） |

## 已知局限性

1. **6 条规则不可升级**：行为缺口类（不用专业 skill 写 skill、不走 TDD、不跑 checklist 等）本质是 "AI 没做什么"，关键词匹配无法检测。需要 sentinel v2.0 行为级检测器。

2. **22/82 规则无硬拦截**：gap(12) + lazy(9) + meta(1) = 22 条规则全靠 AI 自觉遵守。即便本次升级 5 条，仍有 17 条缺口。

3. **patterns.json 经常为空**：模式积累数据缺失，无法辅助判断规则频繁度。
