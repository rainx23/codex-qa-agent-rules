# SQL Identifier Evidence Contract

正式 SQL 校验必须加载 Requirement 与 Knowledge；引用 Change、Risk、Testcase 时还必须加载对应模型。缺少上下文不得降级为仅做 Schema 校验。草稿只能通过显式 `--draft` 进入 pending 语义。

每条 Identifier Evidence 必须包含 `identifier`、`identifier_type`、`qualified_identifier`、`scope_table`、`usage_type`、`source_reference_type`、`source_reference_id`、非空 `evidence_references` 和 `evidence_state`。

Identifier 类型限定为 table、column、function、enum_value、parameter、join_key、filter_value。来源限定为 knowledge_table、knowledge_table_field、complete_ddl、fact、change、formal_document、code_context、builtin_sql、user_confirmation，并按类型执行来源矩阵。

表和字段必须命中真实 Knowledge。字段必须存在于 `scope_table`，且 `qualified_identifier`、字段名、Knowledge Table ID 和字段引用 ID 一致。Complete DDL 还要求 complete scope、无 parse warning、无 unparsed tail 且字段无 unparsed fragment。Partial Knowledge 只能证明明确列出的字段。

Fact 只能证明业务枚举、参数、过滤口径和 Join 关系，不能单独证明物理字段存在。Builtin SQL 只接受目标方言白名单函数；未知函数和 UDF 不得冒充 builtin。

SQL 实际使用的物理表、字段、函数和参数必须与 Identifier Evidence 双向一致。CTE、表别名、字段别名、注释、字符串和参数占位符内容不得被当作物理字段。
