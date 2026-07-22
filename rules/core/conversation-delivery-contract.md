# 对话交付契约

本文件是需求分析、测试点、测试用例、XMind 和完整 QA 产物任务在聊天框中完成交付说明的唯一正式规则来源。聊天回复是正式交付的一部分；文件写入仓库不等于已经向用户完成交付说明。

## 通用门禁

- 最终回复不得只写“已完成”“已生成”“校验通过”“产物见目录”或其他无法定位文件的模糊结论。
- 文件、状态、数量、版本关系和 Confirmation 必须由 Manifest、Requirement Analysis Model、Risk Coverage Matrix 和 Testcase Model 确定性读取；不得从自然语言报告或 XMind 文本猜测、重算或补写。
- 所有路径必须来自 Manifest，统一显示仓库相对 `/` 路径。路径为 null、不存在、为绝对路径或越界时不得虚构替代路径。
- `validation_status` 描述测试设计产物，`sql_status` 描述 SQL 生命周期，必须分开显示。`passed + sql_status=blocked` 是合法组合，不能改写为测试设计 pending 或失败。
- pending 的草稿不得描述成正式用例；failed 不得描述成完整交付；passed 必须标明主要可用文件。
- 只有实际运行过的校验才能写“通过”。未运行时明确写“未执行”“本轮未运行”或“不适用”。
- 不在聊天框复制大段 Requirement/Testcase JSON；JSON 只列路径、类型、用途和状态。

## Blocking Confirmation 即时回复

发现未解决的 blocking Confirmation 时，必须立即在聊天框逐项输出，不得只写入报告：

```markdown
## 需要确认后才能继续

### 阻塞确认点

#### CONF-001：确认点标题

- 问题：具体需要确认的内容
- 当前证据：已有证据能够确认什么
- 不确定点：不能确认什么
- 影响范围：受影响的 Requirement、Risk、TC 或条件组合
- 可选答案：仅在存在明确选项时列出
- 当前处理：正式 XMind 暂停，保留的草稿文件及其路径

## 当前已生成内容

- 需求分析模型：`Manifest 中的路径`
- 草稿分析报告：`Manifest 中的路径`
- 草稿风险矩阵：`Manifest 中的路径`
- 草稿测试用例模型：`Manifest 中的路径`
- 正式 XMind：未生成；原因是对应 CONF 未解决
```

用户回答后按 `confirmation-gate.md` 回写证据和模型，并自动续跑原始任务；不得要求用户重复授权同一范围。

## 最终摘要固定结构

需求分析或完整用例任务结束时，使用 `scripts/render_delivery_summary.py --manifest <manifest.json> --check` 生成稳定 Markdown。不得自由删减固定章节：

1. `处理结果`：需求、风险、用例、`validation_status`、`sql_status`、版本关系、正式 XMind 和真实页面/接口/SQL 执行状态。
2. `待确认点`：blocking、nonblocking、suggested 分组；无记录也逐组写“无”。每项显示状态、影响和当前处理；resolved 标“已解决”，skipped 必须显示跳过原因；同时显示各组待确认数、已解决数和已跳过数。
3. `主要交付文件`：优先显示用户直接使用的文件。passed 首项为正式 `.xmind`，其后是 `.xmind.md` 和 `requirement-analysis.md`；pending 使用准确的草稿名称；requirement-only 不显示不存在的用例文件。
4. `追踪和校验文件`：Requirement Model、Risk Matrix、Testcase Model、Manifest 和 Index，各自显示仓库相对路径、固定类型用途与状态。
5. `用例摘要`：完整用例任务显示 TC、P0 TC、P0 Risk、Risk、入口分支、条件组合、行为覆盖、blocked、excluded、uncovered、relation 和 supersedes。数量只从结构化模型和 Manifest 读取；`entry_branches` 不得当作 TC，`covered_by_tc_ids` 不得当作行为覆盖。
6. `测试维度覆盖`：从 Requirement Model 的 `test_dimension_assessment` 固定展示八类状态；covered 的 TC 数按主维度与辅助维度集合计算，同一 TC 不重复计数，未生成 TC 的维度仍展示处置原因。
7. `校验结果`：Requirement Model、Risk Matrix、Testcase Model、XMind Markdown、Workbook 完整树、Manifest、Index、正式产物统一扫描、全量单元测试和 `git diff --check` 的真实执行状态。
8. `未执行事项`：明确未连接的页面、接口、SQL、自动化和 Git 操作，防止把产物校验误解为业务功能执行通过。

## 三种状态

### passed

必须列出正式 XMind、XMind Markdown、报告、结构化模型、Manifest、Index、Confirmation Summary、用例摘要、校验结果和未执行事项。不得引用 draft 路径。

### pending

必须列出 blocking Confirmation、`pending_reason`、Requirement Model、草稿报告、草稿 Risk Matrix、草稿 Testcase Model、可选草稿 XMind Markdown、正式 XMind 未生成、正式 Index 未登记、已完成/未完成内容及用户下一步需要回答的问题。不得宣称“正式交付完成”“完整交付”或 XMind 校验通过。

### failed

必须列出 `failure_reason`、失败校验、仍可用文件和不可置信文件；不得写“校验通过”或建议直接使用失败的 Workbook。

## 固定文件类型与用途

| Manifest 字段或文件 | 类型 | 用途 |
| --- | --- | --- |
| `report_path` / `requirement-analysis.md` | 需求分析报告 | 人工阅读需求理解、证据、Confirmation、风险、验收标准和回归范围 |
| `analysis_model_paths` / `requirement-analysis.json` | 需求分析模型 | 保存 Fact、Confirmation、Acceptance Criteria 和 Condition Matrix |
| `risk_matrix_path` / `risk-coverage-matrix.json` | 风险覆盖矩阵 | 保存 Risk 与 Requirement、TC 的双向追踪 |
| `testcase_model_path` / `testcase-model.json` | 测试用例模型 | 保存 TC、入口分支、步骤、预期、优先级和条件覆盖 |
| `xmind_md_path` / `*.xmind.md` | 测试用例 Markdown | 审查、版本管理及重新生成 Workbook 的源文件 |
| `xmind_path` / `*.xmind` | 测试用例 | 可直接使用 XMind 打开的正式 Workbook |
| `manifest.json` | 产物清单 | 保存路径、版本、来源 Hash、数量和交付状态 |
| `testcases/index.md` | 全局测试产物索引 | 查询正式历史产物和版本关系 |

类型和用途使用上述固定映射，不根据文件名相似性临时猜测。

## 确定性渲染与校验

- `scripts/render_delivery_summary.py` 默认输出中文 Markdown 到 stdout，可选 `--output <path>`；不得调用 LLM、输出 ANSI 控制字符或维护另一份业务计数。
- `scripts/validate_delivery_summary.py --manifest <manifest> --summary <summary.md>` 校验章节、顺序、状态禁语、路径、计数和 Confirmation Summary；渲染器的 `--check` 使用同一校验入口。
- Manifest 与 Requirement Model 的 Confirmation 数、Manifest 与 Risk/Testcase 模型的 P0/TC/分支数不一致时，必须失败，不得生成成功摘要。
- 当前路径不存在时必须失败或明确标“未生成/不适用/被阻塞”，不得补写一个看似合理的路径。
