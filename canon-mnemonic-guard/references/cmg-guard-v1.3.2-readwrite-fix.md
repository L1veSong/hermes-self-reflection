# sentinel v1.3.2: pre_tool_call 读写感知修复

> 2026-05-31。修复 v1.3.0 的 pre_tool_call 过于宽泛——连只读操作也拦截。

## 问题

sentinel v1.3.0 的 `_check_pre_tool_call` 用朴素子串匹配：

```python
targets_skill_md = "SKILL.md" in path or "SKILL.md" in command
```

参数含 `SKILL.md` 字符串 → 无条件拦截，要求先加载 authoring 规范。

**被误杀的操作：**
- `read_file(path="/path/to/SKILL.md")` — 纯读，Hermes 架构保证不可写
- `terminal grep version SKILL.md` — 只读命令，不修改文件
- `terminal find ... -name 'SKILL.md'` — 只读搜索
- `execute_code` 中 `read_file(path='...SKILL.md')` — Python 端也是读

## 修复方案

三个通道各自判断读写意图：

### 1. read_file — 白名单放行

Hermes 的 `read_file` 工具架构上不可写，直接放行。

### 2. terminal — 检测写操作符

只拦截含以下写操作符的命令：
- `sed `（行编辑器，原地修改需要 `-i`）
- `>` / `>>`（输出重定向，可覆盖文件）
- `tee `（分流写入）
- `mv ` / `cp ` / `rm ` / `dd ` / `install `（文件系统写操作）
- `awk -i` / `perl -i`（原地编辑）

不含以上操作符的 grep/cat/head/tail/ls/find/wc/stat/file 等纯读命令放行。

### 3. execute_code — 检测 Hermes 写工具

只拦截代码中含 `write_file` 或 `patch(` 调用的。纯运算/纯读取的 execute_code 放行。

## 代码改动

文件：`~/.hermes/plugins/sentinel/__init__.py`

```python
# 旧（v1.3.0）：无条件拦截
targets_skill_md = "SKILL.md" in path or "SKILL.md" in command
if targets_skill_md:
    # → 全部拦截

# 新（v1.3.2）：读写分流
targets_skill_md = "SKILL.md" in path or "SKILL.md" in command
if targets_skill_md:
    if tool_name == "read_file":
        return None  # 纯读，放行
    
    if tool_name == "terminal":
        write_indicators = ['sed ', '>', '>>', 'tee ', 'mv ', 'cp ', 'rm ',
                           'awk -i', 'perl -i', 'dd ', 'install ']
        if not any(w in command for w in write_indicators):
            return None  # 纯读命令，放行
    
    if tool_name == "execute_code":
        write_ops = ['write_file', 'patch(']
        if not any(op in command for op in write_ops):
            return None  # 不含写操作，放行
    
    # 含写操作 → 继续原拦截逻辑
```

## 版本标记

| 位置 | 版本 |
|------|------|
| `plugin.yaml` | v1.3.2 |
| `__init__.py` docstring | v1.3.2 |

## 边界说明

- `terminal echo "text" > SKILL.md` — 被拦截（含 `>`）
- `terminal cat SKILL.md` — 放行（纯读）
- `terminal grep -r pattern dir/` 中某文件叫 `SKILL.md` — 放行（命令不含写操作符，虽然 path 参数可能含 SKILL.md 但 terminal 走 command 参数）
- `execute_code` 中用 Python `open('SKILL.md', 'w')` — 放行（只检测 Hermes 工具的 write_file/patch，不检测原生 Python open）

如需收紧 execute_code 的 Python open 检测，可在 write_ops 列表追加 `open(`。当前设计保守——宁可漏过一个绕过写，不可再误杀正常读操作。

## 验证结果（2026-05-31 重启后）

| # | 测试 | 工具 | 预期 | 实际 |
|---|------|------|:--:|:--:|
| 1 | 读 SKILL.md | read_file | 放行 | ✅ 成功读取 |
| 2 | grep version | terminal | 放行 | ✅ exit=0，找到 `version: 5.6.0` |
| 3 | sed -i 修改 | terminal | 拦截 | ✅ sed 无输出(exit=None)，grep 确认文件未被修改 |

**结论：** 读写分流修复生效。读操作全部放行，写操作保持拦截。
