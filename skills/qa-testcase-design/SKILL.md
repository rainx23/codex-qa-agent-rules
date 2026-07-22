---
name: qa-testcase-design
description: 用于基于证据设计 QA 测试点和最小有效 XMind Markdown 用例集，应用风险覆盖、等价类、边界、决策表、状态流转、去重和固定层级。适用于测试点、测试用例、P0 用例、XMind Markdown 或完整 QA 产物生成。Testcase design, test points, P0 cases, XMind Markdown, risk coverage and deduplication.
---

# QA 测试用例设计（QA Testcase Design）

每个 P0 风险必须分别映射 TC；P1/P2 若没有独立 TC，必须记录合法处置状态和原因。结构化步骤必须对应可观察预期。2 至 5 个入口使用稳定 `branch_id`，不少于 6 个同规则入口使用全局 `shared_entry_scope`，两种表达都不改变 TC 计数。

将本 Skill 的根目录解析为当前 `SKILL.md` 向上两级的仓库根目录。

## 规则加载

1. 完整读取 `../../rules/core/testcase-quality-rules.md`。
2. 完整读取 `../../rules/core/traceability-rules.md`。
3. 完整读取 `../../rules/core/confirmation-gate.md`。
4. 完整读取 `../../rules/core/structured-model-contract.md`。
5. 完整读取 `../../rules/core/conversation-delivery-contract.md`。
6. 仅读取与需求匹配的 `../../rules/profiles` 文件。
7. 设计用例前读取 Requirement Analysis Model、可选的 Diff Impact Model 和可选的历史缺陷。

## 执行流程

1. `workflow_stage=confirmation_only` 或存在未解决 blocking 时不得启动本 Skill，不得生成 Risk Coverage Matrix、Testcase Model、草稿用例或 XMind。阻塞归零并切换到 `formal_generation` 后，接收已回写确认结果的 Requirement Analysis Model，并在同一次原始授权下自动恢复用例任务。
2. 先建立并校验 `../../rules/schemas/risk-coverage-matrix.schema.json` 约束的 Risk Coverage Matrix，不得从原始需求文本直接跳到用例。
   - Risk Evidence 只能从关联 Fact/Acceptance Criteria 派生；confirmed TC 的 Risk 与 Fact 链必须全部 confirmed/current。字段结构证据不得扩写为业务行为预期。
3. 根据证据选择等价类、边界、决策表、状态流转、用户路径、Pairwise 或风险驱动等技术。
   - Requirement Model 存在条件矩阵时，先复验 grouped cross product 生成集合，再逐项消费 required combination；每项必须生成行为型 `condition_coverage`，明确命中/不命中数据、可观察结果以及真实 `branch_id`、`step_index`、`expected_index`。配置选项存在性只作为独立结构/容量覆盖；blocking 未解决时不得进入本步骤或生成草稿定位，更不得伪造行为 Oracle。
4. 每个可独立诊断的风险原则上设计一个用例。仅当核心规则、触发条件、操作、数据来源/口径、断言、风险和保护上下文等价时合并；正式/模拟数据源、权限、数据类型、异常路径或不同 P0 风险会改变定位时必须拆分。同一规则覆盖多个真实入口时，只有上述维度完全一致才能保留一个 TC：完整入口为 2 至 5 个时，每个入口渲染为独立平级分支并各自包含步骤和预期；完整入口不少于 6 个时，在根节点下建立唯一全局适用入口范围，各 TC 只保留公共步骤和预期。入口差异导致数据源、权限、预期、异常路径、风险或失败定位不同则拆分 TC。
   - 使用不含纯入口名称的 `core_deduplication_key` 做确定性合并判断；模拟/正式仅入口不同必须合并。允许拆分时必须让真实差异进入核心去重因子，并记录拆分依据。
5. 每个保留的 TC 都必须映射需求、Diff 或历史缺陷，并具有独立失败诊断。
6. 建立并校验 `../../rules/schemas/testcase-model.schema.json` 约束的 Testcase Model，然后按入口数量选择受支持的固定 XMind 层级，并从 `TC001` 开始全局连续编号。
   - `dimension` 根据核心风险和主要 Oracle 选择并决定唯一 XMind 一级节点；`secondary_dimensions` 只做追踪与统计，不能复制 TC、不能与主维度相同或重复。树按主维度分组后不要求遍历顺序仍按 TC 编号递增。
   - 单入口：保留既有 `TC → 测试点 → 步骤 → 预期` 或直接模块层级，不人为增加入口层。
   - 2 至 5 个入口：分组结构使用 `TC → 测试点 → 具体入口 → 步骤 → 预期`；直连结构使用 `TC → 一级模块 → 二级功能点 → 具体入口 → 步骤 → 预期`。至少包含两个有名称的平级入口、各入口独立的步骤和预期；禁止混入公共直连步骤，也禁止“分别打开/依次进入多个入口”等拼接文本。
   - 不少于 6 个入口且公共步骤、预期完全一致：在根节点下使用 `适用入口（以下全部TC均需逐项执行） → 一级范围 → 二级范围 → 具体入口`，TC 继续使用单入口公共步骤层级。所有叶子入口必须在 XMind 和 `shared_entry_scope` 内完整重复列出；模拟交易和正式交易都在范围内时分别展开完整入口，禁止“上述”“同上”“等入口”、省略号或外部清单引用。
7. 使用 `../../scripts/validate_xmind_md.py` 和 `../../scripts/validate_testcase_quality.py` 校验报告、风险矩阵和用例模型。显式重复视为错误，警告必须人工复核，不得静默删除用例。
8. 仅在校验通过后转换，并将模型与渲染产物交给 `../qa-artifact-validation/SKILL.md`。
9. 消费 Knowledge Search 结果和 Data Validation Model 后再选风险。区分 UI 行为、业务数据断言、SQL 校验、对账和展示检查；XMind 引用 `SQLV###` 或 `REC###`，不嵌入大段 SQL。
10. 阻塞解除后首次生成 Risk Coverage Matrix，并从该矩阵生成、校验 Testcase Model；确认前不存在可沿用的草稿 Risk/Testcase。若正式阶段后续确认影响已有模型，重新计算 Risk Coverage Matrix 中受影响的 Risk，并只重算受影响 Fact、条件组合和 TC，随后执行完整一致性门禁；不得仅更新 `.xmind.md`。
11. XMind Markdown 必须从 Testcase Model 渲染，并按语义精简规则去除重复背景；禁止硬字数门禁、自动截断或删除执行所需语义。
    - 拒绝“按已确认规则处理”“按系统现有逻辑处理”“按现有统计口径一致”“其他功能不受影响”等模糊预期；统计口径必须写明对象、来源和 Oracle，回归断言必须写明变更前基线、同条件比较对象和可观察字段。混合 `AND/OR` 使用括号明确优先级。
12. 原始任务包含最终用例时，模型与 Markdown 校验通过后自动交接 `qa-artifact-validation`，继续 Workbook、Manifest 和索引链。
13. 不自由编写最终聊天回复。正式模型交给 `qa-artifact-validation` 后，由确定性对话交付摘要渲染器生成最终回复主体；pending 时不得宣称正式测试用例或 XMind 已完成。

## 可选测试用例价值评估

- Risk Coverage Matrix 和 Testcase Model 均校验通过后，可按用户要求生成独立 Testcase Value Assessment Model；Assessment 只能从正式模型派生，不能直接从原始自然语言评分。
- 用户未要求测试用例价值评估时不强制生成，也不默认输出大段评分报告。评分只用于人工审核和用例优化建议，不计入 TC 数量，XMind 不展示评分节点。
- 评分不得改写 P0/P1/P2、TC 编号、XMind 层级、`risk_ids` 或 `regression_scope`。P0 和历史缺陷用例低分时只能提出改善建议，疑似重复不得自动删除或合并。

需要表达多入口执行状态时，只在结构化模型中生成可选 `execution_instances`；实例关联真实 `tc_id` 和 `branch_id`，分别维护 `branch_count`、`execution_instance_count`，不得改变 `case_count` 或现有 XMind TC 数量。未获得用户实际执行证据时所有实例必须为 `not_run`，本仓库不承担完整测试执行平台职责。

对于既有逻辑变更，聚焦变更条件、反向路径、组合和边界；不要用未变更的入口可用、按钮可点或展示冒烟场景填充用例集。
