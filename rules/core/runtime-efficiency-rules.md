# QA 生成链路运行效率规则

本规则约束日常 Requirement → Risk → Testcase → XMind → Manifest → Index 生成链，目标是在不降低证据、Schema 和交付门禁的前提下消除重复读取、重复生成和失败后无效执行。

## 最小加载与工作区边界

- 同一任务中已经读取的规则、Schema 或模型契约不得无原因重复读取；需要回看字段时优先运行 `python scripts/describe_model_contract.py <model>`。
- 默认不得扫描历史 `testcases/`。只有用户明确要求历史复用、替代关系、同需求升级或历史缺陷回归时，才能读取相关历史业务产物。
- 简单 UI 或样式需求只加载命中的最少 Profile；不得加载 SQL、API、知识库等无关规则。
- 日常业务产物不得在仓库 `scripts/` 下创建临时脚本，尤其禁止 `scripts/_*.py`。临时运行文件必须位于系统临时目录并在退出时清理。
- 最终回复只输出交付摘要，不重复打印完整模型、完整 Schema 或大段脚本日志。

## 契约先行与阶段门禁

- 写 Requirement、Risk、Testcase 或 Manifest 前必须先加载精简契约或合法最小 Fixture，不得根据字段名猜测结构。
- 每个阶段生成后立即校验。前一阶段失败时，后续正式产物调用次数必须为零。
- 同一阶段最多允许一次自动修复重试；第二次校验仍失败时必须停止并输出阶段、命令、退出码、错误摘要和已执行次数。
- 禁止连续三次或更多次重写同一模型，禁止连续多次读取完整 Schema。
- `validate_models.py` 未通过时，禁止生成正式 XMind Workbook、Manifest 和 Index。
- `validate_manifest.py` 未通过时，禁止更新 Index；Manifest 只能由 `build_task_manifest.py` 生成，Index 只能由 `build_testcase_index.py` 更新，禁止手写 Manifest 或文本替换 Index。
- 正式完成状态只以 `validation_status=passed` 为准；不得把 validation failure 描述为内容正确后继续交付。

## 固定执行顺序

正式链路固定为：

`Requirement Model → Requirement 校验 → Risk Matrix → Risk 校验 → Testcase Model → validate_models.py → XMind Markdown → validate_xmind_md.py → validate_testcase_quality.py → md_to_xmind.py → verify_xmind.py → build_task_manifest.py → validate_manifest.py → build_testcase_index.py → validate_testcase_index.py → validate_task.py → delivery summary`

任一步失败立即停止；不得出现模型失败但状态为 completed、Manifest 失败但 Index 已更新，或未执行 `validate_task.py` 却声明完成。

## 日常与发布校验

- 日常任务最终必须执行 `python scripts/validate_task.py --manifest <current-manifest>`。
- 规则、Skill、Schema、脚本、测试、版本、CHANGELOG 或 CI 未变化时，日常任务禁止运行 `validate_release.py` 和全量 unittest。
- 本仓库自身规则或工具变更仍按发布治理运行完整发布门禁。
