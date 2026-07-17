#!/usr/bin/env python3
"""Parse pasted DDL without connecting to or executing any database."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


CREATE_RE = re.compile(r"(?is)\bcreate\s+table\b")
TABLE_NAME_RE = re.compile(r"(?is)\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?(?P<name>(?:`[^`]+`|\"[^\"]+\"|[\w.]+))")
FIELD_RE = re.compile(r"^\s*(?P<name>`[^`]+`|\"[^\"]+\"|[A-Za-z_][\w$]*)\s+(?P<type>[A-Za-z][\w]*(?:\s*\([^)]*\))?(?:\s+[A-Za-z]+)?)", re.I)
SENSITIVE_RE = re.compile(r"(?i)(?:password|passwd|token|jdbc|private[_ -]?key|secret)\s*[:=]")


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_ddl(text: str) -> str:
    """Normalize formatting only; do not rewrite names, types or dialect syntax."""

    without_comments = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    without_comments = re.sub(r"--[^\n]*", " ", without_comments)
    compact = re.sub(r"\s+", " ", without_comments).strip()
    return re.sub(r"\s*([(),])\s*", r"\1", compact)


def split_create_tables(text: str) -> list[str]:
    statements: list[str] = []
    matches = list(CREATE_RE.finditer(text))
    for index, match in enumerate(matches):
        start = match.start()
        end_limit = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        candidate = text[start:end_limit]
        depth = 0
        quote: str | None = None
        end = len(candidate)
        for position, char in enumerate(candidate):
            if quote:
                if char == quote and (position == 0 or candidate[position - 1] != "\\"):
                    quote = None
                continue
            if char in "'\"`":
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth = max(depth - 1, 0)
                if depth == 0:
                    tail = candidate[position + 1:]
                    semicolon = tail.find(";")
                    end = position + 1 + semicolon + 1 if semicolon >= 0 else position + 1
                    break
        statement = candidate[:end].strip()
        if statement:
            statements.append(statement)
    return statements


def _split_top_level(body: str) -> list[str]:
    items: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    for position, char in enumerate(body):
        if quote:
            if char == quote and (position == 0 or body[position - 1] != "\\"):
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            items.append(body[start:position].strip())
            start = position + 1
    items.append(body[start:].strip())
    return [item for item in items if item]


def detect_dialect(ddl: str) -> str:
    lowered = ddl.lower()
    if "engine=" in lowered or "distributed by" in lowered or "duplicate key" in lowered:
        return "doris/starrocks"
    if "stored as" in lowered or "row format" in lowered:
        return "hive"
    return "mysql-compatible"


def parse_statement(statement: str, index: int = 1) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    name_match = TABLE_NAME_RE.search(statement)
    if not name_match:
        return None, [f"第 {index} 条 CREATE TABLE 无法稳定识别表名"]
    full_name = name_match.group("name").replace("`", "").replace('"', "")
    parts = full_name.split(".")
    database = parts[-2] if len(parts) > 1 else ""
    table_name = parts[-1]
    open_paren = statement.find("(", name_match.end())
    if open_paren < 0:
        return None, [f"表 {full_name} 缺少字段定义括号；仅保留原文，不虚构字段"]
    depth = 0
    close_paren = -1
    quote: str | None = None
    for position in range(open_paren, len(statement)):
        char = statement[position]
        if quote:
            if char == quote and statement[position - 1] != "\\":
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                close_paren = position
                break
    if close_paren < 0:
        return None, [f"表 {full_name} 字段定义无法闭合；仅保留原文，不虚构字段"]
    body = statement[open_paren + 1:close_paren]
    fields: list[dict[str, Any]] = []
    keys: list[str] = []
    partitions: list[str] = []
    indexes: list[str] = []
    for item in _split_top_level(body):
        stripped = item.strip()
        upper = stripped.upper()
        if upper.startswith(("UNIQUE INDEX", "INDEX ", "KEY ")):
            indexes.append(stripped)
            continue
        if upper.startswith(("PRIMARY KEY", "UNIQUE KEY", "CONSTRAINT")):
            keys.append(stripped)
            continue
        match = FIELD_RE.match(stripped)
        if not match:
            warnings.append(f"表 {full_name} 无法稳定解析片段：{stripped[:80]}")
            continue
        name = match.group("name").strip("`\"")
        type_name = match.group("type").strip()
        default_match = re.search(r"(?is)\bdefault\s+([^\s,]+)", stripped)
        comment_match = re.search(r"(?is)\bcomment\s+'((?:''|[^'])*)'", stripped)
        nullable_known = bool(re.search(r"(?i)\b(?:not\s+null|null)\b", stripped))
        default_value = default_match.group(1) if default_match else None
        default_state = "known_null" if default_value and default_value.casefold() == "null" else "known_value" if default_match else "unknown"
        evidence_fields = ["name", "type"] + (["nullable"] if nullable_known else []) + (["default"] if default_match else []) + (["comment"] if comment_match else [])
        unknown_fields = [field for field in ("nullable", "default", "comment") if field not in evidence_fields]
        fields.append({
            "name": name,
            "type": type_name,
            "nullable": (not bool(re.search(r"(?i)\bnot\s+null\b", stripped))) if nullable_known else None,
            "default": default_value,
            "default_state": default_state,
            "comment": comment_match.group(1).replace("''", "'") if comment_match else None,
            "ordinal": len(fields) + 1,
            "evidence_fields": evidence_fields,
            "unknown_fields": unknown_fields,
        })
    tail = statement[close_paren + 1:]
    partition_match = re.search(r"(?is)\bpartition\s+by\s+(.+?)(?=\border\s+by\b|\bdistributed\s+by\b|\bproperties\b|$)", tail)
    if partition_match:
        partitions.append(re.sub(r"\s+", " ", partition_match.group(1)).strip())
    for match in re.finditer(r"(?is)\b(?:order\s+by|distributed\s+by)\s+(.+?)(?=\bproperties\b|$)", tail):
        indexes.append(re.sub(r"\s+", " ", match.group(0)).strip())
    for match in re.finditer(r"(?is)\b(?:duplicate|aggregate|unique)\s+key\s*\([^)]*\)", tail):
        keys.append(re.sub(r"\s+", " ", match.group(0)).strip())
    engine_match = re.search(r"(?is)\bengine\s*=\s*([\w]+)", tail)
    properties_match = re.search(r"(?is)\bproperties\s*\((.*?)\)", tail)
    engine_properties: dict[str, str] = {}
    if engine_match:
        engine_properties["engine"] = engine_match.group(1)
    if properties_match:
        for key, value in re.findall(r"['\"]?([\w-]+)['\"]?\s*=\s*['\"]?([^,'\"]+)['\"]?", properties_match.group(1)):
            engine_properties[key] = value.strip()
    raw = statement.strip()
    structure_checks = (
        (r"(?i)\bprimary\s+key\b", "主键", bool(keys)),
        (r"(?i)\bunique\s+key\b", "唯一键", any("UNIQUE KEY" in item.upper() for item in keys)),
        (r"(?i)\bduplicate\s+key\b", "Duplicate Key", any("DUPLICATE KEY" in item.upper() for item in keys)),
        (r"(?i)\baggregate\s+key\b", "Aggregate Key", any("AGGREGATE KEY" in item.upper() for item in keys)),
        (r"(?i)\bpartition\s+by\b", "分区", bool(partitions)),
        (r"(?i)\bdistributed\s+by\b", "分桶", any("DISTRIBUTED BY" in item.upper() for item in indexes)),
        (r"(?i)\b(?:unique\s+)?index\s+\w+", "索引", bool(indexes)),
        (r"(?i)\bengine\s*=", "Engine", "engine" in engine_properties),
        (r"(?i)\bproperties\s*\(", "Properties", bool(properties_match) and len(engine_properties) > int("engine" in engine_properties)),
    )
    for pattern, label, parsed in structure_checks:
        if re.search(pattern, raw) and not parsed:
            warnings.append(f"表 {full_name} 包含 {label}，但未能稳定提取")
    normalized = normalize_ddl(raw)
    model = {
        "table_id": full_name.replace(".", "_"), "domain": "unknown", "database": database,
        "table_name": table_name, "full_name": full_name, "dialect": detect_dialect(raw),
        "schema_scope": "complete" if fields and not warnings else "partial" if fields else "blocked", "current_ddl_path": None,
        "raw_ddl": raw, "normalized_ddl": normalized, "raw_hash": _sha256(raw), "normalized_hash": _sha256(normalized),
        "fields": fields, "keys": keys, "partitions": partitions, "indexes": indexes, "engine_properties": engine_properties,
        "status": "candidate", "source_type": "chat_ddl", "source_requirement_ids": [], "last_verified_at": None,
        "parse_warnings": warnings, "applicability_scope": None,
    }
    return model, warnings


def parse_ddl(text: str) -> dict[str, Any]:
    input_raw_hash = _sha256(text)
    input_normalized_hash = _sha256(normalize_ddl(text))
    if SENSITIVE_RE.search(text):
        return {"tables": [], "warnings": ["输入疑似包含敏感凭据标识，已拒绝解析并且不会保存原文"], "sensitive": True, "input_raw_hash": input_raw_hash, "input_normalized_hash": input_normalized_hash}
    statements = split_create_tables(text)
    if not statements:
        return {"tables": [], "warnings": ["未识别到 CREATE TABLE；未生成表结构事实"], "sensitive": False, "input_raw_hash": input_raw_hash, "input_normalized_hash": input_normalized_hash}
    tables: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, statement in enumerate(statements, 1):
        model, item_warnings = parse_statement(statement, index)
        warnings.extend(item_warnings)
        if model is not None:
            tables.append(model)
    return {"tables": tables, "warnings": warnings, "sensitive": False, "input_raw_hash": input_raw_hash, "input_normalized_hash": input_normalized_hash}


def parse_partial_fields(text: str, full_name: str, domain: str = "unknown") -> dict[str, Any]:
    """Convert explicitly supplied fields into a partial, non-persisted table model."""

    parts = full_name.split(".")
    database = parts[-2] if len(parts) > 1 else ""
    table_name = parts[-1]
    fields: list[dict[str, Any]] = []
    for line in text.splitlines():
        match = FIELD_RE.match(line.strip().rstrip(",;"))
        if not match:
            continue
        fields.append({"name": match.group("name").strip("`\""), "type": match.group("type").strip(), "nullable": None, "default": None, "default_state": "unknown", "comment": None, "ordinal": len(fields) + 1, "evidence_fields": ["name", "type"], "unknown_fields": ["nullable", "default", "comment"]})
    item_warnings = [] if fields else ["未识别到明确字段；未补齐整表结构"]
    return {"tables": [{"table_id": full_name.replace(".", "_"), "domain": domain, "database": database, "table_name": table_name, "full_name": full_name, "dialect": "unspecified", "schema_scope": "partial" if fields else "blocked", "current_ddl_path": None, "raw_hash": _sha256(text), "normalized_hash": _sha256(normalize_ddl(text)), "fields": fields, "keys": [], "partitions": [], "indexes": [], "engine_properties": {}, "status": "candidate", "source_type": "chat_partial_fields", "source_requirement_ids": [], "last_verified_at": None, "parse_warnings": item_warnings, "applicability_scope": f"仅限用户明确提供的 {len(fields)} 个字段" if fields else None}], "warnings": item_warnings, "sensitive": bool(SENSITIVE_RE.search(text)), "input_raw_hash": _sha256(text), "input_normalized_hash": _sha256(normalize_ddl(text))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="解析粘贴的 CREATE TABLE DDL；只解析，不连接或执行数据库")
    parser.add_argument("input", nargs="?", help="DDL 文本文件；省略时读取 stdin")
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--table", help="仅提供少量字段时指定 database.table")
    parser.add_argument("--domain", default="unknown")
    args = parser.parse_args(argv)
    text = Path(args.input).read_text(encoding="utf-8-sig") if args.input else sys.stdin.read()
    result = parse_ddl(text)
    if not result["tables"] and args.table and not result.get("sensitive"):
        result = parse_partial_fields(text, args.table, args.domain)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 1 if result.get("sensitive") else 0


if __name__ == "__main__":
    raise SystemExit(main())
