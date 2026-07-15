#!/usr/bin/env python3
"""Validate fixed XMind Markdown with error/warning levels."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qa_validation import ValidationError, validate_markdown_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验统一 XMind Markdown")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--strict", action="store_true", help="warning 也导致非零退出码")
    args = parser.parse_args(argv)
    passed = warnings = failed = 0
    for path in args.files:
        try:
            outline = validate_markdown_file(path)
            for warning in outline.warnings:
                warnings += 1
                print(f"WARNING {warning}")
            if outline.warnings and args.strict:
                failed += 1
                print(f"FAIL {path}: strict 模式拒绝 {len(outline.warnings)} 个 warning", file=sys.stderr)
            else:
                passed += 1
                print(f"PASS {path}: structure valid; tc={len(outline.tc_nodes)}")
        except (OSError, ValidationError) as exc:
            failed += 1
            print(f"FAIL {path}: {exc}", file=sys.stderr)
    print(f"SUMMARY passed={passed} warning={warnings} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
