# 发布验证清单 — 实战版

> 2026-05-28 CMG v5.5.4 第二次更新实战验证。补充 release-checklist.md 未覆盖的检查项。

## 桌面包文件漂移检查

**症状：** 桌面包目录中的文件可能落后于已安装版本。原因：SKILL.md 通过 `skill_manage` 更新后，只改了 `~/.hermes/skills/` 下的文件，桌面目录不会自动同步。

**本次实战：**
- guard SKILL.md: 桌面 671 行 vs 已安装 686 行（差 15 行）
- CMG SKILL.md: 桌面 1422 行 vs 已安装 1449 行（差 27 行）

**检查命令：**
```bash
for skill in canon guard mnemonic; do
  installed=$(wc -l < ~/.hermes/skills/software-development/$skill/SKILL.md)
  desktop=$(wc -l < ~/Desktop/CMG-Ecosystem-vX.Y.Z/$skill/SKILL.md)
  [ "$installed" != "$desktop" ] && echo "⚠️ $skill: 漂移 ${installed}→${desktop}" && cp ...
done
```

**修复：** 打包前逐文件 diff → 发现漂移 → cp 同步 → 再打包。

## sentinel.zip 损坏检测

**症状：** `ls -la ~/Desktop/sentinel.zip` 显示 945B，实际应该 ~17KB。`unzip -l` 揭示只有一个损坏文件。

**根因：** 某次打包操作出错，只写入了一个文件而非完整插件目录。

**检查命令：**
```bash
ls -la ~/Desktop/*.zip | awk '{if ($5 < 2000) print "⚠️ 异常小: " $NF}'
```

## 完整发布验证流程

1. `grep -rn 'v[0-9]\.[0-9]\.[0-9]'` 全文件版本号同步
2. 隐私扫描（会话细节/API key/个人路径）
3. 桌面包 vs 已安装逐文件 diff
4. ZIP 大小检查（不应 < 10KB）
5. `unzip -l` 验证 ZIP 内容完整性
6. `unzip -p ... | grep` 验证 ZIP 内关键内容（如新格式）
7. skill_view 四包全部 available
8. agent.log 检查 sentinel 拦截记录
9. 子包 _comment 声明 vs 实际版本号对比
10. SOUL 激活标记版本匹配

## 本次验证结果

| 检查项 | 结果 |
|--------|------|
| 版本号同步 | ✅ 四包一致 |
| 隐私扫描 | ✅ 零泄露 |
| 桌面包漂移 | ⚠️ guard+CMG 过期→已修复 |
| ZIP 大小 | ✅ 147KB / 82文件 |
| ZIP 内容 | ✅ 新诊断格式存在，旧格式零残留 |
| skill_view | ✅ 4/4 available |
| sentinel 拦截 | ✅ agent.log 10次命中 |
| _comment 一致性 | ✅ canon 2.7.2/guard 4.8.2/mnemonic 3.5.3 |
| SOUL 标记 | ✅ v5.5.4 |
| 副本清理 | ✅ canon/guard/mnemonic 根副本已删 |
