---
name: qa-artifact-validation
description: 用于校验 QA 分析报告、XMind Markdown、XMind Workbook、Manifest、索引、镜像规则树和发布就绪状态。适用于校验、转换、发布、索引及 QA 规则或测试用例产物的最终验收。Artifact validation, XMind validation, manifest, index, workbook conversion and release readiness.
---

# QA 测试产物校验（QA Artifact Validation）

将本 Skill 的根目录解析为当前 `SKILL.md` 向上两级的仓库根目录。

## 执行流程

1. 读取 `../../rules/core/analysis-report-contract.md`，识别显式或自动报告模式；需要时使用对应 `--mode` 运行 `../../scripts/validate_analysis_report.py`。校验模式章节、证据、疑似缺陷依据、P0 映射和联合追踪。
2. 运行 `../../scripts/validate_schemas.py`，在渲染产物前校验 Requirement/Diff Model、Risk Coverage Matrix 和 Testcase Model。
3. 使用 `../../scripts/validate_xmind_md.py` 校验根节点、固定层级、维度、三位编号、语法、重复项、断言、未知规则泄漏和多入口规则。确认分组/直连多入口均有至少两个平级分支，分支步骤与预期完整，不含混合直连步骤、虚构入口或“分别打开/依次进入多个入口”等拼接表达。
4. 使用 `../../scripts/validate_traceability.py` 校验报告、风险矩阵、用例模型与 XMind Markdown 的行级追踪；每个模型和 XMind TC 都必须有明确风险映射。
5. 运行 `../../scripts/md_to_xmind.py` 后重新读取 `content.json`、`metadata.json` 和 `manifest.json`，比较根节点、TC 数量、分支顺序和节点总数。统计 TC 节点而不是 `entry_branches`；同时比较用例模型与 XMind 的维度、公共入口/模块、测试点、步骤、预期和分支内容。
6. 运行 `../../scripts/validate_manifest.py`，校验规则版本、来源哈希、待确认/P0 数量、安全路径、模型、Workbook 内容和 supersedes 关系。
7. 仅在 Manifest 校验通过后运行 `../../scripts/build_testcase_index.py`，再确认 artifact id 只出现一次，且校验状态没有与业务状态混用。
8. 运行语法、Schema 生成检查、规则版本检查、全量测试、Skill 校验、仓库模式校验和 CI 静态检查。
9. 任一必需检查失败时标记校验失败，并停止“完整交付”的结论。
10. 产物存在时运行 `validate_knowledge.py`、`build_knowledge_index.py --check`、`validate_data_validation.py`、`validate_sql_style.py --strict` 和 `validate_sql_artifact.py`。确认 SQL 只读，且只有在用户提供执行证据时才标记为已执行/通过/失败。
11. 接口自动化产物存在时，运行 `../../scripts/validate_api_automation_artifacts.py --excel <case.xlsx> --parameters <parameter.txt> --model <api-automation.json>`；固定表头、JSON、健康校验、变量和参数维度任一失败都阻止交付。

保留历史产物。除非操作已版本化或得到明确授权，不修复或覆盖已有产物。
