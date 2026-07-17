# 待确认点门禁

每个待确认点必须明确分类为 `blocking`、`nonblocking` 或 `suggested`，未分类即校验失败。`blocking_pending_count > 0` 时 Manifest 必须为 `pending` 并说明 `pending_reason`，不得声明完整交付、正式 Workbook 或更新正式索引。用户明确跳过时状态写为 `skipped`，不得把假设升级为 confirmed；仍影响核心预期的跳过项继续阻止 passed。

## 状态真值表

Requirement Model 的结构合法性与 Manifest 的交付就绪状态必须分离。合法的 unresolved blocking Confirmation 表示“模型结构合法、业务确认未完成、Manifest 必须 pending”，不得据此判定 Requirement Model 非法。

| Confirmation severity | Confirmation status | Requirement Model | Manifest 可用状态 |
| --- | --- | --- | --- |
| blocking | pending | 合法 | pending |
| blocking | skipped，关联核心 Fact | 合法 | pending |
| blocking | resolved，解决证据完整且关联 Fact 已更新 | 合法 | 可继续判断 passed |
| nonblocking | pending | 合法 | pending 或 passed，按交付规则决定 |
| suggested | pending | 合法 | pending 或 passed，按交付规则决定 |
| 任意 | resolved 但缺少 resolution、resolution_evidence_references 或 resolved_at | 非法 | 不可交付 |
| 任意 | skipped 但缺少 skip_reason 或 decision_evidence | 非法 | 不可交付 |
| blocking | 核心 missing Fact 未关联 blocking Confirmation | 非法 | 不可交付 |

核心 missing Fact 必须关联 blocking Confirmation。resolved Confirmation 的证据必须支撑确定结论，关联的核心 missing/conflicting Fact 必须已更新为 confirmed；skipped 不得自动改变 Fact 类别，若仍影响核心预期则继续阻止 passed。pending 不要求 resolution、resolved_at 或解决证据。

## 分级

- 阻塞类：核心目标、入口、主流程、核心数据口径或公式、核心预期无法确定；证据直接冲突；权限、安全或数据隔离会改变核心验收；缺失信息会产生相反预期。
- 非阻塞类：不影响已明确主链路，只影响局部规则、补充边界或部分预期。
- 建议确认类：主要影响文案、体验、低频边界或补充回归。

## 决策流程

1. 记录问题、证据、影响、等级和用例处理方式。
2. 有阻塞类且用户未确认或跳过：对话提问，只输出分析、风险和初步思路，暂停最终 XMind。
3. 只有非阻塞类或建议确认类：继续生成已明确的核心用例，未确认部分不写死预期，不为非核心问题反复提问。
4. 用户明确跳过：继续执行，报告保留问题并标记已跳过；不得把默认假设升级为需求事实。
5. 普通功能仅缺少角色、权限或数据范围时，默认按有权限用户访问需求范围设计主链路；只有权限本身改变核心验收时才阻塞。
