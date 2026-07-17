#!/usr/bin/env python3
"""Validate the actual structured models produced for one analysis run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qa_contracts import (
    load_json, validate_diff_model, validate_model_links, validate_requirement_model,
    validate_risk_matrix, validate_testcase_model,
)


def validate_files(requirement: Path | None, diff: Path | None, risk: Path, testcase: Path) -> list[str]:
    errors: list[str] = []
    try:
        requirement_data = load_json(requirement) if requirement else None
        diff_data = load_json(diff) if diff else None
        risk_data = load_json(risk)
        testcase_data = load_json(testcase)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    if requirement_data:
        errors.extend(f"requirement: {item}" for item in validate_requirement_model(requirement_data))
    if diff_data:
        errors.extend(f"diff: {item}" for item in validate_diff_model(diff_data))
    errors.extend(f"risk: {item}" for item in validate_risk_matrix(risk_data))
    errors.extend(f"testcase: {item}" for item in validate_testcase_model(testcase_data))
    modes = {model.get("report_mode") for model in (requirement_data, diff_data) if model}
    expected_mode = "combined" if requirement_data and diff_data else "requirement" if requirement_data else "diff"
    if modes != {expected_mode}:
        errors.append(f"report_mode 必须为 {expected_mode}，实际为 {sorted(str(item) for item in modes)}")
    errors.extend(validate_model_links(requirement_data, diff_data, risk_data, testcase_data))
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="校验本次生成的 Requirement/Diff/Risk/Testcase 模型")
    parser.add_argument("--requirement", type=Path)
    parser.add_argument("--diff", type=Path)
    parser.add_argument("--risk", required=True, type=Path)
    parser.add_argument("--testcase", required=True, type=Path)
    args = parser.parse_args()
    if not args.requirement and not args.diff:
        parser.error("--requirement 与 --diff 至少提供一个")
    errors = validate_files(args.requirement, args.diff, args.risk, args.testcase)
    for error in errors:
        print(f"FAIL {error}", file=sys.stderr)
    if not errors:
        print("PASS actual structured models are valid")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
