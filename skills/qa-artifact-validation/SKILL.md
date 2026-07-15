---
name: qa-artifact-validation
description: Validate QA analysis reports, XMind Markdown, XMind workbooks, manifests, indexes, mirrored rule trees, and release readiness. Use when the user asks to validate, convert, publish, index, or perform final acceptance of QA rule or testcase artifacts.
---

# QA Artifact Validation

Resolve the repository root as two levels above this SKILL.md.

## Execute

1. Read ../../rules/core/analysis-report-contract.md, identify the explicit or automatic report mode, and run ../../scripts/validate_analysis_report.py with the corresponding `--mode` when needed. Validate mode-specific sections, evidence, suspected-defect proof, P0 mapping, and combined traceability.
2. Run ../../scripts/validate_xmind_md.py for roots, fixed hierarchy, dimensions, numbering, syntax, structure, duplicate semantics, assertions, and unknown-rule leakage.
3. Run ../../scripts/validate_testcase_quality.py with the analysis report when available to verify TC traceability.
4. Run ../../scripts/md_to_xmind.py and re-read content.json, metadata.json, and manifest.json to compare root, TC count, and total node count.
5. Run ../../scripts/validate_manifest.py to validate fields, enums, counts, artifact paths, Workbook contents, and version relations.
6. Run ../../scripts/build_testcase_index.py only after Manifest validation, then verify the artifact id occurs exactly once.
7. Run Python syntax checks, all unit tests, Skill quick validation, reference checks, and root-template hash comparison.
8. Mark validation failed and stop completion claims whenever any required check fails.

Keep historical artifacts. Never repair or overwrite an existing artifact unless the operation is explicitly versioned or authorized.
