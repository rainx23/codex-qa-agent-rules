# Schema Migration Contract

Schema migration supports only `1.0.0 -> 2.0.0`. It is a typed structural
conversion, never a recursive version-marker replacement.

## Detection and dispatch

The root must be an object. Explicit `model_type`, `artifact_type`, or `kind`
takes priority and must agree with stable structural signatures. Unknown,
ambiguous, and conflicting inputs fail. Requirement, Diff, Risk, Testcase,
Manifest, Validation SQL, API Model, API Artifact, Execution, and Knowledge
Table use separate migrators.

## Truth preservation

Every change is classified as `copied`, `renamed`, `transformed`, `defaulted`,
`unknown`, `reconfirm_required`, `dropped`, or `error`. Missing proof never
becomes confirmed, resolved, accepted, current, or passed. Unknown legacy
fields and dropped values remain in the report with their JSON path and value.
Core uncertainty makes the result pending; strict mode rejects it.

## Safety and repeatability

The default requires a distinct output path. In-place migration is explicit.
Output is UTF-8 with a trailing newline and stable list order. A validated
temporary file is atomically replaced; errors remove staged targets. Dry-run
does not write a model and reports `destination_written=false`. Migrating a
valid 2.0.0 model produces identical bytes, `status=unchanged`, and no changes.

## Reports and Bundle order

Reports contain source/destination SHA-256 hashes, per-field changes, unknown,
reconfirm and dropped entries, validation results, warnings, errors and final
status. Bundle order is Requirement, Diff, Risk, Testcase, SQL/API, API
Artifact, Execution, Knowledge, then Manifest. Manifest never inherits a legacy
passed status without revalidation of dependencies, paths and hashes.
