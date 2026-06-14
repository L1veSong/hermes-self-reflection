# sentinel 代码审计清单

> 用于审查 sentinel 插件 `__init__.py` 代码质量。7 项检查，逐项验证。
> 最后运行: 2026-06-14 (v1.4.0)

## 审计框架

```
1. _parse_fm(text)         ← YAML frontmatter 解析正确性
2. _load_ban_rules()       ← 缓存失效逻辑正确性
3. _inject_active_rules()  ← 关键词匹配正确性
4. _detect_urls()          ← URL 正则覆盖度
5. _pre_llm_call()         ← contexts 合并正确性
6. _post_llm_call() + CoVe ← CLI 检测正确性
7. 整体检查                ← import/命名/异常处理
```

## 检查项详解

### 1. _parse_fm — YAML Frontmatter 解析

**子检查:**
- 1a. `keywords: [a, b]` 列表格式: `re.findall(r'"([^"]*)"')` + fallback `split(",")` → 双引号和裸列表都兼容
- 1b. keywords 引号/无引号: `strip().strip('"').strip("'")` → 两种格式均正常
- 1c. **block scalar (`|`) 与冒号冲突**: 块标量内容行含冒号时，旧代码先检查冒号再检查块模式，导致块的冒号行被解析为 key:value → 破坏 block scalar 完整性

**1c 修复方案 (已验证):**
```python
# 关键：在检查冒号之前先判断块模式
if block_key is not None:
    if not stripped:
        block_buf.append("")
        continue
    if is_indented:
        block_buf.append(stripped)
        continue
    # 非缩进 → 关闭块
    fm[block_key] = "\n".join(block_buf)
    block_key = None; block_buf = None
    # Fall through 解析此行
```

### 2. _load_ban_rules — 缓存逻辑

**子检查:**
- 2a. mtime 比较: 文件级 mtime (非目录级) → 编辑/新增/删除/重命名均正确失效
- 2b. sorted(glob): `sorted(rules_dir.glob("*.md"))` → 确定性遍历

### 3. _inject_active_rules — 关键词匹配

**子检查:**
- 3a. 中文大小写: `msg_lower = user_message.lower()` + `kw.lower()` → 正确(中文 lower 为 no-op)
- 3b. 空 keyword 保护: 三层 guard (加载时 `continue` + 注入前 `if not rules` + 匹配时 `if score > 0`)

### 4. _detect_urls — URL 正则

**子检查:**
- 4a. 正则覆盖: `https?://[^\s<>"')\]]+(?<![,\.;:!?\)\]}>])` → 覆盖基本URL/路径/查询/端口/片段/Markdown链接/逗号结尾
- 已知边界: 中文紧接URL时会被连带匹配（如 `https://example.com你好`），但实际罕见，且仅为提示性质

### 5. _pre_llm_call — contexts 合并

**子检查:**
- 5a. 空 context 过滤: 所有 6 个注入源都有 `if xxx:` 门控
- 5b. 分隔符: `"\n\n".join(contexts)` → 适当

### 6. _post_llm_call / _add_cove_check — CLI 检测

**子检查:**
- 6a. CLI 检测: `_hook_enabled("post_llm_call")` 内置平台门控 → 非 CLI 返回 False
- 6b. CoVe 非 CLI 安全: 仅被 `_post_llm_call` 调用 → 被 6a 阻断链保护

### 7. 整体检查

**子检查:**
- 7a. 未使用 import: 全部 typing 导入有实际使用
- 7b. 命名一致性: 全文件 snake_case
- 7c. 异常处理: `_save_escalation()` 和 `_maybe_add_to_blacklist()` 写文件无 try/except → **已修复**

## 已知陷阱

| 陷阱 | 发现版本 | 状态 |
|------|---------|:--:|
| `_parse_fm` block scalar 冒号行被当 key:value 解析 | v1.4.0 | ✅ 已修复 |
| `_detect_platform()` 冗余 `import os` | v1.4.0 | ✅ 已修复 |
| `_save_escalation`/`_maybe_add_to_blacklist` 无异常处理 | v1.4.0 | ✅ 已修复 |

## 审计执行流程

```bash
# 1. 加载
read_file ~/.hermes/plugins/sentinel/__init__.py

# 2. 逐项验证（按检查项顺序）
# 3. 发现 Bug → patch 修复
# 4. 每次 patch 后 patch 工具自动 lint

# 5. 覆盖度校验
# 逐条核对: 发现数 = 修复数 = 验证数
```
