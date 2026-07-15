# 产物治理规则

分析报告的三种模式和章节要求以 `rules/core/analysis-report-contract.md` 为唯一正文来源。

## 产物集合

完整输出必须包含分析报告、XMind Markdown、经复验的 .xmind Workbook、Manifest 和 testcases/index.md 记录。新版本不得覆盖历史文件。

## Manifest

Manifest 至少记录：

- artifact_id、source_type、source_id 和生成时间。
- requirement_id 或 commit_range。
- source_hash 和 rule_version。
- report_path、xmind_md_path、xmind_path。
- case_count、p0_count、pending_count。
- validation_status、relation、supersedes 和 failure_reason。

计数不得为负，P0 数不得超过用例数。relation 只允许新增、补充、替代、废弃；替代和废弃必须填写 supersedes。passed 状态要求三个产物路径存在且 Workbook 复验通过；failed 状态必须填写 failure_reason。

## 流程

1. 写入版本化报告和 Markdown。
2. 校验报告与 Markdown。
3. 转换并复验 Workbook。
4. 生成并校验 Manifest。
5. 原子更新索引，确保 artifact_id 唯一。
6. 记录新增、补充、替代或废弃关系。

任一步失败都不得宣称完整产物完成。失败时保留可用的 Markdown 和报告，不伪造 Workbook 路径。

## 索引

索引保留历史记录，统一 UTF-8，表头固定。不同项目副本可保留各自历史行，但规则、脚本和表结构必须一致。乱码历史行应进行可逆编码修复，无法可靠修复时原样保留并在备注标记。
