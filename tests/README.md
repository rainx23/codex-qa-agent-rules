# Tests

规则、脚本、Schema 和 CI 契约的离线自动化测试。

## 目录定位

覆盖行为回归、生成契约、Fixture 和 Golden 输出，不依赖网络或外部服务。

## 主要内容

| 路径 | 作用 | 是否手工维护 |
| --- | --- | --- |
| `test_*.py` | 单元与集成测试 | 是 |
| `test_anti_hallucination_contracts.py` | 反幻觉、门禁、模型和 SQL 配置反例 | 是 |
| `test_anti_hallucination_fixtures.py` | 八类独立反幻觉 Fixture 的统一回归入口 | 是 |
| `fixtures/anti_hallucination/` | confirmed inference、blocking gate、DDL partial、模糊断言、缺失证据、虚构标识符、疑似缺陷、API health scope 的合法/非法输入与 Golden | 是 |
| `test_testcase_value_assessment.py` | 七维评分确定性、持久化重算、Hash、路径安全及 P0/历史缺陷保护 | 是 |
| `test_testcase_value_cli.py` | 可选 Assessment CLI 输出顺序、warning/suggestion 和退出码契约 | 是 |
| `test_testcase_value_golden.py` | 验证 CLI Assessment 输出 Golden、编码、换行和顺序稳定性 | 是 |
| `test_verify_xmind.py` | 验证 Markdown 与 Workbook 的完整递归树、顺序和父子层级一致性 | 是 |
| `test_testcase_value_ci_contract.py` | 验证 Windows/Linux 与 Python 3.10/3.12 兼容性 Job 配置 | 是 |
| `test_evidence_precision.py` | 证据精确定位、派生链、confirmed/current 链路和字段结构边界 | 是 |
| `test_testcase_index.py` | passed Manifest 索引唯一性、漏登、重复和正式路径完整性 | 是 |
| `test_delivery_summary.py` | passed/pending/failed 对话摘要、Confirmation、路径、计数、顺序和 CLI 契约 | 是 |
| `test_dimension_assessment.py` | 八类测试维度扫描、主辅维度、covered 引用和单主维度复核 warning | 是 |
| `fixtures/value-assessment/` | computed 合法模型组、Golden、Hash 错误、评分篡改和未知 TC 的独立 Assessment Fixture | 是 |
| `fixtures/` | 输入样例 | 是 |
| `golden/` | 预期输出 | 是 |

## 使用入口

- 独立反幻觉回归：`python -m unittest discover -s tests -p test_anti_hallucination_fixtures.py -v`。
- 测试用例价值评估回归：运行 `test_testcase_value_assessment.py`、`test_testcase_value_cli.py`、`test_testcase_value_golden.py` 和 `test_testcase_value_ci_contract.py`。
- 全量回归：`python -m unittest discover -s tests -v`。

## 维护约束

- 改变规则、脚本、Schema、CI 或产物契约时必须补充或更新测试。
- Testcase Value Assessment 测试必须保持整数算法、跨 Python 3.10/3.12 结果、换行归一化 Hash、跨平台路径拒绝、保护规则和 CLI 非阻塞语义稳定。
- CI 只验证仓库提供的合法 Assessment Fixture，不要求所有测试产物包含 Assessment；warning 和 suggestion 仍然非阻塞。
- 产物治理兼容测试覆盖文本换行/BOM Hash、二进制 Hash、完整 Manifest/index 一致性及 Workbook 完整树复验。
- 回归测试覆盖 blocking Confirmation 解决后的 Fact/计数迁移、原始任务自动续跑契约、正式产物完整性，以及 XMind 无损语义精简、符号、截断和逻辑优先级行为。
- 回归测试覆盖 `validation_status=passed + sql_status=blocked`、证据精度与索引全量覆盖；这些规则均使用通用 Fixture，不绑定特定业务样例。
- 对话摘要回归使用正式 passed 产物与临时 pending/failed Fixture，验证固定章节、文件用途、无 Confirmation 时的“无”、计数单一来源、跨平台路径和无 ANSI 输出。
- 条件矩阵、配置存在性/行为分离、多入口核心去重和正式产物统一扫描分别由对应 `test_condition_matrix_*`、`test_entry_branch_*` 与 `test_formal_artifact_scan.py` 覆盖。
- Golden 变化必须经过人工确认，测试运行时不得自动创建或覆盖 Golden，也不为不同操作系统或 Python 版本维护不同副本。
- Fixture 和 Golden 只服务测试，不作为业务历史版本说明。

版本与完整变更历史统一见 [CHANGELOG.md](../CHANGELOG.md)。
