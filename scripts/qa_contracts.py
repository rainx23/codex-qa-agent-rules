#!/usr/bin/env python3
"""Single executable source for QA model and manifest contracts."""

from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any, Callable

from file_hash_utils import stable_file_content_hash, stable_multi_file_hash
from assertion_quality import expectation_quality_error
from validate_evidence import (
    _resolve_evidence_path,
    evidence_reference_identity,
    validate_evidence_references as validate_authentic_evidence_references,
)


SCHEMA_VERSION = "2.0.0"
REPORT_MODES = ("requirement", "diff", "combined")
FACT_CATEGORIES = ("confirmed", "conflicting", "inferred", "missing")
SOURCE_TYPES = (
    "user_confirmation", "requirement", "zentao_section_3",
    "openspec", "markdown", "screenshot", "diff", "code_context",
    "acceptance_criteria", "formal_change_record", "api_document", "sql_definition",
    "complete_ddl", "knowledge_table", "historical_defect", "pasted_text", "chat_snapshot",
)
COVERAGE_STATUSES = ("已覆盖", "疑似遗漏", "实现不一致", "需求外变更", "无法判断")
TEST_PRIORITIES = ("P0", "P1", "P2")
EVIDENCE_STATES = ("已确认", "疑似", "待确认")
REGRESSION_SCOPES = ("核心回归", "关联回归", "冒烟回归")
BUSINESS_IMPACTS = ("critical", "high", "medium", "low")
VALIDATION_STATUSES = ("passed", "failed", "pending")
WORKFLOW_STAGES = ("confirmation_only", "formal_generation", "completed")
RELATIONS = ("新增", "补充", "替代", "废弃")
PENDING_SEVERITIES = ("blocking", "nonblocking", "suggested")
PENDING_STATUSES = ("pending", "skipped", "resolved")
DIMENSIONS = (
    "功能测试", "数据测试", "异常测试", "权限测试",
    "导出测试", "兼容性测试", "回归测试", "SQL验证",
)
REQUIREMENT_ASPECTS = (
    "business_goal", "entry", "role", "flow", "field_rule",
    "data_definition", "state", "operation", "exclusion", "acceptance_basis",
)
TEST_DIMENSION_STATUSES = ("covered", "not_applicable", "explicitly_excluded", "pending", "blocked")
CONDITION_MATRIX_APPLICABILITY_STATUSES = ("required", "not_required", "blocked")
SCOPE_DISPOSITION_STATUSES = TEST_DIMENSION_STATUSES
TC_PATTERN = r"^TC\d{3}$"
SEMVER_PATTERN = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"
GENERATED_AT_FORMAT = "%Y-%m-%d %H:%M:%S"
ALLOWED_TIMEZONES = ("Asia/Shanghai", "UTC")
ZERO_HASH = "sha256:" + "0" * 64
KNOWLEDGE_STATUSES = ("active_confirmed", "candidate", "conflicting", "superseded", "deprecated", "missing")
SCHEMA_SCOPES = ("complete", "partial", "blocked")
RISK_DISPOSITIONS = ("active", "covered", "merged", "deferred", "accepted", "blocked", "not_applicable", "resolved")
CONDITION_COVERAGE_TYPES = ("behavior", "configuration")
SHARED_ENTRY_SCOPE_MIN_ENTRIES = 6
TC_SPLIT_REASONS = (
    "data_source", "permission_rule", "calculation_basis", "operation",
    "oracle", "exception_handling", "risk_diagnostic",
)
FIXED_API_ASSERTION_SCOPE = "parameter_health"
FIXED_API_HEALTH_CHECKS = (
    {"path": "content.code", "operator": "equals", "expected": 0},
    {"path": "content.msg", "operator": "equals", "expected": "OK"},
)
VALUE_ASSESSMENT_ALGORITHM_VERSION = "1.0.0"
VALUE_ASSESSMENT_REASON_CODES = (
    "CRITICAL_BUSINESS_IMPACT",
    "HIGH_BUSINESS_IMPACT",
    "P0_RISK_COVERAGE",
    "UNIQUE_P1_RISK_COVERAGE",
    "HISTORICAL_DEFECT_REGRESSION",
    "CORE_REGRESSION",
    "LOW_VALUE_REACHABILITY_ASSERTION",
    "MULTI_RISK_DIAGNOSTIC_WEAKNESS",
    "LOW_EVIDENCE_CONFIDENCE",
    "HIGH_MAINTENANCE_COST",
    "POSSIBLE_DUPLICATE",
    "HIGH_SIMILARITY_DUPLICATE",
    "INSUFFICIENT_INPUTS",
)
VALUE_ASSESSMENT_MAINTENANCE_FIELDS = (
    "external_system_dependency_count",
    "mutable_shared_data_dependency_count",
    "manual_oracle_count",
    "environment_specific_dependency_count",
)
VALUE_ASSESSMENT_DIMENSION_FIELDS = (
    "business_impact",
    "risk_coverage_value",
    "regression_value",
    "diagnostic_value",
    "evidence_confidence",
    "maintenance_cost",
    "redundancy_penalty",
)
VALUE_ASSESSMENT_GUARDRAILS = ("p0_mapped", "historical_defect_regression")
VALUE_ASSESSMENT_RECOMMENDATIONS = (
    "retain",
    "retain_guarded",
    "retain_guarded_and_improve",
    "standard_maintain",
    "review_simplification",
    "review_duplicate",
    "retain_guarded_and_review_duplicate",
    "split_for_diagnosis",
    "reconfirm_priority_evidence",
    "insufficient_inputs",
)
VALUE_ASSESSMENT_BANDS = (
    "high_value_core",
    "regression_keep",
    "standard_value",
    "review_simplify_or_merge",
    "low_value_review",
)
VALUE_ASSESSMENT_WARNING_CODES = (
    "LOW_EVIDENCE_CONFIDENCE",
    "P0_LOW_SCORE_GUARDED",
    "HISTORICAL_DEFECT_LOW_SCORE_GUARDED",
    "POSSIBLE_DUPLICATE_REVIEW_REQUIRED",
    "MULTI_RISK_DIAGNOSTIC_WEAKNESS",
)
VALUE_ASSESSMENT_SUGGESTION_CODES = (
    "REVIEW_LOW_VALUE_SMOKE",
    "REVIEW_SIMPLIFICATION",
    "REVIEW_DUPLICATE",
    "SPLIT_FOR_DIAGNOSIS",
    "RECONFIRM_PRIORITY_EVIDENCE",
    "RETAIN_GUARDED_AND_IMPROVE",
)
VAGUE_ASSERTIONS = (
    "页面正常", "功能正常", "展示正常", "运行正常", "交互正常", "数据正常", "符合预期",
    "返回结果无误", "数据没有问题", "系统按业务规则处理", "结果满足要求", "页面表现符合设计",
    "没有出现异常情况", "结果与实际一致", "正常返回相关内容", "处理正确", "结果正确", "数据正确",
    "无异常", "无问题", "符合需求", "符合设计", "具体业务结果以确认口径为准", "按后续确认结果验证",
    "没有未处理异常即可",
    "data correctness", "result correctness", "function works", "meets requirement", "meets expectation",
    "no issue", "no problem", "no exception", "business handling is correct",
    "按已确认规则处理", "按系统现有逻辑处理", "按规则处理", "处理成功", "展示正确",
)
STRUCTURE_EVIDENCE_MARKERS = (
    "字段存在", "字段片段", "字段清单", "字段定义", "包含字段", "表结构", "控件存在", "选项存在",
)
CAPABILITY_EVIDENCE_MARKERS = (
    "可追加多个用户", "支持多个用户", "支持多选", "可以多选", "可多选", "可选择多个",
    "可配置多个值", "支持追加",
)
BEHAVIOR_EVIDENCE_CATEGORIES = (
    ("deduplication", ("自动去重", "去重", "重复值被拒绝", "重复用户不可选择", "重复值被合并", "重复选择提示")),
    ("participation", ("不参与统计", "不参与权限", "权限判断", "默认过滤", "过滤", "排除")),
    ("persistence", ("保存后", "删除一个值", "删除一个用户", "删除后")),
    ("inheritance", ("继承", "覆盖原有", "覆盖已有")),
    ("uniqueness", ("唯一约束",)),
)
DATA_VALIDATION_REQUIREMENTS = ("required", "optional", "not_required", "blocked")
VALIDATION_METHODS = ("sql", "cross_source_reconciliation", "mixed", "not_applicable", "blocked")
SQL_GENERATION_STATUSES = ("ready", "partial", "blocked", "not_required")
API_AUTOMATION_MODES = ("new", "maintenance")
API_AUTOMATION_ACTIONS = ("create", "update", "none", "blocked")
API_PARAMETER_CHANGE_TYPES = ("added", "removed", "renamed", "type_changed", "default_changed", "required_changed", "format_changed", "unchanged")
SQL_EXECUTION_STATUSES = ("planned", "generated", "reviewed", "executed", "passed", "failed", "blocked")
SENSITIVE_PATTERN = re.compile(r"(?i)(?:password|passwd|token|jdbc|private[_ -]?key|secret)\s*[:=]")
COMMIT_SHA_PATTERN = r"^[0-9a-fA-F]{7,40}$"
CAPTURED_AT_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def stable_normalized_file_hash(path: Path) -> str:
    return stable_file_content_hash(path, normalize_text_newlines=True)


def compute_core_deduplication_key(factors: dict[str, Any]) -> str:
    """Return a deterministic entry-agnostic key for testcase merge decisions."""

    ordered_fields = (
        "business_object", "trigger_condition", "core_action", "core_assertion",
        "risk_semantics", "data_source", "permission_rule", "calculation_basis",
        "exception_handling",
    )
    normalized = {
        field: re.sub(r"\s+", " ", str(factors.get(field, ""))).strip().casefold()
        for field in ordered_fields
    }
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def _evidence_reference() -> dict[str, Any]:
    return _object(
        [
            "source_type", "storage_type", "source_path", "snapshot_path", "source_record_id",
            "line_start", "line_end", "commit_sha", "content_hash", "excerpt", "captured_at",
            "captured_timezone", "evidence_status",
        ],
        {
            "source_type": {"enum": list(SOURCE_TYPES)}, "storage_type": {"enum": ["file", "snapshot"]},
            "source_path": {"type": ["string", "null"]}, "snapshot_path": {"type": ["string", "null"]},
            "source_record_id": {"type": ["string", "null"]},
            "line_start": {"type": ["integer", "null"], "minimum": 1}, "line_end": {"type": ["integer", "null"], "minimum": 1},
            "commit_sha": {"type": ["string", "null"], "pattern": COMMIT_SHA_PATTERN}, "content_hash": {"type": ["string", "null"], "pattern": r"^sha256:[0-9a-fA-F]{64}$"},
            "excerpt": _string(), "captured_at": _string(pattern=CAPTURED_AT_PATTERN), "captured_timezone": {"enum": list(ALLOWED_TIMEZONES)}, "evidence_status": {"enum": ["current", "stale", "reconfirm_required"]},
            "stale_reason": {"type": ["string", "null"]}, "working_tree_evidence": {"type": "boolean"},
        },
    )


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
    if isinstance(value, int) and not isinstance(value, bool) and "maximum" in schema:
        if value > schema["maximum"]:
            errors.append(f"{path} 不得大于 {schema['maximum']}")
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
        pattern_properties = schema.get("patternProperties", {})
        for field in value.keys() - properties.keys():
            matching = [
                field_schema for pattern, field_schema in pattern_properties.items()
                if re.fullmatch(pattern, str(field))
            ]
            if matching:
                for field_schema in matching:
                    errors.extend(validate_schema_shape(value[field], field_schema, f"{path}.{field}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path} 包含未定义字段：{field}")
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(validate_schema_shape(value[field], schema["additionalProperties"], f"{path}.{field}"))
        for field, field_schema in properties.items():
            if field in value:
                errors.extend(validate_schema_shape(value[field], field_schema, f"{path}.{field}"))
    return list(dict.fromkeys(errors))


def requirement_schema(version: str) -> dict[str, Any]:
    original_task_scope = _object(
        [
            "request_id", "request_text", "rule_paths", "source_ids",
            "requested_deliverables", "authorized_at", "continuation_policy",
        ],
        {
            "request_id": _string(), "request_text": _string(), "rule_paths": _strings(1),
            "source_ids": _strings(1),
            "requested_deliverables": {
                "type": "array",
                "items": {"enum": [
                    "requirement_analysis", "risk_coverage_matrix", "testcase_model",
                    "xmind_markdown", "xmind_workbook", "manifest", "index",
                ]},
                "minItems": 1,
                "uniqueItems": True,
            },
            "authorized_at": _string(pattern=CAPTURED_AT_PATTERN),
            "continuation_policy": {"const": "auto_resume"},
        },
    )
    confirmation_checkpoint = _object(
        [
            "checkpoint_id", "created_at", "scan_completed", "evidence_saved",
            "requirement_aspects_scanned", "test_dimensions_scanned",
            "condition_matrix_assessed", "confirmation_scan_completed",
            "downstream_artifacts_generated",
        ],
        {
            "checkpoint_id": _string(), "created_at": _string(pattern=CAPTURED_AT_PATTERN),
            "scan_completed": {"type": "boolean"}, "evidence_saved": {"type": "boolean"},
            "requirement_aspects_scanned": {
                "type": "array",
                "items": {"enum": list(REQUIREMENT_ASPECTS)},
                "uniqueItems": True,
            },
            "test_dimensions_scanned": {
                "type": "array", "items": {"enum": list(DIMENSIONS)}, "uniqueItems": True,
            },
            "condition_matrix_assessed": {"type": "boolean"},
            "confirmation_scan_completed": {"type": "boolean"},
            "downstream_artifacts_generated": {
                "type": "array",
                "items": {"enum": [
                    "risk_coverage_matrix", "testcase_model", "xmind_markdown",
                    "xmind_workbook", "formal_report", "manifest", "index",
                ]},
                "uniqueItems": True,
            },
        },
    )
    test_dimension_assessment = _object(
        ["dimension", "status", "reason", "fact_ids", "risk_ids", "confirmation_ids", "testcase_ids", "evidence_references"],
        {
            "dimension": {"enum": list(DIMENSIONS)},
            "status": {"enum": list(TEST_DIMENSION_STATUSES)},
            "reason": _string(), "fact_ids": _strings(), "risk_ids": _strings(),
            "confirmation_ids": _strings(), "testcase_ids": _strings(),
            "evidence_references": {"type": "array", "items": _evidence_reference()},
        },
    )
    condition_matrix_applicability = _object(
        ["status", "dimension_ids", "reason", "evidence_references"],
        {
            "status": {"enum": list(CONDITION_MATRIX_APPLICABILITY_STATUSES)},
            "dimension_ids": _strings(), "reason": _string(),
            "evidence_references": {"type": "array", "items": _evidence_reference()},
            "confirmation_ids": _strings(), "missing_fact_ids": _strings(),
        },
    )
    scope_disposition = _object(
        ["scope_item", "status", "reason", "evidence_references"],
        {
            "scope_item": _string(), "status": {"enum": list(SCOPE_DISPOSITION_STATUSES)},
            "reason": _string(), "evidence_references": {"type": "array", "items": _evidence_reference()},
            "fact_ids": _strings(), "confirmation_ids": _strings(),
        },
    )
    condition_dimension = _object(
        ["dimension_id", "dimension_name", "values"],
        {"dimension_id": _string(), "dimension_name": _string(), "values": _strings(1)},
    )
    required_combination = _object(
        ["combination_id", "dimension_values", "covered_by_tc_ids"],
        {
            "combination_id": _string(), "dimension_values": {"type": "object"},
            "covered_by_tc_ids": {"type": "array", "items": _string(pattern=TC_PATTERN), "uniqueItems": True},
        },
    )
    excluded_combination = _object(
        ["combination_id", "dimension_values", "exclusion_reason"],
        {
            "combination_id": _string(), "dimension_values": {"type": "object"},
            "exclusion_reason": _string(),
        },
    )
    variable_dimension = _object(
        ["dimension_id", "values"],
        {"dimension_id": _string(), "values": _strings(1)},
    )
    combination_group = _object(
        ["group_id", "fixed_values", "variable_dimensions", "expected_combination_count"],
        {
            "group_id": _string(), "fixed_values": {"type": "object"},
            "variable_dimensions": {"type": "array", "items": variable_dimension, "minItems": 1},
            "expected_combination_count": {"type": "integer", "minimum": 1},
            "constraints": _strings(),
        },
    )
    combination_generation = _object(
        ["mode", "groups"],
        {
            "mode": {"const": "grouped_cross_product"},
            "groups": {"type": "array", "items": combination_group, "minItems": 1},
        },
    )
    condition_matrix = _object(
        ["dimensions", "combination_generation", "required_combinations", "excluded_combinations", "coverage_summary"],
        {
            "dimensions": {"type": "array", "items": condition_dimension, "minItems": 2},
            "combination_generation": combination_generation,
            "required_combinations": {"type": "array", "items": required_combination},
            "excluded_combinations": {"type": "array", "items": excluded_combination},
            "coverage_summary": {"type": "object"},
        },
    )
    fact = _object(
        ["fact_id", "category", "statement", "source_type", "source_reference", "confidence", "affects_core_expectation", "evidence_references"],
        {
            "fact_id": _string(), "category": {"enum": list(FACT_CATEGORIES)},
            "statement": _string(), "source_type": {"enum": list(SOURCE_TYPES)},
            "source_reference": _string(), "confidence": {"enum": ["high", "medium", "low"]},
            "affects_core_expectation": {"type": "boolean"}, "handling": {"type": ["string", "null"]},
            "evidence_references": {"type": "array", "items": _evidence_reference(), "minItems": 1},
        },
    )
    confirmation = _object(
        ["confirmation_id", "severity", "statement", "fact_ids", "status"],
        {
            "confirmation_id": _string(), "severity": {"enum": list(PENDING_SEVERITIES)},
            "statement": _string(), "fact_ids": _strings(1), "status": {"enum": list(PENDING_STATUSES)},
            "resolution": {"type": ["string", "null"]}, "resolution_evidence_references": {"type": "array", "items": _evidence_reference()},
            "resolved_at": {"type": ["string", "null"], "pattern": CAPTURED_AT_PATTERN}, "skip_reason": {"type": ["string", "null"]},
            "decision_evidence": {"type": "array", "items": _evidence_reference()},
            "question": _string(), "current_evidence": _string(), "uncertainty": _string(),
            "impact_scope": _strings(1), "answer_options": _strings(), "current_handling": _string(),
        },
    )
    risk = _object(
        ["risk_id", "statement", "test_priority", "evidence_state", "evidence_references"],
        {"risk_id": _string(), "statement": _string(), "test_priority": {"enum": list(TEST_PRIORITIES)}, "evidence_state": {"enum": list(EVIDENCE_STATES)}, "evidence_references": {"type": "array", "items": _evidence_reference(), "minItems": 1}},
    )
    criterion = _object(
        ["criterion_id", "statement", "fact_ids", "risk_ids", "evidence_references"],
        {"criterion_id": _string(), "statement": _string(), "fact_ids": _strings(1), "risk_ids": _strings(), "evidence_references": {"type": "array", "items": _evidence_reference(), "minItems": 1}},
    )
    body = _object(
        ["schema_version", "analysis_id", "report_mode", "source_type", "source_ids", "analysis_scope", "business_goal", "acceptance_basis", "facts", "confirmation_points", "risks", "acceptance_criteria", "regression_scope", "matched_profiles", "data_validation_required", "data_validation_reason", "recommended_validation_method", "sql_generation_status", "validation_missing_information"],
        {
            "schema_version": {"const": SCHEMA_VERSION}, "analysis_id": _string(),
            "report_mode": {"enum": ["requirement", "combined"]}, "source_type": _string(),
            "source_ids": _strings(1), "analysis_scope": _string(), "business_goal": _string(),
            "acceptance_basis": _string(), "facts": {"type": "array", "items": fact, "minItems": 1},
            "confirmation_points": {"type": "array", "items": confirmation},
            "risks": {"type": "array", "items": risk}, "acceptance_criteria": {"type": "array", "items": criterion},
            "regression_scope": _strings(1), "matched_profiles": _strings(),
            "data_validation_required": {"enum": list(DATA_VALIDATION_REQUIREMENTS)}, "data_validation_reason": _string(),
            "recommended_validation_method": {"enum": list(VALIDATION_METHODS)}, "sql_generation_status": {"enum": list(SQL_GENERATION_STATUSES)},
            "validation_missing_information": _strings(),
            "condition_matrix_required": {"type": "boolean"},
            "condition_matrix": condition_matrix,
            "test_dimension_assessment": {"type": "array", "items": test_dimension_assessment},
            "condition_matrix_applicability": condition_matrix_applicability,
            "scope_dispositions": {"type": "array", "items": scope_disposition},
            "workflow_stage": {"enum": list(WORKFLOW_STAGES)},
            "original_task_scope": original_task_scope,
            "confirmation_checkpoint": confirmation_checkpoint,
            "risk_directions": _strings(),
        },
    )
    return _base_schema("Requirement Analysis Model", version, body)


def diff_schema(version: str) -> dict[str, Any]:
    changed_file = _object(
        ["path", "status", "change_category", "business_relevance", "generated_file", "formatting_only"],
        {"path": _string(), "status": _string(), "change_category": _string(), "business_relevance": {"type": "boolean"}, "generated_file": {"type": "boolean"}, "formatting_only": {"type": "boolean"}},
    )
    change = _object(
        ["change_id", "file", "symbol_or_location", "change_type", "summary", "evidence_reference", "evidence_references", "affected_contracts", "direct_callers", "indirect_callers", "existing_tests"],
        {"change_id": _string(), "file": _string(), "symbol_or_location": _string(), "change_type": _string(), "summary": _string(), "evidence_reference": _string(), "evidence_references": {"type": "array", "items": _evidence_reference(), "minItems": 1}, "affected_contracts": _strings(), "direct_callers": _strings(), "indirect_callers": _strings(), "existing_tests": _strings()},
    )
    coverage = _object(
        ["requirement_id", "change_ids", "coverage_status", "evidence_state", "risk_ids"],
        {"requirement_id": _string(), "change_ids": _strings(), "coverage_status": {"enum": list(COVERAGE_STATUSES)}, "evidence_state": {"enum": list(EVIDENCE_STATES)}, "risk_ids": _strings()},
    )
    impact_chain = _object(
        ["chain_id", "change_ids", "source_component", "affected_component", "propagation_path", "affected_contracts", "impact_type", "evidence_references", "confidence"],
        {"chain_id": _string(), "change_ids": _strings(1), "source_component": _string(), "affected_component": _string(),
         "propagation_path": _strings(1), "affected_contracts": _strings(1), "impact_type": _string(),
         "evidence_references": {"type": "array", "items": _evidence_reference(), "minItems": 1}, "confidence": {"enum": ["high", "medium", "low"]}},
    )
    diff_risk = _object(
        ["risk_id", "statement", "risk_title", "core_assertion", "risk_level", "change_ids", "requirement_fact_ids", "fact_ids", "evidence_state", "business_impact", "test_priority", "regression_scope", "disposition_status", "handling", "evidence_references"],
        {"risk_id": _string(), "statement": _string(), "change_ids": _strings(1), "requirement_fact_ids": _strings(),
         "fact_ids": _strings(), "risk_title": _string(), "core_assertion": _string(), "risk_level": _string(),
         "disposition_status": {"enum": list(RISK_DISPOSITIONS)},
         "evidence_state": {"enum": list(EVIDENCE_STATES)}, "business_impact": {"enum": list(BUSINESS_IMPACTS)},
         "test_priority": {"enum": list(TEST_PRIORITIES)}, "regression_scope": {"enum": list(REGRESSION_SCOPES)}, "handling": _string(),
         "evidence_references": {"type": "array", "items": _evidence_reference(), "minItems": 1}},
    )
    suspected_defect = _object(
        ["defect_id", "title", "requirement_fact_ids", "change_ids", "evidence_state", "observed_behavior", "expected_behavior", "impact", "confidence", "handling", "evidence_references"],
        {"defect_id": _string(pattern=r"^DEF\d{3}$"), "title": _string(), "requirement_fact_ids": _strings(1), "change_ids": _strings(1),
         "evidence_state": {"enum": list(EVIDENCE_STATES)}, "observed_behavior": _string(), "expected_behavior": _string(),
         "impact": _string(), "confidence": {"enum": ["high", "medium"]}, "handling": _string(),
         "evidence_references": {"type": "array", "items": _evidence_reference(), "minItems": 1}},
    )
    body = _object(
        ["schema_version", "analysis_id", "report_mode", "repository", "comparison_type", "comparison_expression", "base_commit", "head_commit", "working_tree_state", "changed_files", "change_items", "impact_chains", "coverage_results", "suspected_defects", "risks", "regression_scope", "matched_profiles"],
        {
            "schema_version": {"const": SCHEMA_VERSION}, "analysis_id": _string(), "report_mode": {"enum": ["diff", "combined"]},
            "repository": _string(), "comparison_type": _string(), "comparison_expression": _string(),
            "base_commit": {"type": ["string", "null"]}, "head_commit": {"type": ["string", "null"]},
            "working_tree_state": _string(), "changed_files": {"type": "array", "items": changed_file},
            "change_items": {"type": "array", "items": change}, "impact_chains": {"type": "array", "items": impact_chain},
            "coverage_results": {"type": "array", "items": coverage}, "suspected_defects": {"type": "array", "items": suspected_defect},
            "risks": {"type": "array", "items": diff_risk}, "regression_scope": _strings(1), "matched_profiles": _strings(),
        },
    )
    return _base_schema("Diff Impact Model", version, body)


def knowledge_table_schema(version: str) -> dict[str, Any]:
    field = _object(
        [
            "name", "type", "nullable", "default", "default_state", "comment", "ordinal",
            "evidence_fields", "unknown_fields", "raw_fragment", "parsed_tokens",
            "unparsed_fragment", "generated", "generated_expression", "generated_type",
            "auto_increment", "inline_constraints",
        ],
        {
            "name": _string(), "type": _string(), "nullable": {"type": ["boolean", "null"]},
            "default": {"type": ["string", "null"]}, "comment": {"type": ["string", "null"]},
            "default_state": {"enum": ["known_null", "known_value", "unknown"]}, "ordinal": {"type": "integer", "minimum": 1},
            "evidence_fields": _strings(1), "unknown_fields": _strings(),
            "raw_fragment": _string(), "parsed_tokens": _strings(), "unparsed_fragment": {"type": ["string", "null"]},
            "generated": {"type": ["boolean", "null"]},
            "generated_expression": {"type": ["string", "null"]},
            "generated_type": {"type": ["string", "null"]},
            "auto_increment": {"type": ["boolean", "null"]},
            "inline_constraints": _strings(),
        },
    )
    body = _object(
        [
            "table_id", "domain", "database", "table_name", "full_name", "dialect",
            "schema_scope", "current_ddl_path", "raw_hash", "normalized_hash", "fields",
            "keys", "partitions", "indexes", "engine_properties", "status", "source_type",
            "source_requirement_ids", "last_verified_at", "parse_warnings", "raw_tail",
            "parsed_tail_tokens", "unparsed_tail",
        ],
        {
            "table_id": _string(), "domain": _string(), "database": _string(), "table_name": _string(), "full_name": _string(),
            "dialect": _string(), "schema_scope": {"enum": list(SCHEMA_SCOPES)},
            "current_ddl_path": {"type": ["string", "null"]}, "raw_ddl": {"type": ["string", "null"]}, "normalized_ddl": {"type": ["string", "null"]},
            "raw_hash": _string(pattern=r"^sha256:[0-9a-fA-F]{64}$"),
            "normalized_hash": _string(pattern=r"^sha256:[0-9a-fA-F]{64}$"), "fields": {"type": "array", "items": field},
            "keys": _strings(), "partitions": _strings(), "indexes": _strings(), "engine_properties": {"type": "object"},
            "status": {"enum": list(KNOWLEDGE_STATUSES)}, "source_type": _string(), "source_requirement_ids": _strings(),
            "last_verified_at": {"type": ["string", "null"]}, "related_logic_ids": _strings(), "related_metric_ids": _strings(),
            "parse_warnings": _strings(), "applicability_scope": {"type": ["string", "null"]},
            "raw_tail": {"type": "string"}, "parsed_tail_tokens": _strings(),
            "unparsed_tail": {"type": ["string", "null"]},
        },
    )
    return _base_schema("Knowledge Table Model", version, body)


def logic_version_schema(version: str) -> dict[str, Any]:
    body = _object(
        ["logic_id", "name", "domain", "version", "status", "effective_from", "effective_to", "conditions", "data_sources", "join_rules", "filters", "calculation", "result", "exceptions", "supersedes", "changed_by_requirement", "evidence_sources"],
        {
            "logic_id": _string(), "name": _string(), "domain": _string(), "version": _string(), "status": {"enum": list(KNOWLEDGE_STATUSES)},
            "effective_from": {"type": ["string", "null"]}, "effective_to": {"type": ["string", "null"]},
            "conditions": _strings(), "data_sources": _strings(), "join_rules": _strings(), "filters": _strings(),
            "calculation": _string(), "result": _string(), "exceptions": _strings(), "supersedes": {"type": ["string", "null"]},
            "changed_by_requirement": {"type": ["string", "null"]}, "evidence_sources": _strings(1),
        },
    )
    return _base_schema("Logic Version Model", version, body)


def metric_schema(version: str) -> dict[str, Any]:
    body = _object(
        ["metric_id", "metric_name", "business_definition", "numerator", "denominator", "calculation_order", "multiplier", "dimensions", "data_sources", "join_keys", "filters", "deduplication_key", "time_range", "timezone_or_trade_calendar", "null_rule", "zero_denominator_rule", "precision", "rounding_position", "aggregation_method", "detail_summary_relation", "formal_simulated_scope", "evidence_sources", "status"],
        {
            "metric_id": _string(), "metric_name": _string(), "business_definition": _string(), "numerator": _string(), "denominator": _string(),
            "calculation_order": _strings(1), "multiplier": _string(), "dimensions": _strings(), "data_sources": _strings(1), "join_keys": _strings(),
            "filters": _strings(), "deduplication_key": _string(), "time_range": _string(), "timezone_or_trade_calendar": _string(),
            "null_rule": _string(), "zero_denominator_rule": _string(), "precision": _string(), "rounding_position": _string(),
            "aggregation_method": _string(), "detail_summary_relation": _string(), "formal_simulated_scope": _string(),
            "evidence_sources": _strings(1), "status": {"enum": list(KNOWLEDGE_STATUSES)},
        },
    )
    return _base_schema("Metric Model", version, body)


def requirement_knowledge_schema(version: str) -> dict[str, Any]:
    body = _object(
        ["requirement_id", "title", "domain", "status", "related_tables", "used_fields", "related_logic_ids", "related_metric_ids", "related_requirements", "changed_items", "report_path", "effective_version"],
        {
            "requirement_id": _string(), "title": _string(), "domain": _string(), "status": {"enum": list(KNOWLEDGE_STATUSES)},
            "related_tables": _strings(), "used_fields": _strings(), "related_logic_ids": _strings(), "related_metric_ids": _strings(),
            "related_requirements": _strings(), "changed_items": _strings(), "report_path": {"type": ["string", "null"]}, "effective_version": _string(),
        },
    )
    return _base_schema("Requirement Knowledge Model", version, body)


def data_validation_schema(version: str) -> dict[str, Any]:
    query_ref = _object(
        ["sql_id", "purpose", "status"],
        {"sql_id": _string(pattern=r"^SQLV\d{3}$"), "purpose": _string(), "status": {"enum": list(SQL_EXECUTION_STATUSES)}, "evidence_sources": _strings(), "execution_evidence": {"type": ["string", "null"]}},
    )
    reconciliation_ref = _object(
        ["reconciliation_id", "purpose", "status"],
        {"reconciliation_id": _string(pattern=r"^REC\d{3}$"), "purpose": _string(), "status": {"enum": list(SQL_EXECUTION_STATUSES)}, "evidence_sources": _strings()},
    )
    body = _object(
        ["data_validation_required", "reason", "validation_method", "sql_generation_status", "schema_sources", "metric_ids", "validation_queries", "reconciliation_plans", "blocking_questions"],
        {
            "data_validation_required": {"enum": list(DATA_VALIDATION_REQUIREMENTS)}, "reason": _string(), "validation_method": {"enum": list(VALIDATION_METHODS)},
            "sql_generation_status": {"enum": list(SQL_GENERATION_STATUSES)}, "schema_sources": _strings(), "metric_ids": _strings(),
            "validation_queries": {"type": "array", "items": query_ref}, "reconciliation_plans": {"type": "array", "items": reconciliation_ref},
            "blocking_questions": _strings(), "requirement_ids": _strings(), "risk_ids": _strings(), "tc_ids": {"type": "array", "items": _string(pattern=TC_PATTERN), "uniqueItems": True},
        },
    )
    return _base_schema("Data Validation Model", version, body)


def validation_sql_schema(version: str) -> dict[str, Any]:
    identifier_evidence = _object(
        ["identifier", "identifier_type", "qualified_identifier", "scope_table", "usage_type", "source_reference_type", "source_reference_id", "evidence_references", "evidence_state"],
        {"identifier": _string(), "identifier_type": {"enum": ["table", "column", "function", "enum_value", "parameter", "join_key", "filter_value"]},
         "qualified_identifier": _string(), "scope_table": {"type": ["string", "null"]}, "usage_type": _string(),
         "source_reference": _string(), "source_reference_type": {"enum": ["knowledge_table", "knowledge_table_field", "complete_ddl", "fact", "change", "formal_document", "code_context", "builtin_sql", "user_confirmation"]},
         "source_reference_id": _string(), "evidence_references": {"type": "array", "items": _evidence_reference(), "minItems": 1}, "evidence_state": {"const": "confirmed"}},
    )
    query = _object(
        ["sql_id", "purpose", "requirement_ids", "risk_ids", "tc_ids", "dialect", "tables", "fields", "parameters", "metric_ids", "expected_assertion", "execution_status", "sql_path", "evidence_sources", "identifier_evidence"],
        {
            "sql_id": _string(pattern=r"^SQLV\d{3}$"), "purpose": _string(), "requirement_ids": _strings(), "risk_ids": _strings(1),
            "tc_ids": {"type": "array", "items": _string(pattern=TC_PATTERN), "minItems": 1, "uniqueItems": True}, "dialect": _string(), "tables": _strings(1), "fields": _strings(),
            "parameters": _strings(), "metric_ids": _strings(), "expected_assertion": _string(), "execution_status": {"enum": list(SQL_EXECUTION_STATUSES)},
            "sql_path": _string(), "evidence_sources": _strings(1), "identifier_evidence": {"type": "array", "items": identifier_evidence, "minItems": 1},
            "execution_evidence": {"type": ["string", "null"]},
        },
    )
    body = _object(["schema_version", "sql_items"], {"schema_version": {"const": SCHEMA_VERSION}, "sql_items": {"type": "array", "items": query, "minItems": 1}})
    return _base_schema("Validation SQL Artifact Model", version, body)


def reconciliation_schema(version: str) -> dict[str, Any]:
    plan = _object(
        ["reconciliation_id", "baseline_entry", "target_entry", "comparison_dimensions", "comparison_fields", "filters", "time_range", "tolerance", "requirement_ids", "risk_ids", "tc_ids", "evidence_sources", "status"],
        {
            "reconciliation_id": _string(pattern=r"^REC\d{3}$"), "baseline_entry": _string(), "target_entry": _string(), "comparison_dimensions": _strings(1),
            "comparison_fields": _strings(1), "filters": _strings(), "time_range": _string(), "tolerance": _string(), "requirement_ids": _strings(), "risk_ids": _strings(),
            "tc_ids": {"type": "array", "items": _string(pattern=TC_PATTERN), "uniqueItems": True}, "evidence_sources": _strings(1), "status": {"enum": list(SQL_EXECUTION_STATUSES)},
        },
    )
    return _base_schema("Reconciliation Plan Model", version, _object(["schema_version", "reconciliation_plans"], {"schema_version": {"const": SCHEMA_VERSION}, "reconciliation_plans": {"type": "array", "items": plan, "minItems": 1}}))


def api_automation_schema(version: str) -> dict[str, Any]:
    endpoint = _object(
        ["name", "code", "method", "url", "body_type"],
        {"name": _string(), "code": _string(), "method": _string(), "url": _string(), "body_type": _string()},
    )
    coverage = _object(
        ["requirement", "groovy_before", "groovy_after", "sql_before", "sql_after", "default_request", "existing_automation"],
        {field: {"type": "boolean"} for field in ("requirement", "groovy_before", "groovy_after", "sql_before", "sql_after", "default_request", "existing_automation")},
    )
    parameter = _object(
        ["name", "location", "type", "required", "default_value", "value_format", "source", "change_type", "evidence", "branch_ids"],
        {"name": _string(), "location": _string(), "type": _string(), "required": {"type": "boolean"}, "default_value": {"type": ["string", "null"]}, "value_format": _string(), "source": _string(), "change_type": {"enum": list(API_PARAMETER_CHANGE_TYPES)}, "evidence": _strings(1), "branch_ids": _strings()},
    )
    relationship = _object(["parameter_names", "relationship_type", "condition", "evidence"], {"parameter_names": _strings(2), "relationship_type": _string(), "condition": _string(), "evidence": _strings(1)})
    branch = _object(["branch_id", "condition", "source", "status", "covered"], {"branch_id": _string(), "condition": _string(), "source": _string(), "status": _string(), "covered": {"type": "boolean"}})
    parameterization = _object(["parameter_name_text", "parameter_value_text", "combination_count", "generation_reason"], {"parameter_name_text": _string(), "parameter_value_text": _string(), "combination_count": {"type": "integer", "minimum": 1}, "generation_reason": _string()})
    excel_case = _object(["case_name", "method", "url", "body_type", "body", "headers", "validation", "priority", "interface_code"], {"case_name": _string(), "method": _string(), "url": _string(), "body_type": _string(), "body": _string(), "headers": _string(), "validation": _string(), "priority": _string(), "interface_code": _string()})
    health_check = _object(["path", "operator", "expected"], {"path": {"enum": ["content.code", "content.msg"]}, "operator": {"const": "equals"}, "expected": {"type": ["integer", "string"]}})
    validation = _object(["assertion_scope", "checks"], {"assertion_scope": {"const": FIXED_API_ASSERTION_SCOPE}, "checks": {"type": "array", "items": health_check, "minItems": 2, "maxItems": 2}})
    body = _object(
        ["schema_version", "model_id", "method", "url_or_path", "required_environment_variables", "validation", "business_assertions", "mode", "automation_action", "automation_required", "endpoint", "source_coverage", "parameters", "parameter_relationships", "branches", "parameterization", "excel_case", "assertion_level", "assertion_scope", "health_check_contract", "business_assertion_status", "blocking_questions", "evidence", "generated_artifacts", "validation_status"],
        {"schema_version": {"const": SCHEMA_VERSION}, "model_id": _string(), "method": _string(), "url_or_path": _string(), "required_environment_variables": _strings(), "validation": validation, "business_assertions": {"type": "array", "maxItems": 0}, "mode": {"enum": list(API_AUTOMATION_MODES)}, "automation_action": {"enum": list(API_AUTOMATION_ACTIONS)}, "automation_required": {"type": "boolean"}, "endpoint": endpoint, "source_coverage": coverage, "parameters": {"type": "array", "items": parameter}, "parameter_relationships": {"type": "array", "items": relationship}, "branches": {"type": "array", "items": branch}, "parameterization": parameterization, "excel_case": {"type": "array", "items": excel_case}, "assertion_level": _object(["health_check"], {"health_check": {"const": True}}),
         "assertion_scope": {"const": "parameter_health"}, "health_check_contract": _object(["code_path", "code_expected", "message_path", "message_expected"], {"code_path": {"const": "content.code"}, "code_expected": {"const": 0}, "message_path": {"const": "content.msg"}, "message_expected": {"const": "OK"}}),
         "business_assertion_status": {"const": "not_implemented"}, "blocking_questions": _strings(), "evidence": _strings(1), "generated_artifacts": _strings(), "validation_status": {"enum": list(VALIDATION_STATUSES)}},
    )
    return _base_schema("API Automation Model", version, body)


def risk_matrix_schema(version: str) -> dict[str, Any]:
    risk = _object(
        ["risk_id", "risk_title", "risk_level", "requirement_ids", "fact_ids", "change_ids", "business_entry", "business_entries", "business_object", "conditions", "data_shapes", "core_action", "core_assertion", "business_impact", "test_priority", "evidence_state", "regression_scope", "merge_key", "testcase_ids", "disposition_status", "disposition_reason", "evidence_references"],
        {
            "risk_id": _string(), "requirement_ids": _strings(), "fact_ids": _strings(), "change_ids": _strings(),
            "risk_title": _string(), "risk_level": _string(),
            "business_entry": _string(), "business_entries": _strings(1), "business_object": _string(), "conditions": _strings(),
            "data_shapes": _strings(), "core_action": _string(), "core_assertion": _string(),
            "business_impact": {"enum": list(BUSINESS_IMPACTS)}, "test_priority": {"enum": list(TEST_PRIORITIES)},
            "evidence_state": {"enum": list(EVIDENCE_STATES)}, "regression_scope": {"enum": list(REGRESSION_SCOPES)},
            "merge_key": _string(), "testcase_ids": {"type": "array", "items": _string(pattern=TC_PATTERN), "uniqueItems": True},
            "disposition_status": {"enum": list(RISK_DISPOSITIONS)}, "disposition_reason": _string(), "merged_to": _strings(), "confirmation_ids": _strings(), "decision_evidence": {"type": "array", "items": _evidence_reference()},
            "merged_into_risk_id": {"type": ["string", "null"]}, "merge_reason": {"type": ["string", "null"]}, "merge_evidence_references": {"type": "array", "items": _evidence_reference()},
            "blocked_by_confirmation_ids": _strings(), "blocked_reason": {"type": ["string", "null"]},
            "defer_reason": {"type": ["string", "null"]}, "defer_until": {"type": ["string", "null"]}, "owner": {"type": ["string", "null"]},
            "decision_evidence_references": {"type": "array", "items": _evidence_reference()},
            "acceptance_reason": {"type": ["string", "null"]}, "accepted_by": {"type": ["string", "null"]}, "accepted_at": {"type": ["string", "null"]}, "residual_impact": {"type": ["string", "null"]},
            "not_applicable_reason": {"type": ["string", "null"]}, "scope_evidence_references": {"type": "array", "items": _evidence_reference()},
            "resolution": {"type": ["string", "null"]}, "resolution_evidence_references": {"type": "array", "items": _evidence_reference()}, "resolved_at": {"type": ["string", "null"]}, "resolution_testcase_ids": _strings(),
            "evidence_references": {"type": "array", "items": _evidence_reference(), "minItems": 1},
        },
    )
    body = _object(
        ["schema_version", "matrix_id", "analysis_ids", "risk_items", "coverage_summary"],
        {"schema_version": {"const": SCHEMA_VERSION}, "matrix_id": _string(), "analysis_ids": _strings(1), "risk_items": {"type": "array", "items": risk, "minItems": 1}, "coverage_summary": {"type": "object"}},
    )
    return _base_schema("Risk Coverage Matrix", version, body)


def testcase_schema(version: str) -> dict[str, Any]:
    action = _object(["step_id", "action", "expected_results"], {"step_id": _string(pattern=r"^STEP\d{3}$"), "action": _string(), "expected_results": _strings(1)})
    entry_branch = _object(
        ["branch_id", "entry_name", "steps", "expected_results"],
        {
            "branch_id": _string(), "entry_name": _string(),
            "steps": _strings(1), "expected_results": _strings(1),
        },
    )
    assertion_mapping = _object(
        ["step_index", "expected_index", "observable_result"],
        {
            "step_index": {"type": "integer", "minimum": 1},
            "expected_index": {"type": "integer", "minimum": 1},
            "observable_result": _string(),
        },
    )
    condition_coverage = _object(
        ["combination_id", "coverage_type", "dimension_values", "expected_match_state"],
        {
            "combination_id": _string(), "coverage_type": {"enum": list(CONDITION_COVERAGE_TYPES)},
            "dimension_values": {"type": "object"}, "expected_match_state": _string(),
            "observable_result": _string(),
            "branch_id": _string(), "step_index": {"type": "integer", "minimum": 1},
            "expected_index": {"type": "integer", "minimum": 1},
            "assertion_mappings": {"type": "array", "minItems": 1, "items": assertion_mapping},
            "scope_path": _strings(1),
        },
    )
    shared_scope_entry = _object(
        ["entry_name"],
        {"entry_name": _string()},
    )
    shared_scope_subgroup = _object(
        ["subgroup_name", "entries"],
        {
            "subgroup_name": _string(),
            "entries": {"type": "array", "items": shared_scope_entry, "minItems": 1},
        },
    )
    shared_scope_group = _object(
        ["group_name", "subgroups"],
        {
            "group_name": _string(),
            "subgroups": {"type": "array", "items": shared_scope_subgroup, "minItems": 1},
        },
    )
    shared_entry_scope = _object(
        ["scope_id", "scope_title", "applies_to_tc_ids", "groups"],
        {
            "scope_id": _string(),
            "scope_title": {"const": "适用入口（以下全部TC均需逐项执行）"},
            "applies_to_tc_ids": {"type": "array", "items": _string(pattern=TC_PATTERN), "minItems": 1, "uniqueItems": True},
            "groups": {"type": "array", "items": shared_scope_group, "minItems": 1},
        },
    )
    core_deduplication_factors = _object(
        ["business_object", "trigger_condition", "core_action", "core_assertion", "risk_semantics"],
        {
            "business_object": _string(), "trigger_condition": _string(), "core_action": _string(),
            "core_assertion": _string(), "risk_semantics": _string(), "data_source": _string(),
            "permission_rule": _string(), "calculation_basis": _string(),
            "exception_handling": _string(),
        },
    )
    case = _object(
        ["tc_id", "dimension", "common_entry", "module_level_1", "module_level_2", "test_point", "steps", "expected_results", "risk_ids", "requirement_ids", "change_ids", "historical_defect_ids", "test_priority", "evidence_state", "regression_scope", "deduplication_key"],
        {
            "tc_id": _string(pattern=TC_PATTERN), "dimension": {"enum": list(DIMENSIONS)},
            "secondary_dimensions": {"type": "array", "items": {"enum": list(DIMENSIONS)}, "uniqueItems": True},
            "common_entry": {"type": ["string", "null"]}, "module_level_1": {"type": ["string", "null"]},
            "module_level_2": {"type": ["string", "null"]}, "test_point": _string(),
            "steps": _strings(), "expected_results": _strings(), "actions": {"type": "array", "items": action}, "risk_ids": _strings(1),
            "requirement_ids": _strings(), "change_ids": _strings(), "historical_defect_ids": _strings(),
            "entry_branches": {"type": "array", "items": entry_branch, "minItems": 2, "uniqueItems": True},
            "preconditions": _strings(), "test_data_refs": _strings(), "environment_refs": _strings(), "role_refs": _strings(),
            "cleanup_steps": _strings(), "oracle_sources": _strings(), "automation_candidate": {"enum": ["yes", "no", "unknown"]}, "automation_reason": _string(),
            "test_priority": {"enum": list(TEST_PRIORITIES)}, "evidence_state": {"enum": list(EVIDENCE_STATES)},
            "regression_scope": {"enum": list(REGRESSION_SCOPES)}, "deduplication_key": _string(),
            "core_deduplication_factors": core_deduplication_factors,
            "core_deduplication_key": _string(pattern=r"^sha256:[0-9a-fA-F]{64}$"),
            "split_reason": {"enum": list(TC_SPLIT_REASONS)}, "split_reason_detail": _string(),
            "condition_coverage": {"type": "array", "items": condition_coverage, "uniqueItems": True},
            "shared_entry_scope_id": _string(),
        },
    )
    execution_instance = _object(
        ["execution_instance_id", "tc_id", "branch_id", "execution_status", "executor", "executed_at", "defect_ids", "rerun_of", "execution_evidence"],
        {"execution_instance_id": _string(), "tc_id": _string(pattern=TC_PATTERN), "branch_id": {"type": ["string", "null"]},
         "execution_status": {"enum": ["not_run", "passed", "failed", "blocked", "skipped"]},
         "executor": {"type": ["string", "null"]}, "executed_at": {"type": ["string", "null"]}, "defect_ids": _strings(),
         "rerun_of": {"type": ["string", "null"]}, "execution_evidence": {"type": ["object", "string", "null"]},
         "failure_description": {"type": ["string", "null"]}, "confirmation_ids": _strings(), "decision_evidence": {"type": ["object", "string", "null"]}},
    )
    body = _object(
        ["schema_version", "root_title", "cases"],
        {"schema_version": {"const": SCHEMA_VERSION}, "model_id": _string(), "root_title": _string(), "cases": {"type": "array", "items": case, "minItems": 1},
         "branch_count": {"type": "integer", "minimum": 0}, "execution_instance_count": {"type": "integer", "minimum": 0},
         "execution_instances": {"type": "array", "items": execution_instance},
         "shared_entry_scope": shared_entry_scope},
    )
    return _base_schema("Testcase Model", version, body)


def testcase_value_assessment_schema(version: str) -> dict[str, Any]:
    hash_value = _string(pattern=r"^sha256:[0-9a-f]{64}$")
    testcase_reference = _object(
        ["model_id", "path", "content_hash"],
        {"model_id": _string(), "path": _string(), "content_hash": hash_value},
    )
    risk_reference = _object(
        ["matrix_id", "path", "content_hash"],
        {"matrix_id": _string(), "path": _string(), "content_hash": hash_value},
    )
    requirement_reference = {
        "type": ["object", "null"],
        "additionalProperties": False,
        "required": ["analysis_id", "path", "content_hash"],
        "properties": {
            "analysis_id": _string(), "path": _string(), "content_hash": hash_value,
        },
    }
    maintenance_value = _object(
        list(VALUE_ASSESSMENT_MAINTENANCE_FIELDS),
        {field: {"type": "integer", "minimum": 0} for field in VALUE_ASSESSMENT_MAINTENANCE_FIELDS},
    )
    maintenance_inputs = {
        "type": "object",
        "propertyNames": {"pattern": TC_PATTERN},
        "patternProperties": {TC_PATTERN: maintenance_value},
        "additionalProperties": False,
    }
    dimensions = _object(
        list(VALUE_ASSESSMENT_DIMENSION_FIELDS),
        {field: {"type": "integer", "minimum": 0, "maximum": 5} for field in VALUE_ASSESSMENT_DIMENSION_FIELDS},
    )
    assessment = _object(
        [
            "tc_id", "score_status", "dimensions", "total_score", "value_band",
            "guardrails", "reason_codes", "recommendation",
        ],
        {
            "tc_id": _string(pattern=TC_PATTERN),
            "score_status": {"enum": ["computed", "insufficient_inputs"]},
            "dimensions": dimensions,
            "total_score": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
            "value_band": {"enum": [*VALUE_ASSESSMENT_BANDS, None]},
            "guardrails": {
                "type": "array", "items": {"enum": list(VALUE_ASSESSMENT_GUARDRAILS)}, "uniqueItems": True,
            },
            "reason_codes": {
                "type": "array", "items": {"enum": list(VALUE_ASSESSMENT_REASON_CODES)}, "uniqueItems": True,
            },
            "recommendation": {"enum": list(VALUE_ASSESSMENT_RECOMMENDATIONS)},
        },
    )
    assessment["allOf"] = [
        {
            "if": {"properties": {"score_status": {"const": "computed"}}},
            "then": {
                "properties": {
                    "total_score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "value_band": {"enum": list(VALUE_ASSESSMENT_BANDS)},
                }
            },
        },
        {
            "if": {"properties": {"score_status": {"const": "insufficient_inputs"}}},
            "then": {
                "properties": {
                    "total_score": {"type": "null"},
                    "value_band": {"type": "null"},
                    "recommendation": {"const": "insufficient_inputs"},
                    "reason_codes": {"contains": {"const": "INSUFFICIENT_INPUTS"}},
                }
            },
        },
    ]
    body = _object(
        [
            "schema_version", "assessment_model_id", "algorithm_version",
            "testcase_model_reference", "risk_matrix_reference",
            "requirement_model_reference", "assessments",
        ],
        {
            "schema_version": {"const": SCHEMA_VERSION},
            "assessment_model_id": _string(pattern=r"^TVA-\d{3}$"),
            "algorithm_version": {"const": VALUE_ASSESSMENT_ALGORITHM_VERSION},
            "testcase_model_reference": testcase_reference,
            "risk_matrix_reference": risk_reference,
            "requirement_model_reference": requirement_reference,
            "maintenance_inputs": maintenance_inputs,
            "assessments": {"type": "array", "items": assessment, "minItems": 1},
        },
    )
    return _base_schema("Testcase Value Assessment Model", version, body)


def manifest_schema(version: str) -> dict[str, Any]:
    required = [
        "schema_version", "artifact_id", "source_type", "source_id", "source_files", "source_hash_algorithm",
        "source_hash", "rule_version", "generated_at", "generated_timezone", "report_mode", "report_path",
        "analysis_model_paths", "risk_matrix_path", "testcase_model_path", "xmind_md_path", "xmind_path",
        "draft_report_path", "draft_risk_matrix_path", "draft_testcase_model_path", "draft_xmind_md_path",
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
        "branch_count": {"type": "integer", "minimum": 0},
        "execution_instance_count": {"type": "integer", "minimum": 0},
        "draft_report_path": {"type": ["string", "null"]}, "draft_risk_matrix_path": {"type": ["string", "null"]},
        "draft_testcase_model_path": {"type": ["string", "null"]}, "draft_xmind_md_path": {"type": ["string", "null"]},
        "p0_count": {"type": "integer", "minimum": 0, "description": "Compatibility alias of p0_case_count."},
        "p0_risk_count": {"type": "integer", "minimum": 0}, "p0_case_count": {"type": "integer", "minimum": 0},
        "pending_count": {"type": "integer", "minimum": 0}, "blocking_pending_count": {"type": "integer", "minimum": 0},
        "nonblocking_pending_count": {"type": "integer", "minimum": 0}, "suggested_pending_count": {"type": "integer", "minimum": 0},
        "knowledge_snapshot": {"type": ["string", "null"]}, "data_validation_model": {"type": ["string", "null"]},
        "validation_sql": {"type": ["string", "null"]}, "reconciliation_plan": {"type": ["string", "null"]},
        "sql_count": {"type": "integer", "minimum": 0}, "reconciliation_count": {"type": "integer", "minimum": 0},
        "sql_status": {"enum": list(SQL_EXECUTION_STATUSES)}, "execution_evidence": {"type": ["string", "null"]}, "ddl_hashes": _strings(), "logic_versions": _strings(), "metric_versions": _strings(),
        "validation_status": {"enum": list(VALIDATION_STATUSES)}, "relation": {"enum": list(RELATIONS)},
        "supersedes": {"type": ["string", "null"]}, "failure_reason": {"type": ["string", "null"]},
        "pending_reason": {"type": ["string", "null"]},
        "lifecycle_status": {"enum": ["active", "superseded", "archived"]},
    }
    return _base_schema("QA Artifact Manifest", version, _object(required, properties))


def schema_documents(root: Path) -> dict[str, dict[str, Any]]:
    version = read_rule_version(root)
    return {
        "requirement-analysis.schema.json": requirement_schema(version),
        "diff-impact.schema.json": diff_schema(version),
        "risk-coverage-matrix.schema.json": risk_matrix_schema(version),
        "testcase-model.schema.json": testcase_schema(version),
        "testcase-value-assessment.schema.json": testcase_value_assessment_schema(version),
        "artifact-manifest.schema.json": manifest_schema(version),
        "knowledge-table.schema.json": knowledge_table_schema(version),
        "logic-version.schema.json": logic_version_schema(version),
        "metric.schema.json": metric_schema(version),
        "requirement-knowledge.schema.json": requirement_knowledge_schema(version),
        "data-validation.schema.json": data_validation_schema(version),
        "validation-sql.schema.json": validation_sql_schema(version),
        "reconciliation-plan.schema.json": reconciliation_schema(version),
        "api-automation.schema.json": api_automation_schema(version),
    }


def _required(data: dict[str, Any], fields: tuple[str, ...] | list[str]) -> list[str]:
    return [f"缺少字段：{field}" for field in fields if field not in data]


def _unique_ids(items: list[dict[str, Any]], key: str) -> tuple[set[str], list[str]]:
    ids = [item.get(key) for item in items]
    errors = [f"{key} 必须是非空字符串" for value in ids if not isinstance(value, str) or not value]
    if len([value for value in ids if isinstance(value, str)]) != len(set(value for value in ids if isinstance(value, str))):
        errors.append(f"{key} 重复")
    return {value for value in ids if isinstance(value, str)}, errors


def _validate_evidence_references(
    items: Any,
    label: str,
    confirmed: bool = False,
    *,
    changed_files: set[str] | None = None,
    expected_change_file: str | None = None,
    evidence_root: Path | None = None,
) -> list[str]:
    return validate_authentic_evidence_references(
        items,
        label=label,
        root=evidence_root or REPOSITORY_ROOT,
        confirmed=confirmed,
        changed_files=changed_files,
        expected_change_file=expected_change_file,
    )


def summarize_confirmations(requirement_model: dict[str, Any]) -> dict[str, int]:
    """Return the single delivery-readiness summary for Requirement confirmations."""

    facts = requirement_model.get("facts", []) if isinstance(requirement_model.get("facts"), list) else []
    confirmations = (
        requirement_model.get("confirmation_points", [])
        if isinstance(requirement_model.get("confirmation_points"), list) else []
    )
    core_fact_ids = {
        fact.get("fact_id")
        for fact in facts
        if fact.get("affects_core_expectation") is True and isinstance(fact.get("fact_id"), str)
    }
    unresolved_core_fact_count = sum(
        fact.get("affects_core_expectation") is True and fact.get("category") in {"missing", "conflicting"}
        for fact in facts
    )
    pending_count = 0
    blocking_pending_count = 0
    nonblocking_pending_count = 0
    suggested_pending_count = 0
    skipped_core_count = 0
    for point in confirmations:
        status = point.get("status")
        severity = point.get("severity")
        linked_core = bool(set(point.get("fact_ids", [])) & core_fact_ids)
        skipped_core = status == "skipped" and linked_core
        if status == "pending" or skipped_core:
            pending_count += 1
        if severity == "blocking" and (status == "pending" or skipped_core):
            blocking_pending_count += 1
        if severity == "nonblocking" and status == "pending":
            nonblocking_pending_count += 1
        if severity == "suggested" and status == "pending":
            suggested_pending_count += 1
        if skipped_core:
            skipped_core_count += 1
    return {
        "pending_count": pending_count,
        "blocking_pending_count": blocking_pending_count,
        "nonblocking_pending_count": nonblocking_pending_count,
        "suggested_pending_count": suggested_pending_count,
        "skipped_core_count": skipped_core_count,
        "unresolved_core_fact_count": unresolved_core_fact_count,
    }


def _condition_key(values: Any) -> str | None:
    if not isinstance(values, dict) or not all(isinstance(key, str) for key in values):
        return None
    return json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _generate_expected_condition_combinations(
    condition_matrix: dict[str, Any],
    dimension_ids: set[str],
    dimension_values: dict[str, set[str]],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    generation = condition_matrix.get("combination_generation")
    if not isinstance(generation, dict):
        return {}, ["CONDITION_MATRIX_REQUIRED: condition_matrix_required=true 时必须提供 combination_generation"]
    if generation.get("mode") != "grouped_cross_product":
        return {}, ["CONDITION_MATRIX_REQUIRED: combination_generation.mode 必须为 grouped_cross_product"]
    groups = generation.get("groups", []) if isinstance(generation.get("groups"), list) else []
    _, group_errors = _unique_ids(groups, "group_id")
    errors = [f"CONDITION_MATRIX_REQUIRED: {item}" for item in group_errors]
    generated: dict[str, dict[str, Any]] = {}
    for group in groups:
        group_id = group.get("group_id")
        fixed = group.get("fixed_values") if isinstance(group.get("fixed_values"), dict) else {}
        variables = group.get("variable_dimensions") if isinstance(group.get("variable_dimensions"), list) else []
        variable_ids = [item.get("dimension_id") for item in variables if isinstance(item, dict)]
        if len(variable_ids) != len(set(variable_ids)):
            errors.append(f"CONDITION_MATRIX_REQUIRED: group {group_id} variable_dimensions 重复")
        declared_ids = set(fixed) | set(variable_ids)
        if declared_ids != dimension_ids:
            errors.append(
                f"CONDITION_MATRIX_REQUIRED: group {group_id} 必须用 fixed_values + variable_dimensions 完整覆盖全部维度"
            )
            continue
        if set(fixed) & set(variable_ids):
            errors.append(f"CONDITION_MATRIX_REQUIRED: group {group_id} 固定维度与可变维度重复")
            continue
        invalid_group = False
        for dimension_id, value in fixed.items():
            if not isinstance(value, str) or value not in dimension_values.get(dimension_id, set()):
                errors.append(
                    f"CONDITION_MATRIX_REQUIRED: group {group_id} fixed_values.{dimension_id} 枚举值非法：{value}"
                )
                invalid_group = True
        variable_values: list[list[str]] = []
        for variable in variables:
            dimension_id = variable.get("dimension_id")
            values = variable.get("values", []) if isinstance(variable.get("values"), list) else []
            if not values or any(value not in dimension_values.get(dimension_id, set()) for value in values):
                errors.append(
                    f"CONDITION_MATRIX_REQUIRED: group {group_id} variable_dimensions.{dimension_id} 包含非法或空枚举"
                )
                invalid_group = True
            variable_values.append(values)
        if invalid_group:
            continue
        generated_count = 1
        for values in variable_values:
            generated_count *= len(values)
        if group.get("expected_combination_count") != generated_count:
            errors.append(
                f"CONDITION_GENERATION_COUNT_MISMATCH: group {group_id} expected_combination_count="
                f"{group.get('expected_combination_count')} 与生成数量 {generated_count} 不一致"
            )
        for selected in product(*variable_values):
            values = dict(fixed)
            values.update(dict(zip(variable_ids, selected)))
            key = _condition_key(values)
            if key in generated:
                errors.append(
                    f"CONDITION_COMBINATION_DUPLICATED: group {group_id} 与其他分组生成相同组合 {key}"
                )
            elif key is not None:
                generated[key] = values
    return generated, errors


def validate_requirement_model(data: dict[str, Any], *, evidence_root: Path | None = None) -> list[str]:
    errors = validate_schema_shape(data, requirement_schema("0.0.0"))
    workflow_stage = data.get("workflow_stage")
    facts = data.get("facts", []) if isinstance(data.get("facts"), list) else []
    confirmations = data.get("confirmation_points", []) if isinstance(data.get("confirmation_points"), list) else []
    fact_ids = {item.get("fact_id") for item in facts if isinstance(item, dict)}
    confirmation_ids = {item.get("confirmation_id") for item in confirmations if isinstance(item, dict)}
    if workflow_stage == "confirmation_only":
        scope = data.get("original_task_scope")
        checkpoint = data.get("confirmation_checkpoint")
        if not isinstance(scope, dict):
            errors.append("CONFIRMATION_ONLY_ORIGINAL_SCOPE_REQUIRED: 必须保存完整原始任务范围")
        elif scope.get("continuation_policy") != "auto_resume":
            errors.append("CONFIRMATION_ONLY_AUTO_RESUME_REQUIRED: 原始任务必须设置自动续跑")
        if not isinstance(checkpoint, dict):
            errors.append("CONFIRMATION_ONLY_CHECKPOINT_REQUIRED: 必须保存最小 Requirement Analysis Checkpoint")
        else:
            if checkpoint.get("scan_completed") is not True or checkpoint.get("confirmation_scan_completed") is not True:
                errors.append("CONFIRMATION_SCAN_INCOMPLETE: 发现首个问题后仍必须完成剩余需求扫描")
            if checkpoint.get("evidence_saved") is not True:
                errors.append("CONFIRMATION_ONLY_EVIDENCE_REQUIRED: 必须保存可复验 Evidence")
            if checkpoint.get("condition_matrix_assessed") is not True:
                errors.append("CONFIRMATION_ONLY_CONDITION_ASSESSMENT_REQUIRED: 必须判断条件矩阵适用性")
            if set(checkpoint.get("requirement_aspects_scanned", [])) != set(REQUIREMENT_ASPECTS):
                errors.append("CONFIRMATION_ONLY_REQUIREMENT_SCAN_INCOMPLETE: 必须扫描十类需求要素")
            if set(checkpoint.get("test_dimensions_scanned", [])) != set(DIMENSIONS):
                errors.append("CONFIRMATION_ONLY_DIMENSION_SCAN_INCOMPLETE: 必须完整扫描八类测试维度")
            if checkpoint.get("downstream_artifacts_generated") != []:
                errors.append("CONFIRMATION_ONLY_DOWNSTREAM_ARTIFACT_FORBIDDEN: 确认前不得生成下游测试产物")
        if data.get("risks"):
            errors.append("CONFIRMATION_ONLY_FORMAL_RISK_FORBIDDEN: 确认前仅记录 risk_directions，不生成正式 Risk")
        if not isinstance(data.get("risk_directions"), list):
            errors.append("CONFIRMATION_ONLY_RISK_DIRECTIONS_REQUIRED: 必须记录风险方向")
        if not isinstance(data.get("test_dimension_assessment"), list):
            errors.append("CONFIRMATION_ONLY_DIMENSION_ASSESSMENT_REQUIRED: 必须保存八类测试维度扫描")
        if not isinstance(data.get("condition_matrix_applicability"), dict):
            errors.append("CONFIRMATION_ONLY_CONDITION_APPLICABILITY_REQUIRED: 必须保存条件矩阵适用性")
        for point in confirmations:
            missing_details = [
                field for field in (
                    "question", "current_evidence", "uncertainty", "impact_scope", "current_handling",
                )
                if not point.get(field)
            ]
            if missing_details:
                errors.append(
                    f"CONFIRMATION_DETAILS_INCOMPLETE: {point.get('confirmation_id')} 缺少 {missing_details}"
                )
    assessment = data.get("test_dimension_assessment")
    if assessment is not None:
        items = assessment if isinstance(assessment, list) else []
        dimensions = [item.get("dimension") for item in items if isinstance(item, dict)]
        if len(dimensions) != len(set(dimensions)):
            errors.append("DUPLICATE_TEST_DIMENSION_ASSESSMENT: 每个测试分类维度只能出现一次")
        if set(dimensions) != set(DIMENSIONS):
            errors.append("TEST_DIMENSION_ASSESSMENT_INCOMPLETE: 必须完整扫描固定八个测试分类维度")
        for item in items:
            if not isinstance(item, dict):
                continue
            dimension, status = item.get("dimension"), item.get("status")
            reason = str(item.get("reason", "")).strip()
            evidence = item.get("evidence_references", [])
            if status not in TEST_DIMENSION_STATUSES:
                errors.append(f"INVALID_TEST_DIMENSION_STATUS: {dimension} status={status}")
            if status == "not_applicable" and not reason:
                errors.append(f"NOT_APPLICABLE_DIMENSION_WITHOUT_REASON: {dimension}")
            if status == "not_applicable" and not (set(item.get("fact_ids", [])) & fact_ids or evidence):
                errors.append(f"NOT_APPLICABLE_DIMENSION_WITHOUT_REASON: {dimension} 缺少范围 Fact 或 Evidence")
            if status == "explicitly_excluded" and not evidence:
                errors.append(f"EXCLUDED_DIMENSION_WITHOUT_EVIDENCE: {dimension}")
            if status == "pending" and not (set(item.get("confirmation_ids", [])) & confirmation_ids):
                errors.append(f"PENDING_DIMENSION_WITHOUT_CONFIRMATION: {dimension}")
            if status == "blocked" and not reason:
                errors.append(f"BLOCKED_DIMENSION_WITHOUT_REASON: {dimension}")
            if status == "blocked" and not (
                set(item.get("confirmation_ids", [])) & confirmation_ids
                or set(item.get("fact_ids", [])) & fact_ids
            ):
                errors.append(f"BLOCKED_DIMENSION_WITHOUT_REASON: {dimension} 缺少 Confirmation 或 Missing Fact")
    applicability = data.get("condition_matrix_applicability")
    if isinstance(applicability, dict):
        status = applicability.get("status")
        if status == "required" and not isinstance(data.get("condition_matrix"), dict):
            errors.append("CONDITION_MATRIX_REQUIRED_FOR_MULTI_DIMENSION_REQUIREMENT: required 时必须提供 condition_matrix")
        if status == "required" and not applicability.get("dimension_ids"):
            errors.append("CONDITION_MATRIX_REQUIRED_FOR_MULTI_DIMENSION_REQUIREMENT: required 时必须提供 dimension_ids")
        if status == "not_required" and not str(applicability.get("reason", "")).strip():
            errors.append("CONDITION_MATRIX_REQUIRED_FOR_MULTI_DIMENSION_REQUIREMENT: not_required 必须说明无组合差异的依据")
        if status == "blocked" and not (
            set(applicability.get("confirmation_ids", [])) & confirmation_ids
            or set(applicability.get("missing_fact_ids", [])) & fact_ids
        ):
            errors.append("CONDITION_MATRIX_REQUIRED_FOR_MULTI_DIMENSION_REQUIREMENT: blocked 必须关联 Confirmation 或 Missing Fact")
    for disposition in data.get("scope_dispositions", []) if isinstance(data.get("scope_dispositions"), list) else []:
        if not isinstance(disposition, dict):
            continue
        status = disposition.get("status")
        evidence = disposition.get("evidence_references", [])
        if status == "explicitly_excluded" and not evidence:
            errors.append(f"TEST_SCOPE_EXCLUDED_WITHOUT_EVIDENCE: {disposition.get('scope_item')}")
        if status == "pending" and not (set(disposition.get("confirmation_ids", [])) & confirmation_ids):
            errors.append(f"TEST_SCOPE_EXCLUDED_WITHOUT_EVIDENCE: {disposition.get('scope_item')} pending 未关联 Confirmation")
        if status == "blocked" and not str(disposition.get("reason", "")).strip():
            errors.append(f"TEST_SCOPE_EXCLUDED_WITHOUT_EVIDENCE: {disposition.get('scope_item')} blocked 缺少原因")
    condition_matrix = data.get("condition_matrix")
    if data.get("condition_matrix_required") is True and not isinstance(condition_matrix, dict):
        errors.append("CONDITION_MATRIX_REQUIRED: 明确列出两个及以上条件维度时必须建立 condition_matrix")
    if isinstance(condition_matrix, dict):
        dimensions = condition_matrix.get("dimensions", []) if isinstance(condition_matrix.get("dimensions"), list) else []
        dimension_ids, dimension_errors = _unique_ids(dimensions, "dimension_id")
        errors.extend(f"CONDITION_MATRIX_REQUIRED: {item}" for item in dimension_errors)
        dimension_values = {
            item.get("dimension_id"): set(item.get("values", []))
            for item in dimensions if isinstance(item, dict) and isinstance(item.get("dimension_id"), str)
        }
        required = condition_matrix.get("required_combinations", []) if isinstance(condition_matrix.get("required_combinations"), list) else []
        excluded = condition_matrix.get("excluded_combinations", []) if isinstance(condition_matrix.get("excluded_combinations"), list) else []
        combination_ids, combination_errors = _unique_ids([*required, *excluded], "combination_id")
        errors.extend(f"CONDITION_MATRIX_REQUIRED: {item}" for item in combination_errors)
        used_values = {dimension_id: set() for dimension_id in dimension_ids}
        required_keys: dict[str, str] = {}
        excluded_keys: dict[str, str] = {}
        for collection_name, combination in [
            *(("required", item) for item in required),
            *(("excluded", item) for item in excluded),
        ]:
            combination_id = combination.get("combination_id")
            values = combination.get("dimension_values")
            if not isinstance(values, dict) or set(values) != dimension_ids:
                errors.append(
                    f"CONDITION_MATRIX_REQUIRED: {combination_id} dimension_values 必须完整对应全部维度"
                )
                continue
            for dimension_id, value in values.items():
                if not isinstance(value, str) or value not in dimension_values.get(dimension_id, set()):
                    errors.append(
                        f"CONDITION_MATRIX_REQUIRED: {combination_id}.{dimension_id} 枚举值非法：{value}"
                    )
                else:
                    used_values[dimension_id].add(value)
            key = _condition_key(values)
            if key is not None:
                target = required_keys if collection_name == "required" else excluded_keys
                if key in target:
                    errors.append(
                        f"CONDITION_COMBINATION_DUPLICATED: {combination_id} 与 {target[key]} 的 dimension_values 重复"
                    )
                else:
                    target[key] = str(combination_id)
        for key in sorted(set(required_keys) & set(excluded_keys)):
            errors.append(
                f"CONDITION_COMBINATION_DUPLICATED: {required_keys[key]} 同时出现在 required 和 excluded：{key}"
            )
        expected, generation_errors = _generate_expected_condition_combinations(
            condition_matrix, dimension_ids, dimension_values
        )
        errors.extend(generation_errors)
        actual_keys = set(required_keys) | set(excluded_keys)
        for key in sorted(set(expected) - actual_keys):
            errors.append(f"REQUIRED_COMBINATION_UNCOVERED: grouped_cross_product 缺少组合 {key}")
        for key in sorted(actual_keys - set(expected)):
            combination_id = required_keys.get(key) or excluded_keys.get(key)
            errors.append(f"UNEXPECTED_CONDITION_COMBINATION: {combination_id} 不在 grouped_cross_product 生成集合：{key}")
        for dimension_id, values in dimension_values.items():
            for value in sorted(values - used_values.get(dimension_id, set())):
                errors.append(
                    f"ENUMERATION_VALUE_UNCOVERED: {dimension_id}={value} 未进入 required/excluded combination"
                )
        for combination in required:
            if workflow_stage != "confirmation_only" and not combination.get("covered_by_tc_ids"):
                errors.append(
                    f"REQUIRED_COMBINATION_UNCOVERED: {combination.get('combination_id')} 未映射 TC"
                )
        for combination in excluded:
            if not str(combination.get("exclusion_reason", "")).strip():
                errors.append(
                    f"COMBINATION_EXCLUSION_WITHOUT_REASON: {combination.get('combination_id')} 缺少 exclusion_reason"
                )
        summary = condition_matrix.get("coverage_summary", {})
        expected_summary = {
            "required_combination_count": len(required),
            "covered_combination_count": sum(bool(item.get("covered_by_tc_ids")) for item in required),
            "excluded_combination_count": len(excluded),
        }
        for field, expected_count in expected_summary.items():
            if summary.get(field) != expected_count:
                errors.append(
                    f"CONDITION_MATRIX_REQUIRED: coverage_summary.{field}={summary.get(field)} 与实际 {expected_count} 不一致"
                )
    requirement = data.get("data_validation_required")
    method = data.get("recommended_validation_method")
    reason = str(data.get("data_validation_reason", ""))
    indicator_accuracy = any(token in reason for token in ("指标准确", "计算准确", "数值正确", "金额", "比例", "收益率", "完成率"))
    if requirement == "not_required" and method != "not_applicable":
        errors.append("not_required 数据验证必须推荐 not_applicable")
    if indicator_accuracy and method not in {"sql", "mixed"}:
        errors.append("指标准确性需求默认必须推荐 SQL")
    if requirement == "blocked" and method != "blocked":
        errors.append("blocked 数据验证必须推荐 blocked")
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
        source_reference = str(fact.get("source_reference", "")).strip()
        if category == "confirmed" and fact.get("source_type") in {"inference", "code_context", "screenshot", "historical_defect"}:
            errors.append(f"确定事实 {fact_id} 不得仅使用限制性来源 {fact.get('source_type')}")
        if category == "confirmed" and fact.get("confidence") == "low":
            errors.append(f"确定事实 {fact_id} confidence 不得为 low")
        if category == "confirmed" and (not source_reference or re.fullmatch(r"(?:推测|猜测|根据名称判断)[。.]?", source_reference)):
            errors.append(f"确定事实 {fact_id} 缺少可验证 source_reference")
        if category == "missing" and not fact.get("handling"):
            errors.append(f"缺失事实 {fact_id} 必须说明 handling")
        evidence_references = fact.get("evidence_references")
        errors.extend(_validate_evidence_references(evidence_references, f"事实 {fact_id}", category == "confirmed", evidence_root=evidence_root))
        statement = str(fact.get("statement", ""))
        excerpts = [
            str(evidence.get("excerpt", "")) for evidence in evidence_references or []
            if isinstance(evidence, dict) and evidence.get("evidence_status") == "current"
        ]
        if category == "confirmed" and excerpts:
            for behavior_category, markers in BEHAVIOR_EVIDENCE_CATEGORIES:
                if not any(marker in statement for marker in markers):
                    continue
                if not any(any(marker in excerpt for marker in markers) for excerpt in excerpts):
                    evidence_boundary = "结构/容量" if all(
                        any(marker in excerpt for marker in (*STRUCTURE_EVIDENCE_MARKERS, *CAPABILITY_EVIDENCE_MARKERS))
                        for excerpt in excerpts
                    ) else "当前"
                    errors.append(
                        f"EVIDENCE_CAPABILITY_CANNOT_CONFIRM_BEHAVIOR: 事实 {fact_id} 的{evidence_boundary}证据"
                        f"不能确认 {behavior_category} 行为"
                    )
        if isinstance(evidence_references, list) and not any(
            isinstance(evidence, dict) and evidence.get("source_type") == fact.get("source_type")
            for evidence in evidence_references
        ):
            errors.append(f"事实 {fact_id} 主 source_type 必须与至少一条 Evidence source_type 一致")
    confirmation_fact_ids = {
        fact_id for point in confirmations for fact_id in point.get("fact_ids", []) if isinstance(fact_id, str)
    }
    _, confirmation_id_errors = _unique_ids(confirmations, "confirmation_id")
    errors.extend(confirmation_id_errors)
    facts_by_id = {
        fact.get("fact_id"): fact for fact in facts if isinstance(fact.get("fact_id"), str)
    }
    for point in confirmations:
        point_id = point.get("confirmation_id")
        linked = point.get("fact_ids", [])
        if not linked:
            errors.append(f"Confirmation {point_id} fact_ids 不能为空")
        unknown = set(linked) - fact_ids
        if unknown:
            errors.append(f"Confirmation {point_id} 引用不存在 Fact: {sorted(unknown)}")
        if point.get("status") == "resolved":
            if not point.get("resolution") or not point.get("resolved_at") or not point.get("resolution_evidence_references"):
                errors.append(f"Confirmation {point_id} resolved 必须提供 resolution、resolution_evidence_references 和 resolved_at")
            if point.get("resolved_at") and not valid_generated_at(point.get("resolved_at")):
                errors.append(f"Confirmation {point_id} resolved_at 格式非法")
            errors.extend(_validate_evidence_references(point.get("resolution_evidence_references"), f"Confirmation {point_id} resolution", True, evidence_root=evidence_root))
            unresolved_linked = [
                fact_id for fact_id in linked
                if facts_by_id.get(fact_id, {}).get("affects_core_expectation") is True
                and facts_by_id.get(fact_id, {}).get("category") in {"missing", "conflicting"}
            ]
            if unresolved_linked:
                errors.append(
                    f"Confirmation {point_id} 已 resolved，但关联核心 Fact 仍为 missing/conflicting：{unresolved_linked}"
                )
        if point.get("status") == "skipped":
            if not point.get("skip_reason") or not point.get("decision_evidence"):
                errors.append(f"Confirmation {point_id} skipped 必须提供 skip_reason 和 decision_evidence")
            errors.extend(_validate_evidence_references(point.get("decision_evidence"), f"Confirmation {point_id} decision", evidence_root=evidence_root))
    for fact_id, category in categories.items():
        if category == "conflicting" and fact_id not in confirmation_fact_ids:
            errors.append(f"冲突事实 {fact_id} 未关联待确认点")
        if category == "missing" and facts and next((fact for fact in facts if fact.get("fact_id") == fact_id), {}).get("affects_core_expectation"):
            linked_points = [point for point in confirmations if fact_id in point.get("fact_ids", [])]
            if not linked_points or not any(point.get("severity") == "blocking" for point in linked_points):
                errors.append(f"核心缺失事实 {fact_id} 必须关联 blocking Confirmation")
    for criterion in criteria:
        linked = criterion.get("fact_ids", [])
        if not linked:
            errors.append(f"核心验收 {criterion.get('criterion_id')} 未关联 fact_id")
        for fact_id in linked:
            if fact_id not in fact_ids:
                errors.append(f"验收标准引用不存在事实：{fact_id}")
            elif categories.get(fact_id) != "confirmed":
                errors.append(f"非确定事实 {fact_id} 不得进入确定性验收标准")
        criterion_evidence = criterion.get("evidence_references")
        errors.extend(_validate_evidence_references(criterion_evidence, f"验收标准 {criterion.get('criterion_id')}", True, evidence_root=evidence_root))
        linked_evidence = {
            evidence_reference_identity(evidence)
            for fact_id in linked
            for evidence in facts_by_id.get(fact_id, {}).get("evidence_references", [])
            if isinstance(evidence, dict)
        }
        unrelated = {
            evidence_reference_identity(evidence)
            for evidence in criterion_evidence or [] if isinstance(evidence, dict)
        } - linked_evidence
        if unrelated:
            errors.append(
                f"ACCEPTANCE_EVIDENCE_NOT_DERIVED_FROM_FACT: 验收标准 {criterion.get('criterion_id')} 的证据未派生自关联 Fact"
            )
    return list(dict.fromkeys(errors))


def validate_diff_model(data: dict[str, Any], *, evidence_root: Path | None = None) -> list[str]:
    errors = validate_schema_shape(data, diff_schema("0.0.0"))
    changes = data.get("change_items", []) if isinstance(data.get("change_items"), list) else []
    changed_files = {
        item.get("path") for item in data.get("changed_files", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    change_ids, id_errors = _unique_ids(changes, "change_id")
    errors.extend(id_errors)
    for change in changes:
        evidence_references = change.get("evidence_references")
        if isinstance(evidence_references, list) and any(
            not isinstance(evidence, dict) or evidence.get("source_type") not in {"diff", "code_context"}
            for evidence in evidence_references
        ):
            errors.append(f"变更 {change.get('change_id')} Evidence source_type 只允许 diff/code_context")
        errors.extend(_validate_evidence_references(
            evidence_references,
            f"变更 {change.get('change_id')}",
            True,
            changed_files=changed_files,
            expected_change_file=change.get("file"),
            evidence_root=evidence_root,
        ))
    chains = data.get("impact_chains", []) if isinstance(data.get("impact_chains"), list) else []
    _, chain_errors = _unique_ids(chains, "chain_id")
    errors.extend(chain_errors)
    for chain in chains:
        unknown = set(chain.get("change_ids", [])) - change_ids
        if unknown:
            errors.append(f"影响链 {chain.get('chain_id')} 引用不存在 change_id：{sorted(unknown)}")
        errors.extend(_validate_evidence_references(chain.get("evidence_references"), f"影响链 {chain.get('chain_id')}", True, evidence_root=evidence_root))
    diff_risks = data.get("risks", []) if isinstance(data.get("risks"), list) else []
    diff_risk_ids, risk_errors = _unique_ids(diff_risks, "risk_id")
    errors.extend(risk_errors)
    for risk in diff_risks:
        unknown = set(risk.get("change_ids", [])) - change_ids
        if unknown:
            errors.append(f"Diff 风险 {risk.get('risk_id')} 引用不存在 change_id：{sorted(unknown)}")
        errors.extend(_validate_evidence_references(risk.get("evidence_references"), f"Diff 风险 {risk.get('risk_id')}", risk.get("evidence_state") == "已确认", evidence_root=evidence_root))
    for coverage in data.get("coverage_results", []) if isinstance(data.get("coverage_results"), list) else []:
        status = coverage.get("coverage_status")
        if status not in COVERAGE_STATUSES:
            errors.append(f"覆盖状态非法：{status}")
        unknown = set(coverage.get("change_ids", [])) - change_ids
        if unknown:
            errors.append(f"覆盖结果引用不存在 change_id：{sorted(unknown)}")
        if status in {"疑似遗漏", "实现不一致"} and not coverage.get("risk_ids"):
            errors.append(f"{status} 的需求点必须关联风险")
        unknown_risks = set(coverage.get("risk_ids", [])) - diff_risk_ids
        if unknown_risks:
            errors.append(f"覆盖结果引用不存在 Diff 风险：{sorted(unknown_risks)}")
    defects = data.get("suspected_defects", []) if isinstance(data.get("suspected_defects"), list) else []
    _, defect_errors = _unique_ids(defects, "defect_id")
    errors.extend(defect_errors)
    for defect in defects:
        defect_id = defect.get("defect_id")
        if set(defect.get("change_ids", [])) - change_ids:
            errors.append(f"疑似缺陷 {defect_id} 引用不存在 change_id")
        if defect.get("observed_behavior") == defect.get("expected_behavior"):
            errors.append(f"疑似缺陷 {defect_id} observed 与 expected 不得相同")
        if defect.get("confidence") == "low":
            errors.append(f"低置信度项 {defect_id} 只能记录为风险")
        errors.extend(_validate_evidence_references(defect.get("evidence_references"), f"疑似缺陷 {defect_id}", True, evidence_root=evidence_root))
    return list(dict.fromkeys(errors))


def validate_risk_matrix(data: dict[str, Any], *, evidence_root: Path | None = None) -> list[str]:
    errors = validate_schema_shape(data, risk_matrix_schema("0.0.0"))
    risks = data.get("risk_items", []) if isinstance(data.get("risk_items"), list) else []
    _, id_errors = _unique_ids(risks, "risk_id")
    errors.extend(id_errors)
    risk_by_id = {item.get("risk_id"): item for item in risks}
    vague_assertions = {"验证功能正常", "验证是否正常", "确认功能正常", "测试功能", "验证风险", "功能正常"}
    for item in risks:
        risk_id = item.get("risk_id")
        assertion = str(item.get("core_assertion", "")).strip()
        if assertion in vague_assertions or len(assertion) < 8 or (assertion.startswith("验证") and len(assertion) < 12):
            errors.append(f"Risk {risk_id} core_assertion 必须是可观察、可判定的断言")
        disposition = item.get("disposition_status")
        target = item.get("merged_into_risk_id") or next(iter(item.get("merged_to", [])), None)
        blocked_ids = item.get("blocked_by_confirmation_ids") or item.get("confirmation_ids", [])
        decisions = item.get("decision_evidence_references") or item.get("decision_evidence", [])
        if disposition == "merged":
            if target not in risk_by_id:
                errors.append(f"merged Risk {risk_id} 引用不存在的目标 {target}")
            if target == risk_id:
                errors.append(f"merged Risk {risk_id} 不得合并到自身")
            if not item.get("merge_reason"):
                errors.append(f"merged Risk {risk_id} 缺少 merge_reason")
            if item.get("testcase_ids"):
                errors.append(f"merged Risk {risk_id} 不得直接关联 TC")
        if disposition == "blocked" and (not blocked_ids or not item.get("blocked_reason")):
            errors.append(f"blocked Risk {risk_id} 缺少阻塞确认点或原因")
        if disposition == "deferred" and (not all(item.get(k) for k in ("defer_reason", "defer_until", "owner")) or not decisions):
            errors.append(f"deferred Risk {risk_id} 缺少延期决定合同")
        if disposition == "accepted" and (not all(item.get(k) for k in ("acceptance_reason", "accepted_by", "accepted_at", "residual_impact")) or not decisions):
            errors.append(f"accepted Risk {risk_id} 缺少接受决定合同")
        if disposition == "not_applicable" and not (item.get("not_applicable_reason") and item.get("scope_evidence_references")):
            errors.append(f"not_applicable Risk {risk_id} 缺少原因或范围证据")
        if disposition == "resolved" and not all(item.get(k) for k in ("resolution", "resolved_at")):
            errors.append(f"resolved Risk {risk_id} 缺少解决结论或时间")
    for start, item in risk_by_id.items():
        if item.get("disposition_status") != "merged":
            continue
        seen: set[str] = set()
        current = start
        while current in risk_by_id and risk_by_id[current].get("disposition_status") == "merged":
            if current in seen:
                errors.append(f"merged Risk 链存在循环：{start}")
                break
            seen.add(current)
            current_item = risk_by_id[current]
            current = current_item.get("merged_into_risk_id") or next(iter(current_item.get("merged_to", [])), "")
    for risk in risks:
        if risk.get("test_priority") not in TEST_PRIORITIES:
            errors.append(f"风险 {risk.get('risk_id')} 优先级非法")
        if risk.get("test_priority") == "P0" and not risk.get("testcase_ids"):
            errors.append(f"P0 风险 {risk.get('risk_id')} 未映射 TC")
        disposition = risk.get("disposition_status")
        if not risk.get("testcase_ids") and disposition not in RISK_DISPOSITIONS:
            errors.append(f"风险 {risk.get('risk_id')} 没有 TC 且缺少处置状态")
        if disposition == "covered" and not risk.get("testcase_ids"):
            errors.append(f"covered 风险 {risk.get('risk_id')} 必须关联 TC")
        if disposition == "merged" and not risk.get("merged_to"):
            errors.append(f"merged 风险 {risk.get('risk_id')} 必须引用目标 Risk/TC")
        if disposition == "accepted" and not risk.get("decision_evidence"):
            errors.append(f"accepted 风险 {risk.get('risk_id')} 必须提供决策证据")
        if disposition == "blocked" and not risk.get("confirmation_ids"):
            errors.append(f"blocked 风险 {risk.get('risk_id')} 必须关联待确认点")
        if disposition == "merged" and risk.get("risk_id") in set(risk.get("merged_to", [])):
            errors.append(f"merged 风险 {risk.get('risk_id')} 不得合并到自身")
        if disposition == "accepted" and any(not isinstance(item, dict) for item in risk.get("decision_evidence", [])):
            errors.append(f"accepted 风险 {risk.get('risk_id')} decision_evidence 必须是 Evidence Reference")
        for tc_id in risk.get("testcase_ids", []):
            if not re.fullmatch(TC_PATTERN, str(tc_id)):
                errors.append(f"风险 {risk.get('risk_id')} 引用非法 TC：{tc_id}")
        if risk.get("business_entry") not in risk.get("business_entries", []):
            errors.append(f"风险 {risk.get('risk_id')} 主 business_entry 必须包含在 business_entries")
        errors.extend(_validate_evidence_references(risk.get("evidence_references"), f"风险 {risk.get('risk_id')}", risk.get("evidence_state") == "已确认", evidence_root=evidence_root))
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
    shared_scope = data.get("shared_entry_scope") if isinstance(data.get("shared_entry_scope"), dict) else None
    shared_scope_id = shared_scope.get("scope_id") if shared_scope else None
    shared_scope_paths: set[tuple[str, str, str]] = set()
    if shared_scope:
        group_names: list[str] = []
        abbreviated_markers = ("上述", "同上", "前述", "等入口", "其余入口", "其他入口", "同前")
        for group in shared_scope.get("groups", []):
            group_name = str(group.get("group_name", ""))
            group_names.append(group_name)
            subgroup_names: list[str] = []
            for subgroup in group.get("subgroups", []):
                subgroup_name = str(subgroup.get("subgroup_name", ""))
                subgroup_names.append(subgroup_name)
                entry_names = [str(entry.get("entry_name", "")) for entry in subgroup.get("entries", [])]
                if len(entry_names) != len(set(entry_names)):
                    errors.append(f"SHARED_ENTRY_SCOPE_DUPLICATE_ENTRY: {group_name}/{subgroup_name} 入口名称重复")
                for entry_name in entry_names:
                    path = (group_name, subgroup_name, entry_name)
                    if path in shared_scope_paths:
                        errors.append(f"SHARED_ENTRY_SCOPE_DUPLICATE_PATH: {'/'.join(path)}")
                    shared_scope_paths.add(path)
                    if any(marker in entry_name for marker in abbreviated_markers):
                        errors.append(f"SHARED_ENTRY_SCOPE_ABBREVIATED: {'/'.join(path)} 必须展开完整入口")
            if len(subgroup_names) != len(set(subgroup_names)):
                errors.append(f"SHARED_ENTRY_SCOPE_DUPLICATE_SUBGROUP: {group_name} 分组名称重复")
        if len(group_names) != len(set(group_names)):
            errors.append("SHARED_ENTRY_SCOPE_DUPLICATE_GROUP: 一级范围分组名称重复")
        if len(shared_scope_paths) < SHARED_ENTRY_SCOPE_MIN_ENTRIES:
            errors.append(
                f"SHARED_ENTRY_SCOPE_REQUIRES_SIX_OR_MORE: 共享入口范围至少需要 {SHARED_ENTRY_SCOPE_MIN_ENTRIES} 个完整入口，实际 {len(shared_scope_paths)}"
            )
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
        secondary = case.get("secondary_dimensions", [])
        if case.get("dimension") in secondary:
            errors.append(f"SECONDARY_DIMENSION_DUPLICATES_PRIMARY: {tc_id}")
        if len(secondary) != len(set(secondary)):
            errors.append(f"DUPLICATE_SECONDARY_DIMENSION: {tc_id}")
        for dimension in secondary:
            if dimension not in DIMENSIONS:
                errors.append(f"UNKNOWN_SECONDARY_DIMENSION: {tc_id} {dimension}")
        common = case.get("common_entry")
        modules = bool(case.get("module_level_1") and case.get("module_level_2"))
        if bool(common) == modules:
            errors.append(f"{tc_id} 必须在 common_entry 与两级模块结构中二选一")
        branches = case.get("entry_branches", [])
        scope_reference = case.get("shared_entry_scope_id")
        if branches and len(branches) >= SHARED_ENTRY_SCOPE_MIN_ENTRIES:
            errors.append(
                f"SIX_OR_MORE_ENTRIES_REQUIRE_SHARED_SCOPE: {tc_id} 有 {len(branches)} 个入口，必须使用 shared_entry_scope 公共步骤结构"
            )
        if scope_reference:
            if not shared_scope or scope_reference != shared_scope_id:
                errors.append(f"SHARED_ENTRY_SCOPE_REFERENCE_INVALID: {tc_id} 引用不存在的 {scope_reference}")
            if branches:
                errors.append(f"SHARED_ENTRY_SCOPE_MIXED_WITH_BRANCHES: {tc_id} 不得同时使用 shared_entry_scope 与 entry_branches")
        if branches:
            if case.get("steps") or case.get("expected_results"):
                errors.append(f"{tc_id} 多入口模型顶层 steps 和 expected_results 必须为空")
            branch_names = [branch.get("entry_name") for branch in branches]
            branch_ids = [branch.get("branch_id") for branch in branches]
            if len(branch_names) != len(set(branch_names)):
                errors.append(f"{tc_id} 入口分支 entry_name 必须唯一")
            if len(branch_ids) != len(set(branch_ids)):
                errors.append(f"{tc_id} 入口分支 branch_id 必须唯一")
            for branch in branches:
                if re.fullmatch(r"(?:入口|页面|弹窗)[A-Z一二三四五六七八九十0-9]+", str(branch.get("entry_name"))):
                    errors.append(f"ENTRY_BRANCH_WITHOUT_REAL_ENTRY: {tc_id} 入口名称缺少业务语义：{branch.get('entry_name')}")
                if not str(branch.get("branch_id", "")).startswith(f"{tc_id}-B"):
                    errors.append(f"{tc_id} 分支 branch_id 必须使用 {tc_id}-B 前缀")
                errors.extend(_validate_step_expectations(tc_id, branch.get("steps", []), branch.get("expected_results", []), "entry_branches"))
                if case.get("core_deduplication_key") and not any(
                    str(branch.get("entry_name", "")) in str(step) for step in branch.get("steps", [])
                ):
                    errors.append(
                        f"ENTRY_BRANCH_DIAGNOSTIC_NOT_INDEPENDENT: {tc_id} 的 {branch.get('branch_id')} 步骤未标明真实入口"
                    )
        else:
            if not case.get("test_point") or not case.get("steps") or not case.get("expected_results"):
                errors.append(f"{tc_id} 缺少唯一测试点、步骤或预期")
        steps_text = " ".join(str(step) for step in case.get("steps", []))
        entry_marker_count = sum(steps_text.count(marker) for marker in ("页面", "弹窗", "页签", "下钻", "入口"))
        explicit_multi_entry = bool(re.search(r"分别(?:打开|进入)|依次(?:打开|进入)|在多个|所有相关", steps_text))
        if not branches and not scope_reference and case.get("common_entry") and (
            entry_marker_count >= 2 and bool(re.search(r"[/、，,]|分别|以及|多个|三个|各个", steps_text))
            or entry_marker_count >= 1 and explicit_multi_entry
        ):
            errors.append(f"{tc_id} 可能将多个入口压在同一步骤，必须填写 entry_branches 并拆成平级分支")
        errors.extend(_validate_step_expectations(tc_id, case.get("steps", []), case.get("expected_results", []), "expected_results"))
        for action in case.get("actions", []):
            errors.extend(_validate_step_expectations(tc_id, [action.get("action")], action.get("expected_results", []), f"actions.{action.get('step_id')}"))
        factors = case.get("core_deduplication_factors")
        core_key = case.get("core_deduplication_key")
        if bool(factors) != bool(core_key):
            errors.append(f"{tc_id} core_deduplication_factors 与 core_deduplication_key 必须同时提供")
        if isinstance(factors, dict) and core_key:
            expected_core_key = compute_core_deduplication_key(factors)
            if core_key != expected_core_key:
                errors.append(f"{tc_id} core_deduplication_key 与确定性计算结果不一致")
        if bool(case.get("split_reason")) != bool(case.get("split_reason_detail")):
            errors.append(f"{tc_id} 拆分 TC 时必须同时提供 split_reason 与 split_reason_detail")
        coverage_ids = [
            item.get("combination_id") for item in case.get("condition_coverage", [])
            if isinstance(item, dict)
        ]
        if len(coverage_ids) != len(set(coverage_ids)):
            errors.append(f"{tc_id} condition_coverage.combination_id 重复")
    cases_by_core_key: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        if case.get("core_deduplication_key"):
            cases_by_core_key.setdefault(str(case["core_deduplication_key"]), []).append(case)
    for same_core_cases in cases_by_core_key.values():
        if len(same_core_cases) < 2:
            continue
        duplicate_ids = [str(case.get("tc_id")) for case in same_core_cases]
        errors.append(
            f"DUPLICATE_TC_SPLIT_BY_ENTRY_ONLY: {duplicate_ids} 的 core_deduplication_key 相同"
        )
        errors.append(
            f"IDENTICAL_RULE_NOT_MERGED_TO_ENTRY_BRANCHES: {duplicate_ids} 应合并为一个 TC 的平级 entry_branches"
        )
    if shared_scope:
        expected_scope_tcs = {str(item) for item in shared_scope.get("applies_to_tc_ids", [])}
        actual_scope_tcs = {str(case.get("tc_id")) for case in cases if case.get("shared_entry_scope_id") == shared_scope_id}
        if expected_scope_tcs != actual_scope_tcs:
            errors.append(
                f"SHARED_ENTRY_SCOPE_TC_MISMATCH: applies_to_tc_ids={sorted(expected_scope_tcs)} 实际引用={sorted(actual_scope_tcs)}"
            )
        unknown_scope_tcs = expected_scope_tcs - tc_ids
        if unknown_scope_tcs:
            errors.append(f"SHARED_ENTRY_SCOPE_UNKNOWN_TC: {sorted(unknown_scope_tcs)}")
    branches = {branch.get("branch_id") for case in cases for branch in case.get("entry_branches", [])}
    actual_branch_count = len(branches)
    if "branch_count" in data and data.get("branch_count") != actual_branch_count:
        errors.append(f"branch_count={data.get('branch_count')} 与实际 {actual_branch_count} 不一致")
    instances = data.get("execution_instances", []) if isinstance(data.get("execution_instances"), list) else []
    instance_ids, instance_errors = _unique_ids(instances, "execution_instance_id")
    errors.extend(instance_errors)
    if "execution_instance_count" in data and data.get("execution_instance_count") != len(instances):
        errors.append("execution_instance_count 与 execution_instances 数量不一致")
    for instance in instances:
        instance_id = instance.get("execution_instance_id")
        if instance.get("tc_id") not in tc_ids:
            errors.append(f"执行实例 {instance_id} 引用不存在 TC")
        if instance.get("branch_id") is not None and instance.get("branch_id") not in branches:
            errors.append(f"执行实例 {instance_id} 引用不存在 branch_id")
        if instance.get("tc_id") in tc_ids and any(case.get("entry_branches") for case in cases if case.get("tc_id") == instance.get("tc_id")) and not instance.get("branch_id"):
            errors.append(f"多入口执行实例 {instance_id} 必须填写 branch_id")
        if instance.get("rerun_of") is not None and instance.get("rerun_of") not in instance_ids:
            errors.append(f"执行实例 {instance_id} rerun_of 不存在")
        if instance.get("rerun_of") == instance_id:
            errors.append(f"执行实例 {instance_id} rerun_of 不得指向自身")
        if instance.get("execution_status") == "not_run" and any(instance.get(key) is not None and instance.get(key) != [] for key in ("executor", "executed_at", "execution_evidence")):
            errors.append(f"执行实例 {instance_id} not_run 不得伪造执行信息")
        if instance.get("execution_status") != "not_run" and not isinstance(instance.get("execution_evidence"), dict):
            errors.append(f"执行实例 {instance_id} 没有实际执行证据，只允许 not_run")
        evidence = instance.get("execution_evidence")
        if isinstance(evidence, dict):
            required = {"evidence_type", "path", "content_hash", "captured_at"}
            if not required.issubset(evidence):
                errors.append(f"执行实例 {instance_id} 执行证据字段不完整")
            if evidence.get("evidence_type") not in {"screenshot", "log", "report", "manual_record"}:
                errors.append(f"执行实例 {instance_id} evidence_type 非法")
            if not re.fullmatch(r"^sha256:[0-9a-fA-F]{64}$", str(evidence.get("content_hash", ""))):
                errors.append(f"执行实例 {instance_id} content_hash 非法")
            if not re.fullmatch(CAPTURED_AT_PATTERN, str(evidence.get("captured_at", ""))):
                errors.append(f"执行实例 {instance_id} captured_at 格式非法")
        if instance.get("execution_status") == "failed" and not instance.get("defect_ids") and not instance.get("failure_description"):
            errors.append(f"失败执行实例 {instance_id} 必须关联 defect_id 或失败说明")
        if instance.get("execution_status") == "blocked" and not instance.get("confirmation_ids"):
            errors.append(f"阻塞执行实例 {instance_id} 必须关联 Confirmation")
        if instance.get("execution_status") == "skipped" and not instance.get("decision_evidence"):
            errors.append(f"跳过执行实例 {instance_id} 必须提供决策证据")
    for instance in instances:
        seen: set[str] = set()
        current = instance
        while current.get("rerun_of"):
            target = current.get("rerun_of")
            if target in seen:
                errors.append(f"执行实例 {instance.get('execution_instance_id')} rerun_of 形成循环")
                break
            seen.add(target)
            current = next((item for item in instances if item.get("execution_instance_id") == target), {})
    return list(dict.fromkeys(errors))


def _validate_step_expectations(tc_id: Any, steps: Any, expected_results: Any, location: str) -> list[str]:
    steps = steps if isinstance(steps, list) else []
    expected_results = expected_results if isinstance(expected_results, list) else []
    errors: list[str] = []
    if steps and len(expected_results) < len(steps):
        errors.append(f"{tc_id} {location} 每个步骤必须至少对应一个预期")
    for result in expected_results:
        vague = next((token for token in VAGUE_ASSERTIONS if token in str(result)), None)
        if vague and not re.search(r"(?:字段|状态|文案).*(?:异常.*正常|正常.*异常)", str(result)):
            errors.append(f"{tc_id} {location} 包含模糊断言或未确认口径：{vague}")
        quality_error = expectation_quality_error(str(result), " ".join(str(step) for step in steps))
        if quality_error:
            errors.append(f"{quality_error}: {tc_id} {location} 缺少可执行基线或 Oracle：{result}")
    return errors


def _validate_id_items(items: list[dict[str, Any]], field: str, label: str) -> list[str]:
    _, errors = _unique_ids(items, field)
    return [f"{label}{error}" for error in errors]


def validate_knowledge_table(data: dict[str, Any]) -> list[str]:
    errors = validate_schema_shape(data, knowledge_table_schema("0.0.0"))
    if data.get("full_name") != f"{data.get('database')}.{data.get('table_name')}":
        errors.append("full_name 必须等于 database.table_name")
    if data.get("schema_scope") == "partial" and data.get("current_ddl_path"):
        errors.append("partial schema_scope 不得填写整表 current_ddl_path")
    fields = data.get("fields", []) if isinstance(data.get("fields"), list) else []
    names = [item.get("name") for item in fields]
    if len(names) != len(set(names)):
        errors.append("字段名必须唯一")
    if data.get("status") == "active_confirmed" and not data.get("source_requirement_ids"):
        errors.append("active_confirmed 表知识必须关联来源需求")
    if data.get("schema_scope") == "complete" and (not fields or data.get("parse_warnings")):
        errors.append("complete 表必须有字段且不得包含解析 warning")
    expected_ordinals = list(range(1, len(fields) + 1))
    if [field.get("ordinal") for field in fields] != expected_ordinals:
        errors.append("字段 ordinal 必须从 1 开始连续递增")
    for field in fields:
        field_name = field.get("name")
        if field.get("generated") is True and not field.get("generated_expression"):
            errors.append(f"生成列 {field_name} 必须提供 generated_expression")
        if field.get("generated") is True and not field.get("generated_type"):
            errors.append(f"生成列 {field_name} 必须提供 generated_type")
        if field.get("generated") is False and field.get("generated_expression") is not None:
            errors.append(f"非生成列 {field_name} 的 generated_expression 必须为 null")
        if field.get("generated") is False and field.get("generated_type") is not None:
            errors.append(f"非生成列 {field_name} 的 generated_type 必须为 null")
    if data.get("schema_scope") == "complete":
        if data.get("unparsed_tail") is not None:
            errors.append("complete 表的 unparsed_tail 必须为 null")
        for field in fields:
            field_name = field.get("name")
            if field.get("generated") not in {True, False}:
                errors.append(f"complete 字段 {field_name} 必须明确 generated 状态")
            if field.get("auto_increment") not in {True, False}:
                errors.append(f"complete 字段 {field_name} 必须明确 auto_increment 状态")
            if not field.get("raw_fragment"):
                errors.append(f"complete 字段 {field_name} 必须保留 raw_fragment")
            if not field.get("parsed_tokens"):
                errors.append(f"complete 字段 {field_name} 必须保留 parsed_tokens")
            if field.get("unparsed_fragment") is not None:
                errors.append(f"complete 字段 {field_name} 不得包含 unparsed_fragment")
    if data.get("schema_scope") == "partial":
        has_unparsed = data.get("unparsed_tail") is not None or any(
            field.get("unparsed_fragment") is not None for field in fields
        )
        if has_unparsed and not data.get("parse_warnings"):
            errors.append("partial 表保留未解析内容时必须提供 parse_warnings")
        if data.get("status") == "active_confirmed" and not data.get("applicability_scope"):
            errors.append("active_confirmed partial 知识必须声明 applicability_scope")
        for field in fields:
            if field.get("nullable") is not None and "nullable" in field.get("unknown_fields", []):
                errors.append(f"partial 字段 {field.get('name')} 不得把未知 nullable 写成确定值")
    return list(dict.fromkeys(errors))


def validate_logic_version(data: dict[str, Any]) -> list[str]:
    errors = validate_schema_shape(data, logic_version_schema("0.0.0"))
    if data.get("status") == "active_confirmed" and not data.get("evidence_sources"):
        errors.append("active_confirmed 逻辑必须有关联证据")
    if data.get("supersedes") == data.get("logic_id"):
        errors.append("logic supersedes 不能指向自身")
    return list(dict.fromkeys(errors))


def validate_metric(data: dict[str, Any]) -> list[str]:
    errors = validate_schema_shape(data, metric_schema("0.0.0"))
    if data.get("status") == "active_confirmed" and not data.get("evidence_sources"):
        errors.append("active_confirmed 指标必须有关联证据")
    if any(token in str(data.get("business_definition", "")) for token in ("未知", "待确认", "猜测")):
        errors.append("指标业务定义不能包含未确认推断")
    return list(dict.fromkeys(errors))


def validate_requirement_knowledge(data: dict[str, Any]) -> list[str]:
    errors = validate_schema_shape(data, requirement_knowledge_schema("0.0.0"))
    if data.get("status") == "active_confirmed" and not data.get("effective_version"):
        errors.append("active_confirmed 需求知识必须有 effective_version")
    return list(dict.fromkeys(errors))


def validate_data_validation(data: dict[str, Any]) -> list[str]:
    errors = validate_schema_shape(data, data_validation_schema("0.0.0"))
    requirement = data.get("data_validation_required")
    method = data.get("validation_method")
    generation = data.get("sql_generation_status")
    queries = data.get("validation_queries", []) if isinstance(data.get("validation_queries"), list) else []
    recs = data.get("reconciliation_plans", []) if isinstance(data.get("reconciliation_plans"), list) else []
    reason = str(data.get("reason", ""))
    indicator_accuracy = any(token in reason for token in ("指标准确", "计算准确", "数值正确", "金额", "比例", "收益率", "完成率"))
    if requirement == "required" and method in {"sql", "mixed"} and not queries:
        errors.append("required 的 SQL 数据验证必须关联 validation_queries")
    if method == "cross_source_reconciliation" and not recs:
        errors.append("cross_source_reconciliation 必须关联 reconciliation_plans")
    if method == "mixed" and (not queries or not recs):
        errors.append("mixed 必须同时包含 SQL 和直接对数方案")
    if indicator_accuracy and method not in {"sql", "mixed"}:
        errors.append("指标准确性默认必须使用 SQL，页面对页面不能替代 SQL")
    if requirement == "not_required" and method != "not_applicable":
        errors.append("not_required 必须使用 not_applicable")
    if requirement == "blocked":
        if method != "blocked" or generation not in {"blocked", "partial"}:
            errors.append("blocked 数据验证必须标记 blocked 方法和 SQL 状态")
        if queries:
            errors.append("blocked 不得生成正式 validation_queries")
    if method == "cross_source_reconciliation":
        for rec in recs:
            if not rec.get("evidence_sources"):
                errors.append("直接对数方案必须提供明确证据来源")
    if generation == "not_required" and requirement not in {"not_required", "blocked"} and method != "cross_source_reconciliation":
        errors.append("SQL generation status=not_required 仅适用于不需要验证或阻塞")
    for query in queries:
        if query.get("status") in {"executed", "passed", "failed"} and not query.get("execution_evidence"):
            errors.append(f"{query.get('sql_id')} 没有执行结果证据，不得标记 {query.get('status')}")
    return list(dict.fromkeys(errors))


def validate_validation_sql(data: dict[str, Any], *, risk_ids: set[str] | None = None, tc_ids: set[str] | None = None, fact_ids: set[str] | None = None, confirmed_fact_ids: set[str] | None = None, knowledge_tables: dict[str, dict[str, Any]] | None = None) -> list[str]:
    errors = validate_schema_shape(data, validation_sql_schema("0.0.0"))
    items = data.get("sql_items", []) if isinstance(data.get("sql_items"), list) else []
    errors.extend(_validate_id_items(items, "sql_id", "SQL"))
    for item in items:
        if risk_ids is not None and not set(item.get("risk_ids", [])) <= risk_ids:
            errors.append(f"{item.get('sql_id')} 引用不存在 Risk")
        if tc_ids is not None and not set(item.get("tc_ids", [])) <= tc_ids:
            errors.append(f"{item.get('sql_id')} 引用不存在 TC")
        if item.get("execution_status") in {"executed", "passed", "failed"} and not item.get("execution_evidence"):
            errors.append(f"{item.get('sql_id')} 未有用户执行结果时不得标记 {item.get('execution_status')}")
        if not item.get("tc_ids"):
            errors.append(f"{item.get('sql_id')} 必须关联至少一个 TC")
        if not item.get("risk_ids"):
            errors.append(f"{item.get('sql_id')} 必须关联至少一个 Risk")
        covered = {entry.get("identifier") for entry in item.get("identifier_evidence", [])}
        used = set(item.get("tables", [])) | set(item.get("fields", [])) | set(item.get("parameters", [])) | set(item.get("metric_ids", []))
        if used - covered:
            errors.append(f"{item.get('sql_id')} 标识缺少证据：{sorted(used - covered)}")
        for evidence in item.get("identifier_evidence", []):
            identifier = evidence.get("identifier")
            source_type = evidence.get("source_reference_type")
            source_id = evidence.get("source_reference_id")
            if source_type == "fact" and fact_ids is not None and (source_id not in fact_ids or source_id not in (confirmed_fact_ids or set())):
                errors.append(f"{item.get('sql_id')} identifier {identifier} 的 Fact 证据不存在或未 confirmed")
            if source_type == "complete_ddl":
                table_name = identifier.rsplit(".", 2)[0] if evidence.get("identifier_type") == "field" and identifier.count(".") >= 2 else identifier
                table = next((value for key, value in (knowledge_tables or {}).items() if key == table_name or value.get("full_name") == table_name), None)
                if not table or table.get("schema_scope") != "complete":
                    errors.append(f"{item.get('sql_id')} identifier {identifier} 缺少 complete DDL 证据")
            if evidence.get("identifier_type") == "table" and identifier not in item.get("tables", []):
                errors.append(f"{item.get('sql_id')} table identifier_type 与 tables 不一致")
            if evidence.get("identifier_type") == "field" and identifier not in item.get("fields", []):
                errors.append(f"{item.get('sql_id')} field identifier_type 与 fields 不一致")
            if evidence.get("identifier_type") == "parameter" and identifier not in item.get("parameters", []):
                errors.append(f"{item.get('sql_id')} parameter identifier_type 与 parameters 不一致")
            if evidence.get("identifier_type") == "metric" and identifier not in item.get("metric_ids", []):
                errors.append(f"{item.get('sql_id')} metric identifier_type 与 metric_ids 不一致")
    return list(dict.fromkeys(errors))


def validate_reconciliation(data: dict[str, Any]) -> list[str]:
    errors = validate_schema_shape(data, reconciliation_schema("0.0.0"))
    items = data.get("reconciliation_plans", []) if isinstance(data.get("reconciliation_plans"), list) else []
    errors.extend(_validate_id_items(items, "reconciliation_id", "REC"))
    for item in items:
        if item.get("baseline_entry") == item.get("target_entry"):
            errors.append(f"{item.get('reconciliation_id')} baseline_entry 与 target_entry 不得相同")
    return list(dict.fromkeys(errors))


def _validate_fixed_api_checks(validation: Any, label: str) -> list[str]:
    if not isinstance(validation, dict):
        return [f"{label} validation 必须为 object"]
    if validation.get("assertion_scope") != FIXED_API_ASSERTION_SCOPE:
        return [f"{label} assertion_scope 必须固定为 {FIXED_API_ASSERTION_SCOPE}"]
    checks = validation.get("checks")
    if not isinstance(checks, list) or len(checks) != 2:
        return [f"{label} checks 必须恰好包含两条固定健康检查"]
    errors: list[str] = []
    for index, expected in enumerate(FIXED_API_HEALTH_CHECKS):
        actual = checks[index]
        if not isinstance(actual, dict) or set(actual) != {"path", "operator", "expected"}:
            errors.append(f"{label} check[{index}] 结构非法")
            continue
        if actual.get("path") != expected["path"] or actual.get("operator") != "equals":
            errors.append(f"{label} check[{index}] 路径或 operator 不符合固定契约")
        value = actual.get("expected")
        if expected["path"] == "content.code":
            if type(value) is not int or value != 0:
                errors.append(f"{label} content.code expected 必须是整数 0")
        elif type(value) is not str or value != "OK":
            errors.append(f"{label} content.msg expected 必须是字符串 OK")
    return errors


def validate_api_automation(data: dict[str, Any]) -> list[str]:
    if not isinstance(data, dict):
        return ["API Model 根节点必须为 object"]
    errors = validate_schema_shape(data, api_automation_schema("0.0.0"))
    errors.extend(_validate_fixed_api_checks(data.get("validation"), "API Model"))
    if not isinstance(data.get("business_assertions"), list) or data.get("business_assertions"):
        errors.append("API Model business_assertions 必须存在且为空数组")
    action = data.get("automation_action")
    if action == "blocked" and not data.get("blocking_questions"):
        errors.append("blocked 接口自动化必须提供 blocking_questions")
    if action != "blocked" and data.get("blocking_questions") and data.get("validation_status") == "passed":
        errors.append("非阻塞模型通过时不得保留 blocking_questions")
    parameters = data.get("parameters", []) if isinstance(data.get("parameters"), list) else []
    names = [item.get("name") for item in parameters]
    if len(names) != len(set(names)):
        errors.append("接口参数名必须唯一")
    for item in parameters:
        if not item.get("evidence"):
            errors.append(f"参数 {item.get('name')} 缺少证据")
    for case in data.get("excel_case", []) if isinstance(data.get("excel_case"), list) else []:
        if case.get("method") != str(case.get("method", "")).lower():
            errors.append("Excel 用例 method 必须为小写")
        for field in ("body", "headers", "validation"):
            try:
                json.loads(case.get(field, ""))
            except (TypeError, json.JSONDecodeError):
                errors.append(f"Excel 用例 {field} 必须是合法 JSON")
        statement = str(case.get("validation", "")) + " " + " ".join(data.get("evidence", []))
        if re.search(r"content\.code\s*=\s*0.*content\.msg\s*=\s*OK.*业务数据正确", statement, re.S):
            errors.append("参数健康检查不得宣称业务数据正确")
        try:
            validation = json.loads(case.get("validation", ""))
        except (TypeError, json.JSONDecodeError):
            validation = None
        if data.get("assertion_scope") == "parameter_health" and isinstance(validation, dict):
            checks = validation.get("validate")
            if not isinstance(checks, list) or len(checks) != 2:
                errors.append("parameter_health 只允许 content.code 和 content.msg 两项健康检查")
            else:
                seen: list[str] = []
                for check in checks:
                    path = check.get("check") if isinstance(check, dict) else None
                    seen.append(path)
                    expected = check.get("expected") if isinstance(check, dict) else None
                    if path == "content.code" and expected not in (0, "0"):
                        errors.append("content.code 健康检查 expected 必须为 0")
                    elif path == "content.msg" and expected != "OK":
                        errors.append("content.msg 健康检查 expected 必须为 OK")
                    elif path not in {"content.code", "content.msg"}:
                        errors.append("parameter_health 不得增加业务字段断言")
                if sorted(seen) != ["content.code", "content.msg"]:
                    errors.append("parameter_health 必须恰好包含 content.code 和 content.msg")
    return list(dict.fromkeys(errors))


validate_reconciliation_plan = validate_reconciliation
validate_validation_sql_model = validate_validation_sql


def validate_model_links(
    requirement: dict[str, Any] | None,
    diff: dict[str, Any] | None,
    risk_matrix: dict[str, Any],
    testcase_model: dict[str, Any],
    validation_status: str | None = None,
) -> list[str]:
    """Validate IDs and reverse mappings across all structured handoff models."""

    errors: list[str] = []
    criteria_by_id = {
        item.get("criterion_id"): item for item in (requirement or {}).get("acceptance_criteria", [])
    }
    requirement_ids = set(criteria_by_id)
    change_ids = {item.get("change_id") for item in (diff or {}).get("change_items", [])}
    confirmed_fact_ids = {item.get("fact_id") for item in (requirement or {}).get("facts", []) if item.get("category") == "confirmed"}
    risks = {item.get("risk_id"): item for item in risk_matrix.get("risk_items", [])}
    diff_risks = {item.get("risk_id"): item for item in (diff or {}).get("risks", [])}
    defect_ids = {item.get("defect_id") for item in (diff or {}).get("suspected_defects", [])}
    cases = {item.get("tc_id"): item for item in testcase_model.get("cases", [])}
    shared_scope = testcase_model.get("shared_entry_scope") if isinstance(testcase_model.get("shared_entry_scope"), dict) else {}
    shared_scope_paths = {
        (
            str(group.get("group_name", "")),
            str(subgroup.get("subgroup_name", "")),
            str(entry.get("entry_name", "")),
        )
        for group in shared_scope.get("groups", [])
        for subgroup in group.get("subgroups", [])
        for entry in subgroup.get("entries", [])
    }
    facts_by_id = {item.get("fact_id"): item for item in (requirement or {}).get("facts", [])}
    facts = set(facts_by_id)
    confirmations = {item.get("confirmation_id"): item for item in (requirement or {}).get("confirmation_points", [])}
    assessment = (requirement or {}).get("test_dimension_assessment")
    if isinstance(assessment, list):
        for item in assessment:
            if not isinstance(item, dict):
                continue
            dimension = item.get("dimension")
            risk_ids = set(item.get("risk_ids", []))
            testcase_ids = set(item.get("testcase_ids", []))
            if item.get("status") == "covered":
                if not testcase_ids:
                    errors.append(f"COVERED_DIMENSION_WITHOUT_TESTCASE: {dimension}")
                if not risk_ids:
                    errors.append(f"COVERED_DIMENSION_WITHOUT_RISK: {dimension}")
            if validation_status == "passed" and item.get("status") == "pending":
                errors.append(f"PENDING_DIMENSION_WITHOUT_CONFIRMATION: passed 产物不得保留 pending 维度 {dimension}")
            if risk_ids - set(risks):
                errors.append(f"COVERED_DIMENSION_WITHOUT_RISK: {dimension} 引用不存在 Risk {sorted(risk_ids - set(risks))}")
            if testcase_ids - set(cases):
                errors.append(f"COVERED_DIMENSION_WITHOUT_TESTCASE: {dimension} 引用不存在 TC {sorted(testcase_ids - set(cases))}")
            for tc_id in testcase_ids & set(cases):
                case_dimensions = {cases[tc_id].get("dimension"), *cases[tc_id].get("secondary_dimensions", [])}
                if dimension not in case_dimensions:
                    errors.append(f"TESTCASE_PRIMARY_DIMENSION_MISMATCH: {tc_id} 未声明评估维度 {dimension}")
    for risk_id in set(risks) & set(diff_risks):
        left, right = risks[risk_id], diff_risks[risk_id]
        if left.get("disposition_status") != right.get("disposition_status", "covered"):
            errors.append(f"Risk {risk_id} 在 Diff 与 Risk Matrix 的 disposition_status 不一致")
        for field in ("change_ids", "risk_title", "core_assertion", "risk_level", "test_priority", "business_impact", "regression_scope", "evidence_state", "disposition_status"):
            if field in left and field in right and left.get(field) != right.get(field):
                errors.append(f"Risk {risk_id} 在 Diff 与 Risk Matrix 的 {field} 不一致")
        if set(left.get("change_ids", [])) != set(right.get("change_ids", [])):
            errors.append(f"Risk {risk_id} 在 Diff 与 Risk Matrix 的 change_ids 不一致")
        left_facts = set(left.get("fact_ids", []))
        right_facts = set(right.get("fact_ids", right.get("requirement_fact_ids", [])))
        if (left_facts or "fact_ids" in left) and left_facts != right_facts:
            errors.append(f"Risk {risk_id} 在 Diff 与 Risk Matrix 的 fact_ids 不一致")
    analysis_ids = set(risk_matrix.get("analysis_ids", []))
    for model in (requirement, diff):
        if model and model.get("analysis_id") not in analysis_ids:
            errors.append(f"风险矩阵未关联分析模型：{model.get('analysis_id')}")
    if requirement and diff and requirement.get("report_mode") != diff.get("report_mode"):
        errors.append("Requirement 与 Diff report_mode 不一致")
    for defect in (diff or {}).get("suspected_defects", []):
        unknown_facts = set(defect.get("requirement_fact_ids", [])) - confirmed_fact_ids
        unknown_changes = set(defect.get("change_ids", [])) - change_ids
        if unknown_facts:
            errors.append(f"疑似缺陷 {defect.get('defect_id')} 缺少 confirmed Fact：{sorted(unknown_facts)}")
        if unknown_changes:
            errors.append(f"疑似缺陷 {defect.get('defect_id')} 缺少真实 Change：{sorted(unknown_changes)}")
    for risk_id, risk in risks.items():
        fact_ids = set(risk.get("fact_ids", []))
        if not fact_ids and not risk.get("change_ids"):
            errors.append(f"Risk {risk_id} 必须至少引用一个真实 Fact 或 Change")
        if requirement is not None and fact_ids - facts:
            errors.append(f"Risk {risk_id} 引用不存在的 Fact：{sorted(fact_ids - facts)}")
        if requirement is not None:
            linked_evidence = {
                evidence_reference_identity(evidence)
                for fact_id in fact_ids
                for evidence in facts_by_id.get(fact_id, {}).get("evidence_references", [])
                if isinstance(evidence, dict)
            }
            linked_evidence.update(
                evidence_reference_identity(evidence)
                for criterion_id in risk.get("requirement_ids", [])
                for evidence in criteria_by_id.get(criterion_id, {}).get("evidence_references", [])
                if isinstance(evidence, dict)
            )
            risk_evidence = {
                evidence_reference_identity(evidence)
                for evidence in risk.get("evidence_references", []) if isinstance(evidence, dict)
            }
            if risk_evidence - linked_evidence:
                errors.append(
                    f"EVIDENCE_REFERENCE_NOT_DERIVED_FROM_LINKED_FACT: Risk {risk_id} 的证据未派生自关联 Fact/Acceptance Criteria"
                )
            if risk.get("evidence_state") == "已确认" and any(
                facts_by_id.get(fact_id, {}).get("category") != "confirmed"
                or not any(
                    isinstance(evidence, dict) and evidence.get("evidence_status") == "current"
                    for evidence in facts_by_id.get(fact_id, {}).get("evidence_references", [])
                )
                for fact_id in fact_ids
            ):
                errors.append(f"CONFIRMED_RISK_WITH_UNCONFIRMED_FACT: Risk {risk_id} 引用了未确认或无 current 证据的 Fact")
        disposition = risk.get("disposition_status")
        if disposition == "blocked":
            blocked_ids = set(risk.get("blocked_by_confirmation_ids") or risk.get("confirmation_ids", []))
            unknown = blocked_ids - confirmations.keys()
            if unknown:
                errors.append(f"blocked Risk {risk_id} 引用不存在的 Confirmation：{sorted(unknown)}")
            for confirmation_id in blocked_ids & confirmations.keys():
                confirmation = confirmations[confirmation_id]
                if confirmation.get("severity") != "blocking" or confirmation.get("status") not in {"pending", "skipped"}:
                    errors.append(f"blocked Risk {risk_id} 的 {confirmation_id} 必须是 pending/skipped blocking Confirmation")
            if validation_status == "passed":
                errors.append(f"passed 状态不得包含 blocked Risk {risk_id}")
        if disposition == "merged":
            target_id = risk.get("merged_into_risk_id") or next(iter(risk.get("merged_to", [])), None)
            target = risks.get(target_id)
            if target and not ((set(risk.get("fact_ids", [])) & set(target.get("fact_ids", []))) or (set(risk.get("change_ids", [])) & set(target.get("change_ids", []))) or risk.get("merge_evidence_references")):
                errors.append(f"merged Risk {risk_id} 与目标 {target_id} 缺少共享 Fact/Change 或合并证据")
        if requirement is not None:
            unknown = set(risk.get("requirement_ids", [])) - requirement_ids
            if unknown:
                errors.append(f"风险 {risk_id} 引用不存在需求点：{sorted(unknown)}")
        if diff is not None:
            unknown = set(risk.get("change_ids", [])) - change_ids
            if unknown:
                errors.append(f"风险 {risk_id} 引用不存在 Diff 变更：{sorted(unknown)}")
            if risk.get("change_ids") and risk_id not in diff_risks:
                errors.append(f"风险矩阵 {risk_id} 有 Diff 变更但 Diff Model 未建立同名风险")
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
        if case.get("evidence_state") == "已确认":
            linked_risks = [risks[risk_id] for risk_id in case.get("risk_ids", []) if risk_id in risks]
            linked_criteria = [
                criteria_by_id[criterion_id]
                for criterion_id in case.get("requirement_ids", []) if criterion_id in criteria_by_id
            ]
            has_unconfirmed_link = any(risk.get("evidence_state") != "已确认" for risk in linked_risks)
            for criterion in linked_criteria:
                for fact_id in criterion.get("fact_ids", []):
                    fact = facts_by_id.get(fact_id, {})
                    if fact.get("category") != "confirmed" or not any(
                        isinstance(evidence, dict) and evidence.get("evidence_status") == "current"
                        for evidence in fact.get("evidence_references", [])
                    ):
                        has_unconfirmed_link = True
            if has_unconfirmed_link:
                errors.append(
                    f"CONFIRMED_TESTCASE_WITH_UNCONFIRMED_LINK: {tc_id} 已确认，但关联 Risk/Fact 仍未确认"
                )
        if diff is not None:
            unknown = set(case.get("change_ids", [])) - change_ids
            if unknown:
                errors.append(f"{tc_id} 引用不存在 Diff 变更：{sorted(unknown)}")
        for risk_id in set(case.get("risk_ids", [])) & risks.keys():
            if tc_id not in risks[risk_id].get("testcase_ids", []):
                errors.append(f"{tc_id} 与风险 {risk_id} 的双向映射不一致")
    for instance in testcase_model.get("execution_instances", []):
        unknown_defects = set(instance.get("defect_ids", [])) - defect_ids
        if unknown_defects:
            errors.append(
                f"执行实例 {instance.get('execution_instance_id')} 引用不存在疑似缺陷：{sorted(unknown_defects)}"
            )
    for risk_id, risk in risks.items():
        for tc_id in set(risk.get("testcase_ids", [])) & cases.keys():
            if risk_id not in cases[tc_id].get("risk_ids", []):
                errors.append(f"风险 {risk_id} 与 {tc_id} 的双向映射不一致")
    for risk_id, risk in diff_risks.items():
        if risk_id not in risks:
            errors.append(f"Diff 风险 {risk_id} 未进入 Risk Matrix")
        if requirement is not None:
            unknown = set(risk.get("requirement_fact_ids", [])) - confirmed_fact_ids
            if unknown:
                errors.append(f"Diff 风险 {risk_id} 引用不存在 confirmed Fact：{sorted(unknown)}")
    condition_matrix = (requirement or {}).get("condition_matrix")
    if isinstance(condition_matrix, dict):
        required_combinations = condition_matrix.get("required_combinations", [])
        required_by_id = {
            item.get("combination_id"): item
            for item in required_combinations if isinstance(item, dict)
        }
        coverage_by_id: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        behavior_locations: dict[tuple[str, str, int], str] = {}
        for tc_id, case in cases.items():
            for coverage in case.get("condition_coverage", []):
                if isinstance(coverage, dict) and isinstance(coverage.get("combination_id"), str):
                    coverage_by_id.setdefault(coverage["combination_id"], []).append((tc_id, coverage))
        for combination_id, combination in required_by_id.items():
            mapped_tcs = set(combination.get("covered_by_tc_ids", []))
            unknown_tcs = mapped_tcs - cases.keys()
            if unknown_tcs:
                errors.append(
                    f"REQUIRED_COMBINATION_UNCOVERED: {combination_id} 引用不存在 TC：{sorted(unknown_tcs)}"
                )
            linked = [
                (tc_id, coverage) for tc_id, coverage in coverage_by_id.get(str(combination_id), [])
                if tc_id in mapped_tcs
            ]
            behavior = [item for item in linked if item[1].get("coverage_type") == "behavior"]
            if not behavior:
                if validation_status == "pending":
                    continue
                if linked and all(item[1].get("coverage_type") == "configuration" for item in linked):
                    errors.append(
                        f"CONFIG_EXISTENCE_IS_NOT_BEHAVIOR_COVERAGE: {combination_id} 只有配置存在性覆盖"
                    )
                else:
                    errors.append(
                        f"REQUIRED_COMBINATION_UNCOVERED: {combination_id} 缺少行为型 condition_coverage"
                    )
                continue
            expected_values = combination.get("dimension_values")
            if any(coverage.get("dimension_values") != expected_values for _, coverage in behavior):
                errors.append(
                    f"REQUIRED_COMBINATION_UNCOVERED: {combination_id} condition_coverage 与矩阵维度值不一致"
                )
            if (requirement or {}).get("condition_matrix_required") is True:
                for tc_id, coverage in behavior:
                    case = cases[tc_id]
                    branch_id = coverage.get("branch_id")
                    scope_path = coverage.get("scope_path")
                    mappings = coverage.get("assertion_mappings")
                    legacy_mapping = {
                        "step_index": coverage.get("step_index"),
                        "expected_index": coverage.get("expected_index"),
                        "observable_result": coverage.get("observable_result"),
                    }
                    has_legacy_mapping = any(value is not None for value in legacy_mapping.values())
                    if mappings is not None and has_legacy_mapping:
                        errors.append(
                            f"CONDITION_COVERAGE_MAPPING_CONFLICT: {combination_id} 不得同时使用单断言和 assertion_mappings"
                        )
                        continue
                    if mappings is None:
                        mappings = [legacy_mapping]
                        uses_multi_mapping = False
                    else:
                        uses_multi_mapping = True
                    if not isinstance(mappings, list) or not mappings:
                        errors.append(f"CONDITION_COVERAGE_ASSERTION_MAPPING_REQUIRED: {combination_id}")
                        continue
                    if case.get("shared_entry_scope_id"):
                        normalized_scope_path = tuple(str(item) for item in (scope_path or []))
                        matching_scope_paths = [
                            path for path in shared_scope_paths
                            if path[:len(normalized_scope_path)] == normalized_scope_path
                        ]
                        if not normalized_scope_path or not matching_scope_paths:
                            errors.append(
                                f"CONDITION_COVERAGE_SCOPE_MISMATCH: {combination_id} 引用不存在 scope_path：{scope_path}"
                            )
                            continue
                        steps = case.get("steps", [])
                        expected_results = case.get("expected_results", [])
                        if len(steps) != len(expected_results):
                            errors.append(
                                f"CONDITION_COVERAGE_STEP_REFERENCE_INVALID: {tc_id} 共享入口 steps 与 expected_results 必须一一对应"
                            )
                        if uses_multi_mapping:
                            mapping_keys = [
                                (item.get("step_index"), item.get("expected_index"), item.get("observable_result"))
                                for item in mappings if isinstance(item, dict)
                            ]
                            if len(mapping_keys) != len(mappings) or len(mapping_keys) != len(set(mapping_keys)):
                                errors.append(f"CONDITION_COVERAGE_ASSERTION_MAPPING_DUPLICATED: {combination_id}")
                            if {item[1] for item in mapping_keys} != set(range(1, len(expected_results) + 1)):
                                errors.append(f"CONDITION_COVERAGE_ASSERTION_MAPPING_INCOMPLETE: {combination_id}")
                        for mapping in mappings:
                            step_index = mapping.get("step_index") if isinstance(mapping, dict) else None
                            expected_index = mapping.get("expected_index") if isinstance(mapping, dict) else None
                            if (not isinstance(step_index, int) or isinstance(step_index, bool) or not 1 <= step_index <= len(steps)
                                    or not isinstance(expected_index, int) or isinstance(expected_index, bool) or not 1 <= expected_index <= len(expected_results)):
                                errors.append(f"CONDITION_COVERAGE_STEP_REFERENCE_INVALID: {combination_id} 的 step_index/expected_index 非法")
                                continue
                            if mapping.get("observable_result") != expected_results[expected_index - 1]:
                                errors.append(f"CONDITION_COVERAGE_STEP_REFERENCE_INVALID: {combination_id} observable_result 必须等于所引用 expected_results[{expected_index}]")
                            if not uses_multi_mapping:
                                location = (tc_id, "/".join(normalized_scope_path), step_index)
                                prior = behavior_locations.get(location)
                                if prior and prior != combination_id:
                                    errors.append(f"CONDITION_COVERAGE_NOT_INDEPENDENT: {prior} 与 {combination_id}")
                                else:
                                    behavior_locations[location] = str(combination_id)
                        continue
                    branch = next(
                        (item for item in case.get("entry_branches", []) if item.get("branch_id") == branch_id),
                        None,
                    )
                    if branch is None:
                        errors.append(
                            f"CONDITION_COVERAGE_BRANCH_MISMATCH: {combination_id} 引用不存在 branch_id：{branch_id}"
                        )
                        continue
                    business_entry = (coverage.get("dimension_values") or {}).get("business_entry")
                    if business_entry and branch.get("entry_name") != business_entry:
                        errors.append(
                            f"CONDITION_COVERAGE_BRANCH_MISMATCH: {combination_id} 的 business_entry={business_entry} "
                            f"与 {branch_id} 的 entry_name={branch.get('entry_name')} 不一致"
                        )
                    steps = branch.get("steps", [])
                    expected_results = branch.get("expected_results", [])
                    if len(steps) != len(expected_results):
                        errors.append(
                            f"CONDITION_COVERAGE_STEP_REFERENCE_INVALID: {tc_id}.{branch_id} steps 与 expected_results 必须一一对应"
                        )
                    if uses_multi_mapping:
                        mapping_keys = [
                            (item.get("step_index"), item.get("expected_index"), item.get("observable_result"))
                            for item in mappings if isinstance(item, dict)
                        ]
                        if len(mapping_keys) != len(mappings) or len(mapping_keys) != len(set(mapping_keys)):
                            errors.append(f"CONDITION_COVERAGE_ASSERTION_MAPPING_DUPLICATED: {combination_id}")
                        if {item[1] for item in mapping_keys} != set(range(1, len(expected_results) + 1)):
                            errors.append(f"CONDITION_COVERAGE_ASSERTION_MAPPING_INCOMPLETE: {combination_id}")
                    for mapping in mappings:
                        step_index = mapping.get("step_index") if isinstance(mapping, dict) else None
                        expected_index = mapping.get("expected_index") if isinstance(mapping, dict) else None
                        if (not isinstance(step_index, int) or isinstance(step_index, bool) or not 1 <= step_index <= len(steps)
                                or not isinstance(expected_index, int) or isinstance(expected_index, bool) or not 1 <= expected_index <= len(expected_results)):
                            errors.append(f"CONDITION_COVERAGE_STEP_REFERENCE_INVALID: {combination_id} 的 step_index/expected_index 非法")
                            continue
                        if mapping.get("observable_result") != expected_results[expected_index - 1]:
                            errors.append(f"CONDITION_COVERAGE_STEP_REFERENCE_INVALID: {combination_id} observable_result 必须等于所引用 expected_results[{expected_index}]")
                        if not uses_multi_mapping:
                            location = (tc_id, str(branch_id), step_index)
                            prior = behavior_locations.get(location)
                            if prior and prior != combination_id:
                                errors.append(f"CONDITION_COVERAGE_NOT_INDEPENDENT: {prior} 与 {combination_id}")
                            else:
                                behavior_locations[location] = str(combination_id)
        unknown_coverage = set(coverage_by_id) - set(required_by_id)
        if unknown_coverage:
            errors.append(
                f"REQUIRED_COMBINATION_UNCOVERED: testcase 引用不存在 required combination：{sorted(unknown_coverage)}"
            )
        behavior_coverages = [
            coverage for entries in coverage_by_id.values() for _, coverage in entries
            if coverage.get("coverage_type") == "behavior"
        ]
        relation_oracles: dict[tuple[str, str, str], dict[str, str]] = {}
        for coverage in behavior_coverages:
            values = coverage.get("dimension_values", {})
            relation = values.get("relation")
            if relation not in {"包含于", "不包含"}:
                continue
            comparison_key = (
                str(values.get("permission_type")), str(values.get("business_entry")),
                str(values.get("expected_match_state")),
            )
            relation_oracles.setdefault(comparison_key, {})[str(relation)] = str(coverage.get("observable_result"))
        for comparison_key, oracles in relation_oracles.items():
            if len(oracles) == 2 and oracles.get("包含于") == oracles.get("不包含"):
                errors.append(
                    f"RELATION_ORACLE_NOT_DISTINCT: {comparison_key} 的包含于与不包含使用相同 Oracle"
                )
        relation_scenarios: dict[tuple[str, str], set[str]] = {}
        for coverage in behavior_coverages:
            values = coverage.get("dimension_values", {})
            key = (str(values.get("permission_type")), str(values.get("relation")))
            relation_scenarios.setdefault(key, set()).add(
                f"{values.get('expected_match_state', '')} {coverage.get('expected_match_state', '')} {coverage.get('observable_result', '')}"
            )
        for (permission_type, relation), scenario_texts in relation_scenarios.items():
            combined = " ".join(sorted(scenario_texts))
            missing_markers: list[str] = []
            if relation == "包含于":
                if not any(marker in combined for marker in ("任一满足", "任一角色", "一个命中", "至少一个命中")):
                    missing_markers.append("任一满足")
                if not any(marker in combined for marker in ("全部不满足", "全部不命中", "所有角色均不属于")):
                    missing_markers.append("全部不满足")
            if relation == "完全包含于":
                for label, markers in (
                    ("全部满足", ("全部满足", "全部命中", "全部角色均属于")),
                    ("部分满足", ("部分满足", "部分命中", "只有部分")),
                    ("全部不满足", ("全部不满足", "全部不命中", "所有角色均不属于")),
                ):
                    if not any(marker in combined for marker in markers):
                        missing_markers.append(label)
            if "指定用户" in permission_type:
                for label, markers in (
                    ("单用户命中", ("单用户命中",)), ("单用户不命中", ("单用户不命中",)),
                    ("多用户一个命中", ("多用户一个命中", "多用户至少一个命中")),
                    ("多用户全部不命中", ("多用户全部不命中",)),
                ):
                    if not any(marker in combined for marker in markers):
                        missing_markers.append(label)
            if missing_markers and validation_status != "pending":
                errors.append(
                    f"RELATION_SCENARIO_INCOMPLETE: {permission_type}/{relation} 缺少 {sorted(set(missing_markers))}"
                )
    return list(dict.fromkeys(errors))


def validate_test_dimension_warnings(
    requirement: dict[str, Any] | None,
    testcase_model: dict[str, Any],
) -> list[str]:
    """Return review-only warnings that must not block unless strict is requested."""
    cases = [item for item in testcase_model.get("cases", []) if isinstance(item, dict)]
    assessment = (requirement or {}).get("test_dimension_assessment", [])
    covered = {
        item.get("dimension") for item in assessment
        if isinstance(item, dict) and item.get("status") == "covered"
    }
    primary = {item.get("dimension") for item in cases}
    if len(cases) >= 5 and len(primary) == 1 and len(covered) >= 2:
        return [
            "SINGLE_PRIMARY_DIMENSION_REVIEW_REQUIRED: TC>=5、主维度集中且需求评估识别出多个 covered 风险类型，需人工复核"
        ]
    return []


_VALUE_IMPACT_SCORES = {"critical": 5, "high": 4, "medium": 2, "low": 1}
_VALUE_REGRESSION_SCORES = {"核心回归": 5, "关联回归": 3, "冒烟回归": 1}
_VALUE_REACHABILITY_MARKERS = (
    "页面打开", "成功打开", "可以打开", "可打开", "按钮可点击", "可以点击", "可点击",
    "入口可访问", "可以访问", "可访问", "展示正常", "页面正常",
)
_VALUE_FORMATTING_PUNCTUATION = str.maketrans(
    "", "", ",.;:!?，。；：！？、()（）[]【】{}<>《》\"'“”‘’`~*#_|/\\-"
)


def _value_normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = re.sub(r"\s+", " ", value.casefold()).strip()
    return normalized.translate(_VALUE_FORMATTING_PUNCTUATION)


def _value_string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _value_execution_parts(case: dict[str, Any]) -> tuple[list[str], list[str], int]:
    branches = case.get("entry_branches")
    if isinstance(branches, list) and branches:
        steps: list[str] = []
        expected: list[str] = []
        valid_paths = 0
        valid_branches = [item for item in branches if isinstance(item, dict)]
        for branch in sorted(valid_branches, key=lambda item: str(item.get("branch_id", ""))):
            branch_steps = _value_string_items(branch.get("steps"))
            branch_expected = _value_string_items(branch.get("expected_results"))
            steps.extend(branch_steps)
            expected.extend(branch_expected)
            if branch_steps and branch_expected:
                valid_paths += 1
        return steps, expected, valid_paths
    steps = _value_string_items(case.get("steps"))
    expected = _value_string_items(case.get("expected_results"))
    return steps, expected, 1 if steps and expected else 0


def _value_case_semantics(case: dict[str, Any]) -> str:
    parts = [_value_normalize_text(case.get("test_point"))]
    parts.extend(_value_normalize_text(item) for item in _value_string_items(case.get("steps")))
    parts.extend(_value_normalize_text(item) for item in _value_string_items(case.get("expected_results")))
    branches = case.get("entry_branches")
    if isinstance(branches, list):
        valid_branches = [item for item in branches if isinstance(item, dict)]
        for branch in sorted(valid_branches, key=lambda item: str(item.get("branch_id", ""))):
            parts.append(_value_normalize_text(branch.get("entry_name")))
            parts.extend(_value_normalize_text(item) for item in _value_string_items(branch.get("steps")))
            parts.extend(_value_normalize_text(item) for item in _value_string_items(branch.get("expected_results")))
    return "\x1f".join(item for item in parts if item)


def _value_bigrams(value: str) -> set[str]:
    if not value:
        return set()
    if len(value) == 1:
        return {value}
    return {value[index:index + 2] for index in range(len(value) - 1)}


def _value_similarity_bp(left: str, right: str) -> int:
    left_bigrams = _value_bigrams(left)
    right_bigrams = _value_bigrams(right)
    union = left_bigrams | right_bigrams
    if not union:
        return 0
    return len(left_bigrams & right_bigrams) * 10000 // len(union)


def _value_cost_score(units: int) -> int:
    if units <= 0:
        return 0
    if units <= 2:
        return 1
    if units <= 5:
        return 2
    if units <= 9:
        return 3
    if units <= 14:
        return 4
    return 5


def _validate_value_maintenance_inputs(
    maintenance_inputs: dict[str, Any] | None,
    testcase_ids: set[str],
) -> dict[str, dict[str, int]]:
    if maintenance_inputs is None:
        return {}
    if not isinstance(maintenance_inputs, dict):
        raise ValueError("maintenance_inputs 必须是以 tc_id 为键的 object")
    result: dict[str, dict[str, int]] = {}
    allowed = set(VALUE_ASSESSMENT_MAINTENANCE_FIELDS)
    for tc_id in sorted(maintenance_inputs):
        if tc_id not in testcase_ids:
            raise ValueError(f"maintenance_inputs 引用不存在 TC：{tc_id}")
        values = maintenance_inputs[tc_id]
        if not isinstance(values, dict):
            raise ValueError(f"maintenance_inputs.{tc_id} 必须是 object")
        unknown = sorted(set(values) - allowed)
        if unknown:
            raise ValueError(f"maintenance_inputs.{tc_id} 包含非法字段：{unknown}")
        normalized: dict[str, int] = {}
        for field in VALUE_ASSESSMENT_MAINTENANCE_FIELDS:
            value = values.get(field, 0)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"maintenance_inputs.{tc_id}.{field} 必须是非负整数且不能是 boolean")
            normalized[field] = value
        result[tc_id] = normalized
    return result


def _value_evidence_confidence(
    case: dict[str, Any],
    risks: list[dict[str, Any]],
    requirement_model: dict[str, Any] | None,
) -> int:
    states = [case.get("evidence_state")] + [risk.get("evidence_state") for risk in risks]
    if any(state == "待确认" for state in states):
        return 1
    if any(state not in EVIDENCE_STATES for state in states):
        return 0
    if requirement_model is None:
        return 3 if any(state == "疑似" for state in states) else 4

    facts = requirement_model.get("facts")
    if not isinstance(facts, list):
        return 0
    facts_by_id = {
        str(fact.get("fact_id")): fact
        for fact in facts
        if isinstance(fact, dict) and isinstance(fact.get("fact_id"), str)
    }
    fact_ids = sorted({
        str(fact_id)
        for risk in risks
        for fact_id in risk.get("fact_ids", []) if isinstance(risk.get("fact_ids"), list)
        if isinstance(fact_id, str) and fact_id
    })
    if not fact_ids or any(fact_id not in facts_by_id for fact_id in fact_ids):
        return 0
    linked_facts = [facts_by_id[fact_id] for fact_id in fact_ids]
    categories = [fact.get("category") for fact in linked_facts]
    reference_statuses: list[Any] = []
    for item in [*risks, *linked_facts]:
        references = item.get("evidence_references")
        if not isinstance(references, list) or not references:
            return 0
        reference_statuses.extend(
            reference.get("evidence_status")
            for reference in references
            if isinstance(reference, dict)
        )
    if not reference_statuses or any(status not in {"current", "stale", "reconfirm_required"} for status in reference_statuses):
        return 0
    if "missing" in categories or any(status in {"stale", "reconfirm_required"} for status in reference_statuses):
        return 1
    if any(state == "疑似" for state in states) or any(category in {"conflicting", "inferred"} for category in categories):
        return 3
    if all(category == "confirmed" for category in categories) and all(status == "current" for status in reference_statuses):
        return 5
    return 0


def calculate_testcase_value_assessments(
    testcase_model: dict[str, Any],
    risk_model: dict[str, Any],
    requirement_model: dict[str, Any] | None = None,
    maintenance_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate deterministic, non-blocking testcase value assessments in memory."""

    if not isinstance(testcase_model, dict):
        raise ValueError("testcase_model 必须是 object")
    if not isinstance(risk_model, dict):
        raise ValueError("risk_model 必须是 object")
    if requirement_model is not None and not isinstance(requirement_model, dict):
        raise ValueError("requirement_model 必须是 object 或 None")

    raw_cases = testcase_model.get("cases")
    cases = [item for item in raw_cases if isinstance(item, dict)] if isinstance(raw_cases, list) else []
    cases = sorted(cases, key=lambda item: str(item.get("tc_id", "")))
    testcase_ids = {
        str(case.get("tc_id"))
        for case in cases
        if isinstance(case.get("tc_id"), str) and case.get("tc_id")
    }
    normalized_maintenance = _validate_value_maintenance_inputs(maintenance_inputs, testcase_ids)

    raw_risks = risk_model.get("risk_items")
    risks = [item for item in raw_risks if isinstance(item, dict)] if isinstance(raw_risks, list) else []
    risks = sorted(risks, key=lambda item: str(item.get("risk_id", "")))
    risks_by_id = {
        str(risk.get("risk_id")): risk
        for risk in risks
        if isinstance(risk.get("risk_id"), str) and risk.get("risk_id")
    }

    case_contexts: dict[str, dict[str, Any]] = {}
    for case in cases:
        tc_id = str(case.get("tc_id", ""))
        risk_ids = sorted({
            item for item in case.get("risk_ids", [])
            if isinstance(case.get("risk_ids"), list) and isinstance(item, str)
        })
        linked_risks = [risks_by_id[risk_id] for risk_id in risk_ids if risk_id in risks_by_id]
        valid_risks = [
            risk for risk in linked_risks
            if tc_id in {
                item for item in risk.get("testcase_ids", [])
                if isinstance(risk.get("testcase_ids"), list) and isinstance(item, str)
            }
        ]
        merge_keys = tuple(sorted({
            str(risk.get("merge_key")) for risk in valid_risks
            if isinstance(risk.get("merge_key"), str) and risk.get("merge_key")
        }))
        case_contexts[tc_id] = {
            "case": case,
            "risks": valid_risks,
            "merge_keys": merge_keys,
            "semantics": _value_case_semantics(case),
            "deduplication_key": str(case.get("deduplication_key", "")),
        }

    redundancy_by_tc = {tc_id: 0 for tc_id in sorted(case_contexts)}
    sorted_ids = sorted(case_contexts)
    for left_index, left_id in enumerate(sorted_ids):
        left = case_contexts[left_id]
        for right_id in sorted_ids[left_index + 1:]:
            right = case_contexts[right_id]
            same_deduplication_key = bool(left["deduplication_key"]) and left["deduplication_key"] == right["deduplication_key"]
            same_merge_keys = bool(left["merge_keys"]) and left["merge_keys"] == right["merge_keys"]
            if not (same_deduplication_key or same_merge_keys):
                continue
            similarity_bp = _value_similarity_bp(left["semantics"], right["semantics"])
            penalty = 0
            if same_deduplication_key and same_merge_keys and left["semantics"] == right["semantics"] and bool(left["semantics"]):
                penalty = 5
            elif similarity_bp >= 9500 and same_merge_keys:
                penalty = 4
            elif similarity_bp >= 8400:
                penalty = 2
            redundancy_by_tc[left_id] = max(redundancy_by_tc[left_id], penalty)
            redundancy_by_tc[right_id] = max(redundancy_by_tc[right_id], penalty)

    assessments: list[dict[str, Any]] = []
    reason_order = {code: index for index, code in enumerate(VALUE_ASSESSMENT_REASON_CODES)}
    for tc_id in sorted(case_contexts):
        context = case_contexts[tc_id]
        case = context["case"]
        linked_risks = context["risks"]
        merge_keys = context["merge_keys"]
        reason_codes: set[str] = set()

        business_impact = max((_VALUE_IMPACT_SCORES.get(str(risk.get("business_impact")), 0) for risk in linked_risks), default=0)
        if business_impact == 5:
            reason_codes.add("CRITICAL_BUSINESS_IMPACT")
        elif business_impact == 4:
            reason_codes.add("HIGH_BUSINESS_IMPACT")

        coverage_values: list[int] = []
        for risk in linked_risks:
            priority = risk.get("test_priority")
            covered_by = sorted({
                item for item in risk.get("testcase_ids", [])
                if isinstance(risk.get("testcase_ids"), list) and isinstance(item, str)
            })
            if priority == "P0":
                coverage_values.append(5)
            elif priority == "P1":
                coverage_values.append(4 if covered_by == [tc_id] else 3)
            elif priority == "P2":
                coverage_values.append(2 if covered_by == [tc_id] else 1)
        risk_coverage_value = max(coverage_values, default=0)
        p0_mapped = any(risk.get("test_priority") == "P0" for risk in linked_risks)
        if p0_mapped:
            reason_codes.add("P0_RISK_COVERAGE")
        if any(risk.get("test_priority") == "P1" and sorted(set(risk.get("testcase_ids", []))) == [tc_id] for risk in linked_risks):
            reason_codes.add("UNIQUE_P1_RISK_COVERAGE")

        historical_defect = bool(_value_string_items(case.get("historical_defect_ids")))
        regression_value = 5 if historical_defect else _VALUE_REGRESSION_SCORES.get(str(case.get("regression_scope")), 0)
        if historical_defect:
            reason_codes.add("HISTORICAL_DEFECT_REGRESSION")
        if case.get("regression_scope") == "核心回归":
            reason_codes.add("CORE_REGRESSION")

        steps, expected_results, execution_path_count = _value_execution_parts(case)
        normalized_expected = [_value_normalize_text(item) for item in expected_results]
        reachability_only = bool(normalized_expected) and all(
            any(marker in expected for marker in _VALUE_REACHABILITY_MARKERS)
            for expected in normalized_expected
        )
        if not steps or not expected_results or not merge_keys:
            diagnostic_value = 0
        elif len(merge_keys) == 1:
            diagnostic_value = 5
        elif len(merge_keys) == 2:
            diagnostic_value = 3
        else:
            diagnostic_value = 1
        if reachability_only:
            diagnostic_value = min(diagnostic_value, 1)
            reason_codes.add("LOW_VALUE_REACHABILITY_ASSERTION")
        if len(merge_keys) >= 2:
            reason_codes.add("MULTI_RISK_DIAGNOSTIC_WEAKNESS")

        evidence_confidence = _value_evidence_confidence(case, linked_risks, requirement_model)
        if evidence_confidence <= 1:
            reason_codes.add("LOW_EVIDENCE_CONFIDENCE")

        structural_units = (
            len(steps)
            + len(expected_results)
            + sum(len(_value_string_items(case.get(field))) for field in (
                "preconditions", "test_data_refs", "environment_refs", "role_refs",
                "cleanup_steps", "oracle_sources",
            ))
            + 2 * max(execution_path_count - 1, 0)
        )
        structural_cost = _value_cost_score(structural_units)
        observed = normalized_maintenance.get(tc_id, {})
        observed_units = (
            2 * observed.get("external_system_dependency_count", 0)
            + 2 * observed.get("mutable_shared_data_dependency_count", 0)
            + observed.get("manual_oracle_count", 0)
            + observed.get("environment_specific_dependency_count", 0)
        )
        maintenance_cost = max(structural_cost, _value_cost_score(observed_units))
        if maintenance_cost >= 4:
            reason_codes.add("HIGH_MAINTENANCE_COST")

        redundancy_penalty = redundancy_by_tc[tc_id]
        if redundancy_penalty >= 2:
            reason_codes.add("POSSIBLE_DUPLICATE")
        if redundancy_penalty >= 4:
            reason_codes.add("HIGH_SIMILARITY_DUPLICATE")

        insufficient = not linked_risks
        if insufficient:
            reason_codes.add("INSUFFICIENT_INPUTS")
        positive = (
            6 * business_impact
            + 5 * risk_coverage_value
            + 4 * regression_value
            + 3 * diagnostic_value
            + 2 * evidence_confidence
        )
        penalty = 2 * maintenance_cost + 4 * redundancy_penalty
        total_score = None if insufficient else min(max(positive - penalty, 0), 100)
        if total_score is None:
            value_band = None
        elif total_score >= 80:
            value_band = "high_value_core"
        elif total_score >= 65:
            value_band = "regression_keep"
        elif total_score >= 45:
            value_band = "standard_value"
        elif total_score >= 25:
            value_band = "review_simplify_or_merge"
        else:
            value_band = "low_value_review"

        guardrails: list[str] = []
        if p0_mapped:
            guardrails.append("p0_mapped")
        if historical_defect:
            guardrails.append("historical_defect_regression")
        guarded = bool(guardrails)
        if insufficient:
            recommendation = "insufficient_inputs"
        elif redundancy_penalty >= 2:
            recommendation = "retain_guarded_and_review_duplicate" if guarded else "review_duplicate"
        elif guarded:
            recommendation = "retain_guarded_and_improve" if total_score is not None and total_score < 65 else "retain_guarded"
        elif evidence_confidence <= 1 and any(risk.get("test_priority") in {"P0", "P1"} for risk in linked_risks):
            recommendation = "reconfirm_priority_evidence"
        elif len(merge_keys) >= 2:
            recommendation = "split_for_diagnosis"
        elif maintenance_cost >= 4 or value_band in {"review_simplify_or_merge", "low_value_review"}:
            recommendation = "review_simplification"
        elif value_band == "standard_value":
            recommendation = "standard_maintain"
        else:
            recommendation = "retain"

        assessments.append({
            "tc_id": tc_id,
            "score_status": "insufficient_inputs" if insufficient else "computed",
            "dimensions": {
                "business_impact": business_impact,
                "risk_coverage_value": risk_coverage_value,
                "regression_value": regression_value,
                "diagnostic_value": diagnostic_value,
                "evidence_confidence": evidence_confidence,
                "maintenance_cost": maintenance_cost,
                "redundancy_penalty": redundancy_penalty,
            },
            "total_score": total_score,
            "value_band": value_band,
            "guardrails": guardrails,
            "reason_codes": sorted(reason_codes, key=lambda code: reason_order[code]),
            "recommendation": recommendation,
        })
    return {
        "algorithm_version": VALUE_ASSESSMENT_ALGORITHM_VERSION,
        "assessments": assessments,
    }


def _load_value_assessment_reference(
    reference: Any,
    *,
    root: Path,
    label: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(reference, dict):
        return None, [f"{label} 必须是 object"]
    resolved, errors = _resolve_evidence_path(reference.get("path"), root=root, label=f"{label}.path")
    if errors or resolved is None:
        return None, errors
    actual_hash = stable_normalized_file_hash(resolved)
    if reference.get("content_hash") != actual_hash:
        return None, [f"{label}.content_hash 与归一化文件 Hash 不一致"]
    try:
        return load_json(resolved), []
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, [f"{label} 无法读取：{exc}"]


def validate_testcase_value_assessment(
    assessment_model: dict[str, Any],
    *,
    root: Path,
) -> list[str]:
    """Validate persisted assessment references and every recomputed result field."""

    errors = validate_schema_shape(
        assessment_model,
        testcase_value_assessment_schema("0.0.0"),
    )
    if not isinstance(assessment_model, dict):
        return errors

    assessments = assessment_model.get("assessments")
    persisted = [item for item in assessments if isinstance(item, dict)] if isinstance(assessments, list) else []
    persisted_ids = [item.get("tc_id") for item in persisted]
    string_ids = [item for item in persisted_ids if isinstance(item, str)]
    duplicate_ids = sorted({item for item in string_ids if string_ids.count(item) > 1})
    if duplicate_ids:
        errors.append(f"Assessment tc_id 重复：{duplicate_ids}")
    for item in persisted:
        status = item.get("score_status")
        if status == "computed" and (not isinstance(item.get("total_score"), int) or isinstance(item.get("total_score"), bool) or item.get("value_band") is None):
            errors.append(f"{item.get('tc_id')} computed 必须提供整数 total_score 和非空 value_band")
        if status == "insufficient_inputs":
            if item.get("total_score") is not None or item.get("value_band") is not None:
                errors.append(f"{item.get('tc_id')} insufficient_inputs 的 total_score 和 value_band 必须为 null")
            if item.get("recommendation") != "insufficient_inputs" or "INSUFFICIENT_INPUTS" not in item.get("reason_codes", []):
                errors.append(f"{item.get('tc_id')} insufficient_inputs 缺少固定 recommendation 或 reason_code")

    testcase_model, reference_errors = _load_value_assessment_reference(
        assessment_model.get("testcase_model_reference"), root=root, label="testcase_model_reference",
    )
    errors.extend(reference_errors)
    risk_model, reference_errors = _load_value_assessment_reference(
        assessment_model.get("risk_matrix_reference"), root=root, label="risk_matrix_reference",
    )
    errors.extend(reference_errors)

    requirement_reference = assessment_model.get("requirement_model_reference")
    requirement_model: dict[str, Any] | None = None
    if requirement_reference is not None:
        requirement_model, reference_errors = _load_value_assessment_reference(
            requirement_reference, root=root, label="requirement_model_reference",
        )
        errors.extend(reference_errors)

    if testcase_model is not None:
        reference = assessment_model.get("testcase_model_reference", {})
        if isinstance(reference, dict) and reference.get("model_id") != testcase_model.get("model_id"):
            errors.append("testcase_model_reference.model_id 与实际 Testcase Model 不一致")
    if risk_model is not None:
        reference = assessment_model.get("risk_matrix_reference", {})
        if isinstance(reference, dict) and reference.get("matrix_id") != risk_model.get("matrix_id"):
            errors.append("risk_matrix_reference.matrix_id 与实际 Risk Matrix 不一致")
    if requirement_model is not None:
        reference = assessment_model.get("requirement_model_reference", {})
        if isinstance(reference, dict) and reference.get("analysis_id") != requirement_model.get("analysis_id"):
            errors.append("requirement_model_reference.analysis_id 与实际 Requirement Model 不一致")

    if testcase_model is None or risk_model is None:
        return list(dict.fromkeys(errors))
    model_errors: list[str] = []
    if requirement_model is not None:
        model_errors.extend(
            f"Requirement Model 非法：{error}"
            for error in validate_requirement_model(requirement_model, evidence_root=root)
        )
    model_errors.extend(
        f"Risk Matrix 非法：{error}"
        for error in validate_risk_matrix(risk_model, evidence_root=root)
    )
    model_errors.extend(
        f"Testcase Model 非法：{error}" for error in validate_testcase_model(testcase_model)
    )
    model_errors.extend(
        f"Assessment 引用模型链路非法：{error}"
        for error in validate_model_links(requirement_model, None, risk_model, testcase_model)
    )
    errors.extend(model_errors)
    if model_errors:
        return list(dict.fromkeys(errors))
    try:
        recomputed = calculate_testcase_value_assessments(
            testcase_model,
            risk_model,
            requirement_model,
            assessment_model.get("maintenance_inputs"),
        )
    except ValueError as exc:
        errors.append(str(exc))
        return list(dict.fromkeys(errors))

    recomputed_items = recomputed["assessments"]
    recomputed_by_id = {item["tc_id"]: item for item in recomputed_items}
    persisted_by_id = {
        str(item.get("tc_id")): item
        for item in persisted
        if isinstance(item.get("tc_id"), str)
    }
    unknown_ids = sorted(set(persisted_by_id) - set(recomputed_by_id))
    missing_ids = sorted(set(recomputed_by_id) - set(persisted_by_id))
    if unknown_ids:
        errors.append(f"Assessment 包含 Testcase Model 不存在的 TC：{unknown_ids}")
    if missing_ids:
        errors.append(f"Assessment 遗漏可计算 TC：{missing_ids}")
    compared_fields = (
        "score_status", "dimensions", "total_score", "value_band",
        "guardrails", "reason_codes", "recommendation",
    )
    for tc_id in sorted(set(persisted_by_id) & set(recomputed_by_id)):
        for field in compared_fields:
            if persisted_by_id[tc_id].get(field) != recomputed_by_id[tc_id].get(field):
                errors.append(f"{tc_id} 持久化评分与重算结果不一致：{field}")
    return list(dict.fromkeys(errors))


def format_testcase_value_assessment(assessment_model: dict[str, Any]) -> list[str]:
    """Format an already validated assessment with deterministic advisory messages."""

    reason_order = {code: index for index, code in enumerate(VALUE_ASSESSMENT_REASON_CODES)}
    guardrail_order = {code: index for index, code in enumerate(VALUE_ASSESSMENT_GUARDRAILS)}
    lines: list[str] = []
    warning_count = 0
    suggestion_count = 0
    computed_count = 0
    insufficient_count = 0
    assessments = sorted(assessment_model["assessments"], key=lambda item: item["tc_id"])
    for assessment in assessments:
        tc_id = assessment["tc_id"]
        status = assessment["score_status"]
        dimensions = assessment["dimensions"]
        guardrails = sorted(assessment["guardrails"], key=lambda code: guardrail_order[code])
        reason_codes = sorted(assessment["reason_codes"], key=lambda code: reason_order[code])
        score = "null" if assessment["total_score"] is None else str(assessment["total_score"])
        band = "null" if assessment["value_band"] is None else assessment["value_band"]
        lines.append(
            f"ASSESSMENT {tc_id} status={status} score={score} band={band} "
            f"recommendation={assessment['recommendation']}"
        )
        lines.append(
            f"DIMENSIONS {tc_id} "
            + " ".join(f"{field}={dimensions[field]}" for field in VALUE_ASSESSMENT_DIMENSION_FIELDS)
        )
        lines.extend(f"GUARDRAIL {tc_id} {guardrail}" for guardrail in guardrails)
        lines.extend(f"REASON {tc_id} {reason}" for reason in reason_codes)

        if status == "computed":
            computed_count += 1
        else:
            insufficient_count += 1

        if status == "insufficient_inputs":
            continue

        guarded = bool(guardrails)
        low_band = assessment["value_band"] in {"review_simplify_or_merge", "low_value_review"}
        high_priority = "p0_mapped" in guardrails or dimensions["risk_coverage_value"] >= 3
        multi_risk = "MULTI_RISK_DIAGNOSTIC_WEAKNESS" in reason_codes
        warnings: list[str] = []
        suggestions: list[str] = []
        if high_priority and dimensions["evidence_confidence"] <= 2:
            warnings.append("LOW_EVIDENCE_CONFIDENCE")
        if "p0_mapped" in guardrails and low_band:
            warnings.append("P0_LOW_SCORE_GUARDED")
        if "historical_defect_regression" in guardrails and low_band:
            warnings.append("HISTORICAL_DEFECT_LOW_SCORE_GUARDED")
        if dimensions["redundancy_penalty"] >= 2:
            warnings.append("POSSIBLE_DUPLICATE_REVIEW_REQUIRED")
        if dimensions["diagnostic_value"] <= 1 and multi_risk:
            warnings.append("MULTI_RISK_DIAGNOSTIC_WEAKNESS")

        if (
            dimensions["business_impact"] <= 1
            and dimensions["risk_coverage_value"] <= 2
            and dimensions["diagnostic_value"] <= 1
            and not guarded
        ):
            suggestions.append("REVIEW_LOW_VALUE_SMOKE")
        if dimensions["maintenance_cost"] >= 4 and dimensions["business_impact"] <= 2 and not guarded:
            suggestions.append("REVIEW_SIMPLIFICATION")
        if dimensions["redundancy_penalty"] >= 2:
            suggestions.append("REVIEW_DUPLICATE")
        if dimensions["diagnostic_value"] <= 1 and multi_risk:
            suggestions.append("SPLIT_FOR_DIAGNOSIS")
        if high_priority and dimensions["evidence_confidence"] <= 2:
            suggestions.append("RECONFIRM_PRIORITY_EVIDENCE")
        if guarded and assessment["total_score"] is not None and assessment["total_score"] < 45:
            suggestions.append("RETAIN_GUARDED_AND_IMPROVE")

        lines.extend(f"WARNING {tc_id} {code}" for code in warnings)
        lines.extend(f"SUGGESTION {tc_id} {code}" for code in suggestions)
        warning_count += len(warnings)
        suggestion_count += len(suggestions)

    lines.append(
        "SUMMARY testcase_value_assessment "
        f"computed={computed_count} insufficient={insufficient_count} "
        f"warning={warning_count} suggestion={suggestion_count} error=0"
    )
    return lines


MODEL_VALIDATORS: dict[str, Callable[[dict[str, Any]], list[str]]] = {
    "requirement": validate_requirement_model,
    "diff": validate_diff_model,
    "risk": validate_risk_matrix,
    "testcase": validate_testcase_model,
    "knowledge_table": validate_knowledge_table,
    "logic": validate_logic_version,
    "metric": validate_metric,
    "requirement_knowledge": validate_requirement_knowledge,
    "data_validation": validate_data_validation,
    "validation_sql": validate_validation_sql,
    "reconciliation": validate_reconciliation,
    "reconciliation_plan": validate_reconciliation,
    "api_automation": validate_api_automation,
}


def stable_source_hash(root: Path, paths: list[str]) -> str:
    return stable_multi_file_hash(root, paths)


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


def build_model_id_index(
    *,
    requirement_model: dict[str, Any] | None = None,
    diff_model: dict[str, Any] | None = None,
    risk_model: dict[str, Any] | None = None,
    testcase_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the single typed ID index shared by reports, manifests and model links."""

    requirement_model = requirement_model or {}
    diff_model = diff_model or {}
    risk_model = risk_model or {}
    testcase_model = testcase_model or {}

    def ids(items: Any, field: str) -> set[str]:
        if not isinstance(items, list):
            return set()
        return {
            str(item[field])
            for item in items
            if isinstance(item, dict) and isinstance(item.get(field), str) and item[field]
        }

    facts = requirement_model.get("facts", [])
    confirmations = requirement_model.get("confirmation_points", [])
    changes = diff_model.get("change_items", [])
    risks = risk_model.get("risk_items", [])
    cases = testcase_model.get("cases", [])
    testcase_ids = ids(cases, "tc_id")
    branch_ids: set[str] = set()
    branch_to_testcase: dict[str, str] = {}
    for case in cases if isinstance(cases, list) else []:
        if not isinstance(case, dict):
            continue
        for branch in case.get("entry_branches", []) if isinstance(case.get("entry_branches"), list) else []:
            if isinstance(branch, dict) and isinstance(branch.get("branch_id"), str):
                branch_id = branch["branch_id"]
                branch_ids.add(branch_id)
                branch_to_testcase[branch_id] = str(case.get("tc_id", ""))
    return {
        "fact_ids": ids(facts, "fact_id"),
        "confirmation_ids": ids(confirmations, "confirmation_id"),
        "change_ids": ids(changes, "change_id"),
        "risk_ids": ids(risks, "risk_id"),
        "testcase_ids": testcase_ids,
        "branch_ids": branch_ids,
        "branch_to_testcase": branch_to_testcase,
        "core_fact_ids": {
            str(item.get("fact_id")) for item in facts
            if isinstance(item, dict) and item.get("affects_core_expectation") is True
        },
        "blocking_confirmation_ids": {
            str(item.get("confirmation_id")) for item in confirmations
            if isinstance(item, dict) and item.get("severity") == "blocking" and item.get("status") != "resolved"
        },
        "high_risk_ids": {
            str(item.get("risk_id")) for item in risks
            if isinstance(item, dict) and (
                item.get("test_priority") == "P0" or item.get("business_impact") in {"critical", "high"}
            )
        },
    }
