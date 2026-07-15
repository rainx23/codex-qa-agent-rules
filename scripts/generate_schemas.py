#!/usr/bin/env python3
"""Generate JSON Schemas from the executable Python contract source."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qa_contracts import schema_documents


def render(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成或检查 QA JSON Schema")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    target = root / "rules/schemas"
    failed = 0
    for name, schema in schema_documents(root).items():
        path = target / name
        expected = render(schema)
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8-sig") != expected:
                failed += 1
                print(f"FAIL {path}: Schema 不是 qa_contracts.py 的最新生成结果", file=sys.stderr)
            else:
                print(f"PASS {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8")
            print(f"PASS {path}: generated")
    print(f"SUMMARY passed={len(schema_documents(root)) - failed} warning=0 failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
