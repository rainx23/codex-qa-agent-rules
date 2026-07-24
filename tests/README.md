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
| `test_one_pass_pipeline.py` | 模型单次读取、Markdown 单次解析、摘要不二次渲染、当前任务真实阶段审计和发布/日常门禁分离 | 是 |
| `test_confirmation_workflow.py` | 一次授权、confirmation_only、集中确认、部分/批量回复、自动续跑和快慢校验分层 | 是 |
| `test_pre_review_and_knowledge_candidates.py` | 显式 pre_review 路由/禁产物/不续跑，以及知识候选提示、来源边界和不自动持久化 | 是 |
| `test_openspec_removal.py` | OpenSpec 来源硬删除、保留来源、当前路由/Skill、生成 Schema 与历史 JSON 无依赖 | 是 |
| `test_codebuddy_adapter.py` | CodeBuddy 总入口、包装 Skill 清单、名称、描述和正式 Skill 引用一致性 | 是 |
| `test_dimension_assessment.py` | 八类测试维度扫描、主辅维度、covered 引用和单主维度复核 warning | 是 |
| `test_analysis_report_validation.py` | 分析报告主摘要 ID 唯一性与 passed 正式用例措辞门禁 | 是 |
| `fixtures/value-assessment/` | computed 合法模型组、Golden、Hash 错误、评分篡改和未知 TC 的独立 Assessment Fixture | 是 |
| `fixtures/` | 输入样例 | 是 |
| `golden/` | 预期输出 | 是 |

## 使用入口

- 独立反幻觉回归：`python -m unittest discover -s tests -p test_anti_hallucination_fixtures.py -v`。
- 一次生成链路回归：`python -m unittest tests.test_one_pass_pipeline -v`。
- 测试用例价值评估回归：运行 `test_testcase_value_assessment.py`、`test_testcase_value_cli.py`、`test_testcase_value_golden.py` 和 `test_testcase_value_ci_contract.py`。
- 全量回归：`python -m unittest discover -s tests -v`。

## 维护约束

- 改变规则、脚本、Schema、CI 或产物契约时必须补充或更新测试。
- Testcase Value Assessment 测试必须保持整数算法、跨 Python 3.10/3.12 结果、换行归一化 Hash、跨平台路径拒绝、保护规则和 CLI 非阻塞语义稳定。
- Testcase Value Assessment 仍只验证仓库提供的合法 Fixture，不要求所有测试产物包含该评分模型；但当前 `RULE_VERSION` 的 passed requirement/combined 正式用例产物必须完整包含八类 `test_dimension_assessment`。warning 和 suggestion 仍然非阻塞。
- 产物治理兼容测试覆盖文本换行/BOM Hash、二进制 Hash、完整 Manifest/index 一致性及 Workbook 完整树复验。
- 回归测试覆盖 blocking Confirmation 解决后的 Fact/计数迁移、原始任务自动续跑契约、正式产物完整性，以及 XMind 无损语义精简、符号、截断和逻辑优先级行为。
- confirmation_only 回归固定覆盖确认前无 Risk/Testcase/XMind/Manifest/Index、首个问题后继续扫描、批量与部分回答、旧 pending/passed 兼容、快速校验不触发全量门禁，以及正式阶段继续通过 Manifest 全链复验。
- pre_review 与 extract_candidate 回归只覆盖新增模式边界，不复制现有 Evidence、Fact、Confirmation、正式产物或知识持久化测试。
- 回归测试覆盖 `validation_status=passed + sql_status=blocked`、证据精度与索引全量覆盖；这些规则均使用通用 Fixture，不绑定特定业务样例。
- 对话摘要回归使用正式 passed 产物与临时 pending/failed Fixture，验证固定章节、文件用途、无 Confirmation 时的“无”、计数单一来源、跨平台路径和无 ANSI 输出。
- 测试运行期工作区必须创建在系统临时目录并由测试生命周期清理；`tests/fixtures/` 只保存固定、可复用输入，不得在其中创建随机运行目录，即使测试异常也不得残留。
- 条件矩阵、配置存在性/行为分离、多入口核心去重和正式产物统一扫描分别由对应 `test_condition_matrix_*`、`test_entry_branch_*`、`test_shared_entry_scope.py` 与 `test_formal_artifact_scan.py` 覆盖；全局适用入口测试固定 6 个入口阈值、完整展开、禁用简称和模型/XMind 映射。
- 一次生成链路回归必须固定验证同一模型文件只加载一次、同一 Markdown 只解析一次、摘要校验不再调用渲染器、子进程输出不直接回灌上下文，以及日常入口不执行全量历史扫描。
- Golden 变化必须经过人工确认，测试运行时不得自动创建或覆盖 Golden，也不为不同操作系统或 Python 版本维护不同副本。
- Fixture 和 Golden 只服务测试，不作为业务历史版本说明。
- CodeBuddy 适配回归必须覆盖总入口缺失、包装 Skill 缺失、Frontmatter 描述漂移和正式 Skill 引用错误；测试只验证薄包装一致性，不复制正式 QA 工作流测试。

版本与完整变更历史统一见 [CHANGELOG.md](../CHANGELOG.md)。
