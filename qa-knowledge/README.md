# QA Knowledge Boundary

## 目录定位

项目本地、可复用业务知识的边界说明；公共规则仓库仅保留脱敏示例。

## 主要内容

| 路径 | 作用 | 是否手工维护 |
| --- | --- | --- |
| `examples/` | 脱敏的 DDL、逻辑、指标和索引示例 | 是 |

## 使用入口

- 使用 `scripts/validate_knowledge.py qa-knowledge/examples` 校验知识结构。

## 维护约束

- 不保存真实 DDL、指标或历史需求；持久化草稿必须经过用户确认。
- 索引由脚本生成或检查；新增目录职责、命令或生成边界时更新本 README。
- `examples/` 下索引属于自动生成内容，不直接手工修改。

版本与完整变更历史统一见 [CHANGELOG.md](../CHANGELOG.md)。

`qa-knowledge/` is the project-local location for confirmed, reusable business knowledge. The public rules repository only ships `examples/` with sanitized facts.

- Complete DDL is stored once under `domains/<domain>/tables/<database>.<table>/current.sql`; structural changes move the previous file to `history/` and update `changelog.json`.
- Partial fields are current-scope facts only and never create or overwrite a complete table DDL.
- Logic, metric and requirement knowledge are versioned independently and reference tables/fields rather than copying DDL or report bodies.
- Indexes contain IDs, status, keywords, versions and relative paths only. Search loads active hits first; it does not read the entire history.
- Nothing in this directory connects to a database or executes SQL. Persisting a draft requires explicit user confirmation.
