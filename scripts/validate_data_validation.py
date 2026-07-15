#!/usr/bin/env python3
"""Validate data-validation decisions without executing SQL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qa_contracts import validate_data_validation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 Data Validation Model")
    parser.add_argument("model", type=Path)
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.model.read_text(encoding="utf-8-sig"))
        errors = validate_data_validation(data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
    else:
        print(f"PASS {args.model}: data validation model valid")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
