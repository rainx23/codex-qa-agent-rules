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
4. Read only matched ../../rules/profiles files.
5. Read requirement and Diff analysis artifacts before case design.

## Execute

1. Stop final XMind only when a blocking gate remains unresolved.
2. Build the risk coverage matrix before writing any TC.
3. Select equivalence, boundary, decision-table, state-transition, user-path, pairwise, or risk-driven techniques according to the facts.
4. Derive one case per independently diagnosable risk, then merge equivalent fields, modules, pages, dialogs, formal or simulated names, and data from the same equivalence class.
5. Verify every retained TC has a requirement, Diff, or historical-defect mapping and a distinct failure diagnosis.
6. Render only one of the two fixed XMind hierarchies and number TC globally from TC001.
7. Run ../../scripts/validate_xmind_md.py and ../../scripts/validate_testcase_quality.py. When a report exists, pass it as the traceability report.
8. Convert only after validation passes, then hand all artifacts to ../qa-artifact-validation/SKILL.md.

For changes to existing logic, focus on changed conditions, inverse paths, combinations, and boundaries. Do not pad the set with unchanged entry, button, or display smoke cases.

