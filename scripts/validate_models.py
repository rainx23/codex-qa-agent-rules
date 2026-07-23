#!/usr/bin/env python3
"""Validate one run's structured models and emit machine-locatable failures."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from qa_contracts import (
    load_json,
    summarize_confirmations,
    validate_diff_model,
    validate_model_links,
    validate_requirement_model,
    validate_risk_matrix,
    validate_test_dimension_warnings,
    validate_testcase_model,
)
from validate_evidence import evidence_precision_warnings


CODE_PREFIX = re.compile(r"^([A-Z][A-Z0-9_]+):\s*(.*)$")
PATH_PREFIX = re.compile(r"^(\$(?:\.[A-Za-z0-9_]+|\[\d+\])*)\s+(.*)$")


def _evidence_root(path: Path) -> Path:
    parent = path.resolve().parent
    for candidate in (parent, *parent.parents):
        if (candidate / "RULE_VERSION").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    return parent


def _pointer(path: str) -> str:
    if path == "$":
        return "/"
    tokens = re.findall(r"\.([A-Za-z0-9_]+)|\[(\d+)\]", path[1:])
    return "/" + "/".join(name or index for name, index in tokens)


def _issue(
    model: str,
    file: Path | str,
    pointer: str,
    code: str,
    message: str,
    **context: str,
) -> str:
    fields = [
        f"model={model}",
        f"file={Path(file).name if isinstance(file, Path) else file}",
        f"json_pointer={pointer}",
        f"error_code={code}",
        f"message={message}",
    ]
    fields.extend(f"{name}={value}" for name, value in context.items())
    return " | ".join(fields)


def _model_issues(model: str, path: Path, raw_errors: list[str]) -> list[str]:
    result: list[str] = []
    for raw in raw_errors:
        pointer = "/"
        message = raw
        match = PATH_PREFIX.match(raw)
        if match:
            pointer = _pointer(match.group(1))
            message = match.group(2)
        code = f"{model.upper()}_MODEL_INVALID"
        unknown = re.search(r"包含未定义字段[：:]\s*(.+)$", message)
        if unknown:
            code = "SCHEMA_UNKNOWN_PROPERTY"
            field = unknown.group(1).strip()
            pointer = pointer.rstrip("/") + "/" + field.replace("~", "~0").replace("/", "~1")
        elif "缺少字段" in message:
            code = "SCHEMA_REQUIRED_PROPERTY_MISSING"
        result.append(_issue(model, path, pointer, code, message))
    return result


def _combination_index(requirement: dict[str, Any] | None, combination_id: str) -> int | None:
    combinations = ((requirement or {}).get("condition_matrix") or {}).get(
        "required_combinations", []
    )
    return next(
        (
            index
            for index, item in enumerate(combinations)
            if isinstance(item, dict) and item.get("combination_id") == combination_id
        ),
        None,
    )


def _coverage_pointer(testcase: dict[str, Any], combination_id: str) -> str:
    for case_index, case in enumerate(testcase.get("cases", [])):
        for coverage_index, coverage in enumerate(case.get("condition_coverage", [])):
            if isinstance(coverage, dict) and coverage.get("combination_id") == combination_id:
                return f"/cases/{case_index}/condition_coverage/{coverage_index}/combination_id"
    return "/cases/*/condition_coverage"


def _link_issue(
    raw: str,
    requirement_path: Path | None,
    testcase_path: Path,
    requirement: dict[str, Any] | None,
    testcase: dict[str, Any],
) -> str:
    match = CODE_PREFIX.match(raw)
    code, message = (match.group(1), match.group(2)) if match else ("MODEL_LINK_INVALID", raw)
    combination_match = re.search(r"\b(?:COMB|COMBO|CM)-[A-Za-z0-9_-]+\b", raw)
    combination_id = combination_match.group(0) if combination_match else ""
    index = _combination_index(requirement, combination_id) if combination_id else None
    requirement_pointer = (
        f"/condition_matrix/required_combinations/{index}" if index is not None else ""
    )
    context = {"combination_id": combination_id} if combination_id else {}

    if code == "CONDITION_COVERAGE_UNKNOWN_COMBINATION":
        return _issue(
            "testcase", testcase_path, _coverage_pointer(testcase, combination_id),
            code, message, **context,
        )
    if code in {
        "REQUIRED_COMBINATION_UNCOVERED",
        "CONFIG_EXISTENCE_IS_NOT_BEHAVIOR_COVERAGE",
        "REQUIRED_COMBINATION_FORWARD_COVERAGE_MISSING",
    }:
        if requirement_pointer:
            context["requirement_pointer"] = requirement_pointer
        return _issue(
            "testcase", testcase_path, "/cases/*/condition_coverage",
            code, message, **context,
        )
    if code in {
        "CONDITION_COVERAGE_DUPLICATED",
        "CONDITION_COVERAGE_BRANCH_MISMATCH",
        "CONDITION_COVERAGE_SCOPE_MISMATCH",
        "CONDITION_COVERAGE_STEP_REFERENCE_INVALID",
        "CONDITION_COVERAGE_ASSERTION_MAPPING_REQUIRED",
        "CONDITION_COVERAGE_ASSERTION_MAPPING_DUPLICATED",
        "CONDITION_COVERAGE_ASSERTION_MAPPING_INCOMPLETE",
        "CONDITION_COVERAGE_MAPPING_CONFLICT",
        "CONDITION_COVERAGE_NOT_INDEPENDENT",
    }:
        return _issue(
            "testcase", testcase_path, _coverage_pointer(testcase, combination_id),
            code, message, **context,
        )
    if code in {
        "CONDITION_COVERAGE_REVERSE_INDEX_MISSING",
        "REQUIRED_COMBINATION_UNKNOWN_TESTCASE",
        "REQUIRED_COMBINATION_TC_DUPLICATED",
    } and requirement_path:
        suffix = "/covered_by_tc_ids" if requirement_pointer else ""
        return _issue(
            "requirement", requirement_path, requirement_pointer + suffix or "/condition_matrix",
            code, message, **context,
        )
    return _issue(
        "cross_model",
        f"{requirement_path.name if requirement_path else '-'},"
        f"{testcase_path.name}",
        "/",
        code,
        message,
        **context,
    )


def validate_files(
    requirement: Path | None,
    diff: Path | None,
    risk: Path,
    testcase: Path,
) -> list[str]:
    try:
        requirement_data = load_json(requirement) if requirement else None
        diff_data = load_json(diff) if diff else None
        risk_data = load_json(risk)
        testcase_data = load_json(testcase)
    except (OSError, ValueError) as exc:
        return [_issue("input", "unknown", "/", "MODEL_FILE_READ_ERROR", str(exc))]

    errors: list[str] = []
    evidence_root = _evidence_root(requirement or diff or risk)
    if requirement_data:
        errors.extend(_model_issues(
            "requirement", requirement,
            validate_requirement_model(requirement_data, evidence_root=evidence_root),
        ))
    if diff_data:
        errors.extend(_model_issues(
            "diff", diff, validate_diff_model(diff_data, evidence_root=evidence_root)
        ))
    errors.extend(_model_issues(
        "risk", risk, validate_risk_matrix(risk_data, evidence_root=evidence_root)
    ))
    errors.extend(_model_issues(
        "testcase", testcase, validate_testcase_model(testcase_data)
    ))
    modes = {model.get("report_mode") for model in (requirement_data, diff_data) if model}
    expected_mode = (
        "combined" if requirement_data and diff_data
        else "requirement" if requirement_data else "diff"
    )
    if modes != {expected_mode}:
        errors.append(_issue(
            "cross_model", f"{requirement.name if requirement else '-'},"
            f"{diff.name if diff else '-'}", "/report_mode", "REPORT_MODE_MISMATCH",
            f"report_mode 必须为 {expected_mode}，实际为 {sorted(str(item) for item in modes)}",
        ))
    inferred_status = None
    if requirement_data and summarize_confirmations(requirement_data)["blocking_pending_count"] > 0:
        inferred_status = "pending"
    for raw in validate_model_links(
        requirement_data, diff_data, risk_data, testcase_data,
        validation_status=inferred_status,
    ):
        errors.append(_link_issue(
            raw, requirement, testcase, requirement_data, testcase_data
        ))
    return list(dict.fromkeys(errors))


def validate_warnings(requirement: Path | None) -> list[str]:
    if requirement is None:
        return []
    try:
        data = load_json(requirement)
    except (OSError, ValueError):
        return []
    return evidence_precision_warnings(data.get("facts", []), root=_evidence_root(requirement))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="校验本次生成的 Requirement/Diff/Risk/Testcase 模型"
    )
    parser.add_argument("--requirement", type=Path)
    parser.add_argument("--diff", type=Path)
    parser.add_argument("--risk", required=True, type=Path)
    parser.add_argument("--testcase", required=True, type=Path)
    parser.add_argument("--strict", action="store_true", help="将测试维度 warning 提升为失败")
    args = parser.parse_args()
    if not args.requirement and not args.diff:
        parser.error("--requirement 与 --diff 至少提供一个")
    errors = validate_files(args.requirement, args.diff, args.risk, args.testcase)
    warnings = validate_warnings(args.requirement)
    requirement_data = load_json(args.requirement) if args.requirement else None
    testcase_data = load_json(args.testcase)
    warnings.extend(validate_test_dimension_warnings(requirement_data, testcase_data))
    if args.strict:
        errors.extend(
            _issue("requirement", args.requirement or "-", "/", "STRICT_WARNING", warning)
            for warning in warnings
        )
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
