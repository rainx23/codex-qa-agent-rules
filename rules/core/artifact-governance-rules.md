# 产物治理规则

分析报告的三种模式和章节要求以 `rules/core/analysis-report-contract.md` 为唯一正文来源；结构化中间模型及生命周期以 `rules/core/structured-model-contract.md` 为准。规则版本只读取根目录 `RULE_VERSION`。

## 产物集合

完整输出必须包含分析报告、XMind Markdown、经复验的 .xmind Workbook、Manifest 和 testcases/index.md 记录。新版本不得覆盖历史文件。

## Manifest

Manifest 至少记录：

- artifact_id、source_type、source_id、带时区生成时间和 generated_timezone。
- source_files、source_hash_algorithm、按稳定顺序计算的 source_hash，以及可选 source_snapshot_path。
- 从 `RULE_VERSION` 读取的 rule_version 和报告模式。
- report_path、分析模型路径、风险矩阵路径、Testcase Model 路径、xmind_md_path、xmind_path。
- case_count、明确表示 P0 用例数的 p0_count/p0_case_count、p0_risk_count。
- `case_count`、`p0_count/p0_case_count` 按 TC 统计；同一 TC 下的 `entry_branches` 只用于表达入口分支，不得被计为额外 TC。
- pending_count 及 blocking/nonblocking/suggested 三类分项。
- validation_status、relation、supersedes、failure_reason 和 pending_reason。

来源组合哈希必须复算，正式 passed 产物禁止全零哈希。所有产物路径必须是仓库内相对路径，禁止绝对路径和 `..` 越界。计数不得为负，三类待确认数之和必须等于 pending_count，P0 用例数不得超过用例总数。relation 只允许新增、补充、替代、废弃；替代和废弃必须填写存在且不形成循环的 supersedes。passed 状态要求报告、四类结构化模型、Markdown 和 Workbook 全部存在并交叉复验；failed 状态必须填写 failure_reason 且不得伪造 Workbook；pending 状态必须填写 pending_reason，允许最终产物路径为空。

## 流程

1. 写入版本化报告和 Markdown。
2. 校验报告与 Markdown。
3. 转换并复验 Workbook。
4. 生成并校验 Manifest。
5. 原子更新索引，确保 artifact_id 唯一。
6. 记录新增、补充、替代或废弃关系。

任一步失败都不得宣称完整产物完成。失败时保留可用的 Markdown 和报告，不伪造 Workbook 路径。

## 索引

索引保留历史记录，统一 UTF-8，表头固定。校验状态只表达 `待校验/已校验/校验失败`，产物关系只表达新增、补充、替代、废弃；原业务状态写入备注，不能混入校验状态。旧记录必须标记 `legacy_rule_version=unknown`（无法确认时）、`current_validation_status=未按当前规则校验` 和 `migration_status=未迁移`。不同项目副本可保留各自历史行，但规则、脚本和表结构必须一致。乱码历史行应进行可逆编码修复，无法可靠修复时原样保留并在备注标记。

## 历史产物兼容

- 新规则校验失败只表示历史产物不符合当前规范，不推翻原业务周期的测试结论。
- 禁止覆盖旧报告、Markdown 或 Workbook；实际迁移必须生成版本化新产物，并以 `relation=替代`、`supersedes` 和索引记录建立关系。
- 本批工程化改造不具备重新确认历史需求事实和补齐结构化追踪模型的证据，因此不改生产历史产物。`tests/fixtures/legacy` 使用真实旧版 Markdown 的固定哈希副本演示迁移：保留原副本，合并重复场景，改写模糊预期，校验 P0 业务覆盖，并在临时目录转换和复验 Workbook。该测试 Fixture 不冒充正式业务 Manifest 或索引迁移记录。
