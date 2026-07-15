# QA 规则发布验收清单

本文件是发布入口；正式规则分别位于 rules/core、rules/profiles 和 skills。

## 必须执行

1. Python 语法：

       python -m compileall -q scripts tests

2. 仓库 Skill 契约：

       python scripts/validate_skill_contracts.py skills

3. 自动化回归：

       python -m unittest discover -s tests -v

4. Manifest 示例和索引编码：

       python scripts/validate_manifest.py testcases/manifest.example.json
       python scripts/repair_text_encoding.py testcases/index.md --check

5. 三种分析报告模式：

       python scripts/validate_analysis_report.py tests/fixtures/reports/requirement_only.md --mode requirement
       python scripts/validate_analysis_report.py tests/fixtures/reports/diff_only.md --mode diff
       python scripts/validate_analysis_report.py tests/fixtures/reports/requirement_diff_combined.md --mode combined

6. XMind 样例：

       python scripts/validate_xmind_md.py tests/fixtures/valid_case_xmind.md
       python scripts/md_to_xmind.py tests/fixtures/valid_case_xmind.md -o 临时输出路径

7. 根目录和 codex-qa-agent-rules 的同名规则、Skills、脚本和测试逐文件比较哈希。

## 必须覆盖的失败路径

- 多根、TC 跳号和重复、非法维度、Tab、非 4 空格、层级跳跃。
- 标签节点、模糊预期、语义重复、未确认口径写死。
- 报告缺章节、联动报告缺追踪矩阵、疑似缺陷缺双证据、P0 无测试映射。
- 中文/数字编号章节正文提取、三种报告模式、禅道第三部分优先、目标偏差和产品规则冲突。
- Manifest 负数、非法枚举、路径缺失、计数不一致和 Workbook 损坏。
- 输出文件已存在、批量转换部分失败、索引 artifact_id 重复。

任一必需步骤失败时不得发布或宣称完整重构完成。
