# Execution Instance Contract

Execution Model 必须引用真实 Testcase Model，并声明真实 `branch_count`、`execution_instance_count` 和完整 `execution_instances`。每个可执行 Branch 至少保留一个 initial 实例；rerun 计入实例数但不增加 Branch 数。

Initial 固定 `run_sequence=1` 且无 rerun 引用。Rerun 必须引用同一 Testcase、同一 Branch 的直接前序 failed/blocked 实例，序号连续、时间不倒退且链无自引用或循环。最终状态取同一 Branch 的最高序号，历史实例不得删除。

`not_run` 不得携带执行信息；`passed` 必须有具体实际结果及 current Evidence；`failed` 必须关联真实 Defect 或 suspected_defect blocking Confirmation；`blocked` 必须关联真实 unresolved blocking Confirmation；`skipped` 必须有正式决策字段和证据。

执行证据必须位于仓库内、SHA-256 一致、状态 current，且 `source_record_id` 和文件内容同时包含 Execution、TC 与 Branch ID。正式 passed Execution Model 的所有核心 Branch 最终必须 passed。
