# 证据与事实规则

## 事实模型

分析前建立结构化事实表，区分确定事实、冲突事实、推断事实和缺失事实。核心结论必须标注来源：需求原文、用户补充、截图、Markdown 文件、Diff、代码上下文、接口说明、SQL 口径、历史缺陷或推断需确认。

## Evidence Reference

`source_type` is a closed enum: `user_confirmation`, `requirement`, `zentao_section_3`, `acceptance_criteria`, `formal_change_record`, `markdown`, `screenshot`, `diff`, `code_context`, `api_document`, `sql_definition`, `complete_ddl`, `knowledge_table`, `historical_defect`, `pasted_text`, `chat_snapshot`. 每条 Evidence 必须显式声明 `storage_type=file|snapshot`，不得再从 `source_type` 猜测存储方式。

事实、变更、影响链、风险、疑似缺陷和验收标准必须使用可追溯的 `evidence_references`。每条必须完整包含 `source_type`、`storage_type`、`source_path`、`snapshot_path`、`source_record_id`、`line_start`、`line_end`、`commit_sha`、`content_hash`、`excerpt`、`captured_at`、`captured_timezone` 和 `evidence_status`；允许为 null 的字段仍必须出现，并由 storage type 决定其合法性。

### File Evidence

`file` 适用于仓库内真实文件。必须填写仓库内相对 `source_path`，`snapshot_path=null`，并复验文件存在性、SHA-256、文本行号和 excerpt。requirement、markdown、diff、code_context、api_document、sql_definition、complete_ddl 和 knowledge_table 只允许 file。diff/code_context 还必须提供合法 commit SHA；仅当明确 `working_tree_evidence=true` 时允许 commit_sha 为 null。

### Snapshot Evidence

`snapshot` 适用于 user_confirmation、pasted_text、chat_snapshot，以及已保存快照的 zentao_section_3、acceptance_criteria、formal_change_record、screenshot、historical_defect。必须填写仓库内相对 `snapshot_path` 和稳定 `source_record_id`，`source_path=null`；内容哈希对应 snapshot 文件。user_confirmation、pasted_text、chat_snapshot 只允许 snapshot。禅道第三部分、验收标准、正式变更记录、截图和历史缺陷可以使用真实 file 或 snapshot，但不得只有记录 ID 或描述。

截图必须指向真实文件或快照并具有内容哈希和稳定附件 ID；二进制截图允许空行号，但 excerpt 只能描述直接可观察内容，不得包含推断。用户确认必须保存聊天快照，粘贴文本必须保存原始文本快照，chat_snapshot 必须保存相关消息上下文而非助手总结。

- UTF-8 文本证据必须定位到真实行号；Diff/代码证据必须包含 Commit、文件和变更位置。
- 文本 Evidence 的 `line_start`/`line_end` 按原文件物理行计数，空行同样占一行。校验器仅统一 CRLF/CR 为 LF 并移除开头 UTF-8 BOM；`excerpt` 必须与闭区间 `[line_start, line_end]` 的原文切片逐字一致，不折叠空白、不做全文搜索，也不得用文件其他位置的相同文字冒充该行证据。一个 Fact 可引用多段精确证据。
- 三个及以上 confirmed Fact 若机械地全部引用同一份多行来源的同一个首行区间，校验器输出证据过度集中 warning，要求人工复核，而不按 Fact 数量复制同一引用。
- current 哈希必须与真实文件一致；stale 或 reconfirm_required 不得支撑 confirmed Fact，并必须说明重新确认原因。
- confirmed Fact 至少需要一条通过全部真实性校验且状态为 current 的 Evidence；其他 Evidence 即使不承担 confirmed 支撑，也必须结构合法。
- Fact 顶层 source_type 必须与至少一条 Evidence source_type 一致。
- Change Evidence 必须为 diff/code_context，路径等于 change.file 且位于 changed_files。
- “需求原文”“代码上下文”“截图”等泛化文字不能单独构成完整证据定位。
- 当可访问的来源文件内容与已记录哈希不一致时，`current` 校验失败；旧证据必须标记为 `stale` 或 `reconfirm_required`，或重新采集。

## DDL 解析证据完整性

- 完整 DDL 与局部字段必须复用同一个字段片段解析器；字段名和完整类型识别后，从左到右循环消费约束 Token。
- 每个字段必须保留 `raw_fragment`、非空 `parsed_tokens` 和 `unparsed_fragment`。未知语法不得删除；必须原样进入 `unparsed_fragment` 并使表降级为 `partial`。
- `nullable` 只由显式 `NULL` 或 `NOT NULL` 决定。`DEFAULT NULL` 只产生 `default_state=known_null`，Comment 或 Default 字符串内的关键字不参与约束判断。
- Generated Column 必须保存 `generated`、`generated_expression` 与 `generated_type`；表达式使用括号深度和引号状态扫描，不得用非贪婪正则截断。
- 表定义尾部必须保留 `raw_tail`、`parsed_tail_tokens` 与 `unparsed_tail`。Engine、Key、Partition、Distributed、Order、Properties 和 Comment 从左到右消费，任何未知尾部均使表降级为 `partial`。
- `schema_scope=complete` 只允许所有字段与表尾完全消费、所有表级约束均已归属且 `parse_warnings=[]` 的结果。无法闭合字段括号、没有可靠字段或敏感输入属于 `blocked`。

## 约束

- 确定事实可进入验收标准和确定性预期。
- 冲突事实进入阻塞类待确认点，不自行裁决。
- 推断事实只能进入风险或待确认点；得到确认前不得写成预期。
- 缺失事实说明缺口、影响和处理方式。
- 不将当前代码行为自动视为业务预期。
- 字段存在、字段清单、DDL 片段等结构证据只能证明结构；“可追加多个用户”“支持多选”“可配置多个值”等容量/能力证据只能证明容量。二者均不得推导自动去重、拒绝/合并重复值、保存后去重、删除后处理、继承/覆盖/排除、不参与统计或权限、默认过滤、唯一约束等额外业务行为。confirmed Fact 声明这类行为时，至少一条 current Evidence 必须明确表达同类行为语义；明确写出“重复用户自动去重”等行为的证据允许支撑同义 Fact。
- 不虚构 SQL 表名、字段、接口、页面、权限、枚举、默认值和兜底规则。
- 疑似缺陷必须同时引用需求证据和 Diff 证据，并标记证据状态；证据不足只能称疑似风险。
