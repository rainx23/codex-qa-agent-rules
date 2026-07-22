# 结构化模型交接契约

结构化模型用于 Skills 内部交接和自动校验，不改变分析报告或固定 XMind Markdown 层级。可复用模型保存到版本化产物目录；只用于单次执行的模型保存到临时目录并在完成后清理。

当前 `RULE_VERSION` 下，`validation_status=passed`、具有正式 `testcase_model_path` 且模式为 `requirement` 或 `combined` 的 Manifest，其 Requirement Analysis Model 必须完整填写 `test_dimension_assessment`，固定且仅一次扫描功能、数据、异常、权限、导出、兼容性、回归和 SQL 八类测试分类维度；不得以其他新增字段是否出现作为启用门槛。旧 `rule_version` 历史产物保持兼容，pending/failed 产物以及没有 Requirement Analysis Model 的纯 diff 产物不被强制回写。它与 `condition_matrix` 的业务条件维度是两个不同概念：前者决定风险覆盖状态，后者表达入口、角色、关系、操作、状态、日期、页位和数据形态等组合条件。`condition_matrix_applicability` 记录矩阵为何 required/not_required/blocked，`scope_dispositions` 记录正式范围项的有证据处置。

Testcase Model 的 `dimension` 是决定 XMind 一级节点的唯一主维度；`secondary_dimensions` 只参与风险追踪和覆盖统计，不得与主维度相同或重复，也不得导致同一 TC 在多个一级节点重复渲染。主维度依据核心风险与主要 Oracle 选择，不依据需求标题或模块名称机械归类。

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

Manifest `validation_status` 只描述测试设计产物完整性，`sql_status` 独立描述 SQL 生命周期。测试设计全链完整时允许 `validation_status=passed` 与 `sql_status=blocked` 并存；SQL 被阻塞不得迫使完整测试设计降级为 pending，也不得伪造 `validation_sql` 或 `execution_evidence`。

原始任务范围是续跑依据。若任务同时要求需求分析和测试用例，blocking Confirmation 归零后必须从已更新的 Requirement Analysis Model 继续完成尚未生成或需要重算的下游产物，不得要求用户重复授权同一任务，也不得用阻塞期间的 Markdown 草稿替代结构化模型交接。

报告与模型必须来自同一分析结果，不得在事实、待确认点、风险、模式或计数上互相矛盾。Risk Coverage Matrix 同时保存主 `business_entry` 和用于合并场景的 `business_entries` 覆盖入口列表。需求点、Diff 变更、风险和 TC 的 ID 必须双向一致；所有 P0 风险必须映射 TC；模型 TC 与 Markdown TC 集合、维度、公共入口/模块层级、测试点、步骤和预期必须一致。

确认回复完成后必须先回写 Confirmation、Fact、风险和验收标准，再重新生成 Risk Coverage Matrix 与 Testcase Model，最后渲染 XMind。只修改报告或 XMind Markdown 而不同步 JSON 模型属于不完整状态迁移。

Evidence Reference 必须显式区分 `file` 与 `snapshot`，并统一通过 `scripts/validate_evidence.py` 复验路径、哈希、文本行号、excerpt、记录 ID 和状态。Schema 只描述字段形状，真实性由同一公共验证器执行；`qa_contracts.py` 和 `validate_models.py` 不得维护第二套文件校验。confirmed Fact 至少需要一条真实且 current 的同源 Evidence；stale/reconfirm_required 只能保留为历史或待确认依据。

Evidence 不是可自由复制的说明文字：Acceptance Criteria 必须从关联 Fact 派生证据，Risk 必须从关联 Fact/Acceptance Criteria 派生证据，confirmed TC 的整条 Risk → Acceptance → Fact 链均须为 confirmed/current。字段结构证据不得越权确认运行时业务行为。

## Confirmation 与交付状态

Requirement Model 校验只判断结构、Fact/Confirmation 引用、核心 missing Fact 的 blocking 关联，以及 resolved/skipped 的证据完整性。未解决的 blocking Confirmation 本身不构成模型结构错误；它通过统一 Confirmation Summary 影响 Manifest 状态。

统一 Summary 必须计算 `pending_count`、`blocking_pending_count`、`nonblocking_pending_count`、`suggested_pending_count`、`skipped_core_count` 和 `unresolved_core_fact_count`。其中 skipped 且关联核心 Fact 同时计入 pending_count、blocking_pending_count 和 skipped_core_count；核心 missing/conflicting Fact 只有在存在有效 resolved Confirmation 且 Fact 已更新后才视为解决。Manifest 和报告不得自行实现另一套统计口径。

## Diff Impact 强类型契约

- `impact_chains` 必须使用具名对象，至少包含 `chain_id`、`change_ids`、源/受影响组件、传播路径、受影响契约、影响类型、证据引用和置信度。
- `risks` 必须至少包含 `risk_id`、陈述、变更/事实引用、证据状态、业务影响、测试优先级、回归范围、处置和证据引用；`suspected_defects` 同样不得使用无约束对象。
- Change、Impact Chain、Diff Risk、Suspected Defect 与 Requirement Fact、Risk Matrix、Testcase 之间的引用 ID 必须真实存在，并执行双向交叉校验。

## 多入口 Testcase Model

- Testcase Model 可选 `entry_branches`；它只用于 2 至 5 个真实入口，每个分支严格包含 `entry_name`、`steps`、`expected_results`，可附带需求、Diff 和风险关联字段。
- 单入口时 `entry_branches` 缺省或为空，顶层 `steps`、`expected_results` 必须非空；多入口时至少两个分支，顶层步骤和预期必须为空，禁止两种表达混用。
- 分支顺序、入口名称、步骤和预期必须与 XMind Markdown 一一对应；校验器比较分支数量、顺序、名称、步骤和预期，不以分支数量替代 TC 数量。
- 同一组步骤和预期适用于不少于 6 个完整入口时，Testcase Model 必须使用唯一 `shared_entry_scope`。范围包含稳定 `scope_id`、固定 `scope_title`、`applies_to_tc_ids` 以及“一级分组 → 二级分组 → 完整入口”的 `groups`；引用 TC 填写同名 `shared_entry_scope_id`、保留顶层公共 `steps`/`expected_results`，不得再填写 `entry_branches`。
- `shared_entry_scope` 的完整入口叶子少于 6 个时校验失败；单个 TC 出现 6 个及以上 `entry_branches` 时同样失败。正式和模拟等范围组必须各自完整列出入口，禁止“上述”“同上”“前述”“等入口”“其余入口”“其他入口”“同前”和省略号。
- XMind 根节点下允许唯一 `适用入口（以下全部TC均需逐项执行）` 范围节点；其分组、顺序和入口叶子必须与 Testcase Model 完全一致。范围树不是 TC、步骤或预期，不改变 TC 数量；所有 `applies_to_tc_ids` 必须真实存在且与 TC 的范围引用双向一致。
- 共享范围下的条件组合使用 `condition_coverage.scope_path` 定位完整或分组路径，并引用 TC 顶层 `step_index`/`expected_index`；普通入口分支继续使用 `branch_id`。两种定位方式不得混用。
- 可选 `execution_instances` 只建立执行契约，不改变 XMind 展示。每个实例使用稳定 `execution_instance_id`、`tc_id`、`branch_id`、执行状态、执行人/时间、缺陷引用、重跑引用和执行证据。
- `execution_status` 仅允许 `not_run`、`passed`、`failed`、`blocked`、`skipped`；没有用户提供的实际执行证据时只能为 `not_run`。
- `case_count` 只统计 TC；`branch_count` 与 `execution_instance_count` 独立统计，执行实例不得增加 TC 数量。

## 条件矩阵与核心去重契约

- Requirement Analysis Model 可选 `condition_matrix_required` 和 `condition_matrix`；历史模型缺省时保持兼容。新分析明确列出两个及以上条件维度时必须设置 `condition_matrix_required=true` 并填写 `dimensions`、`combination_generation`、`required_combinations`、`excluded_combinations` 与 `coverage_summary`。
- `combination_generation.mode=grouped_cross_product`；每个 group 使用稳定 `group_id`、`fixed_values`、带取值子集的 `variable_dimensions`、`expected_combination_count` 和可选约束说明。校验器确定性生成 expected combination set，使用完整 `dimension_values` 的规范化稳定键，要求 required + excluded 与 expected set 完全一致；缺少、多出、required/excluded 重复及分组计数错误均阻止交付。
- 每个 required combination 使用稳定 `combination_id`、完整 `dimension_values` 和 `covered_by_tc_ids`；排除项必须携带 `exclusion_reason`。Testcase Model 通过 `condition_coverage` 逐项声明 `behavior` 或 `configuration`，只有行为型覆盖可满足 required combination。condition matrix 正式模型中的每个行为覆盖还必须填写 `branch_id`、一基 `step_index` 和 `expected_index`，引用真实且入口一致的分支、独立步骤及对应预期；步骤与预期数量相等，多个高风险组合不得共用同一定位。
- 未解决的 blocking Confirmation 可以保留完整 expected set 和草稿 TC 定位，但不得把未知 Oracle 标为 behavior coverage；pending 校验允许这些组合等待确认，passed 校验必须全部具有确定性行为覆盖。
- Testcase Model 可选保存 `core_deduplication_factors` 与确定性 `core_deduplication_key`。因子不包含纯入口名称，至少包括业务对象、触发条件、核心动作、核心断言和风险语义；数据源、权限规则、计算口径及异常处理用于防止误合并。
- 同核心键的多个 TC 为错误；2 至 5 个真实入口合并为一个 TC 的平级 `entry_branches`，不少于 6 个同规则入口合并为 `shared_entry_scope` 加公共步骤。确需拆分时，核心差异应反映在结构化因子中，并可补充 `split_reason` 与 `split_reason_detail` 供审计。

## Testcase Value Assessment Model

### 模型作用

Testcase Value Assessment Model 保存可复算的测试用例价值评估结果，绑定 Testcase Model、Risk Coverage Matrix 和可选 Requirement Model，记录 `algorithm_version`、客观 `maintenance_inputs` 与逐 TC `assessments`。它独立于 Testcase Model、XMind Markdown、Execution Model 和 Manifest。

### 字段职责

- `schema_version`：结构契约版本。
- `algorithm_version`：确定性评分算法版本。
- `testcase_model_reference`：静态用例来源及其路径、ID、Hash。
- `risk_matrix_reference`：风险来源及其路径、ID、Hash。
- `requirement_model_reference`：可选的需求与证据上下文；缺失时按评分内核规则处理。
- `maintenance_inputs`：只能保存外部系统、共享可变数据、人工判定和环境特定依赖等客观非负计数。
- `assessments`：只能保存统一评分内核生成的 `computed` 或 `insufficient_inputs` 结果。

### 禁止事项

- 不允许人工或 AI 直接填写 `dimensions` 或修改 `total_score`。
- 不允许自由填写 `reason_codes`，`recommendation` 不得包含删除、降级或自动合并指令。
- 不允许 Assessment 覆盖 Testcase、Risk、Requirement 或 Evidence 的正式字段。
- Assessment 是阶段一可选模型，缺失不得阻止旧产物通过。

### 重算校验

持久化 Assessment 必须校验引用路径、模型 ID 和归一化 Hash，并在评分前完整校验引用的 Requirement Model、Risk Matrix、Testcase Model 及其跨模型双向链接，再调用 `scripts/qa_contracts.py` 的唯一评分内核重新计算。任一引用模型或链接非法时必须停止，不得生成误导评分。`dimensions`、`total_score`、`value_band`、`guardrails`、`reason_codes` 和 `recommendation` 必须全部一致，不能只比较总分；引用 Hash 不一致或持久化结果被篡改必须报错。

## 数据与知识模型

- Knowledge Table、Logic Version、Metric、Requirement Knowledge 和 Data Validation Model 由 `scripts/qa_contracts.py` 统一生成 Schema。
- 完整 DDL 使用 `schema_scope=complete` 并保存原始/规范化哈希；原文中明确存在的主键、唯一键、Duplicate/Aggregate Key、分区、分桶、索引、Engine 和 Properties 必须全部稳定提取，否则降级为 `partial` 或 `blocked`。局部字段使用 `partial`，不得覆盖 complete 版本。
- Data Validation Model 使用 `required`、`optional`、`not_required`、`blocked`；验证方式使用 `sql`、`cross_source_reconciliation`、`mixed`、`not_applicable`、`blocked`。指标准确性默认必须有关联 SQL。
- Validation SQL 使用全局 `SQLV###`，直接对数使用 `REC###`；它们可被多个 TC 复用，必须与需求、风险和 TC 建立引用关系。知识、SQL 和对数模型不得成为新的 XMind 层级。
Schema contract version is `2.0.0`; it is distinct from the repository `RULE_VERSION`. Models with `schema_version=1.0.0` require the explicit migration script and re-confirmation before validation.

## DDL 完整消费门禁

Knowledge Table 的字段必须携带 `raw_fragment`、`parsed_tokens`、`unparsed_fragment`、`generated`、`generated_expression`、`generated_type`、`auto_increment` 与 `inline_constraints`；表级必须携带 `raw_tail`、`parsed_tail_tokens` 和 `unparsed_tail`。完整 DDL 与 partial fields 必须复用同一个扫描式字段解析入口。

`schema_scope=complete` 必须同时满足：字段非空、ordinal 连续、字段名唯一、所有字段 `unparsed_fragment=null`、`unparsed_tail=null`、Generated Column 信息自洽且无解析 warning。原文未声明 nullable/default/comment 可以保留 unknown；解析器未读懂的内容必须保留并降级为 `partial`。字段括号无法闭合或没有可靠字段时必须为 `blocked`。
