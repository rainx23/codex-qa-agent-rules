#!/usr/bin/env python3
"""Validate versioned knowledge files, references, hashes, indexes and privacy boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from qa_contracts import (
    SENSITIVE_PATTERN, validate_data_validation, validate_knowledge_table, validate_logic_version,
    validate_metric, validate_requirement_knowledge,
)
from parse_chat_ddl import normalize_ddl
from build_knowledge_index import build_indexes


def _hash_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _json_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.json") if "indexes" not in path.parts and "schemas" not in path.parts)


def _classify(path: Path, data: dict[str, Any]) -> str | None:
    if path.name == "metadata.json" and "table_id" in data:
        return "table"
    if path.name == "current.json" and "logic_id" in data:
        return "logic"
    if path.name == "current.json" and "metric_id" in data:
        return "metric"
    if "requirement_id" in data and "related_tables" in data:
        return "requirement"
    if "data_validation_required" in data:
        return "data_validation"
    return None


def _check_cycles(logics: list[dict[str, Any]]) -> list[str]:
    graph = {item.get("logic_id"): item.get("supersedes") for item in logics if item.get("logic_id")}
    errors: list[str] = []
    for start in graph:
        seen: set[str] = set()
        current: str | None = start
        while current:
            if current in seen:
                errors.append(f"logic supersedes 形成循环：{start}")
                break
            seen.add(current)
            current = graph.get(current)
    return errors


def _index_entries(root: Path) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    indexes = root / "indexes"
    for path in sorted(indexes.glob("*.json")) if indexes.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            result[path.name] = []
            continue
        result[path.name] = data if isinstance(data, list) else data.get("entries", []) if isinstance(data, dict) else []
    return result


def validate_knowledge(root: Path) -> list[str]:
    errors: list[str] = []
    if not root.is_dir():
        return [f"知识根目录不存在：{root}"]
    all_text_files = [path for path in root.rglob("*") if path.is_file() and ".git" not in path.parts]
    for path in all_text_files:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            errors.append(f"知识文件不是 UTF-8：{path}")
            continue
        if SENSITIVE_PATTERN.search(text):
            errors.append(f"知识文件疑似包含凭据关键字：{path}")
    models: list[tuple[Path, str, dict[str, Any]]] = []
    for path in _json_files(root):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"JSON 无法读取：{path}: {exc}")
            continue
        if not isinstance(data, dict):
            continue
        kind = _classify(path, data)
        if kind:
            models.append((path, kind, data))
            validator = {"table": validate_knowledge_table, "logic": validate_logic_version, "metric": validate_metric, "requirement": validate_requirement_knowledge, "data_validation": validate_data_validation}[kind]
            errors.extend(f"{path}: {error}" for error in validator(data))
    active: dict[tuple[str, str], Path] = {}
    ids: dict[str, Path] = {}
    logics: list[dict[str, Any]] = []
    for path, kind, data in models:
        id_field = {"table": "table_id", "logic": "logic_id", "metric": "metric_id", "requirement": "requirement_id", "data_validation": None}[kind]
        if id_field:
            identifier = data.get(id_field)
            key = f"{kind}:{identifier}"
            if key in ids:
                errors.append(f"ID 重复：{identifier} ({ids[key]} 与 {path})")
            ids[key] = path
            if data.get("status") == "active_confirmed":
                active_key = (kind, str(identifier))
                if active_key in active:
                    errors.append(f"同一对象存在多个 active_confirmed 版本：{identifier}")
                active[active_key] = path
        if kind == "logic":
            logics.append(data)
        if kind == "table" and data.get("current_ddl_path"):
            ddl_path = (path.parent / str(data["current_ddl_path"])).resolve()
            if not ddl_path.is_file():
                errors.append(f"current.sql 不存在：{ddl_path}")
            else:
                ddl_text = ddl_path.read_text(encoding="utf-8-sig")
                raw_hash = "sha256:" + hashlib.sha256(ddl_text.strip().encode("utf-8")).hexdigest()
                normalized = normalize_ddl(ddl_text)
                normalized_hash = "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()
                if raw_hash != data.get("raw_hash"):
                    errors.append(f"DDL raw_hash 不一致：{path}")
                if normalized_hash != data.get("normalized_hash"):
                    errors.append(f"DDL normalized_hash 不一致：{path}")
    errors.extend(_check_cycles(logics))
    expected_indexes = build_indexes(root)
    actual_indexes = _index_entries(root)
    for index_name, expected_entries in expected_indexes.items():
        expected_text = json.dumps(expected_entries, ensure_ascii=False, indent=2) + "\n"
        index_path = root / "indexes" / index_name
        if not index_path.is_file() or index_path.read_text(encoding="utf-8-sig") != expected_text:
            errors.append(f"索引漂移：{index_name}")
    for index_name, entries in actual_indexes.items():
        for entry in entries:
            target = entry.get("path")
            if target and not (root / target).is_file():
                errors.append(f"索引 {index_name} 引用不存在路径：{target}")
    return list(dict.fromkeys(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验脱敏知识库，不连接数据库")
    parser.add_argument("root", type=Path)
    args = parser.parse_args(argv)
    errors = validate_knowledge(args.root)
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
    else:
        print(f"PASS {args.root}: knowledge valid")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
