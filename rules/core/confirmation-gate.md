# 待确认点门禁

每个待确认点必须明确分类为 `blocking`、`nonblocking` 或 `suggested`，未分类即校验失败。新任务的确认前阶段使用独立 `workflow_stage=confirmation_only` Checkpoint，不生成 Manifest；历史 `pending` Manifest 继续按原契约兼容。用户明确跳过时状态写为 `skipped`，不得把假设升级为 confirmed；仍影响核心预期的跳过项继续阻止正式阶段。

## 一次授权与集中确认

用户一次请求同时包含需求分析和测试用例时，即完成整个原始任务授权。执行固定分为两阶段：第一阶段完整分析并集中确认，第二阶段正式生成测试产物。无 blocking 时自动进入第二阶段；存在 blocking 时扫描完当前全部材料后一次性返回全部问题，用户回复后自动续跑，不要求重复规则路径、需求内容或“继续生成”。

发现首个 blocking 后必须立即停止 Risk Coverage Matrix、Testcase Model、XMind、正式报告、Manifest 和 Index 的下游生成，但继续读取和扫描剩余需求。Checkpoint 必须证明十类需求要素、八类测试维度、条件矩阵适用性和 Confirmation 扫描均已完成，且 `downstream_artifacts_generated=[]`。

## 状态真值表

Requirement Model 的结构合法性与 Manifest 的交付就绪状态必须分离。合法的 unresolved blocking Confirmation 表示“模型结构合法、业务确认未完成、Manifest 必须 pending”，不得据此判定 Requirement Model 非法。

| Confirmation severity | Confirmation status | Requirement Model | Manifest 可用状态 |
| --- | --- | --- | --- |
| blocking | pending | 合法 | confirmation_only；历史 Manifest 可为 pending |
| blocking | skipped，关联核心 Fact | 合法 | confirmation_only；历史 Manifest 可为 pending |
| blocking | resolved，解决证据完整且关联 Fact 已更新 | 合法 | 可继续判断 passed |
| nonblocking | pending | 合法 | pending 或 passed，按交付规则决定 |
| suggested | pending | 合法 | pending 或 passed，按交付规则决定 |
| 任意 | resolved 但缺少 resolution、resolution_evidence_references 或 resolved_at | 非法 | 不可交付 |
| 任意 | skipped 但缺少 skip_reason 或 decision_evidence | 非法 | 不可交付 |
| blocking | 核心 missing Fact 未关联 blocking Confirmation | 非法 | 不可交付 |

核心 missing Fact 必须关联 blocking Confirmation。resolved Confirmation 的证据必须支撑确定结论，关联的核心 missing/conflicting Fact 必须已更新为 confirmed；skipped 不得自动改变 Fact 类别，若仍影响核心预期则继续阻止 passed。pending 不要求 resolution、resolved_at 或解决证据。

## 阻塞解除后的状态迁移与自动续跑

处理确认回复时必须保留用户原始任务范围，并只更新本轮回答实际覆盖的 Confirmation：

1. `pending blocking Confirmation` 收到用户答案或证据后，更新为 `status=resolved`，同时填写 `resolution`、`resolution_evidence_references` 和 `resolved_at`；用户原文或附件必须保存为可复验的解决证据，不得只改报告文案。
2. 根据解决证据同步更新关联的 missing/conflicting Fact。证据已形成确定结论时更新为 `confirmed`；仍有冲突时保持或更新为 `conflicting`；证据仍不足时保持 `missing`，不得为了归零强制升级事实。
3. 从同一份 Checkpoint 同步更新关联 Fact 和验收标准，再使用统一函数重算 Confirmation Summary 与 `blocking_pending_count`。确认前不存在草稿 Risk/Testcase 可供复用；正式阶段已存在模型时只重算受影响 Risk、条件组合和 TC，并执行完整一致性复验。
4. 用户答案引入新的核心冲突时，可以新建 blocking Confirmation 并保持 pending；不得把未回答的既有 Confirmation 自动 resolved。
5. `blocking_pending_count > 0` 时继续保持 `confirmation_only`；`blocking_pending_count=0` 时切换为 `formal_generation` 并立即恢复原始任务，不要求用户再次发送“继续”“生成最终用例”或同义重复指令。
6. 原始任务已包含需求分析和测试用例时，归零后自动执行尚未完成的正式链：Requirement Analysis Model → 可选 Diff Impact Model → Risk Coverage Matrix → Testcase Model → XMind Markdown → XMind Workbook → Manifest → index。任一步失败都停止完整交付结论并保留可诊断结果。
7. resolved Confirmation 对应的 Fact、Risk、TC 和可观察预期必须同步更新；禁止只更新需求报告或 `.xmind.md`，也禁止继续用阻塞状态下的旧 Risk/Testcase 模型。
8. 新流程确认前不生成草稿路径。全部 blocking 解除且正式校验通过后才能生成或更新正式 Workbook、passed Manifest 和正式索引；历史 pending Manifest 不强制迁移。

## 分级

- 阻塞类：核心目标、入口、主流程、核心数据口径或公式、核心预期无法确定；证据直接冲突；权限、安全或数据隔离会改变核心验收；缺失信息会产生相反预期。
- 非阻塞类：不影响已明确主链路，只影响局部规则、补充边界或部分预期。
- 建议确认类：主要影响文案、体验、低频边界或补充回归。

## 决策流程

1. 记录问题、证据、影响、等级和用例处理方式。
2. 有阻塞类且用户未确认或跳过：继续完成剩余分析后集中提问，只输出分析范围、需求理解、已确认规则、缺失和冲突、风险方向、回归范围、全部确认问题和暂停状态。
3. 只有非阻塞类或建议确认类：继续生成已明确的核心用例，未确认部分不写死预期，不为非核心问题反复提问。
4. 用户明确跳过：继续执行，报告保留问题并标记已跳过；不得把默认假设升级为需求事实。
5. 普通功能仅缺少角色、权限或数据范围时，默认按有权限用户访问需求范围设计主链路；只有权限本身改变核心验收时才阻塞。
