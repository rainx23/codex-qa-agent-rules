---
name: qa-requirement-analysis
description: Analyze QA requirements from Zentao, OpenSpec, Markdown, screenshots, or pasted text; build evidence-backed facts, confirmation gates, risks, acceptance criteria, and regression scope. Use when the user asks for requirement analysis, a new requirement review, OpenSpec analysis, or needs a requirement baseline before Diff analysis.
---

# QA Requirement Analysis

Resolve the repository root as two levels above this SKILL.md.

## Load rules

1. Read ../../rules/core/evidence-rules.md completely.
2. Read ../../rules/core/confirmation-gate.md completely.
3. Read ../../rules/core/analysis-report-contract.md completely.
4. Read ../../rules/core/traceability-rules.md completely.
5. Read ../../rules/core/structured-model-contract.md completely.
6. For Zentao or an equivalent sectioned requirement, read ../../rules/profiles/zentao.md and use the third-part product rules as the default acceptance basis.
7. Read only the other ../../rules/profiles files matched by the requirement.
8. If final cases are requested, hand the structured result to ../qa-testcase-design/SKILL.md.

## Execute

1. Confirm that every requested source is readable and state the analysis scope.
2. For Zentao, distinguish the first-part business background from the third-part product implementation rules. Apply user-confirmed scope first; do not treat ordinary background-versus-plan differences as blocking conflicts.
3. Extract the business goal, system or page entry, actor, main flow, field rules, data definitions, acceptance criteria, exception behavior, and stated exclusions.
4. Build a fact table with confirmed, conflicting, inferred, and missing facts. Attach an allowed source label to every core conclusion.
5. Apply the confirmation gate. Ask only blocking questions; retain non-blocking and suggested questions in the report without stopping known work.
6. Build a Requirement Analysis Model that validates against ../../rules/schemas/requirement-analysis.schema.json. Derive the report and model from the same facts; verify criteria reference confirmed fact IDs and conflicts reference confirmation points.
7. For requirement-only input, output the pure-requirement contract: analysis scope, requirement understanding, rule decomposition, evidence, pending questions, risks, test-point summary, and regression scope. Do not require a suspected-defect section.
8. When Diff evidence exists, pass the Requirement Analysis Model to the Diff skill and switch the final report to the combined contract before designing cases.

Do not render XMind here. Do not promote templates, code behavior, or inference into requirement facts.
