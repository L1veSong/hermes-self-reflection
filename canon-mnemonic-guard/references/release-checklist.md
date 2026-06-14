# 发布自检清单

每次版本发布前，逐项确认。跳过任一项即视为未完成发布。

---

## 版本号同步（四包制 · 20 处）

v5.2.0 起，CMG 不再是单文件发布——四个独立 Skill 包须同步升版。

### CMG 外观层（本仓库 · 6 处）

- [ ] `SKILL.md` frontmatter `version`
- [ ] `SKILL.md` `_comment` 行→子包版本号与实际一致
- [ ] `SKILL.md` 标题（`# 三省引擎 (CMG) vX.X.X`）
- [ ] `SKILL.md` 注入格式消息（`三省引擎 vX.X.X · 永久规则`）
- [ ] `SKILL.md` 激活消息（`三省引擎 vX.X.X 已激活`）
- [ ] `SKILL.md` 典则线「当前」标注更新
- [ ] `README.md` 标题 + Badge 版本号
- [ ] `scripts/init.py` 激活标记 + 标题 + 提示文本（v5.5.2 教训：init.py 三处 v5.4.0 跨两版本未更新）
- [ ] `scripts/init.py` 激活标记版本号（`[CMG vX.X.X]`）
- [ ] `scripts/init.py` 初始化标题（`CMG 三省引擎 vX.X.X 初始化`）
- [ ] `scripts/init.py` 提示文本版本号

### 子包独立验证（每个子包 2 处，共 6 处）

- [ ] `canon/SKILL.md` frontmatter `version`
- [ ] `canon/SKILL.md` 激活消息版本号
- [ ] `guard/SKILL.md` frontmatter `version`
- [ ] `guard/SKILL.md` 激活消息版本号
- [ ] `mnemonic/SKILL.md` frontmatter `version`
- [ ] `mnemonic/SKILL.md` 激活消息版本号

### 跨文件残留扫描（5 处）

- [ ] CMG 文件中无上一版 major 版本号残留（历史表格除外）
- [ ] Canon 文件中无上一版版本号残留（历史表格除外）
- [ ] Guard 文件中无上一版版本号残留（历史表格除外）
- [ ] Mnemonic 文件中无上一版版本号残留（历史表格除外）
- [ ] CMG `_comment` 声明的子包版本号 = grep 子包 SKILL.md 的实际版本号

**验证命令（一键跑完）：**
```bash
echo "=== 子包版本号 ===" && \
for skill in canon guard mnemonic; do \
  echo -n "$skill: " && grep "version:" ~/.hermes/skills/software-development/$skill/SKILL.md | head -1; \
done && \
echo "=== CMG 外观层 ===" && \
grep "version:" ~/.hermes/skills/software-development/canon-mnemonic-guard/SKILL.md | head -1 && \
echo "=== CMG _comment ===" && \
grep "_comment" ~/.hermes/skills/software-development/canon-mnemonic-guard/SKILL.md | head -1 && \
echo "=== 旧版残留扫描 ===" && \
echo "Canon:" && grep -c "2\.4\.[0-9]" ~/.hermes/skills/software-development/canon/SKILL.md ~/.hermes/skills/software-development/canon-mnemonic-guard/SKILL.md && \
echo "Guard:" && grep -c "4\.[0-3]\.[0-9]" ~/.hermes/skills/software-development/guard/SKILL.md ~/.hermes/skills/software-development/canon-mnemonic-guard/SKILL.md && \
echo "Mnemonic:" && grep -c "3\.[0-2]\.[0-9]" ~/.hermes/skills/software-development/mnemonic/SKILL.md ~/.hermes/skills/software-development/canon-mnemonic-guard/SKILL.md
```

---

## 内容自洽（4 处）

- [ ] `SKILL.md` 版本变更表新增当前版本条目
- [ ] `SKILL.md` 典则线「当前」标注更新
- [ ] `CHANGELOG.md` 新增当前版本条目
- [ ] `README.md` 内容反映当前版本状态（非旧版「规划中」等描述）

---

## 测试（3 项 → v5.5.4 升级为 5 项）

- [ ] **🔴 功能实测（v5.5.4 新增）：** 用户说「发布」→ 禁止直接说「可以上传」。必须先跑：`!diagnose` 五阶段全部通过 + `!log` 三线数据正常 + `grep cmg.guard agent.log` 确认插件拦截在运行。三项全过才能说「可以上传」。**本条来自 2026-05-28 教训：用户两次纠正「测试呢？没测试怎么发布？」，第一次未固化重犯，第二次才固化 rule_073(hard)。**
- [ ] **🔴 agent.log 拦截验证（v5.5.4 新增）：** `grep -c 'cmg.guard.*hit' ~/.hermes/logs/agent.log` 必须 > 0。确认 sentinel 插件不是注册了但空转。
- [ ] `skill_view` 加载四个 Skill 均成功
- [ ] `readiness_status: available`
- [ ] `setup_needed: false`

## 健康检查（E1 · v5.2.0 新增）

发布前运行 E1 健康检查，确保核心文件就绪：

```bash
REFLECT_DIR="$HOME/.hermes/self-reflection"
echo "rules/:" && [ -d "$REFLECT_DIR/rules" ] && echo "  OK" || echo "  MISSING"
echo "state.json:" && [ -f "$REFLECT_DIR/state.json" ] && echo "  OK" || echo "  MISSING"
echo "patterns.json:" && [ -f "$REFLECT_DIR/patterns.json" ] && echo "  OK" || echo "  MISSING"
echo "intercept_log.jsonl:" && [ -f "$REFLECT_DIR/intercept_log.jsonl" ] && echo "  OK" || echo "  MISSING (首次运行后自动创建)"
echo "mnemonic_state.json:" && [ -f "$REFLECT_DIR/mnemonic_state.json" ] && echo "  OK" || echo "  MISSING (首次运行后自动创建)"
```

mnemonic_state.json 缺失不阻塞发布——Mnemonic 首次加载时自动初始化。

---

## 打包

- [ ] **🔴 桌面文件同步（v5.5.4 教训）：** 发布前对比已安装 vs 桌面包，逐文件验证行数一致。命令：`for f in canon-mnemonic-guard canon guard mnemonic; do echo "$f: installed=$(wc -l < ~/.hermes/skills/software-development/$f/SKILL.md) desktop=$(wc -l < ~/Desktop/CMG-Ecosystem-vX.X.X/$f/SKILL.md)"; done`。任一行数不一致 → 从已安装 cp 到桌面。
- [ ] `zip -r ~/Desktop/Canon-Mnemonic-Guard-vX.X.X.zip . -x ".git/*"`
- [ ] 确认 ZIP 文件存在且大小 > 1KB

---

## 历史教训

> 本清单之所以存在，是因为 v2.2.9 → v5.0.0 期间多次发布时 README 标题、注入/激活消息、CHANGELOG 滞后。纯粹靠脑子记不可靠，必须逐项打勾。

### v5.2.0 新增教训

1. **`patch` 工具引号陷阱：** 当 old_string/new_string 中包含 `\"`（反斜杠转义引号）时，`patch` 工具报 "Escape-drift detected"。解法：用 `read_file` 确认文件中的实际字符（通常是未转义的 `"`），然后在 old_string/new_string 中直接使用未转义引号。不要预判文件内容——先读再写。

2. **四包制版本号不在脑子：** v5.2.0 发布时，CMG SKILL.md 中 3 处硬编码 `v5.1.0`（注入消息、激活消息、典则线「当前」标记）在 frontmatter 更新后仍然滞留。单靠 `grep version:` 不够——`grep` 只命中 frontmatter 行。必须额外 grep 全文的旧 major 版本号（如 `5\.1\.0`）来找这些散落的硬编码。

3. **多文件残留扫描是必须的，不是可选的：** 四包同步升版时，每个子包 SKILL.md 的版本号由 skill_manage 正确更新，但 CMG 外观层内部的子包版本引用（`_comment` 行、版本路线章节）需要手动 grep 确认一致。

### v5.5.4 新增教训

6. **未经测试就声称「可以上传」（2026-05-28 两次纠正）：** 用户说「测试呢？没测试怎么发布？」→ Agent 未固化 → 数分钟后再次声称「可以上传」→ 用户纠正「你之前说过发布前必须测试」。同一会话两次纠正同一问题→CMG P1 escalation 生效→固化 rule_073(hard)。**教训：** 用户说「发布」/「上传」→ 触发发布流程前必须先跑全量功能测试，不跑就说的=违规。此规则已写入 CMG ban#073，sentinel 哨兵下次直接阻断。发布清单测试项从 3 项升级为 5 项（新增功能实测+agent.log 拦截验证）。

5. **桌面文件过期（2026-05-28 实战）：** 发布 v5.5.4 后在会话中改了三省引擎 SKILL.md 的诊断格式 + Guard SKILL.md 坑点，但桌面包仍是旧版。发布审计时发现：CMG SKILL.md 桌面包 1422 行 vs 已安装 1449 行，Guard 桌面包 671 行 vs 已安装 686 行，references 缺 v5.5.4-release-lessons.md。**修复：** 发布清单新增「桌面文件同步」检查——对比已安装 vs 桌面行数，不一致立即 cp 同步。此检查放在 ZIP 压缩前，不可跳过。

4. **scripts/init.py 是版本号盲区：** v5.5.0/v5.5.1 两次发布，init.py 中三处硬编码 v5.4.0 从未更新。因为版本同步检查只覆盖了 SKILL.md/README.md/CHANGELOG.md，漏了 scripts/ 目录。**修复：** 发布清单新增 3 项 init.py 检查——激活标记版本号、初始化标题、提示文本版本号。
