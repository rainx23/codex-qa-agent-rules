# QA 规则发布验收清单

本文件是发布入口；正式规则分别位于 rules/core、rules/profiles 和 skills。

## 必须执行

1. Python 语法：

       python -m compileall -q scripts tests

2. 仓库 Skill 契约：

       python scripts/validate_skill_contracts.py skills

3. 自动化回归：

       python -m unittest discover -s tests -p test_anti_hallucination_fixtures.py -v
       python -m unittest discover -s tests -v

4. 单一版本、生成 Schema 和仓库模式：

       python scripts/generate_schemas.py --check
       python scripts/validate_schemas.py
       python scripts/validate_rule_version.py
       python scripts/validate_repository_docs.py
       python scripts/validate_models.py --requirement tests/fixtures/models/requirement-analysis.json --diff tests/fixtures/models/diff-impact.json --risk tests/fixtures/models/risk-coverage-matrix.json --testcase tests/fixtures/models/testcase-model.json
       python scripts/validate_repository_mode.py
       python scripts/validate_ci_workflow.py
       python scripts/validate_knowledge.py qa-knowledge/examples
       python scripts/build_knowledge_index.py qa-knowledge/examples --check
       python scripts/validate_sql_style.py tests/fixtures/sql/valid_validation_sql.sql --strict
       python scripts/validate_data_validation.py tests/fixtures/models/data-validation-valid.json
       python scripts/validate_sql_artifact.py tests/fixtures/artifacts/validation-sql-manifest.json

5. Manifest 示例和索引编码：

       python scripts/validate_manifest.py testcases/manifest.example.json
       python scripts/repair_text_encoding.py testcases/index.md --check

6. 三种分析报告模式：

       python scripts/validate_analysis_report.py tests/fixtures/reports/requirement_only.md --mode requirement
       python scripts/validate_analysis_report.py tests/fixtures/reports/diff_only.md --mode diff
       python scripts/validate_analysis_report.py tests/fixtures/reports/requirement_diff_combined.md --mode combined

7. 逐行追踪和 XMind 样例：

       python scripts/validate_traceability.py tests/fixtures/reports/combined_consistent.md tests/fixtures/valid_case_xmind.md --mode combined --risk-matrix tests/fixtures/models/risk-coverage-matrix.json --testcase-model tests/fixtures/models/testcase-model.json
       python scripts/validate_xmind_md.py tests/fixtures/valid_case_xmind.md
       python scripts/validate_xmind_md.py tests/fixtures/multi_entry_valid_xmind.md
       python scripts/validate_xmind_md.py tests/fixtures/multi_entry_direct_valid_xmind.md
       python scripts/md_to_xmind.py tests/fixtures/valid_case_xmind.md -o 临时输出路径

8. CI 工作流必须覆盖 Python 3.10 和 3.12，并以实际 YAML 解析器检查语法。

9. 集成模式下根目录和 `codex-qa-agent-rules` 的同名规则、Skills、脚本和测试逐文件比较哈希；独立模式不得要求嵌套仓库。

10. 检查校验命令未产生非预期文件变化；干净仓库执行 `git diff --exit-code`。

## 必须覆盖的失败路径

- 多根、TC 跳号和重复、非三位 TC、非法维度、Tab、非 4 空格、层级跳跃。
- 标签节点、泛化“正常”预期、状态值 `NORMAL`、语义重复 error、疑似重复 warning、未确认口径写死。
- 报告缺章节、联动报告缺追踪矩阵、疑似缺陷缺双证据、P0 无测试映射。
- TC 仅出现在普通正文、缺需求证据或 Diff 变更 ID、TC 范围、多风险映射和模型/Markdown 不一致。
- 中文/数字编号章节正文提取、三种报告模式、禅道第三部分优先、目标偏差和产品规则冲突。
- 结构化模型的事实状态、冲突确认、Diff 覆盖状态、P0 风险和 TC 来源校验。
- Diff Impact Chain/Risk/Suspected Defect 强类型字段、引用 ID 存在性与跨模型双向一致性。
- Evidence Reference 路径、行号、Commit、内容哈希、截图/粘贴定位和来源变化后的 stale/reconfirm 门禁。
- Testcase Execution Instance 状态枚举、执行证据、重跑引用、分支/实例独立计数及不增加 TC 数量。
- Manifest 来源哈希、规则版本、时区、待确认/P0 计数、安全路径、supersedes 循环、状态语义和 Workbook 损坏。
- 输出文件已存在、两份批量成功加一份局部失败、失败无伪 Workbook、索引 artifact_id 重复。
- 真实历史 XMind Markdown 原样识别，迁移样例合并重复、移除模糊预期且不降低 P0 业务覆盖。
- 多入口有效分支、无公共入口多入口、单入口多余层级、混合直接步骤、单分支、占位入口名和拼接入口步骤；普通组合操作不得被误报。
- 多入口转换后 TC 数保持不变，分支顺序和 golden topic 顺序保持不变，Testcase Model 与 XMind 的分支数量、顺序、名称、步骤和预期一致。
- 单/多张完整 DDL 拆分、规范化哈希去重、格式变化、字段/类型/主键/唯一键/Duplicate Key/Aggregate Key/分区/分桶/索引/Engine/Properties 变化、显式结构解析失败降级、partial 不覆盖 complete、解析 warning、敏感信息拒绝。
- 知识按表/字段/逻辑/指标检索、默认 active、历史按需加载、active 重复、supersedes 循环、索引漂移和同 DDL 重复引用。
- 数据验证 required/optional/not_required/blocked、指标默认 SQL、明确 REC、禁止猜测对数、mixed、SQL 信息不足和 SQL/REC/TC 追踪失败。
- SQL 星号头、author/北京时间秒、关键字小写、逗号前置、CTE v_、只读安全、无 select */limit/DML/凭据、StarRocks lateral json_each 及 strict warning。
- integrated 仓库缺少 `sql_defaults.author` 时给出迁移错误，不使用旧姓名、系统用户名或静默回退。

任一必需步骤失败时不得发布或宣称完整重构完成。
