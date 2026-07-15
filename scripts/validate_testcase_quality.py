#!/usr/bin/env python3
"""Validate testcase quality and optional row-level traceability."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qa_validation import ValidationError, validate_markdown_file
from validate_traceability import validate_files


def validate_quality(
    path: Path,
    traceability_report: Path | None = None,
    mode: str = "auto",
    risk_matrix: Path | None = None,
    testcase_model: Path | None = None,
) -> tuple[list[str], list[str]]:
    outline = validate_markdown_file(path)
    errors: list[str] = []
    warnings = list(outline.warnings)
    if traceability_report is not None:
        trace_errors, trace_warnings = validate_files(
            traceability_report, path, mode, risk_matrix, testcase_model
        )
        errors.extend(trace_errors)
        warnings.extend(trace_warnings)
    return errors, list(dict.fromkeys(warnings))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验最小有效用例集质量")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--traceability-report", type=Path)
    parser.add_argument("--mode", choices=("auto", "requirement", "diff", "combined"), default="auto")
    parser.add_argument("--risk-matrix", type=Path)
    parser.add_argument("--testcase-model", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    passed = warnings_count = failed = 0
    for path in args.files:
        try:
            errors, warnings = validate_quality(
                path, args.traceability_report, args.mode, args.risk_matrix, args.testcase_model
            )
        except (OSError, ValueError, ValidationError) as exc:
            errors, warnings = [str(exc)], []
        for warning in warnings:
            warnings_count += 1
            print(f"WARNING {warning}")
        if args.strict and warnings:
            errors.append("strict 模式拒绝 warning")
        if errors:
            failed += 1
            for error in errors:
                print(f"FAIL {path}: {error}", file=sys.stderr)
        else:
            passed += 1
            print(f"PASS {path}: testcase quality valid")
    print(f"SUMMARY passed={passed} warning={warnings_count} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
