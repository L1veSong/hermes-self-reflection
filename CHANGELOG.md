# CMG 生态系统更新日志

## v5.6.0 (2026-06-14) — 插件改名 + 规则清理 + Dashboard 修复

### 重大变更
- **sentinel（原 cmg-guard）改名**：插件名、配置 key、日志前缀全链路同步
- **规则库清理**：gap 12→4, lazy 9→3（删除 4 空壳，归档 10 死规则到 dead/），总量 82→69
- **Dashboard 七项修复**：时区 bug、趋势图 DPR 模糊、英文 i18n 补全、版本/配置自适应、CJK 审计

### 组件版本
- canon v2.7.2 / guard v4.8.3 / mnemonic v3.5.3（无变更）
- canon-mnemonic-guard v5.6.0（文档同步改名 + 规则数更新）
- sentinel v1.4.0（活跃规则注入 + URL 检测 + CoVe 自检 + 平台检测）
- skill-autoload v1.0.1（无变更）

### sentinel v1.3.0 → v1.4.0
- pre_llm_call：活跃规则注入 + URL 检测提示 + 任务推荐
- post_llm_call：CoVe 自检薄层
- 平台检测：Desktop/GUI 自动跳过不兼容钩子

## v5.5.5 (2026-05-30) — sentinel v1.3.0 + 四名冲突检测

### 新增
- **sentinel v1.2.0 → v1.3.0**：17 个 hook 全面覆盖五阶段
  - **pre_tool_call 阻断**：直接 patch SKILL.md 未经 hermes-agent-skill-authoring → 内核拦截，AI 无执行机会
  - **自披露闭环**：AI 断言必须附带证据（「测试通过了」→ 无证据 → 拦截要求补充）
  - **任务完成声明验证**：AI 声称「完成/搞定/已打包」→ 无核对痕迹 → 拦截
  - **外部来源主张验证**：AI 声称「我看了/三个AI都同意/交叉验证」→ 无原文摘录 → 拦截
  - **拦截通知 visible 模式**：用户可见拦截详情，透明化
- **四名冲突检测**：init.py 安装时 + !diagnose 启动时扫描 canon/guard/mnemonic/canon-mnemonic-guard 是否与第三方 skill 重名
- **scripts/check-name-conflicts.py**：独立冲突检测工具，支持 --fix 交互修复
- 冲突解决三选一：改第三方/改 CMG/两者都改/跳过

### 子包版本
- canon v2.7.2 / guard **v4.8.3**（文档精简 697→77 行）/ mnemonic v3.5.3（无变更）
- canon-mnemonic-guard v5.5.5（+四名冲突检测 + sentinel v1.3.0）
- skill-autoload v1.0.1（无变更）/ sentinel v1.3.0（17hooks + pre_tool_call阻断 + 自披露闭环）

---

## v5.5.4 (2026-05-28) — sentinel v1.2.0

### sentinel v1.1.0 → v1.2.0
- **步骤完整性检查**：pre_llm_call 新增 4 条强制规则（链接完整阅读、文件覆盖度校验、Orchestrator clarify、Skill workflow 执行）
- **分阶段升级系统**：同一错误逐步升级（第1次标记→第2次警告→第3次推草稿→第5次黑名单）
- **新增 post_llm_call 钩子**：AI 回复后二次黑名单扫描
- 哨兵正则优化

### 子包版本
- canon v2.7.2 / guard v4.8.2 / mnemonic v3.5.3（无变更）
- canon-mnemonic-guard v5.5.4（版本号跟踪）
- skill-autoload v1.0.1（无变更）

---

## v5.5.3 (2026-05-26) — 哨兵 + 一键部署

### 新增

- **双层哨兵**：A 层（sentinel Plugin）正则广撒网 + B 层（CMG Skill）LLM 语义判断，关键词漏网率从 80% 降至接近零
- **意图识别优先规则**（rule_meta_001）：用户纠正自动触发 CMG 三步走，不等追问
- **init.py 自动配置**：安装时自动写入 config.yaml（启用插件 + 自动加载），零手动
- **一键卸载**：`python3 init.py --uninstall` 恢复安装前状态，不碰其他配置

### 变更

- sentinel v1.0.0 → v1.1.0：新增 `pre_llm_call` sentinel hook（默认开启），三组正则覆盖 80%+ 纠正句式
- skill-autoload v1.0.0 → v1.0.1：`pre_system_prompt` → `pre_llm_call`，适配 Hermes ≥v0.14.0
- init.py：+Phase 7.5 自动配置 config.yaml，+--uninstall/--purge 卸载支持
- README：重写为完整安装指南 + 兼容性矩阵

### 兼容性

- Hermes ≥v0.14.0：三层全开
- Hermes ≤v0.13.x：skill-autoload 需降级到 v1.0.0（pre_system_prompt）
- 其他 Agent：Skill 层可用，Plugin 层不可用

### 子包版本

- canon v2.7.2 / guard v4.8.2 / mnemonic v3.5.3（无变更）
- canon-mnemonic-guard v5.5.3（+init.py 增强）

---

## v5.5.2 (2026-05-25) — 默认固化阈值10→3

- 默认自动固化阈值从 10 降至 3
- 修复 init.py 版本号滞后（跨两个大版本未更新）

## v5.5.1 (2026-05-25) — 三层闭环首次发布

### 新增插件

- skill-autoload v1.0.0：pre_system_prompt 自动加载 CMG
- sentinel v1.0.0：transform_llm_output 硬拦截

### canon-mnemonic-guard v5.5.1

- README 更新为三层闭环说明
- 配套生态加入两个新插件

---

## v5.5.0 (2026-05-25) — 微型调度器

- 微型调度器：Guard 拦截自动匹配配套 skill
- P1-P4 全部完成

---

## v5.4.0 (2026-05-24) — 大更

- P1: 同会话升级 + P3: 用户纠正提升 + P4: 误报降级
- Mnemonic v3.5.0: 上下文保留

---

## v5.3.0 (2026-05-23) — 风险分级

- Guard 风险分级（不可逆操作暂停确认）

---

## v5.2.0 (2026-05-22) — 四包制

- 定时扫盘 + 协调日志 + 一键诊断
- !scan-recommendations

---

## v5.1.0 (2026-05-21) — 四包分装

- Canon / Guard / Mnemonic 物理拆分

---

## v5.0.0 (2026-05-20) — 三线合一

- 典则 + 护栏 + 忆存 → 三省引擎
