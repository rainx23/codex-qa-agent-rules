#!/usr/bin/env python3
"""Validate row-level requirement, Diff, risk, and testcase mappings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qa_contracts import load_json, validate_risk_matrix, validate_testcase_model
from qa_validation import ValidationError, validate_markdown_file, validate_traceability_mapping
from validate_analysis_report import detect_mode


def validate_files(
    report: Path,
    xmind_md: Path,
    mode: str = "auto",
    risk_matrix_path: Path | None = None,
    testcase_model_path: Path | None = None,
) -> tuple[list[str], list[str]]:
    report_text = report.read_text(encoding="utf-8-sig")
    resolved_mode = detect_mode(report_text, mode)
    outline = validate_markdown_file(xmind_md)
    risk_matrix = load_json(risk_matrix_path) if risk_matrix_path else None
    testcase_model = load_json(testcase_model_path) if testcase_model_path else None
    errors: list[str] = []
    if risk_matrix is not None:
        errors.extend(validate_risk_matrix(risk_matrix))
    if testcase_model is not None:
        errors.extend(validate_testcase_model(testcase_model))
    mapping_errors, warnings, _ = validate_traceability_mapping(
        report_text, resolved_mode, outline, risk_matrix, testcase_model
    )
    errors.extend(mapping_errors)
    return list(dict.fromkeys(errors)), warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验结构化行级追踪关系")
    parser.add_argument("report", type=Path)
    parser.add_argument("xmind_md", type=Path)
    parser.add_argument("--mode", choices=("auto", "requirement", "diff", "combined"), default="auto")
    parser.add_argument("--risk-matrix", type=Path)
    parser.add_argument("--testcase-model", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        errors, warnings = validate_files(
            args.report, args.xmind_md, args.mode, args.risk_matrix, args.testcase_model
        )
    except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        errors, warnings = [str(exc)], []
    for warning in warnings:
        print(f"WARNING {warning}")
    if warnings and args.strict:
        errors.append("strict 模式拒绝 warning")
    for error in errors:
        print(f"FAIL {args.report}: {error}", file=sys.stderr)
    if not errors:
        print(f"PASS {args.report}: row-level traceability valid")
    print(f"SUMMARY passed={0 if errors else 1} warning={len(warnings)} failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
