#!/usr/bin/env python3
"""Build deterministic lightweight knowledge indexes without copying full documents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _entries(root: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.json")):
        if "indexes" in path.parts or "schemas" in path.parts or path.name == "changelog.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        id_field = next((field for field in ("table_id", "logic_id", "metric_id", "requirement_id") if field in data), None)
        if not id_field:
            continue
        identifier = str(data[id_field])
        keywords = {identifier, str(data.get("domain", "")), str(data.get("name", "")), str(data.get("metric_name", "")), str(data.get("table_name", "")), str(data.get("full_name", ""))}
        keywords.update(str(item) for item in data.get("source_requirement_ids", []))
        keywords = sorted(item for item in keywords if item)
        result.append({"id": identifier, "kind": id_field.removesuffix("_id"), "keywords": keywords, "status": data.get("status"), "version": data.get("version", data.get("effective_version")), "path": path.relative_to(root).as_posix()})
    return sorted(result, key=lambda item: (item["kind"], item["id"], item["path"]))


def build_indexes(root: Path) -> dict[str, list[dict[str, Any]]]:
    entries = _entries(root)
    by_kind = {
        "by-table.json": [item for item in entries if item["kind"] == "table"],
        "by-field.json": [], "by-logic.json": [item for item in entries if item["kind"] == "logic"],
        "by-metric.json": [item for item in entries if item["kind"] == "metric"],
        "by-requirement.json": [item for item in entries if item["kind"] == "requirement"],
        "by-domain.json": sorted(entries, key=lambda item: (next((key for key in item["keywords"] if key), ""), item["id"])),
    }
    fields: list[dict[str, Any]] = []
    for item in by_kind["by-table.json"]:
        metadata = root / item["path"]
        try:
            data = json.loads(metadata.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        for field in data.get("fields", []):
            fields.append({"id": field.get("name"), "table_id": data.get("table_id"), "status": data.get("status"), "path": item["path"]})
    by_kind["by-field.json"] = sorted(fields, key=lambda item: (str(item.get("id")), str(item.get("table_id"))))
    return by_kind


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建稳定排序的知识索引，不复制 DDL 正文")
    parser.add_argument("root", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    expected = build_indexes(args.root)
    index_dir = args.root / "indexes"
    failed = 0
    for name, data in expected.items():
        path = index_dir / name
        rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8-sig") != rendered:
                print(f"FAIL {path}: index drift")
                failed += 1
            else:
                print(f"PASS {path}")
        else:
            index_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered, encoding="utf-8")
            print(f"PASS {path}: generated")
    print(f"SUMMARY passed={len(expected) - failed} warning=0 failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
