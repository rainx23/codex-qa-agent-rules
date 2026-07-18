---
name: qa-artifact-validation
description: 用于校验 QA 分析报告、XMind Markdown、XMind Workbook、Manifest、索引、镜像规则树和发布就绪状态。适用于校验、转换、发布、索引及 QA 规则或测试用例产物的最终验收。Artifact validation, XMind validation, manifest, index, workbook conversion and release readiness.
---

# QA 测试产物校验（QA Artifact Validation）

模型校验职责分离：`validate_schemas.py` 校验仓库契约与固定 Fixture；`validate_models.py` 校验本次真实模型；`validate_manifest.py` 对最终报告、模型、XMind、Workbook 和计数做全链路复验。

将本 Skill 的根目录解析为当前 `SKILL.md` 向上两级的仓库根目录。

## 执行流程

1. 读取 `../../rules/core/analysis-report-contract.md`，识别显式或自动报告模式；需要时使用对应 `--mode` 运行 `../../scripts/validate_analysis_report.py`。校验模式章节、证据、疑似缺陷依据、P0 映射和联合追踪。
2. 运行 `../../scripts/validate_schemas.py`，在渲染产物前校验 Requirement/Diff Model、Risk Coverage Matrix 和 Testcase Model。
3. 使用 `../../scripts/validate_xmind_md.py` 校验根节点、固定层级、维度、三位编号、语法、重复项、断言、未知规则泄漏和多入口规则。确认分组/直连多入口均有至少两个平级分支，分支步骤与预期完整，不含混合直连步骤、虚构入口或“分别打开/依次进入多个入口”等拼接表达。
4. 使用 `../../scripts/validate_traceability.py` 校验报告、风险矩阵、用例模型与 XMind Markdown 的行级追踪；每个模型和 XMind TC 都必须有明确风险映射。
5. 运行 `../../scripts/md_to_xmind.py` 后重新读取 `content.json`、`metadata.json` 和 `manifest.json`，递归比较 Markdown 与 Workbook 的完整树：根标题、每个节点标题、子节点数量、顺序和父子层级；首个差异必须报告路径、类型及双方值。保留根节点、TC 数量、分支顺序和节点总数摘要。统计 TC 节点而不是 `entry_branches`；同时比较用例模型与 XMind 的维度、公共入口/模块、测试点、步骤、预期和分支内容。
6. 运行 `../../scripts/validate_manifest.py`，校验规则版本、来源哈希、待确认/P0 数量、安全路径、模型、Workbook 内容和 supersedes 关系。
7. 仅在 Manifest 校验通过后运行 `../../scripts/build_testcase_index.py`，随后必须运行 `../../scripts/validate_testcase_index.py testcases/index.md`；它对每个正式 passed Manifest 复用完整 Manifest 校验，并逐字段核对索引行和备注。确认 artifact id 与 Manifest 路径均唯一、正式文件存在、passed 无漏登，且 pending/failed 没有冒充“已校验”。
8. 运行语法、Schema 生成检查、规则版本检查、全量测试、Skill 校验、仓库模式校验和 CI 静态检查。
   - 先运行 `python -m unittest discover -s tests -p test_anti_hallucination_fixtures.py -v`，确保八类独立反幻觉夹具通过，再运行全量测试。
   - 正式产物使用 `scripts/validate_formal_artifacts.py` 统一扫描 `testcases/**/manifest.json`，跳过 drafts，并对每个 passed Manifest 复用 Manifest、模型、Markdown、Workbook 与索引完整校验；CI 不硬编码具体业务目录。
9. 任一必需检查失败时标记校验失败，并停止“完整交付”的结论。
10. 产物存在时运行 `validate_knowledge.py`、`build_knowledge_index.py --check`、`validate_data_validation.py`、`validate_sql_style.py --strict` 和 `validate_sql_artifact.py`。确认 SQL 只读，且只有在用户提供执行证据时才标记为已执行/通过/失败。
11. 接口自动化产物存在时，运行 `../../scripts/validate_api_automation_artifacts.py --excel <case.xlsx> --parameters <parameter.txt> --model <api-automation.json>`；固定表头、JSON、健康校验、变量和参数维度任一失败都阻止交付。
12. 原始任务同时要求需求分析和测试用例时，passed 交付必须具备并复验 Requirement Analysis Model、Risk Coverage Matrix、Testcase Model、XMind Markdown、Workbook 和 Manifest；缺少任一项不得声明完成。
13. blocking 解除后不得继续只维护 draft 路径。全部正式门禁通过后才生成或更新 Workbook、passed Manifest 和 index；任何正式校验失败时停止完整交付结论。
14. `validation_status` 与 `sql_status` 分开判定。报告、模型、Markdown、Workbook 完整时允许 `passed + sql_status=blocked`；不得因 SQL 缺少 DDL/执行条件把测试设计降级为 pending，也不得为解除阻塞伪造 SQL 或执行证据。

## 可选 Testcase Value Assessment 校验

- 用户提供 Assessment 时，通过 `../../scripts/validate_testcase_quality.py --value-assessment <path>` 校验 Schema、路径、模型 ID、归一化 Hash、三个引用模型及跨模型链接、TC 完整性和持久化重算一致性，并输出 error、warning、suggestion 与评分摘要。`insufficient_inputs` 不得产生依赖分数的低价值或简化建议。
- error 包括 Schema 不合法、引用或 Hash 错误、未知或遗漏 TC、评分字段被篡改以及不支持的 `algorithm_version`；这些错误返回非零退出码。
- 低价值、高维护成本、证据不足、疑似重复以及 P0 或历史缺陷低分保护提示均为非阻塞 warning/suggestion，不得自动修改用例。阶段一不得启用 value strict 门禁。
- 用户未提供 Assessment 时，不搜索默认文件、不报缺失错误、不增加 warning，也不影响现有产物验收。

保留历史产物。除非操作已版本化或得到明确授权，不修复或覆盖已有产物。
