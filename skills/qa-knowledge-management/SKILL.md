---
name: qa-knowledge-management
description: Search, draft, compare, validate, and explicitly persist sanitized historical business knowledge, DDL, logic, metrics, data-validation decisions, and read-only SQL plans without database access.
---

# QA Knowledge Management

Resolve the repository root as two levels above this SKILL.md.

## Load rules

1. Read ../../rules/core/evidence-rules.md, ../../rules/core/analysis-report-contract.md, ../../rules/core/structured-model-contract.md, and ../../rules/core/sql-coding-standards.md.
2. Resolve `rules-repository.json`: integrated repositories use the business project's `qa-knowledge/`; standalone repositories use `qa-knowledge/examples/` for sanitized fixtures.
3. Load only indexes first. Read active hits and the smallest relevant current/history files; do not load the complete knowledge tree by default.

## Modes

- `search`: extract requirement, domain, entry, table, field, logic, metric and Diff identifiers; query indexes; return active/candidate/conflicting/superseded/deprecated/missing evidence with paths and applicability warnings.
- `draft`: parse complete pasted DDL or partial fields, calculate raw/normalized hashes, compare existing knowledge, and produce a review-only change draft. Do not write formal knowledge.
- `persist`: write only after explicit user confirmation. Preserve current/history separation, IDs, hashes, supersedes and index stability. Never persist inferred facts, credentials or a partial schema over a complete schema.
- `compare`: compare old/new DDL, logic, formulas, filters, joins, time, precision and exceptions; report added/removed/changed/unaffected behavior and regression scope.
- `validate`: run knowledge, schema, reference, hash, active-version, supersedes-cycle, index-drift and sensitive-information checks.

## Data validation and SQL

1. Set `data_validation_required` to `required`, `optional`, `not_required`, or `blocked` with a reason and missing information.
2. Use `sql` for indicator accuracy by default; use `cross_source_reconciliation` only with explicit baseline/target, fields, filters, time, tolerance and evidence; use `mixed` when both are needed.
3. Generate only read-only SQL. `SQLV###` and `REC###` are reusable references and may be shared by multiple TCs. XMind must reference IDs rather than embedding large SQL.
4. SQL can reach `generated` or `reviewed` after static checks. Without user execution results it cannot be `executed`, `passed`, or `failed`.

The Skill never connects to a database, executes SQL, stores credentials, or promotes historical knowledge above current user-confirmed requirements.
