#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from qa_validation import ValidationError, validate_markdown_file

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验统一 XMind Markdown")
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    failed = 0
    for path in args.files:
        try:
            outline = validate_markdown_file(path)
            print(f"PASS {path}: {len(outline.tc_nodes)} TC")
        except (OSError, ValidationError) as exc:
            failed += 1
            print(f"FAIL {path}: {exc}", file=sys.stderr)
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())

