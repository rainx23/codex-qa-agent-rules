#!/usr/bin/env python3
"""Atomically update one initialized QA model with validated JSON Patch data."""

from __future__ import annotations

import argparse
import copy
import json
import tempfile
from pathlib import Path
from typing import Any

from qa_contracts import (
    read_rule_version,
    requirement_schema,
    risk_matrix_schema,
    testcase_schema,
    validate_schema_shape,
)


IMMUTABLE_FIELDS = {
    "schema_version",
    "rule_version",
    "generated_at",
    "generated_timezone",
    "model_id",
    "analysis_id",
    "matrix_id",
}
SCHEMA_FACTORIES = {
    "requirement": requirement_schema,
    "risk": risk_matrix_schema,
    "testcase": testcase_schema,
}


def _decode_pointer(pointer: str) -> list[str]:
    if not pointer.startswith("/") or pointer == "/":
        raise ValueError(f"JSON Pointer 必须指向模型内的具体字段：{pointer!r}")
    result: list[str] = []
    for token in pointer[1:].split("/"):
        if "~" in token:
            index = 0
            while index < len(token):
                if token[index] == "~" and (
                    index + 1 >= len(token) or token[index + 1] not in {"0", "1"}
                ):
                    raise ValueError(f"JSON Pointer 转义非法：{pointer}")
                index += 2 if token[index] == "~" else 1
        result.append(token.replace("~1", "/").replace("~0", "~"))
    return result


def _schema_for_tokens(schema: dict[str, Any], tokens: list[str], pointer: str) -> dict[str, Any]:
    current = schema
    for token in tokens:
        if current.get("type") == "array":
            if token != "-" and not token.isdigit():
                raise ValueError(f"数组路径必须使用索引或 '-'：{pointer}")
            current = current.get("items", {})
            continue
        properties = current.get("properties", {})
        if token not in properties:
            raise ValueError(f"不允许的模型字段：{pointer}")
        current = properties[token]
    return current


def _apply_operation(document: Any, operation: dict[str, Any], schema: dict[str, Any]) -> None:
    if not isinstance(operation, dict):
        raise ValueError("JSON Patch 每个操作必须是对象")
    op = operation.get("op")
    pointer = operation.get("path")
    if op not in {"add", "replace"}:
        raise ValueError("仅允许 add 和 replace；删除正式模型字段不属于本工具职责")
    if not isinstance(pointer, str):
        raise ValueError("JSON Patch path 必须是字符串")
    if "value" not in operation:
        raise ValueError(f"{op} 操作必须包含 value：{pointer}")
    tokens = _decode_pointer(pointer)
    if tokens[0] in IMMUTABLE_FIELDS:
        raise ValueError(f"禁止修改模型身份或生成元数据：{pointer}")
    if (
        len(tokens) >= 4
        and tokens[:2] == ["condition_matrix", "required_combinations"]
        and tokens[3] == "condition_coverage"
    ):
        raise ValueError("condition_coverage 只能写入 Testcase Model 的 cases[]")
    target_schema = _schema_for_tokens(schema, tokens, pointer)
    shape_errors = validate_schema_shape(operation["value"], target_schema, path=pointer)
    if shape_errors:
        raise ValueError("补丁值不符合 Schema：" + "；".join(shape_errors))

    parent = document
    for token in tokens[:-1]:
        if isinstance(parent, list):
            if not token.isdigit() or int(token) >= len(parent):
                raise ValueError(f"路径不存在：{pointer}")
            parent = parent[int(token)]
        elif isinstance(parent, dict) and token in parent:
            parent = parent[token]
        else:
            raise ValueError(f"路径不存在：{pointer}")
    final = tokens[-1]
    value = copy.deepcopy(operation["value"])
    if isinstance(parent, list):
        if final == "-":
            if op != "add":
                raise ValueError("replace 不支持 '-' 数组位置")
            parent.append(value)
        elif final.isdigit():
            index = int(final)
            if op == "add" and index <= len(parent):
                parent.insert(index, value)
            elif op == "replace" and index < len(parent):
                parent[index] = value
            else:
                raise ValueError(f"数组索引越界：{pointer}")
        else:
            raise ValueError(f"数组路径非法：{pointer}")
    elif isinstance(parent, dict):
        if op == "replace" and final not in parent:
            raise ValueError(f"replace 路径不存在：{pointer}")
        parent[final] = value
    else:
        raise ValueError(f"路径父节点不是容器：{pointer}")


def update_model(
    root: Path,
    model_path: Path,
    model_kind: str,
    patches: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply a patch batch in memory, validate it, then atomically replace the file."""

    if not isinstance(patches, list) or not patches:
        raise ValueError("JSON Patch 必须是非空数组")
    try:
        original = json.loads(model_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取模型 {model_path}：{exc}") from exc
    if not isinstance(original, dict):
        raise ValueError("模型根节点必须是对象")
    schema = SCHEMA_FACTORIES[model_kind](read_rule_version(root))
    updated = copy.deepcopy(original)
    for operation in patches:
        _apply_operation(updated, operation, schema)
    errors = validate_schema_shape(updated, schema)
    if errors:
        raise ValueError("更新后的模型不符合 Schema：" + "；".join(errors))

    model_path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, dir=model_path.parent, suffix=".model.tmp"
        ) as handle:
            json.dump(updated, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temporary = Path(handle.name)
        temporary.replace(model_path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="通过 stdin 或补丁文件原子更新已初始化 QA 模型；输入必须是 JSON Patch 数组"
    )
    parser.add_argument("--model", choices=tuple(SCHEMA_FACTORIES), required=True)
    parser.add_argument("--file", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--patch-file", type=Path)
    source.add_argument("--stdin", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        raw = (
            args.patch_file.read_text(encoding="utf-8")
            if args.patch_file
            else __import__("sys").stdin.read()
        )
        patches = json.loads(raw)
        update_model(root, args.file, args.model, patches)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        parser.exit(1, f"FAIL {exc}\nSUMMARY passed=0 warning=0 failed=1\n")
    print(f"PASS updated {args.file}")
    print("SUMMARY passed=1 warning=0 failed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
