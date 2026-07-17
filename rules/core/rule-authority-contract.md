# Rule Authority and Terminology Contract

`rules/core/canonical-rules.json` is the structured authority for shared
enumerations and fixed protocols. `scripts/qa_contracts.py` remains the
executable authority; `scripts/validate_rule_consistency.py` fails when the two
drift. The complete Zentao evidence order and conflict semantics have one
textual authority: `rules/profiles/zentao.md`.

## Canonical terms

Use these object names consistently: **Fact**, **Confirmation Point**,
**Evidence Reference**, **Requirement Model**, **Diff Model**, **Risk Coverage
Matrix**, **Testcase Model**, **Execution Instance**, and **Artifact Manifest**.
Chinese prose may explain them, but must not introduce a second structural
name. A natural-language `source_reference` is not an Evidence Reference.

## State responsibilities

Model validity is not formal delivery readiness.

- **Pending** means the structure can be valid while business confirmation,
  evidence, coverage, or execution remains unresolved. Pending may produce
  draft artifacts, but never a formal Workbook or a formal passed artifact.
- **Failed** means malformed Schema, damaged files, nonexistent references,
  unsafe paths, invalid hashes, or validator failure. Normal business
  uncertainty is Pending, not Failed.
- **Passed** means the structure is valid, core Confirmation Points are
  resolved, Risk coverage and required execution are closed, and every formal
  artifact gate passes. Schema validity alone is insufficient.

## XMind derivation

Formal XMind Markdown is derived from the Requirement Model, Diff Model, Risk
Coverage Matrix, and Testcase Model; it is not an independent inference path.
Each executable case retains TC, Risk and Fact or Change traceability, plus a
Branch ID when applicable. Multiple Branches remain separate execution paths.
Missing or conflicting core Facts appear as Confirmation Points and never as a
deterministic expected result. Existing user-facing Markdown hierarchy and
standard fenced code syntax remain unchanged; non-standard `id` attributes are
forbidden.

## Specialized authorities

- Evidence authenticity and `current/stale/reconfirm_required`:
  `rules/core/evidence-rules.md`.
- DDL token consumption and complete/partial scope:
  `rules/core/structured-model-contract.md`.
- SQL Identifier Evidence: `rules/core/sql-validation-contract.md`.
- API fixed parameter-health protocol: `rules/core/api-automation-contract.md`.
- Execution history and reruns: `rules/core/execution-instance-contract.md`.
- Schema migration: `rules/core/schema-migration-contract.md`.

Profiles and Skills may link to these authorities but must not weaken or
reorder their fixed rules.
