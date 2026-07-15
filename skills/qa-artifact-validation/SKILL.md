---
name: qa-artifact-validation
description: Validate QA analysis reports, XMind Markdown, XMind workbooks, manifests, indexes, mirrored rule trees, and release readiness. Use when the user asks to validate, convert, publish, index, or perform final acceptance of QA rule or testcase artifacts.
---

# QA Artifact Validation

Resolve the repository root as two levels above this SKILL.md.

## Execute

1. Read ../../rules/core/analysis-report-contract.md, identify the explicit or automatic report mode, and run ../../scripts/validate_analysis_report.py with the corresponding `--mode` when needed. Validate mode-specific sections, evidence, suspected-defect proof, P0 mapping, and combined traceability.
2. Run ../../scripts/validate_schemas.py and validate the Requirement/Diff models, Risk Coverage Matrix, and Testcase Model before rendered artifacts.
3. Run ../../scripts/validate_xmind_md.py for roots, fixed hierarchy, dimensions, strict three-digit numbering, syntax, duplicate errors/warnings, assertions, and unknown-rule leakage.
4. Run ../../scripts/validate_traceability.py with the report, risk matrix, testcase model and XMind Markdown. Require every model and XMind TC to have an explicit row-level risk mapping.
5. Run ../../scripts/md_to_xmind.py and re-read content.json, metadata.json, and manifest.json to compare root, TC count, and total node count.
6. Run ../../scripts/validate_manifest.py to verify rule version, source hash, pending/P0 counts, safe paths, models, Workbook contents and supersedes relations.
7. Run ../../scripts/build_testcase_index.py only after Manifest validation, then verify the artifact id occurs exactly once and the validation status is not mixed with business status.
8. Run syntax, schema generation check, rule-version check, all tests, Skill validation, repository-mode validation and CI static checks.
9. Mark validation failed and stop completion claims whenever any required check fails.

Keep historical artifacts. Never repair or overwrite an existing artifact unless the operation is explicitly versioned or authorized.
