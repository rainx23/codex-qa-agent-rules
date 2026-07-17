#!/usr/bin/env python3
"""Validate SQL/REC artifact manifests and static SQL files without execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from qa_contracts import validate_reconciliation, validate_validation_sql
from validate_sql_style import find_config, validate_sql


def validate_artifact(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return [str(exc)]
    errors: list[str] = []
    sql_model = {"schema_version": data.get("schema_version", "1.0.0"), "sql_items": data.get("sql_items", data.get("validation_sql", []))}
    if sql_model.get("sql_items"):
        errors.extend(validate_validation_sql(sql_model))
    rec_model = {"schema_version": data.get("schema_version", "1.0.0"), "reconciliation_plans": data.get("reconciliation_plans", data.get("reconciliation_plan", []))}
    if rec_model.get("reconciliation_plans"):
        errors.extend(validate_reconciliation(rec_model))
    sql_items = sql_model.get("sql_items", [])
    known_risks = set(data.get("risk_ids", []))
    known_tcs = set(data.get("tc_ids", []))
    config = find_config(path.parent)
    root = config.parent.resolve() if config else path.parent.resolve()
    for item in sql_items:
        if not known_risks:
            errors.append("SQL Artifact 顶层 risk_ids 不能为空")
        elif not set(item.get("risk_ids", [])).issubset(known_risks):
            errors.append(f"{item.get('sql_id')} 引用未映射风险")
        if not known_tcs:
            errors.append("SQL Artifact 顶层 tc_ids 不能为空")
        elif not set(item.get("tc_ids", [])).issubset(known_tcs):
            errors.append(f"{item.get('sql_id')} 引用未映射 TC")
        sql_path = Path(str(item.get("sql_path", "")))
        if sql_path.is_absolute() or ".." in sql_path.parts:
            errors.append(f"{item.get('sql_id')} SQL 路径禁止绝对路径或 ..：{sql_path}")
            continue
        resolved = (root / sql_path).resolve()
        if resolved != root and root not in resolved.parents:
            errors.append(f"{item.get('sql_id')} SQL 路径越界：{sql_path}")
            continue
        if not sql_path.parts or sql_path.parts[0] not in {"tests", "testcases"} or not resolved.is_file():
            errors.append(f"{item.get('sql_id')} SQL 文件不存在：{sql_path}")
            continue
        style_errors, _ = validate_sql(resolved.read_text(encoding="utf-8-sig"), strict=True, config=config)
        errors.extend(f"{item.get('sql_id')}: {error}" for error in style_errors)
    sql_status = data.get("sql_status")
    if sql_status in {"executed", "passed", "failed"} and not data.get("execution_evidence"):
        errors.append("没有用户执行结果时，sql_status 不得标记 executed/passed/failed")
    if data.get("sql_count") is not None and data.get("sql_count") != len(sql_items):
        errors.append("sql_count 与 SQL ID 数量不一致")
    rec_items = rec_model.get("reconciliation_plans", [])
    if data.get("reconciliation_count") is not None and data.get("reconciliation_count") != len(rec_items):
        errors.append("reconciliation_count 与 REC ID 数量不一致")
    return list(dict.fromkeys(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验验证 SQL 与直接对数产物，不执行 SQL")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    errors = validate_artifact(args.manifest)
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
    else:
        print(f"PASS {args.manifest}: SQL artifact valid; SQL 未执行")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
