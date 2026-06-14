# pre_tool_call 读/写判定边界：stderr 重定向误判

> 2026-05-31 | sentinel v1.3.2

## 症状

```bash
# 纯读命令被拦截
grep "SKILL.md" ~/.hermes/skills/xxx/SKILL.md 2>/dev/null
# → [CMG-GUARD pre_tool_call] 拦截
```

## 根因

`_pre_tool_call` 的 terminal 写操作检测使用子串匹配：

```python
write_indicators = ['sed ', '>', '>>', 'tee ', 'mv ', 'cp ', 'rm ', ...]
has_write = any(w in command for w in write_indicators)
```

`2>/dev/null` 中的 `>` 被匹配为写操作，触发拦截——尽管 `2>/dev/null` 只是 stderr 重定向，不写入任何磁盘文件。

## 触发条件

terminal 命令包含 `SKILL.md` 路径 **且** 包含 shell 重定向操作符 `>` 或 `>>`（即使重定向目标是 `/dev/null`）。

## 绕过方法

- 去掉 stderr 重定向：`grep ... SKILL.md`（不推荐，会刷屏）
- 用 `execute_code` 代替 terminal（execute_code 只检测 `write_file/patch(`，不检测 shell 重定向）
- 用 `read_file` 或 `search_files` 代替 termainl grep（Hermes 工具的推荐方式）

## 是否值得修复

**暂不修复。** 理由：
1. 触发条件苛刻——需要同时命中 SKILL.md 路径 + shell 重定向
2. 绕过简单——execute_code 或 Hermes 工具都可以
3. 修复需要解析 shell 语法（区分 `2>/dev/null` vs `>file`），超出简单子串匹配的复杂度
4. 防御性设计——宁可多拦一个不会写入的 >，不可漏拦一个会写入的 >

## 归类

已知边界，非 bug。v1.3.2 设计文档补充。
