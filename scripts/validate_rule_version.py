#!/usr/bin/env python3
"""Validate the single rule version across generated contracts and examples."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from qa_contracts import read_rule_version, schema_documents


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors: list[str] = []
    try:
        version = read_rule_version(root)
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    example = json.loads((root / "testcases/manifest.example.json").read_text(encoding="utf-8-sig"))
    if example.get("rule_version") != version:
        errors.append(f"Manifest 示例 rule_version={example.get('rule_version')} 与 RULE_VERSION={version} 不一致")
    for name, schema in schema_documents(root).items():
        if schema.get("x-rule-version") != version:
            errors.append(f"{name} 规则版本不一致")
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
    else:
        print(f"PASS RULE_VERSION={version}")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
