#!/usr/bin/env python3
"""Compare DDL structure and emit a reviewable diff; never overwrites knowledge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from parse_chat_ddl import normalize_ddl, parse_ddl


def _load_one(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if "tables" in data:
            return (data.get("tables") or [{}])[0]
        return data
    parsed = parse_ddl(path.read_text(encoding="utf-8-sig"))
    return (parsed.get("tables") or [{}])[0]


def compare_tables(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_fields = {field.get("name"): field for field in old.get("fields", [])}
    new_fields = {field.get("name"): field for field in new.get("fields", [])}
    added = sorted(set(new_fields) - set(old_fields))
    removed = sorted(set(old_fields) - set(new_fields))
    type_changed = sorted(name for name in set(old_fields) & set(new_fields) if old_fields[name].get("type") != new_fields[name].get("type"))
    nullable_changed = sorted(name for name in set(old_fields) & set(new_fields) if old_fields[name].get("nullable") != new_fields[name].get("nullable"))
    default_changed = sorted(name for name in set(old_fields) & set(new_fields) if old_fields[name].get("default") != new_fields[name].get("default"))
    comment_changed = sorted(name for name in set(old_fields) & set(new_fields) if old_fields[name].get("comment") != new_fields[name].get("comment"))
    structural = bool(added or removed or type_changed or nullable_changed or default_changed or comment_changed or old.get("keys") != new.get("keys") or old.get("partitions") != new.get("partitions") or old.get("indexes") != new.get("indexes") or old.get("engine_properties") != new.get("engine_properties"))
    old_normalized = normalize_ddl(old.get("raw_ddl", old.get("normalized_ddl", "")))
    new_normalized = normalize_ddl(new.get("raw_ddl", new.get("normalized_ddl", "")))
    return {
        "full_name": new.get("full_name") or old.get("full_name"),
        "same_normalized_ddl": old.get("normalized_hash") == new.get("normalized_hash") or old_normalized == new_normalized,
        "format_only": not structural and old.get("raw_hash") != new.get("raw_hash"),
        "structural_change": structural,
        "added_fields": added,
        "removed_fields": removed,
        "type_changed_fields": type_changed,
        "nullable_changed_fields": nullable_changed,
        "default_changed_fields": default_changed,
        "comment_changed_fields": comment_changed,
        "keys_changed": old.get("keys") != new.get("keys"),
        "partitions_changed": old.get("partitions") != new.get("partitions"),
        "indexes_changed": old.get("indexes") != new.get("indexes"),
        "engine_properties_changed": old.get("engine_properties") != new.get("engine_properties"),
    }


def compare_documents(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Compare logic/metric JSON with the same review shape used for DDL."""

    keys = sorted(set(old) | set(new))
    changed = [key for key in keys if key in old and key in new and old[key] != new[key]]
    return {
        "document_id": new.get("logic_id") or new.get("metric_id") or new.get("requirement_id"),
        "same_normalized_ddl": old == new,
        "format_only": False,
        "structural_change": bool(changed or set(old) != set(new)),
        "changed_items": changed,
        "added_items": sorted(set(new) - set(old)),
        "removed_items": sorted(set(old) - set(new)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="比较两份 DDL；只输出差异，不自动覆盖知识文件")
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    old = _load_one(args.old)
    new = _load_one(args.new)
    result = compare_tables(old, new) if "fields" in old or "fields" in new else compare_documents(old, new)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
