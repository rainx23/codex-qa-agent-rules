#!/usr/bin/env python3
"""Validate semantic testcase quality and optional report traceability."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from qa_validation import ValidationError, validate_markdown_file


def validate_quality(path: Path, traceability_report: Path | None = None) -> list[str]:
    outline = validate_markdown_file(path)
    errors: list[str] = []
    if traceability_report is not None:
        report = traceability_report.read_text(encoding="utf-8-sig")
        for tc in outline.tc_nodes:
            if tc.title not in report:
                errors.append(f"{tc.title} 未映射到分析报告或追踪矩阵")
        if "风险" not in report or not re.search(r"需求|Diff|历史缺陷", report, re.IGNORECASE):
            errors.append("追踪报告缺少风险或证据映射")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验最小有效用例集质量")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--traceability-report", type=Path)
    args = parser.parse_args(argv)
    failed = 0
    for path in args.files:
        try:
            errors = validate_quality(path, args.traceability_report)
        except (OSError, ValidationError) as exc:
            errors = [str(exc)]
        if errors:
            failed += 1
            print(f"FAIL {path}: " + "；".join(errors), file=sys.stderr)
        else:
            print(f"PASS {path}: 层级、断言、重复和追踪检查通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

