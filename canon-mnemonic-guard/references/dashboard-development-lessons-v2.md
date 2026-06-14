# Dashboard 迭代教训 v2

> 2026-05-31 | 来源：v5.6.0 功能迭代（导出/趋势图/类型互转/虚拟滚动/批量操作）

## 迭代流程铁律

1. **一个功能一个功能加。** 一次加太多崩了不知道哪个引起的。
2. **从 GitHub 干净版开始。** 每加一个验证 API + JS + F12 无报错后再加下一个。
3. **永远不用 sed 插入 JS。** sed 吃掉了 applyLang 的结束 `}`，导致函数被嵌套——`ReferenceError: renderTrend is not defined`。
4. **replace_all 慎用。**
5. **修 X 只改 X。** 不动无关代码。
6. **虚拟滚动 + 批量模式要联动。** renderRules 重建 DOM 后需调用 applyBatchMode 恢复状态。

## 技术教训

- JS 变量声明必须在引用之前（`var maxVal` 放到 `if (maxVal===0)` 前面）
- 新增 UI 文本必须加 data-i18n 和中英文词条
- companion_skills 开关无实际作用，改为纯状态展示
