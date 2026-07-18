# 追踪与优先级规则

## 追踪链

需求与 Diff 并存时必须维护：需求点 → 需求证据 → Diff 实现 → 覆盖状态 → 风险 → 测试点或 TC。覆盖状态只使用：已覆盖、疑似遗漏、实现不一致、需求外变更、无法判断。

## 正式矩阵字段

- 纯需求：需求点ID、需求证据、风险ID、测试点或TC。
- 纯 Diff：Diff变更ID、代码证据、风险ID、测试点或TC。
- 联动：需求点ID、需求证据、Diff变更ID、覆盖状态、风险ID、测试点或TC。

每个 TC 必须出现在至少一条合法数据行，不以普通正文中的编号或 `TC001-TC010` 范围代替。每行必须有风险 ID；联动行必须同时有需求证据和 Diff 变更 ID；疑似遗漏和实现不一致必须关联风险。一个 TC 可显式列出多个风险或需求点，废弃测试点不计入覆盖。

Acceptance Criteria 的 Evidence 必须是其关联 confirmed Fact Evidence 的子集；Risk Evidence 必须派生自其关联 Fact 或 Acceptance Criteria，不得另接无关行号。标记“已确认”的 Risk 必须只引用有 current Evidence 的 confirmed Fact；标记“已确认”的 TC 不得链接待确认/疑似 Risk 或未确认 Fact。

## 分类字段

- 风险等级和执行优先级：P0、P1、P2，不使用 P3。
- 证据状态：已确认、疑似、待确认。
- 回归范围：核心回归、关联回归、冒烟回归。

P0 表示核心链路、资金或关键数据、严重权限安全、接口契约或重大兼容风险；P1 表示主要功能、复杂组合和较广关联影响；P2 表示有证据命中的局部展示或低频边界。严重度、证据置信度和回归范围不得混为同一字段。无业务意义的文档、注释、格式化或重命名不生成业务 TC。

## Testcase Value Assessment 追踪边界

- Testcase Value Assessment Model 通过 `tc_id` 关联 Testcase Model，并从 Risk Coverage Matrix 和可选 Requirement Model 派生可复算评分。
- Risk、Requirement、Testcase 和 Evidence 仍是正式追踪事实来源；Assessment 不能成为新的事实源，也不能反向修改 `risk_ids`、`requirement_ids`、`change_ids`、`historical_defect_ids`、`test_priority`、`regression_scope` 或 `evidence_state`。
- Assessment 只保存评分内核生成的可复算结果。引用模型必须校验仓库相对 `path`、对应 `model_id` 或 `matrix_id` 以及归一化 `content_hash`。
- Assessment 不参与 Manifest `case_count`，不参与 XMind TC 编号，也不参与 Execution Model 的 `branch_count` 或 `execution_instance_count`。
