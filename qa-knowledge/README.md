# QA Knowledge Boundary

`qa-knowledge/` is the project-local location for confirmed, reusable business knowledge. The public rules repository only ships `examples/` with sanitized facts.

- Complete DDL is stored once under `domains/<domain>/tables/<database>.<table>/current.sql`; structural changes move the previous file to `history/` and update `changelog.json`.
- Partial fields are current-scope facts only and never create or overwrite a complete table DDL.
- Logic, metric and requirement knowledge are versioned independently and reference tables/fields rather than copying DDL or report bodies.
- Indexes contain IDs, status, keywords, versions and relative paths only. Search loads active hits first; it does not read the entire history.
- Nothing in this directory connects to a database or executes SQL. Persisting a draft requires explicit user confirmation.
