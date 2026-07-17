#!/usr/bin/env python3
"""Validate SQL/REC artifact manifests and static SQL files without execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from qa_contracts import build_model_id_index, validate_reconciliation, validate_validation_sql
from sql_identifier_extractor import extract_sql_identifiers
from validate_sql_style import find_config, validate_sql


def _load_ids(path: Path | None, key: str) -> set[str]:
    if not path or not path.is_file():
        return set()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    items = data.get("risk_items" if key == "risk_id" else "cases", [])
    return {item.get(key) for item in items if isinstance(item, dict) and item.get(key)}


IDENTIFIER_SOURCES = {
    "table": {"knowledge_table", "complete_ddl", "formal_document"},
    "column": {"knowledge_table_field", "complete_ddl", "formal_document", "change"},
    "function": {"builtin_sql", "formal_document", "code_context"},
    "enum_value": {"fact", "formal_document", "code_context", "user_confirmation"},
    "parameter": {"fact", "formal_document", "user_confirmation"},
    "join_key": {"fact", "knowledge_table_field", "complete_ddl", "formal_document"},
    "filter_value": {"fact", "formal_document", "code_context", "user_confirmation"},
}
BUILTINS = {"sum", "count", "max", "min", "avg", "coalesce", "if", "date_format", "substr", "split", "unnest", "row_number"}


def build_knowledge_identifier_index(models: list[dict[str, Any]]) -> dict[str, Any]:
    tables: dict[str, Any] = {}
    by_id: dict[str, Any] = {}
    for model in models:
        candidates = model.get("tables", [model] if model.get("full_name") else [])
        for table in candidates:
            if not isinstance(table, dict) or not table.get("full_name"):
                continue
            fields = {str(field.get("name")): field for field in table.get("fields", []) if isinstance(field, dict) and field.get("name")}
            value = {**table, "fields_by_name": fields}
            tables[str(table["full_name"]).casefold()] = value
            by_id[str(table.get("table_id", ""))] = value
    return {"tables": tables, "table_ids": by_id}


def validate_sql_artifact(
    artifact: dict[str, Any], *, requirement_model: dict[str, Any] | None,
    knowledge_models: list[dict[str, Any]], diff_model: dict[str, Any] | None = None,
    risk_model: dict[str, Any] | None = None, testcase_model: dict[str, Any] | None = None,
    strict: bool = True, sql_texts: dict[str, str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if strict and requirement_model is None:
        errors.append("strict SQL validation requires Requirement model")
    if strict and not knowledge_models:
        errors.append("strict SQL validation requires Knowledge models")
    index = build_model_id_index(requirement_model=requirement_model, diff_model=diff_model, risk_model=risk_model, testcase_model=testcase_model)
    knowledge = build_knowledge_identifier_index(knowledge_models)
    facts = {item.get("fact_id"): item for item in (requirement_model or {}).get("facts", [])}
    changes = {item.get("change_id"): item for item in (diff_model or {}).get("change_items", [])}
    items = artifact.get("sql_items", artifact.get("validation_sql", []))
    for item in items if isinstance(items, list) else []:
        sql_id = item.get("sql_id")
        if strict and item.get("risk_ids") and risk_model is None:
            errors.append(f"{sql_id} references Risk but Risk model is missing")
        if strict and item.get("tc_ids") and testcase_model is None:
            errors.append(f"{sql_id} references Testcase but Testcase model is missing")
        if set(item.get("risk_ids", [])) - index["risk_ids"]:
            errors.append(f"{sql_id} references unknown Risk ID")
        if set(item.get("tc_ids", [])) - index["testcase_ids"]:
            errors.append(f"{sql_id} references unknown Testcase ID")
        declared: set[tuple[str, str]] = set()
        for evidence in item.get("identifier_evidence", []):
            identifier = str(evidence.get("identifier", ""))
            kind = evidence.get("identifier_type")
            for field in ("identifier", "identifier_type", "qualified_identifier", "scope_table", "usage_type", "source_reference_type", "source_reference_id", "evidence_references", "evidence_state"):
                if field not in evidence:
                    errors.append(f"{sql_id} identifier {identifier} missing {field}")
            if kind not in IDENTIFIER_SOURCES:
                errors.append(f"{sql_id} identifier {identifier} has invalid identifier_type")
                continue
            source_type = evidence.get("source_reference_type")
            source_id = evidence.get("source_reference_id")
            if source_type not in IDENTIFIER_SOURCES[kind]:
                errors.append(f"{sql_id} identifier {identifier} source {source_type} is not allowed for {kind}")
            if not evidence.get("evidence_references"):
                errors.append(f"{sql_id} identifier {identifier} evidence_references must not be empty")
            if evidence.get("evidence_state") != "confirmed" and strict:
                errors.append(f"{sql_id} identifier {identifier} is not confirmed")
            scope = str(evidence.get("scope_table") or "").casefold()
            qualified = str(evidence.get("qualified_identifier") or "")
            if kind in {"column", "join_key"} and not scope:
                errors.append(f"{sql_id} identifier {identifier} requires scope_table")
            table = knowledge["tables"].get(scope)
            if source_type == "knowledge_table":
                table = knowledge["table_ids"].get(str(source_id))
                if not table or str(table.get("full_name", "")).casefold() != qualified.casefold():
                    errors.append(f"{sql_id} table {qualified} does not match Knowledge {source_id}")
                elif strict and table.get("schema_scope") != "complete":
                    errors.append(f"{sql_id} table {qualified} requires complete Knowledge")
            if source_type in {"knowledge_table_field", "complete_ddl"} and kind in {"column", "join_key"}:
                field = table.get("fields_by_name", {}).get(identifier) if table else None
                expected_id = f"{table.get('table_id')}#{identifier}" if table else ""
                if not table or not field or source_id != expected_id or qualified.casefold() != f"{scope}.{identifier}".casefold():
                    errors.append(f"{sql_id} column {identifier} does not exist in scope table {evidence.get('scope_table')}")
                elif source_type == "complete_ddl" and (table.get("schema_scope") != "complete" or table.get("unparsed_tail") is not None or table.get("parse_warnings") or field.get("unparsed_fragment") is not None):
                    errors.append(f"{sql_id} column {identifier} lacks complete DDL field evidence")
            if source_type == "fact":
                fact = facts.get(source_id)
                current = fact and any(ref.get("evidence_status") == "current" for ref in fact.get("evidence_references", []) if isinstance(ref, dict))
                if not fact or fact.get("category") != "confirmed" or not current:
                    errors.append(f"{sql_id} identifier {identifier} references invalid Fact {source_id}")
                if kind == "column":
                    errors.append(f"{sql_id} Fact cannot prove physical column {identifier}")
            if source_type == "change" and source_id not in changes:
                errors.append(f"{sql_id} identifier {identifier} references invalid Change {source_id}")
            if source_type == "builtin_sql" and identifier.casefold() not in BUILTINS:
                errors.append(f"{sql_id} unknown builtin SQL function {identifier}")
            declared.add((kind, qualified.casefold()))
        sql_text = (sql_texts or {}).get(str(sql_id))
        if sql_text:
            extracted = extract_sql_identifiers(sql_text, dialect=str(item.get("dialect", "")))
            used = {("table", value.casefold()) for value in extracted["physical_tables"]}
            used |= {("column", value.casefold()) for value in extracted["columns"]}
            used |= {("function", value.casefold()) for value in extracted["functions"]}
            used |= {("parameter", value.casefold()) for value in extracted["parameters"]}
            used |= {("enum_value", value["qualified_identifier"].casefold()) for value in extracted["filter_values"]}
            if extracted["has_star"] and strict:
                errors.append(f"{sql_id} SELECT * is forbidden in strict mode")
            for value in sorted(used - declared):
                errors.append(f"{sql_id} unproven_identifier: {value[0]} {value[1]}")
            for value in sorted(declared - used):
                if value[0] in {"table", "column", "function", "parameter"}:
                    errors.append(f"{sql_id} unused_identifier_evidence: {value[0]} {value[1]}")
    return list(dict.fromkeys(errors))


def validate_artifact(path: Path, risk_matrix: Path | None = None, testcase_model: Path | None = None, knowledge_root: Path | None = None, *, requirement: Path | None = None, diff: Path | None = None, strict: bool = True) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return [str(exc)]
    errors: list[str] = []
    sql_model = {"schema_version": data.get("schema_version", "2.0.0"), "sql_items": data.get("sql_items", data.get("validation_sql", []))}
    if sql_model.get("sql_items"):
        risk_ids = _load_ids(risk_matrix, "risk_id") if risk_matrix else None
        tc_ids = _load_ids(testcase_model, "tc_id") if testcase_model else None
        facts: set[str] | None = None
        confirmed: set[str] | None = None
        if risk_matrix:
            requirement = risk_matrix.parent / "requirement-analysis.json"
            if requirement.is_file():
                requirement_data = json.loads(requirement.read_text(encoding="utf-8-sig"))
                facts = {item.get("fact_id") for item in requirement_data.get("facts", [])}
                confirmed = {item.get("fact_id") for item in requirement_data.get("facts", []) if item.get("category") == "confirmed"}
        tables: dict[str, dict[str, Any]] = {}
        if knowledge_root and knowledge_root.is_dir():
            for candidate in knowledge_root.rglob("*.json"):
                try:
                    value = json.loads(candidate.read_text(encoding="utf-8-sig"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(value, dict):
                    continue
                for table in value.get("tables", [value] if value.get("full_name") else []):
                    if isinstance(table, dict) and table.get("full_name"):
                        tables[table["full_name"]] = table
        errors.extend(validate_validation_sql(sql_model, risk_ids=risk_ids, tc_ids=tc_ids, fact_ids=facts, confirmed_fact_ids=confirmed, knowledge_tables=tables) if risk_matrix or testcase_model or knowledge_root else validate_validation_sql(sql_model))
        def read_model(model_path: Path | None) -> dict[str, Any] | None:
            return json.loads(model_path.read_text(encoding="utf-8-sig")) if model_path and model_path.is_file() else None
        knowledge_models = list(tables.values())
        sql_texts: dict[str, str] = {}
        config_for_paths = find_config(path.parent)
        root_for_paths = config_for_paths.parent.resolve() if config_for_paths else path.parent.resolve()
        for sql_item in sql_model["sql_items"]:
            candidate = (root_for_paths / str(sql_item.get("sql_path", ""))).resolve()
            if candidate.is_file():
                sql_texts[str(sql_item.get("sql_id"))] = candidate.read_text(encoding="utf-8-sig")
        errors.extend(validate_sql_artifact(data, requirement_model=read_model(requirement), knowledge_models=knowledge_models,
            diff_model=read_model(diff), risk_model=read_model(risk_matrix), testcase_model=read_model(testcase_model), strict=strict, sql_texts=sql_texts))
    rec_model = {"schema_version": data.get("schema_version", "2.0.0"), "reconciliation_plans": data.get("reconciliation_plans", data.get("reconciliation_plan", []))}
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
    parser.add_argument("manifest", nargs="?", type=Path)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--requirement", type=Path)
    parser.add_argument("--diff", type=Path)
    parser.add_argument("--risk", "--risk-matrix", dest="risk_matrix", type=Path)
    parser.add_argument("--testcase", "--testcase-model", dest="testcase_model", type=Path)
    parser.add_argument("--knowledge", "--knowledge-root", dest="knowledge_root", type=Path)
    parser.add_argument("--draft", action="store_true")
    args = parser.parse_args(argv)
    artifact = args.artifact or args.manifest
    if artifact is None:
        parser.error("--artifact is required")
    if not args.draft and (args.requirement is None or args.knowledge_root is None):
        parser.error("strict mode requires --requirement and --knowledge")
    model_count = sum(path is not None for path in (args.requirement, args.diff, args.risk_matrix, args.testcase_model))
    knowledge_count = sum(1 for path in args.knowledge_root.rglob("*.json")) if args.knowledge_root and args.knowledge_root.is_dir() else 0
    print(f"CONTEXT models={model_count} knowledge_json={knowledge_count}")
    errors = validate_artifact(artifact, args.risk_matrix, args.testcase_model, args.knowledge_root, requirement=args.requirement, diff=args.diff, strict=not args.draft)
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
    else:
        print(f"PASS {artifact}: SQL artifact valid; SQL 未执行; mode={'draft/pending' if args.draft else 'strict'}")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
