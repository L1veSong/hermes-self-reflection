# 自披露闭环（Self-Disclosure Loop）— 参考案例

> v5.5.5 新增。适用于需要 AI 对自己的每个断言提供验证证据的场景。

## 问题

AI 经常做出未经验证的断言：「测试通过了」「Obsidian 已安装」「CMG 四名无冲突」——但没有终端输出、没有文件列表、没有任何可验证的证据。用户无法判断真假。

## 解决方案：三步自披露闭环

```
1. 强制招供 → pre_llm_call step check
   AI 回复中必须声明「使用了什么工具、验证了什么」
   缺声明 → 步骤不完整 → 禁止回复

2. 招供即被抓 → transform_llm_output
   扫输出文本 → 发现违规声明（如「测试通过」但没证据）
   → ban 关键词命中 → 拦截

3. 被抓就重来 → ralph-loop
   拦截触发 → 自动重启任务 → 直到输出干净且带证据
```

## 如何启用

### Step 1: 确保 sentinel v1.3.0 已安装

```bash
# 检查版本
grep version ~/.hermes/plugins/sentinel/plugin.yaml
# 应显示: version: 1.3.0
```

### Step 2: 添加 step check 规则

sentinel v1.3.0 自带 `evidence_for_claims` 步骤检查规则（默认开启）。无需额外配置。

### Step 3: 添加 ban 关键词（可选加强）

如果希望更严格——拦截所有无证据的断言——在 rules/ban/ 下添加规则，关键字匹配「通过」「完成」「成功」等词。

### Step 4: 开启 ralph-loop 联动（可选）

sentinel 拦截后，CMG 微型调度器自动推荐 ralph-loop 重做。确保 ralph-loop skill 已安装：

```bash
ls ~/.hermes/skills/software-development/ralph-loop/SKILL.md
```

## 效果

- 没说清用了什么工具 → 堵住，问「请声明使用的工具和验证结果」
- 说了但没贴证据 → 堵住，问「请附带终端输出验证」
- 贴了假证据 → ban 关键词抓到 → 拦截 → ralph-loop 重做

## 关闭

如果觉得太严格，在 config.yaml 中关闭步骤检查：

```yaml
sentinel:
  step_check: false
```

## 适用场景

- 开发工作流：每个 commit/push 前自动验证
- 论文写作：引用文献前确认来源存在
- 系统管理：声称「安装成功」前验证二进制存在
- 任何需要对 AI 输出质量有信心的场景

## 不适用场景

- 创意对话（会打断自然交流）
- 快速问答（不需要证据的闲聊）
- 用户已明确表示信任 AI 判断的场景
