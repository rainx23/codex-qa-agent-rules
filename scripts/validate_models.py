#!/usr/bin/env python3
"""Validate the actual structured models produced for one analysis run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from qa_contracts import (
    load_json, summarize_confirmations, validate_diff_model, validate_model_links,
    validate_requirement_model, validate_risk_matrix, validate_test_dimension_warnings,
    validate_testcase_model,
)
from validate_evidence import evidence_precision_warnings


def _evidence_root(path: Path) -> Path:
    parent = path.resolve().parent
    for candidate in (parent, *parent.parents):
        if (candidate / "RULE_VERSION").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    return parent


def load_models(
    requirement: Path | None,
    diff: Path | None,
    risk: Path,
    testcase: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any], dict[str, Any], Path]:
    """Load every model exactly once for the current validation run."""

    requirement_data = load_json(requirement) if requirement else None
    diff_data = load_json(diff) if diff else None
    risk_data = load_json(risk)
    testcase_data = load_json(testcase)
    evidence_root = _evidence_root(requirement or diff or risk)
    return requirement_data, diff_data, risk_data, testcase_data, evidence_root


def validate_loaded_models(
    requirement_data: dict[str, Any] | None,
    diff_data: dict[str, Any] | None,
    risk_data: dict[str, Any],
    testcase_data: dict[str, Any],
    *,
    evidence_root: Path,
) -> list[str]:
    """Validate already-loaded models without reading the same JSON files again."""

    errors: list[str] = []
    if requirement_data:
        errors.extend(
            f"requirement: {item}"
            for item in validate_requirement_model(requirement_data, evidence_root=evidence_root)
        )
    if diff_data:
        errors.extend(
            f"diff: {item}"
            for item in validate_diff_model(diff_data, evidence_root=evidence_root)
        )
    errors.extend(
        f"risk: {item}"
        for item in validate_risk_matrix(risk_data, evidence_root=evidence_root)
    )
    errors.extend(f"testcase: {item}" for item in validate_testcase_model(testcase_data))

    modes = {model.get("report_mode") for model in (requirement_data, diff_data) if model}
    expected_mode = "combined" if requirement_data and diff_data else "requirement" if requirement_data else "diff"
    if modes != {expected_mode}:
        errors.append(
            f"report_mode 必须为 {expected_mode}，实际为 {sorted(str(item) for item in modes)}"
        )

    inferred_status = None
    if requirement_data and summarize_confirmations(requirement_data)["blocking_pending_count"] > 0:
        inferred_status = "pending"
    errors.extend(
        validate_model_links(
            requirement_data,
            diff_data,
            risk_data,
            testcase_data,
            validation_status=inferred_status,
        )
    )
    return list(dict.fromkeys(errors))


def validate_loaded_warnings(
    requirement_data: dict[str, Any] | None,
    testcase_data: dict[str, Any],
    *,
    evidence_root: Path,
) -> list[str]:
    warnings: list[str] = []
    if requirement_data:
        warnings.extend(
            evidence_precision_warnings(requirement_data.get("facts", []), root=evidence_root)
        )
    warnings.extend(validate_test_dimension_warnings(requirement_data, testcase_data))
    return list(dict.fromkeys(warnings))


def validate_files(requirement: Path | None, diff: Path | None, risk: Path, testcase: Path) -> list[str]:
    """Compatibility wrapper for callers that only need validation errors."""

    try:
        requirement_data, diff_data, risk_data, testcase_data, evidence_root = load_models(
            requirement, diff, risk, testcase
        )
    except (OSError, ValueError) as exc:
        return [str(exc)]
    return validate_loaded_models(
        requirement_data,
        diff_data,
        risk_data,
        testcase_data,
        evidence_root=evidence_root,
    )


def validate_warnings(requirement: Path | None) -> list[str]:
    """Compatibility wrapper retained for existing direct callers."""

    if requirement is None:
        return []
    try:
        data = load_json(requirement)
    except (OSError, ValueError):
        return []
    return evidence_precision_warnings(data.get("facts", []), root=_evidence_root(requirement))


def main() -> int:
    parser = argparse.ArgumentParser(description="校验本次生成的 Requirement/Diff/Risk/Testcase 模型")
    parser.add_argument("--requirement", type=Path)
    parser.add_argument("--diff", type=Path)
    parser.add_argument("--risk", required=True, type=Path)
    parser.add_argument("--testcase", required=True, type=Path)
    parser.add_argument("--strict", action="store_true", help="将测试维度 warning 提升为失败")
    args = parser.parse_args()
    if not args.requirement and not args.diff:
        parser.error("--requirement 与 --diff 至少提供一个")

    try:
        requirement_data, diff_data, risk_data, testcase_data, evidence_root = load_models(
            args.requirement, args.diff, args.risk, args.testcase
        )
    except (OSError, ValueError) as exc:
        errors, warnings = [str(exc)], []
    else:
        errors = validate_loaded_models(
            requirement_data,
            diff_data,
            risk_data,
            testcase_data,
            evidence_root=evidence_root,
        )
        warnings = validate_loaded_warnings(
            requirement_data,
            testcase_data,
            evidence_root=evidence_root,
        )

    if args.strict:
        errors.extend(warnings)
        warnings = []
    for error in errors:
        print(f"FAIL {error}", file=sys.stderr)
    for warning in warnings:
        print(f"WARNING {warning}", file=sys.stderr)
    if not errors:
        print("PASS actual structured models are valid")
    print(f"SUMMARY passed={0 if errors else 1} warning={len(warnings)} failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
