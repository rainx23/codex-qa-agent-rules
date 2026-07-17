# 结构化模型交接契约

结构化模型用于 Skills 内部交接和自动校验，不改变分析报告或固定 XMind Markdown 层级。可复用模型保存到版本化产物目录；只用于单次执行的模型保存到临时目录并在完成后清理。

## 单一来源

- 执行契约、枚举和跨字段规则只维护在 `scripts/qa_contracts.py`。
- `rules/schemas/*.schema.json` 由 `scripts/generate_schemas.py` 生成，不手工维护。
- 运行时使用标准库执行同一契约生成的必填、类型、枚举、正则、唯一性和跨模型 ID 校验，不依赖 `jsonschema`，避免 Schema 只生成不执行。
- `RULE_VERSION` 是规则版本唯一来源，Manifest 不得自行填写其他版本。

## 交接顺序

1. 需求 Skill 生成 Requirement Analysis Model，并从同一分析结果渲染需求报告。
2. Diff Skill 接收可选 Requirement Analysis Model，生成 Diff Impact Model；存在需求模型时以其验收标准判断覆盖。
3. 用例 Skill 接收需求模型、可选 Diff 模型和历史缺陷，先生成 Risk Coverage Matrix，再生成 Testcase Model。
4. Testcase Model 渲染固定 XMind Markdown；模型字段不得成为新的 XMind 节点。
5. 产物 Skill 依次校验报告、分析模型、风险矩阵、用例模型、Markdown、Workbook、Manifest 和索引。

报告与模型必须来自同一分析结果，不得在事实、待确认点、风险、模式或计数上互相矛盾。Risk Coverage Matrix 同时保存主 `business_entry` 和用于合并场景的 `business_entries` 覆盖入口列表。需求点、Diff 变更、风险和 TC 的 ID 必须双向一致；所有 P0 风险必须映射 TC；模型 TC 与 Markdown TC 集合、维度、公共入口/模块层级、测试点、步骤和预期必须一致。

Evidence Reference 必须显式区分 `file` 与 `snapshot`，并统一通过 `scripts/validate_evidence.py` 复验路径、哈希、文本行号、excerpt、记录 ID 和状态。Schema 只描述字段形状，真实性由同一公共验证器执行；`qa_contracts.py` 和 `validate_models.py` 不得维护第二套文件校验。confirmed Fact 至少需要一条真实且 current 的同源 Evidence；stale/reconfirm_required 只能保留为历史或待确认依据。

## Confirmation 与交付状态

Requirement Model 校验只判断结构、Fact/Confirmation 引用、核心 missing Fact 的 blocking 关联，以及 resolved/skipped 的证据完整性。未解决的 blocking Confirmation 本身不构成模型结构错误；它通过统一 Confirmation Summary 影响 Manifest 状态。

统一 Summary 必须计算 `pending_count`、`blocking_pending_count`、`nonblocking_pending_count`、`suggested_pending_count`、`skipped_core_count` 和 `unresolved_core_fact_count`。其中 skipped 且关联核心 Fact 同时计入 pending_count、blocking_pending_count 和 skipped_core_count；核心 missing/conflicting Fact 只有在存在有效 resolved Confirmation 且 Fact 已更新后才视为解决。Manifest 和报告不得自行实现另一套统计口径。

## Diff Impact 强类型契约

- `impact_chains` 必须使用具名对象，至少包含 `chain_id`、`change_ids`、源/受影响组件、传播路径、受影响契约、影响类型、证据引用和置信度。
- `risks` 必须至少包含 `risk_id`、陈述、变更/事实引用、证据状态、业务影响、测试优先级、回归范围、处置和证据引用；`suspected_defects` 同样不得使用无约束对象。
- Change、Impact Chain、Diff Risk、Suspected Defect 与 Requirement Fact、Risk Matrix、Testcase 之间的引用 ID 必须真实存在，并执行双向交叉校验。

## 多入口 Testcase Model

- Testcase Model 可选 `entry_branches`；每个分支严格包含 `entry_name`、`steps`、`expected_results`，可附带需求、Diff 和风险关联字段。
- 单入口时 `entry_branches` 缺省或为空，顶层 `steps`、`expected_results` 必须非空；多入口时至少两个分支，顶层步骤和预期必须为空，禁止两种表达混用。
- 分支顺序、入口名称、步骤和预期必须与 XMind Markdown 一一对应；校验器比较分支数量、顺序、名称、步骤和预期，不以分支数量替代 TC 数量。
- 可选 `execution_instances` 只建立执行契约，不改变 XMind 展示。每个实例使用稳定 `execution_instance_id`、`tc_id`、`branch_id`、执行状态、执行人/时间、缺陷引用、重跑引用和执行证据。
- `execution_status` 仅允许 `not_run`、`passed`、`failed`、`blocked`、`skipped`；没有用户提供的实际执行证据时只能为 `not_run`。
- `case_count` 只统计 TC；`branch_count` 与 `execution_instance_count` 独立统计，执行实例不得增加 TC 数量。

## 数据与知识模型

- Knowledge Table、Logic Version、Metric、Requirement Knowledge 和 Data Validation Model 由 `scripts/qa_contracts.py` 统一生成 Schema。
- 完整 DDL 使用 `schema_scope=complete` 并保存原始/规范化哈希；原文中明确存在的主键、唯一键、Duplicate/Aggregate Key、分区、分桶、索引、Engine 和 Properties 必须全部稳定提取，否则降级为 `partial` 或 `blocked`。局部字段使用 `partial`，不得覆盖 complete 版本。
- Data Validation Model 使用 `required`、`optional`、`not_required`、`blocked`；验证方式使用 `sql`、`cross_source_reconciliation`、`mixed`、`not_applicable`、`blocked`。指标准确性默认必须有关联 SQL。
- Validation SQL 使用全局 `SQLV###`，直接对数使用 `REC###`；它们可被多个 TC 复用，必须与需求、风险和 TC 建立引用关系。知识、SQL 和对数模型不得成为新的 XMind 层级。
Schema contract version is `2.0.0`; it is distinct from the repository `RULE_VERSION` (`2.6.0`). Models with `schema_version=1.0.0` require the explicit migration script and re-confirmation before validation.

## DDL 完整消费门禁

Knowledge Table 的字段必须携带 `raw_fragment`、`parsed_tokens`、`unparsed_fragment`、`generated`、`generated_expression`、`generated_type`、`auto_increment` 与 `inline_constraints`；表级必须携带 `raw_tail`、`parsed_tail_tokens` 和 `unparsed_tail`。完整 DDL 与 partial fields 必须复用同一个扫描式字段解析入口。

`schema_scope=complete` 必须同时满足：字段非空、ordinal 连续、字段名唯一、所有字段 `unparsed_fragment=null`、`unparsed_tail=null`、Generated Column 信息自洽且无解析 warning。原文未声明 nullable/default/comment 可以保留 unknown；解析器未读懂的内容必须保留并降级为 `partial`。字段括号无法闭合或没有可靠字段时必须为 `blocked`。
