---
name: qa-requirement-analysis
description: 用于分析禅道、OpenSpec、Markdown、截图或粘贴文本中的 QA 需求，建立基于证据的事实、待确认门禁、风险、验收标准和回归范围。适用于需求分析、新需求评审以及 Diff 分析前的需求基线建立。Requirement analysis, Zentao, OpenSpec, acceptance baseline, QA risk and regression scope.
---

# QA 需求分析（QA Requirement Analysis）

confirmed Fact 必须有非 inference 的可验证来源，不能使用 low confidence 或“推测/猜测/根据名称判断”作为来源；截图、当前代码和历史知识只能按其证据边界记录，不能自动升级为业务确定事实。

将本 Skill 的根目录解析为当前 `SKILL.md` 向上两级的仓库根目录。

## 规则加载

1. 完整读取 `../../rules/core/evidence-rules.md`。
2. 完整读取 `../../rules/core/confirmation-gate.md`。
3. 完整读取 `../../rules/core/analysis-report-contract.md`。
4. 完整读取 `../../rules/core/traceability-rules.md`。
5. 完整读取 `../../rules/core/structured-model-contract.md`。
6. 完整读取 `../../rules/core/conversation-delivery-contract.md`。
7. 对禅道或同类分段需求，读取 `../../rules/profiles/zentao.md`，并以第三部分产品规则作为默认验收依据。
8. 仅读取与需求匹配的其他 `../../rules/profiles` 文件。
9. 用户要求生成最终用例时，将结构化结果交给 `../qa-testcase-design/SKILL.md`。

## 执行流程

0. 先判断显式意图。只有用户明确要求需求预审/评审、完整性检查、缺失冲突歧义检查且未要求测试用例/XMind，或明确“只分析问题、暂不生成测试用例”时进入 `workflow_stage=pre_review`；同时要求预审/评审和生成/编写测试用例或 XMind 时必须进入 delivery，和普通“分析需求并编写测试用例”一样记录完整原始任务范围并执行 confirmation_only 两阶段链。若本轮消息是在回答已有 Confirmation，则读取此前 Checkpoint，将消息作为确认回复处理，不把它误判为独立新需求，也不要求用户重复“继续生成”。
1. 确认每个需求来源均可读取，并说明本次分析范围。
2. 分析禅道需求时，区分第一部分业务背景与第三部分产品实现规则；优先采用用户确认的范围，不把普通背景与计划差异直接判定为阻塞冲突。
3. 提取业务目标、系统或页面入口、角色、主流程、字段规则、数据定义、验收标准、异常行为和明确排除项。
4. 建立事实表，区分确定事实、冲突事实、推断事实和缺失事实；每个核心结论都必须附允许的证据来源标签。
   - 每个 Fact 引用与其陈述直接对应的精确行号和 excerpt；验收标准只复用关联 Fact 的 Evidence。字段存在、字段清单或支持多值/可追加多个值只证明结构或容量，不得推导过滤、统计、自动去重、重复拒绝/合并、保存、删除、继承或唯一性等行为；confirmed 行为 Fact 必须有明确表达同类行为的 current Evidence。
   - 明确列出两个及以上条件维度时，在 Risk 之前建立结构化条件矩阵；按业务有效分组声明 fixed values、variable dimensions 和 expected count，由确定性 grouped cross product 生成 expected set，并要求 required + excluded 完整覆盖；配置存在性不得冒充行为覆盖。
   - 对正式用例任务固定扫描八个测试分类维度并填写 `test_dimension_assessment`；每类只能出现一次，未覆盖必须记录 not_applicable、explicitly_excluded、pending 或 blocked 的证据化原因。另用 `condition_matrix_applicability` 判断业务条件矩阵是否适用，并用 `scope_dispositions` 记录正式范围项处置。
5. 进入确认前置阶段 `workflow_stage=confirmation_only`。发现首个 blocking Confirmation 后立即停止 Risk Coverage Matrix、Testcase Model、XMind、正式报告、Manifest 和 Index 的生成，但不得停止剩余需求分析；继续完成全部来源、十类需求要素、八类测试维度、条件矩阵适用性和剩余 Confirmation 扫描。
6. 建立并校验 `../../rules/schemas/requirement-analysis.schema.json` 约束的最小 Requirement Analysis Checkpoint。保存完整 Evidence、原始任务范围、Fact、验收依据、八维扫描、条件维度、风险方向和全部 Confirmation；`downstream_artifacts_generated` 必须为空。不要创建 pending Manifest，也不要生成草稿报告、草稿 Risk、草稿 Testcase 或草稿 XMind。
7. 只有需求输入时，输出纯需求分析契约：分析范围、需求理解、规则拆解、证据、待确认点、风险、测试点摘要和回归范围；不强制要求疑似缺陷章节。
8. 存在 Diff 证据时，将 Requirement Analysis Model 交给 Diff Skill，并在设计用例前切换到联合分析契约。
9. 只有用户明确要求知识检索或任务确需历史知识/DDL/指标复用时，才按需调用 `qa-knowledge-management` 的 `search` 模式；默认正式任务完成后不自动搜索或提取知识。
10. 填充数据影响与验证决策：`data_validation_required`、原因、推荐方式、SQL 生成状态、指标定义缺口和阻塞问题。指标准确性默认采用 SQL，除非用户提供明确且可信的对账依据。
11. 用户粘贴完整 DDL 时，解析草稿并与知识库比较规范化哈希；只提供少量字段时标记为 partial，不创建或覆盖完整表 DDL。
12. 扫描完成后使用 `../../scripts/render_confirmation_summary.py` 在一次聊天回复中集中展示全部 Confirmation。每项至少包含 `confirmation_id`、问题、当前证据、不确定点、影响范围、确有明确选项时的可选答案和当前处理状态；不得虚构正式或草稿产物路径。
13. 处理确认回复时，只更新答案覆盖的 Confirmation，保存用户原文快照为 `user_confirmation` Evidence，填写 resolution 或 skip 决策，并同步更新关联 Fact 和验收标准。未回答项保持 pending；新答案产生冲突时允许新增 Confirmation。
14. 重新计算统一 Confirmation Summary。若仍有 blocking，保留 `confirmation_only` Checkpoint 并再次集中展示剩余问题；若 `blocking_pending_count=0` 且原始任务要求测试用例，切换到 `formal_generation` 并立即自动交接给 `qa-testcase-design`，无需用户再次发送继续指令、规则路径或需求内容。
15. 没有 blocking Confirmation 时不暂停，自动进入第二阶段。requirement-only 任务结束时，使用对话交付契约展示分析状态、blocking/nonblocking/suggested 全部分组、报告和 Requirement Model 路径；没有待确认点也必须明确写“无”。

## 接口自动化影响评估

涉及接口或查询条件时，追加 `是否涉及接口`、`是否需要接口自动化`（均为 `yes/no/unknown`）、`自动化动作`（`create/update/none/blocked`）、判断依据、可能受影响的接口/参数、证据状态和待补充材料。新增查询条件但没有 Groovy、接口契约或 Diff 证据时只能提示“可能需要更新接口自动化”，不得虚构参数名、类型或传值格式；需要生成或维护自动化时交接给 `../qa-api-automation/SKILL.md`。

本 Skill 不渲染 XMind；不得把模板、代码行为或推断升级为需求事实。

## pre_review 边界

pre_review 复用现有 Evidence、Fact、Confirmation 和验收依据，检查目标/范围/排除项、入口、角色权限、主分支流程与状态、字段枚举默认值计算时间口径、异常边界依赖以及验收标准的可观察性。每个问题至少填写 `issue_id`、`issue_type`、`severity`、`statement`、`current_evidence`、`impact`、`confirmation_question`，最终给出 `ready`、`conditionally_ready` 或 `not_ready`。该模式禁止生成 Risk Matrix、Testcase Model、测试用例、XMind、Manifest、Index、SQL 或 API 自动化产物，完成后不得自动进入正式用例流程；pre_review 结果也不得用于知识候选提取。
