#!/usr/bin/env python3
"""Single executable source for QA model and manifest contracts."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "1.0.0"
REPORT_MODES = ("requirement", "diff", "combined")
FACT_CATEGORIES = ("confirmed", "conflicting", "inferred", "missing")
SOURCE_TYPES = (
    "user_confirmation", "requirement", "zentao_section_3", "zentao_background",
    "openspec", "markdown", "screenshot", "diff", "code_context",
    "api_document", "sql_definition", "historical_defect", "inference",
)
COVERAGE_STATUSES = ("已覆盖", "疑似遗漏", "实现不一致", "需求外变更", "无法判断")
TEST_PRIORITIES = ("P0", "P1", "P2")
EVIDENCE_STATES = ("已确认", "疑似", "待确认")
REGRESSION_SCOPES = ("核心回归", "关联回归", "冒烟回归")
BUSINESS_IMPACTS = ("critical", "high", "medium", "low")
VALIDATION_STATUSES = ("passed", "failed", "pending")
RELATIONS = ("新增", "补充", "替代", "废弃")
PENDING_SEVERITIES = ("blocking", "nonblocking", "suggested")
PENDING_STATUSES = ("pending", "skipped", "resolved")
DIMENSIONS = (
    "功能测试", "数据测试", "异常测试", "权限测试",
    "导出测试", "兼容性测试", "回归测试", "SQL验证",
)
TC_PATTERN = r"^TC\d{3}$"
SEMVER_PATTERN = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"
GENERATED_AT_FORMAT = "%Y-%m-%d %H:%M:%S"
ALLOWED_TIMEZONES = ("Asia/Shanghai", "UTC")
ZERO_HASH = "sha256:" + "0" * 64


def read_rule_version(root: Path) -> str:
    version = (root / "RULE_VERSION").read_text(encoding="utf-8-sig").strip()
    if not re.fullmatch(SEMVER_PATTERN, version):
        raise ValueError(f"RULE_VERSION 不是语义版本：{version}")
    return version


def _object(required: list[str], properties: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
        **extra,
    }


def _string(min_length: int = 1, **extra: Any) -> dict[str, Any]:
    return {"type": "string", "minLength": min_length, **extra}


def _strings(min_items: int = 0) -> dict[str, Any]:
    return {"type": "array", "items": _string(), "minItems": min_items, "uniqueItems": True}


def _base_schema(title: str, version: str, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$comment": "Generated from scripts/qa_contracts.py; do not edit manually.",
        "x-rule-version": version,
        "title": title,
        **body,
    }


def validate_schema_shape(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Validate the JSON Schema subset emitted by this module using only stdlib."""

    errors: list[str] = []
    expected_type = schema.get("type")
    allowed_types = expected_type if isinstance(expected_type, list) else [expected_type] if expected_type else []
    type_checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if allowed_types and not any(type_checks[kind](value) for kind in allowed_types):
        return [f"{path} 类型必须为 {allowed_types}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path} 必须等于 {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} 枚举值非法：{value!r}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path} 不能为空")
        if schema.get("pattern") and not re.fullmatch(schema["pattern"], value):
            errors.append(f"{path} 格式非法：{value}")
    if isinstance(value, int) and not isinstance(value, bool) and "minimum" in schema:
        if value < schema["minimum"]:
            errors.append(f"{path} 不得小于 {schema['minimum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path} 数量不足 {schema['minItems']}")
        if schema.get("uniqueItems"):
            serialized = [json.dumps(item, sort_keys=True, ensure_ascii=False) for item in value]
            if len(serialized) != len(set(serialized)):
                errors.append(f"{path} 不得包含重复项")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                errors.extend(validate_schema_shape(item, schema["items"], f"{path}[{index}]"))
    if isinstance(value, dict):
        for field in schema.get("required", []):
            if field not in value:
                errors.append(f"{path} 缺少必填字段：{field}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for field in value.keys() - properties.keys():
                errors.append(f"{path} 包含未定义字段：{field}")
        for field, field_schema in properties.items():
            if field in value:
                errors.extend(validate_schema_shape(value[field], field_schema, f"{path}.{field}"))
    return list(dict.fromkeys(errors))


def requirement_schema(version: str) -> dict[str, Any]:
    fact = _object(
        ["fact_id", "category", "statement", "source_type", "source_reference", "confidence", "affects_core_expectation"],
        {
            "fact_id": _string(), "category": {"enum": list(FACT_CATEGORIES)},
            "statement": _string(), "source_type": {"enum": list(SOURCE_TYPES)},
            "source_reference": _string(), "confidence": {"enum": ["high", "medium", "low"]},
            "affects_core_expectation": {"type": "boolean"}, "handling": {"type": ["string", "null"]},
        },
    )
    confirmation = _object(
        ["confirmation_id", "severity", "statement", "fact_ids", "status"],
        {
            "confirmation_id": _string(), "severity": {"enum": list(PENDING_SEVERITIES)},
            "statement": _string(), "fact_ids": _strings(1), "status": {"enum": list(PENDING_STATUSES)},
        },
    )
    risk = _object(
        ["risk_id", "statement", "test_priority", "evidence_state"],
        {"risk_id": _string(), "statement": _string(), "test_priority": {"enum": list(TEST_PRIORITIES)}, "evidence_state": {"enum": list(EVIDENCE_STATES)}},
    )
    criterion = _object(
        ["criterion_id", "statement", "fact_ids", "risk_ids"],
        {"criterion_id": _string(), "statement": _string(), "fact_ids": _strings(1), "risk_ids": _strings()},
    )
    body = _object(
        ["schema_version", "analysis_id", "report_mode", "source_type", "source_ids", "analysis_scope", "business_goal", "acceptance_basis", "facts", "confirmation_points", "risks", "acceptance_criteria", "regression_scope", "matched_profiles"],
        {
            "schema_version": {"const": SCHEMA_VERSION}, "analysis_id": _string(),
            "report_mode": {"enum": ["requirement", "combined"]}, "source_type": _string(),
            "source_ids": _strings(1), "analysis_scope": _string(), "business_goal": _string(),
            "acceptance_basis": _string(), "facts": {"type": "array", "items": fact, "minItems": 1},
            "confirmation_points": {"type": "array", "items": confirmation},
            "risks": {"type": "array", "items": risk}, "acceptance_criteria": {"type": "array", "items": criterion},
            "regression_scope": _strings(1), "matched_profiles": _strings(),
        },
    )
    return _base_schema("Requirement Analysis Model", version, body)


def diff_schema(version: str) -> dict[str, Any]:
    changed_file = _object(
        ["path", "status", "change_category", "business_relevance", "generated_file", "formatting_only"],
        {"path": _string(), "status": _string(), "change_category": _string(), "business_relevance": {"type": "boolean"}, "generated_file": {"type": "boolean"}, "formatting_only": {"type": "boolean"}},
    )
    change = _object(
        ["change_id", "file", "symbol_or_location", "change_type", "summary", "evidence_reference", "affected_contracts", "direct_callers", "indirect_callers", "existing_tests"],
        {"change_id": _string(), "file": _string(), "symbol_or_location": _string(), "change_type": _string(), "summary": _string(), "evidence_reference": _string(), "affected_contracts": _strings(), "direct_callers": _strings(), "indirect_callers": _strings(), "existing_tests": _strings()},
    )
    coverage = _object(
        ["requirement_id", "change_ids", "coverage_status", "evidence_state", "risk_ids"],
        {"requirement_id": _string(), "change_ids": _strings(), "coverage_status": {"enum": list(COVERAGE_STATUSES)}, "evidence_state": {"enum": list(EVIDENCE_STATES)}, "risk_ids": _strings()},
    )
    body = _object(
        ["schema_version", "analysis_id", "report_mode", "repository", "comparison_type", "comparison_expression", "base_commit", "head_commit", "working_tree_state", "changed_files", "change_items", "impact_chains", "coverage_results", "suspected_defects", "risks", "regression_scope", "matched_profiles"],
        {
            "schema_version": {"const": SCHEMA_VERSION}, "analysis_id": _string(), "report_mode": {"enum": ["diff", "combined"]},
            "repository": _string(), "comparison_type": _string(), "comparison_expression": _string(),
            "base_commit": {"type": ["string", "null"]}, "head_commit": {"type": ["string", "null"]},
            "working_tree_state": _string(), "changed_files": {"type": "array", "items": changed_file},
            "change_items": {"type": "array", "items": change}, "impact_chains": {"type": "array"},
            "coverage_results": {"type": "array", "items": coverage}, "suspected_defects": {"type": "array"},
            "risks": {"type": "array"}, "regression_scope": _strings(1), "matched_profiles": _strings(),
        },
    )
    return _base_schema("Diff Impact Model", version, body)


def risk_matrix_schema(version: str) -> dict[str, Any]:
    risk = _object(
        ["risk_id", "requirement_ids", "change_ids", "business_entry", "business_entries", "business_object", "conditions", "data_shapes", "core_action", "core_assertion", "business_impact", "test_priority", "evidence_state", "regression_scope", "merge_key", "testcase_ids"],
        {
            "risk_id": _string(), "requirement_ids": _strings(), "change_ids": _strings(),
            "business_entry": _string(), "business_entries": _strings(1), "business_object": _string(), "conditions": _strings(),
            "data_shapes": _strings(), "core_action": _string(), "core_assertion": _string(),
            "business_impact": {"enum": list(BUSINESS_IMPACTS)}, "test_priority": {"enum": list(TEST_PRIORITIES)},
            "evidence_state": {"enum": list(EVIDENCE_STATES)}, "regression_scope": {"enum": list(REGRESSION_SCOPES)},
            "merge_key": _string(), "testcase_ids": {"type": "array", "items": _string(pattern=TC_PATTERN), "uniqueItems": True},
        },
    )
    body = _object(
        ["schema_version", "matrix_id", "analysis_ids", "risk_items", "coverage_summary"],
        {"schema_version": {"const": SCHEMA_VERSION}, "matrix_id": _string(), "analysis_ids": _strings(1), "risk_items": {"type": "array", "items": risk, "minItems": 1}, "coverage_summary": {"type": "object"}},
    )
    return _base_schema("Risk Coverage Matrix", version, body)


def testcase_schema(version: str) -> dict[str, Any]:
    case = _object(
        ["tc_id", "dimension", "common_entry", "module_level_1", "module_level_2", "test_point", "steps", "expected_results", "risk_ids", "requirement_ids", "change_ids", "historical_defect_ids", "test_priority", "evidence_state", "regression_scope", "deduplication_key"],
        {
            "tc_id": _string(pattern=TC_PATTERN), "dimension": {"enum": list(DIMENSIONS)},
            "common_entry": {"type": ["string", "null"]}, "module_level_1": {"type": ["string", "null"]},
            "module_level_2": {"type": ["string", "null"]}, "test_point": _string(),
            "steps": _strings(1), "expected_results": _strings(1), "risk_ids": _strings(1),
            "requirement_ids": _strings(), "change_ids": _strings(), "historical_defect_ids": _strings(),
            "test_priority": {"enum": list(TEST_PRIORITIES)}, "evidence_state": {"enum": list(EVIDENCE_STATES)},
            "regression_scope": {"enum": list(REGRESSION_SCOPES)}, "deduplication_key": _string(),
        },
    )
    body = _object(
        ["schema_version", "root_title", "cases"],
        {"schema_version": {"const": SCHEMA_VERSION}, "root_title": _string(), "cases": {"type": "array", "items": case, "minItems": 1}},
    )
    return _base_schema("Testcase Model", version, body)


def manifest_schema(version: str) -> dict[str, Any]:
    required = [
        "schema_version", "artifact_id", "source_type", "source_id", "source_files", "source_hash_algorithm",
        "source_hash", "rule_version", "generated_at", "generated_timezone", "report_mode", "report_path",
        "analysis_model_paths", "risk_matrix_path", "testcase_model_path", "xmind_md_path", "xmind_path",
        "case_count", "p0_count", "p0_risk_count", "p0_case_count", "pending_count",
        "blocking_pending_count", "nonblocking_pending_count", "suggested_pending_count",
        "validation_status", "relation", "supersedes", "failure_reason", "pending_reason",
    ]
    properties = {
        "schema_version": {"const": SCHEMA_VERSION}, "artifact_id": _string(), "source_type": _string(),
        "source_id": _string(), "source_files": _strings(), "source_snapshot_path": {"type": ["string", "null"]},
        "source_hash_algorithm": {"const": "sha256"}, "source_hash": _string(pattern=r"^sha256:[0-9a-fA-F]{64}$"),
        "requirement_id": {"type": ["string", "null"]}, "commit_range": {"type": ["string", "null"]},
        "rule_version": {"const": version}, "generated_at": _string(), "generated_timezone": {"enum": list(ALLOWED_TIMEZONES)},
        "report_mode": {"enum": list(REPORT_MODES)}, "report_path": {"type": ["string", "null"]},
        "analysis_model_paths": _strings(), "risk_matrix_path": {"type": ["string", "null"]},
        "testcase_model_path": {"type": ["string", "null"]}, "xmind_md_path": {"type": ["string", "null"]},
        "xmind_path": {"type": ["string", "null"]}, "case_count": {"type": "integer", "minimum": 0},
        "p0_count": {"type": "integer", "minimum": 0, "description": "Compatibility alias of p0_case_count."},
        "p0_risk_count": {"type": "integer", "minimum": 0}, "p0_case_count": {"type": "integer", "minimum": 0},
        "pending_count": {"type": "integer", "minimum": 0}, "blocking_pending_count": {"type": "integer", "minimum": 0},
        "nonblocking_pending_count": {"type": "integer", "minimum": 0}, "suggested_pending_count": {"type": "integer", "minimum": 0},
        "validation_status": {"enum": list(VALIDATION_STATUSES)}, "relation": {"enum": list(RELATIONS)},
        "supersedes": {"type": ["string", "null"]}, "failure_reason": {"type": ["string", "null"]},
        "pending_reason": {"type": ["string", "null"]},
    }
    return _base_schema("QA Artifact Manifest", version, _object(required, properties))


def schema_documents(root: Path) -> dict[str, dict[str, Any]]:
    version = read_rule_version(root)
    return {
        "requirement-analysis.schema.json": requirement_schema(version),
        "diff-impact.schema.json": diff_schema(version),
        "risk-coverage-matrix.schema.json": risk_matrix_schema(version),
        "testcase-model.schema.json": testcase_schema(version),
        "artifact-manifest.schema.json": manifest_schema(version),
    }


def _required(data: dict[str, Any], fields: tuple[str, ...] | list[str]) -> list[str]:
    return [f"缺少字段：{field}" for field in fields if field not in data]


def _unique_ids(items: list[dict[str, Any]], key: str) -> tuple[set[str], list[str]]:
    ids = [item.get(key) for item in items]
    errors = [f"{key} 必须是非空字符串" for value in ids if not isinstance(value, str) or not value]
    if len([value for value in ids if isinstance(value, str)]) != len(set(value for value in ids if isinstance(value, str))):
        errors.append(f"{key} 重复")
    return {value for value in ids if isinstance(value, str)}, errors


def validate_requirement_model(data: dict[str, Any]) -> list[str]:
    errors = validate_schema_shape(data, requirement_schema("0.0.0"))
    facts = data.get("facts", []) if isinstance(data.get("facts"), list) else []
    confirmations = data.get("confirmation_points", []) if isinstance(data.get("confirmation_points"), list) else []
    criteria = data.get("acceptance_criteria", []) if isinstance(data.get("acceptance_criteria"), list) else []
    fact_ids, id_errors = _unique_ids(facts, "fact_id")
    errors.extend(id_errors)
    categories: dict[str, str] = {}
    for fact in facts:
        category = fact.get("category")
        fact_id = fact.get("fact_id")
        if category not in FACT_CATEGORIES:
            errors.append(f"事实 {fact_id} category 非法：{category}")
        if isinstance(fact_id, str):
            categories[fact_id] = str(category)
        if fact.get("source_type") not in SOURCE_TYPES:
            errors.append(f"事实 {fact_id} source_type 非法")
        if category == "missing" and not fact.get("handling"):
            errors.append(f"缺失事实 {fact_id} 必须说明 handling")
    confirmation_fact_ids = {
        fact_id for point in confirmations for fact_id in point.get("fact_ids", []) if isinstance(fact_id, str)
    }
    for fact_id, category in categories.items():
        if category == "conflicting" and fact_id not in confirmation_fact_ids:
            errors.append(f"冲突事实 {fact_id} 未关联待确认点")
    for criterion in criteria:
        linked = criterion.get("fact_ids", [])
        if not linked:
            errors.append(f"核心验收 {criterion.get('criterion_id')} 未关联 fact_id")
        for fact_id in linked:
            if fact_id not in fact_ids:
                errors.append(f"验收标准引用不存在事实：{fact_id}")
            elif categories.get(fact_id) != "confirmed":
                errors.append(f"非确定事实 {fact_id} 不得进入确定性验收标准")
    return list(dict.fromkeys(errors))


def validate_diff_model(data: dict[str, Any]) -> list[str]:
    errors = validate_schema_shape(data, diff_schema("0.0.0"))
    changes = data.get("change_items", []) if isinstance(data.get("change_items"), list) else []
    change_ids, id_errors = _unique_ids(changes, "change_id")
    errors.extend(id_errors)
    for coverage in data.get("coverage_results", []) if isinstance(data.get("coverage_results"), list) else []:
        status = coverage.get("coverage_status")
        if status not in COVERAGE_STATUSES:
            errors.append(f"覆盖状态非法：{status}")
        unknown = set(coverage.get("change_ids", [])) - change_ids
        if unknown:
            errors.append(f"覆盖结果引用不存在 change_id：{sorted(unknown)}")
        if status in {"疑似遗漏", "实现不一致"} and not coverage.get("risk_ids"):
            errors.append(f"{status} 的需求点必须关联风险")
    return list(dict.fromkeys(errors))


def validate_risk_matrix(data: dict[str, Any]) -> list[str]:
    errors = validate_schema_shape(data, risk_matrix_schema("0.0.0"))
    risks = data.get("risk_items", []) if isinstance(data.get("risk_items"), list) else []
    _, id_errors = _unique_ids(risks, "risk_id")
    errors.extend(id_errors)
    for risk in risks:
        if risk.get("test_priority") not in TEST_PRIORITIES:
            errors.append(f"风险 {risk.get('risk_id')} 优先级非法")
        if risk.get("test_priority") == "P0" and not risk.get("testcase_ids"):
            errors.append(f"P0 风险 {risk.get('risk_id')} 未映射 TC")
        for tc_id in risk.get("testcase_ids", []):
            if not re.fullmatch(TC_PATTERN, str(tc_id)):
                errors.append(f"风险 {risk.get('risk_id')} 引用非法 TC：{tc_id}")
        if risk.get("business_entry") not in risk.get("business_entries", []):
            errors.append(f"风险 {risk.get('risk_id')} 主 business_entry 必须包含在 business_entries")
    summary = data.get("coverage_summary", {})
    expected_summary = {
        "risk_count": len(risks),
        "p0_risk_count": sum(risk.get("test_priority") == "P0" for risk in risks),
        "covered_risk_count": sum(bool(risk.get("testcase_ids")) for risk in risks),
    }
    for field, expected in expected_summary.items():
        if summary.get(field) != expected:
            errors.append(f"coverage_summary.{field}={summary.get(field)} 与实际 {expected} 不一致")
    return list(dict.fromkeys(errors))


def validate_testcase_model(data: dict[str, Any]) -> list[str]:
    errors = validate_schema_shape(data, testcase_schema("0.0.0"))
    cases = data.get("cases", []) if isinstance(data.get("cases"), list) else []
    tc_ids, id_errors = _unique_ids(cases, "tc_id")
    errors.extend(id_errors)
    expected = {f"TC{index:03d}" for index in range(1, len(cases) + 1)}
    if tc_ids != expected:
        errors.append(f"TC 编号必须从 TC001 连续：{sorted(tc_ids)}")
    for case in cases:
        tc_id = case.get("tc_id")
        if not re.fullmatch(TC_PATTERN, str(tc_id)):
            errors.append(f"TC 编号必须严格三位：{tc_id}")
        if not case.get("risk_ids"):
            errors.append(f"{tc_id} 未关联风险")
        if not any(case.get(field) for field in ("requirement_ids", "change_ids", "historical_defect_ids")):
            errors.append(f"{tc_id} 未关联需求、Diff 或历史缺陷")
        common = case.get("common_entry")
        modules = bool(case.get("module_level_1") and case.get("module_level_2"))
        if bool(common) == modules:
            errors.append(f"{tc_id} 必须在 common_entry 与两级模块结构中二选一")
        if not case.get("test_point") or not case.get("steps") or not case.get("expected_results"):
            errors.append(f"{tc_id} 缺少唯一测试点、步骤或预期")
        for expected_result in case.get("expected_results", []):
            vague = next(
                (
                    token for token in ("页面正常", "功能正常", "展示正常", "运行正常", "交互正常", "数据正常", "符合预期")
                    if token in expected_result
                ),
                None,
            )
            if vague:
                errors.append(f"{tc_id} expected_results 包含模糊断言：{vague}")
    return list(dict.fromkeys(errors))


def validate_model_links(
    requirement: dict[str, Any] | None,
    diff: dict[str, Any] | None,
    risk_matrix: dict[str, Any],
    testcase_model: dict[str, Any],
) -> list[str]:
    """Validate IDs and reverse mappings across all structured handoff models."""

    errors: list[str] = []
    requirement_ids = {
        item.get("criterion_id") for item in (requirement or {}).get("acceptance_criteria", [])
    }
    change_ids = {item.get("change_id") for item in (diff or {}).get("change_items", [])}
    risks = {item.get("risk_id"): item for item in risk_matrix.get("risk_items", [])}
    cases = {item.get("tc_id"): item for item in testcase_model.get("cases", [])}
    analysis_ids = set(risk_matrix.get("analysis_ids", []))
    for model in (requirement, diff):
        if model and model.get("analysis_id") not in analysis_ids:
            errors.append(f"风险矩阵未关联分析模型：{model.get('analysis_id')}")
    for risk_id, risk in risks.items():
        if requirement is not None:
            unknown = set(risk.get("requirement_ids", [])) - requirement_ids
            if unknown:
                errors.append(f"风险 {risk_id} 引用不存在需求点：{sorted(unknown)}")
        if diff is not None:
            unknown = set(risk.get("change_ids", [])) - change_ids
            if unknown:
                errors.append(f"风险 {risk_id} 引用不存在 Diff 变更：{sorted(unknown)}")
        unknown_tcs = set(risk.get("testcase_ids", [])) - cases.keys()
        if unknown_tcs:
            errors.append(f"风险 {risk_id} 引用不存在 TC：{sorted(unknown_tcs)}")
    for tc_id, case in cases.items():
        unknown_risks = set(case.get("risk_ids", [])) - risks.keys()
        if unknown_risks:
            errors.append(f"{tc_id} 引用不存在风险：{sorted(unknown_risks)}")
        if requirement is not None:
            unknown = set(case.get("requirement_ids", [])) - requirement_ids
            if unknown:
                errors.append(f"{tc_id} 引用不存在需求点：{sorted(unknown)}")
        if diff is not None:
            unknown = set(case.get("change_ids", [])) - change_ids
            if unknown:
                errors.append(f"{tc_id} 引用不存在 Diff 变更：{sorted(unknown)}")
        for risk_id in set(case.get("risk_ids", [])) & risks.keys():
            if tc_id not in risks[risk_id].get("testcase_ids", []):
                errors.append(f"{tc_id} 与风险 {risk_id} 的双向映射不一致")
    for risk_id, risk in risks.items():
        for tc_id in set(risk.get("testcase_ids", [])) & cases.keys():
            if risk_id not in cases[tc_id].get("risk_ids", []):
                errors.append(f"风险 {risk_id} 与 {tc_id} 的双向映射不一致")
    return list(dict.fromkeys(errors))


MODEL_VALIDATORS: dict[str, Callable[[dict[str, Any]], list[str]]] = {
    "requirement": validate_requirement_model,
    "diff": validate_diff_model,
    "risk": validate_risk_matrix,
    "testcase": validate_testcase_model,
}


def stable_source_hash(root: Path, paths: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(paths):
        normalized = Path(relative).as_posix()
        path = (root / normalized).resolve()
        root_resolved = root.resolve()
        if path != root_resolved and root_resolved not in path.parents:
            raise ValueError(f"来源路径越界：{relative}")
        if not path.is_file():
            raise ValueError(f"来源文件不存在：{relative}")
        digest.update(normalized.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def valid_generated_at(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, GENERATED_AT_FORMAT)
    except ValueError:
        return False
    return True


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} 根对象必须是 JSON object")
    return data
