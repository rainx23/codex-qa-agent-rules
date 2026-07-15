---
name: qa-testcase-design
description: Design evidence-backed QA test points and a minimal effective XMind Markdown case set using risk coverage, equivalence classes, boundaries, decision tables, state transitions, deduplication, and fixed hierarchy. Use when the user asks for test points, test cases, P0 cases, XMind Markdown, or complete QA outputs.
---

# QA Testcase Design

Resolve the repository root as two levels above this SKILL.md.

## Load rules

1. Read ../../rules/core/testcase-quality-rules.md completely.
2. Read ../../rules/core/traceability-rules.md completely.
3. Read ../../rules/core/confirmation-gate.md completely.
4. Read ../../rules/core/structured-model-contract.md completely.
5. Read only matched ../../rules/profiles files.
6. Read the Requirement Analysis Model, optional Diff Impact Model, and optional historical defects before case design.

## Execute

1. Stop final XMind only when a blocking gate remains unresolved.
2. Build a Risk Coverage Matrix that validates against ../../rules/schemas/risk-coverage-matrix.schema.json before writing any TC. Do not jump directly from raw requirement text to cases.
3. Select equivalence, boundary, decision-table, state-transition, user-path, pairwise, or risk-driven techniques according to the facts.
4. Derive one case per independently diagnosable risk. Merge only when core rule, trigger, operation, data source/口径, assertion, risk and protected context are equivalent; keep formal/simulated sources, permissions, data types, exception paths and different P0 risks separate when they change diagnosis. If one rule covers multiple real entrances, keep one TC only when those dimensions are identical and render each entrance as an independent peer branch; split TCs when data source, permission, expected result, exception path, risk or failure localization differs.
5. Verify every retained TC has a requirement, Diff, or historical-defect mapping and a distinct failure diagnosis.
6. Build a Testcase Model that validates against ../../rules/schemas/testcase-model.schema.json, then render only one of the two fixed XMind hierarchies and number TC globally from TC001.
   - Single entrance: retain the existing `TC → 测试点 → 步骤 → 预期` or direct-module hierarchy without an artificial entry layer.
   - Grouped multi-entry: use `TC → 测试点 → 具体入口 → 步骤 → 预期`; direct multi-entry: use `TC → 一级模块 → 二级功能点 → 具体入口 → 步骤 → 预期`.
   - Require at least two named peer entrances, independent branch steps and expectations, no mixed direct steps, and no joined text such as “分别打开/依次进入多个入口”.
7. Run ../../scripts/validate_xmind_md.py and ../../scripts/validate_testcase_quality.py with the report, risk matrix and testcase model. Treat explicit duplicates as errors and review warnings without silently deleting cases.
8. Convert only after validation passes, then hand the models and rendered artifacts to ../qa-artifact-validation/SKILL.md.

For changes to existing logic, focus on changed conditions, inverse paths, combinations, and boundaries. Do not pad the set with unchanged entry, button, or display smoke cases.
