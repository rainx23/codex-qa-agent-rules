# 产物治理规则

分析报告的三种模式和章节要求以 `rules/core/analysis-report-contract.md` 为唯一正文来源；结构化中间模型及生命周期以 `rules/core/structured-model-contract.md` 为准。规则版本只读取根目录 `RULE_VERSION`。

## 产物集合

完整输出必须包含分析报告、Requirement Analysis Model、Risk Coverage Matrix、Testcase Model、XMind Markdown、经复验的 .xmind Workbook、Manifest 和 testcases/index.md 记录；存在 Diff 输入时额外包含 Diff 分析报告与 Diff Impact Model。Testcase Value Assessment 仅在用户明确要求时生成，不属于默认必需链。新版本不得覆盖历史文件。

## Manifest

Manifest 至少记录：

- artifact_id、source_type、source_id、带时区生成时间和 generated_timezone。
- source_files、source_hash_algorithm、按稳定顺序计算的 source_hash，以及可选 source_snapshot_path。
- 从 `RULE_VERSION` 读取的 rule_version 和报告模式。
- report_path、分析模型路径、风险矩阵路径、Testcase Model 路径、xmind_md_path、xmind_path。
- case_count、明确表示 P0 用例数的 p0_count/p0_case_count、p0_risk_count。
- `case_count`、`p0_count/p0_case_count` 按 TC 统计；同一 TC 下的 `entry_branches` 只用于表达入口分支，不得被计为额外 TC。
- 可选记录 `knowledge_snapshot`、`data_validation_model`、`validation_sql`、`reconciliation_plan`、`sql_count`、`reconciliation_count`、`sql_status`、DDL/逻辑/指标版本。SQL 和 REC 数量按 ID 统计，未有用户执行结果不得标记 passed。
- pending_count 及 blocking/nonblocking/suggested 三类分项。
- validation_status、relation、supersedes、failure_reason 和 pending_reason。

来源组合哈希必须复算，正式 passed 产物禁止全零哈希。文本内容统一移除 UTF-8 BOM 并将 CRLF/CR 归一为 LF，已知二进制产物保持原始字节；组合哈希包含规范化仓库相对路径、稳定分隔符和内容，路径排序后计算。Manifest、Evidence 和 Assessment 引用复用公共 Hash 实现，不维护重复算法。所有产物路径必须是仓库内相对路径，禁止绝对路径和 `..` 越界。计数不得为负，Manifest 的待确认数量以 Requirement Model 的 Confirmation Summary 为唯一主来源，并与报告交叉验证。relation 只允许新增、补充、替代、废弃；替代和废弃必须填写存在且不形成循环的 supersedes。

### Manifest 状态职责

`confirmation_only` 是 Manifest 之前的独立工作流阶段：只保存 Requirement Analysis Checkpoint 和 Evidence，不创建正式或 pending Manifest，不写 Index，也不生成草稿报告、Risk Matrix、Testcase Model、XMind Markdown 或 Workbook。以下 `pending` 契约仅用于历史兼容或显式旧流程，不强制迁移。

- `pending` 表示业务确认尚未完成，不表示模型可以无效。必须填写 `pending_reason`，正式 `report_path`、`risk_matrix_path`、`testcase_model_path`、`xmind_md_path`、`xmind_path` 必须为 null；Requirement 分析必须通过 `draft_report_path`、`draft_risk_matrix_path`、`draft_testcase_model_path` 和至少一个 Requirement `analysis_model_paths` 完整复验草稿。`draft_xmind_md_path` 可为 null，但 `pending_reason` 必须说明未生成原因。
- `passed` 表示正式产物完成。必须使用正式路径并完整复验报告、模型、Markdown 和 Workbook；`blocking_pending_count`、`skipped_core_count`、`unresolved_core_fact_count` 必须均为 0，且不得存在核心 missing/conflicting Fact。
- `failed` 表示模型结构、Schema、路径、哈希、文件或校验过程无效。必须填写 `failure_reason`，不得声明正式成功产物。正常等待业务确认必须使用 pending，不得使用 failed。

所有 `draft_*` 路径必须真实存在、位于仓库内 `testcases/drafts/` 或 `tests/fixtures/drafts/`，禁止绝对路径、`..` 和越界。Pending 不要求正式 Workbook、正式索引或执行结果，但不得提前返回并跳过草稿模型、报告、数量、版本、哈希格式和路径安全校验。

`validation_status` 与 `sql_status` 是两个正交状态：前者描述测试设计产物，后者描述 SQL 计划/生成/评审/执行状态。完整测试设计允许 `passed + blocked`；`sql_status=blocked` 时 `validation_sql` 和 `execution_evidence` 必须为 null。反之，`pending` 仍必须满足 draft 路径契约，不能只以 SQL 被阻塞为理由绕过草稿校验。

## 流程

1. 写入版本化报告和 Markdown。
2. 校验报告与 Markdown。
3. 转换并复验 Workbook；Markdown 与 `content.json` 必须递归比较根标题、每个节点标题、子节点数量、顺序和父子层级，首个差异需输出完整路径、差异类型及双方值。
4. 生成并校验 Manifest。
5. 原子更新索引，确保 artifact_id 唯一。
6. 运行 `scripts/validate_testcase_index.py testcases/index.md`，确认每个 `testcases/**/manifest.json` 下的 passed Manifest 按 artifact_id 和 Manifest 路径唯一登记，且正式路径真实存在。
7. 记录新增、补充、替代或废弃关系。

CI 和发布前校验统一调用 `scripts/validate_formal_artifacts.py` 扫描 `testcases/**/manifest.json`，跳过 `testcases/drafts/`，并对每个 `validation_status=passed` 的 Manifest 复用完整 Manifest、Requirement/Risk/Testcase Model、XMind Markdown、Workbook 树和索引校验。不得为每个业务目录追加硬编码校验命令。

任一步失败都不得宣称完整产物完成。失败时保留可用的 Markdown 和报告，不伪造 Workbook 路径。

原始任务同时要求需求分析和测试用例时，缺少 Requirement Analysis Model、Risk Coverage Matrix、Testcase Model、XMind Markdown、Workbook 或 Manifest 任一项均不得宣称完整交付；正式索引只能在 passed Manifest 全链路复验后更新。

## 索引

索引保留历史记录，统一 UTF-8，表头固定。校验状态只表达 `待校验/已校验/校验失败`，产物关系只表达新增、补充、替代、废弃；原业务状态写入备注，不能混入校验状态。旧记录必须标记 `legacy_rule_version=unknown`（无法确认时）、`current_validation_status=未按当前规则校验` 和 `migration_status=未迁移`。不同项目副本可保留各自历史行，但规则、脚本和表结构必须一致。乱码历史行应进行可逆编码修复，无法可靠修复时原样保留并在备注标记。

pending/failed Manifest 不要求登记为“已校验”正式行；passed Manifest 必须先通过完整 Manifest 校验，并且只能登记一次。索引的生成时间、来源类型、分析范围、规则版本、版本关系、校验状态、报告、Markdown、Workbook、Manifest 路径及备注计数必须与 Manifest 逐项一致。重复 artifact_id、重复 Manifest 路径、交叉绑定、缺失正式文件、虚假 passed 行或仓库内 passed Manifest 漏登均为错误；`testcases/drafts/` 不强制正式登记。

## 历史产物兼容

- 新规则校验失败只表示历史产物不符合当前规范，不推翻原业务周期的测试结论。
- 当前规则版本的替代产物因真实 blocking Confirmation 保持 pending 时，旧 passed 产物仍按其历史规则版本复验并保留索引；pending 替代本身必须通过草稿、证据、Confirmation 和 Manifest 校验，但不得冒充当前 passed 正式产物。
- 禁止覆盖旧报告、Markdown 或 Workbook；实际迁移必须生成版本化新产物，并以 `relation=替代`、`supersedes` 和索引记录建立关系。
- 本批工程化改造不具备重新确认历史需求事实和补齐结构化追踪模型的证据，因此不改生产历史产物。`tests/fixtures/legacy` 使用真实旧版 Markdown 的固定哈希副本演示迁移：保留原副本，合并重复场景，改写模糊预期，校验 P0 业务覆盖，并在临时目录转换和复验 Workbook。该测试 Fixture 不冒充正式业务 Manifest 或索引迁移记录。
