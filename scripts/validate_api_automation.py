#!/usr/bin/env python3
"""Validate the fixed parameter-health API automation model."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from qa_contracts import validate_api_automation

def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_pos", nargs="?", type=Path)
    parser.add_argument("--model", type=Path)
    args = parser.parse_args(argv)
    path = args.model or args.model_pos
    if path is None: parser.error("--model is required")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        errors = validate_api_automation(value)
    except (OSError, json.JSONDecodeError) as exc:
        errors = [f"API Model 无法读取：{exc}"]
    for error in errors: print(f"FAIL {error}", file=sys.stderr)
    print(f"CONTEXT model={path}")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0
if __name__ == "__main__": raise SystemExit(main())
