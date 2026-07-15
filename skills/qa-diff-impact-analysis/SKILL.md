---
name: qa-diff-impact-analysis
description: Analyze Git Diff, commits, ranges, branches, working-tree changes, public logic, call chains, interfaces, SQL, configurations, migrations, and test coverage for QA impact. Use when the user asks for commit analysis, Diff review, change impact, regression scope, or requirement-to-implementation coverage.
---

# QA Diff Impact Analysis

Resolve the repository root as two levels above this SKILL.md.

## Load rules

1. Read ../../rules/core/evidence-rules.md completely.
2. Read ../../rules/core/confirmation-gate.md completely.
3. Read ../../rules/core/analysis-report-contract.md completely.
4. Read ../../rules/core/traceability-rules.md completely.
5. Read ../../rules/core/structured-model-contract.md completely.
6. Read the matched ../../rules/profiles files.
7. Inherit the Requirement Analysis Model when one exists.

## Execute

1. Validate repository, branch, working tree, staged changes, commit objects, parents, and the exact comparison expression.
2. For one commit compare its first parent; for two commits or explicit old..new and old...new preserve the user expression. Explain merge parents, gray single-branch delivery, shallow-clone gaps, and empty Diff.
3. Obtain name-status, stat, and the relevant patches. Classify business versus non-business and public versus local changes.
4. Handle renames, deletions, binaries, lockfiles, generated files, formatting-only changes, migrations, backfills, feature flags, gray configuration, scheduled jobs, and message producers or consumers.
5. Analyze in this order: interface contract, SQL and data definition, permission and security, public logic, state transition, migration, configuration and gray release, page core logic, local display, documentation.
6. Search direct and indirect callers by symbol, route, SQL id, configuration key, message topic, and field. Check upstream and downstream compatibility and existing automated tests.
7. Build the change-to-business impact chain and a Diff Impact Model that validates against ../../rules/schemas/diff-impact.schema.json. When a Requirement Analysis Model exists, use its fact-backed acceptance criteria as the coverage baseline.
8. Without a requirement baseline, output the pure-Diff contract, including comparison range, changed files, core changes, suspected risks, an explicit suspected-defect conclusion, test points, and regression scope; do not require a trace matrix.
9. With a requirement model, switch to the combined contract and output requirement understanding, Diff understanding, the trace matrix, risks, and suspected defects with complete dual evidence.

Do not generate business cases for documentation, comments, log wording, formatting, lockfile-only, or semantic-free rename changes.
