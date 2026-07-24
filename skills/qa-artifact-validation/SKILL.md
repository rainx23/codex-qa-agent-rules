---
name: qa-artifact-validation
description: 用于校验 QA 分析报告、XMind Markdown、XMind Workbook、Manifest、索引、镜像规则树和发布就绪状态。适用于校验、转换、发布、索引及 QA 规则或测试用例产物的最终验收。Artifact validation, XMind validation, manifest, index, workbook conversion and release readiness.
---

# QA 测试产物校验（QA Artifact Validation）

模型校验职责分离：`validate_schemas.py` 只用于规则发布和 CI；`validate_models.py` 用于本次真实模型的定向调试；日常正式交付最终统一运行一次 `validate_task.py`，由 Manifest 全链复验当前报告、模型、XMind、Workbook 和当前 Index 记录。

将本 Skill 的根目录解析为当前 `SKILL.md` 向上两级的仓库根目录。

开始校验前完整读取 `../../rules/core/conversation-delivery-contract.md`，并将聊天回复视为正式交付的一部分。

## 执行流程

1. 读取 `../../rules/core/analysis-report-contract.md`，识别显式或自动报告模式；需要时使用对应 `--mode` 调用分析报告校验函数。校验模式章节、证据、疑似缺陷依据、P0 映射和联合追踪。
2. 正式模型生成完成后，在同一 Python 进程中一次加载 Requirement/Diff Model、Risk Coverage Matrix 和 Testcase Model，并复用同一批内存对象执行结构、Evidence、条件矩阵、跨模型 ID 和测试维度校验。`scripts/validate_models.py` 仅作为定向调试兼容入口，不得在自动修复循环中重复调用。
   - 正式任务同时校验八类 `test_dimension_assessment`、范围处置证据、主辅维度引用和单一主维度 review warning；SQL blocked 与测试设计 passed 分开表达。
3. XMind Markdown 只解析一次，并将同一个 outline 依次用于结构、质量、追踪、Workbook 转换和完整树复验。确认 2 至 5 个入口的分组/直连结构均有独立平级分支、步骤和预期；不少于 6 个同规则入口改用唯一全局适用入口范围。
4. 使用同一批已加载模型和同一个 Markdown outline 校验报告、风险矩阵、用例模型与 XMind Markdown 的行级追踪；每个模型和 XMind TC 都必须有明确风险映射。
5. Markdown 与模型校验通过后生成 Workbook，并复用已有 outline 递归比较完整树：根标题、每个节点标题、子节点数量、顺序和父子层级。首个差异必须报告路径、类型及双方值。
6. 构建 Manifest 时由代码注入 `RULE_VERSION`、时间、Hash、路径、计数和状态；不得由模型填写或修补确定性字段。Manifest 构建后不单独反复调用完整校验器。
7. passed Manifest 校验通过后原子更新当前 `testcases/index.md` 记录。日常任务只校验当前 Manifest 对应的唯一 Index 行；不得执行 `validate_testcase_index.py` 全量扫描历史 Manifest。
8. 日常业务交付最终只运行一次：

   `python ../../scripts/validate_task.py --manifest <current-manifest> --audit <artifact-directory>/pipeline-audit.json`

   该入口复验当前 Manifest 全链、当前 Index 行、显式相关测试和 `git diff --check`，并由真实执行代码记录每个阶段、耗时、状态和失败次数。成功只返回摘要；失败只返回有限错误，完整阶段摘要写入 audit 文件。
9. 修改规则、Skill、Schema、脚本、测试、版本、CHANGELOG、目录或 CI 时，才运行 `python ../../scripts/validate_release.py`。发布门禁可执行 `validate_schemas.py`、全量 `validate_testcase_index.py`、正式产物统一扫描、反幻觉 Fixture 和全量单元测试。
10. 任一必需检查失败时标记校验失败，并停止“完整交付”的结论。确定性错误由代码直接处理；只有业务语义错误才返回模型，且不自动循环修复。
11. 产物存在时按需校验知识、数据验证、SQL 和接口自动化产物；没有对应产物时不得搜索默认文件或增加无关调用。
12. 原始任务同时要求需求分析和测试用例时，passed 交付必须具备并复验 Requirement Analysis Model、Risk Coverage Matrix、Testcase Model、XMind Markdown、Workbook 和 Manifest；缺少任一项不得声明完成。
13. `confirmation_only` 阶段不接收 Manifest，也不要求任何 `draft_*` 路径。blocking 解除后进入正式阶段，从已更新 Checkpoint 首次生成正式链；不得先生成空模型再用 JSON Patch 循环修补。
14. `validation_status` 与 `sql_status` 分开判定。报告、模型、Markdown、Workbook 完整时允许 `passed + sql_status=blocked`。
15. Manifest 和当前任务校验通过后运行 `python ../../scripts/render_delivery_summary.py --manifest <manifest.json> --check`，使用单次确定性渲染结果作为最终聊天回复主体。摘要只渲染一次，校验器不得再次调用渲染器或重新执行完整产物链。
16. `pre_review` 不接收任何正式测试产物。正式交付通过且存在明显可复用 confirmed Fact 或 resolved Confirmation 时，仅追加一次知识候选提示。

## 可选 Testcase Value Assessment 校验

- Risk Coverage Matrix 和 Testcase Model 均校验通过后，可按用户要求校验独立 Testcase Value Assessment Model。
- 用户未提供 Assessment 时不搜索默认文件、不报缺失错误、不增加 warning，也不影响现有产物验收。
- Assessment 的结构、引用、Hash 或持久化重算错误返回非零退出码；普通 warning/suggestion 不得自动修改用例。

保留历史产物。除非操作已版本化或得到明确授权，不修复或覆盖已有产物。日常任务不得默认读取历史 testcase；全量历史复验只属于发布门禁。
