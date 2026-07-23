#!/usr/bin/env python3
"""Print a compact, deterministic view of one executable QA model contract."""

from __future__ import annotations

import argparse
import json
from typing import Any

from qa_contracts import (
    manifest_schema,
    read_rule_version,
    requirement_schema,
    risk_matrix_schema,
    testcase_schema,
)


def _sample_string(schema: dict[str, Any]) -> str:
    pattern = schema.get("pattern", "")
    if pattern == r"^TC\d{3}$":
        return "TC001"
    if "sha256:" in pattern:
        return "sha256:" + "0" * 64
    if r"\d{4}-\d{2}-\d{2}" in pattern:
        return "2026-01-01 00:00:00"
    if "适用入口" in pattern:
        return "适用入口（示例范围全部TC均需逐项执行）"
    if "STEP" in pattern:
        return "STEP001"
    if "COMMIT" in pattern.upper() or "[0-9a-fA-F]" in pattern:
        return "a" * 40
    return "value"


def minimal_schema_value(schema: dict[str, Any]) -> Any:
    if "const" in schema:
        return schema["const"]
    if schema.get("enum"):
        return schema["enum"][0]
    kinds = schema.get("type")
    if isinstance(kinds, list):
        kinds = next((kind for kind in kinds if kind != "null"), "null")
    if kinds == "object" or "properties" in schema:
        properties = schema.get("properties", {})
        return {
            field: minimal_schema_value(properties[field])
            for field in schema.get("required", [])
        }
    if kinds == "array":
        count = schema.get("minItems", 0)
        return [minimal_schema_value(schema.get("items", {})) for _ in range(count)]
    if kinds == "integer":
        return schema.get("minimum", 0)
    if kinds == "boolean":
        return False
    if kinds == "null":
        return None
    return _sample_string(schema)


def _enum_paths(schema: dict[str, Any], prefix: str = "$", depth: int = 0) -> list[str]:
    if depth > 4:
        return []
    result: list[str] = []
    if schema.get("enum"):
        result.append(f"{prefix}: {json.dumps(schema['enum'], ensure_ascii=False)}")
    for name, child in schema.get("properties", {}).items():
        result.extend(_enum_paths(child, f"{prefix}.{name}", depth + 1))
    if isinstance(schema.get("items"), dict):
        result.extend(_enum_paths(schema["items"], f"{prefix}[]", depth + 1))
    return result


def _nested_levels(schema: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for name, child in schema.get("properties", {}).items():
        if child.get("type") == "array" and isinstance(child.get("items"), dict):
            item = child["items"]
            fields = item.get("required", [])
            result.append(f"$.{name}[] -> {', '.join(fields)}")
        elif child.get("type") == "object":
            result.append(f"$.{name} -> {', '.join(child.get('required', []))}")
    return result


def describe(kind: str) -> dict[str, Any]:
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    version = read_rule_version(root)
    schemas = {
        "requirement": requirement_schema(version),
        "risk": risk_matrix_schema(version),
        "testcase": testcase_schema(version),
        "manifest": manifest_schema(version),
    }
    schema = schemas[kind]
    required = schema.get("required", [])
    optional = [
        name for name in schema.get("properties", {})
        if name not in required
    ]
    constraints: list[str] = []
    if kind in {"requirement", "testcase"}:
        constraints.append("condition_matrix: required combinations 只能由 behavior condition_coverage 满足")
    if kind == "testcase":
        constraints.extend([
            "shared_entry_scope 与 shared_entry_scopes 不能同时使用",
            "shared_entry_scopes[].scope_id 唯一；每个 TC 只能引用一个存在的 Scope",
            "applies_to_tc_ids 与 TC.shared_entry_scope_id 必须双向一致；每个 Scope 至少 6 个叶子入口",
        ])
    return {
        "model": kind,
        "required_fields": required,
        "key_optional_fields": optional,
        "enum_values": _enum_paths(schema),
        "main_nesting": _nested_levels(schema),
        "cross_field_constraints": constraints,
        "minimal_schema_legal_example": minimal_schema_value(schema),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="输出精简 QA 模型契约")
    parser.add_argument("model", choices=("requirement", "risk", "testcase", "manifest"))
    args = parser.parse_args(argv)
    print(json.dumps(describe(args.model), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
