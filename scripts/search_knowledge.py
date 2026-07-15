#!/usr/bin/env python3
"""Search lightweight knowledge indexes; active versions are returned by default."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def search(root: Path, keyword: str = "", kind: str = "", include_history: bool = False) -> list[dict[str, Any]]:
    index_dir = root / "indexes"
    results: list[dict[str, Any]] = []
    for path in sorted(index_dir.glob("*.json")) if index_dir.is_dir() else []:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for item in data if isinstance(data, list) else data.get("entries", []):
            if kind and item.get("kind") != kind and path.stem != f"by-{kind}":
                continue
            if not include_history and item.get("status") not in {None, "active_confirmed"}:
                continue
            haystack = " ".join(str(value) for value in item.values()).casefold()
            if keyword and keyword.casefold() not in haystack:
                continue
            results.append(item)
    unique: dict[tuple[str, str], dict[str, Any]] = {(str(item.get("id")), str(item.get("path"))): item for item in results}
    return sorted(unique.values(), key=lambda item: (str(item.get("kind")), str(item.get("id")), str(item.get("path"))))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按表、字段、逻辑、指标、需求、域或关键词检索知识索引")
    parser.add_argument("root", type=Path)
    parser.add_argument("--table")
    parser.add_argument("--field")
    parser.add_argument("--logic")
    parser.add_argument("--metric")
    parser.add_argument("--requirement")
    parser.add_argument("--domain")
    parser.add_argument("--keyword")
    parser.add_argument("--include-history", action="store_true")
    args = parser.parse_args(argv)
    pairs = [("table", args.table), ("field", args.field), ("logic", args.logic), ("metric", args.metric), ("requirement", args.requirement), ("domain", args.domain), ("", args.keyword)]
    kind, keyword = next(((kind, value) for kind, value in pairs if value), ("", ""))
    result = search(args.root, keyword, kind, args.include_history)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
