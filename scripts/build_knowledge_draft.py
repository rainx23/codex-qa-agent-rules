#!/usr/bin/env python3
"""Create a reviewable knowledge change draft; never persist it automatically."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from compare_ddl import _load_one, compare_tables


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成知识变更草稿，不写入正式知识库")
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    old = _load_one(args.old)
    new = _load_one(args.new)
    diff = compare_tables(old, new)
    result = {"action": "review_required", "old": {"full_name": old.get("full_name"), "normalized_hash": old.get("normalized_hash")}, "new": {"full_name": new.get("full_name"), "normalized_hash": new.get("normalized_hash")}, "change": diff, "persisted": False, "confirmation_required": True}
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
