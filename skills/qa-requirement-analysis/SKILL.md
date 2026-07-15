---
name: qa-requirement-analysis
description: Analyze QA requirements from Zentao, OpenSpec, Markdown, screenshots, or pasted text; build evidence-backed facts, confirmation gates, risks, acceptance criteria, and regression scope. Use when the user asks for requirement analysis, a new requirement review, OpenSpec analysis, or needs a requirement baseline before Diff analysis.
---

# QA Requirement Analysis

Resolve the repository root as two levels above this SKILL.md.

## Load rules

1. Read ../../rules/core/evidence-rules.md completely.
2. Read ../../rules/core/confirmation-gate.md completely.
3. Read ../../rules/core/traceability-rules.md completely.
4. Read only the ../../rules/profiles files matched by the requirement.
5. If final cases are requested, hand the structured result to ../qa-testcase-design/SKILL.md.

## Execute

1. Confirm that every requested source is readable and state the analysis scope.
2. Extract the business goal, system or page entry, actor, main flow, field rules, data definitions, acceptance criteria, exception behavior, and stated exclusions.
3. Build a fact table with confirmed, conflicting, inferred, and missing facts. Attach an allowed source label to every core conclusion.
4. Apply the confirmation gate. Ask only blocking questions; retain non-blocking and suggested questions in the report without stopping known work.
5. Produce requirement understanding, rule decomposition, risks, test-point summary, acceptance baseline, and layered regression scope.
6. When Diff evidence exists, pass the acceptance baseline to the Diff skill before designing cases.

Do not render XMind here. Do not promote templates, code behavior, or inference into requirement facts.

