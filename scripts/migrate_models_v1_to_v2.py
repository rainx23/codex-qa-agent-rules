#!/usr/bin/env python3
"""Conservative v1 -> v2 model migration.

The migrator changes only the schema marker and copies source data. It never
promotes unknown values to confirmed facts; incomplete output is intentional
and must be re-confirmed by the v2 validators.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def migrate(value: object) -> object:
    if isinstance(value, dict):
        result = {key: migrate(item) for key, item in value.items()}
        if result.get("schema_version") == "1.0.0":
            result["schema_version"] = "2.0.0"
        return result
    if isinstance(value, list):
        return [migrate(item) for item in value]
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Conservatively migrate QA models from Schema v1 to v2")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.input.is_dir():
        parser.error(f"input directory does not exist: {args.input}")
    for source in args.input.rglob("*.json"):
        relative = source.relative_to(args.input)
        target = args.output / relative
        data = json.loads(source.read_text(encoding="utf-8-sig"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(migrate(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
