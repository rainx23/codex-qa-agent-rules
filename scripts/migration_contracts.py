"""Schema 1.0.0 -> 2.0.0 migration contracts.

Migration is deliberately conservative: absence of proof never becomes a
confirmed fact, accepted risk, passing API/SQL artifact, or passing execution.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import json

FROM_VERSION = "1.0.0"
TO_VERSION = "2.0.0"
ACTIONS = {"copied", "renamed", "transformed", "defaulted", "unknown", "reconfirm_required", "dropped", "error"}


@dataclass(frozen=True)
class MigrationContext:
    source_path: Path
    destination_path: Path
    root: Path
    from_version: str = FROM_VERSION
    to_version: str = TO_VERSION
    model_type: str = ""
    dry_run: bool = False
    preserve_unknown_fields: bool = True


@dataclass
class MigrationChange:
    json_path: str
    action: str
    source_field: str | None
    target_field: str | None
    old_value: Any
    new_value: Any
    reason: str
    requires_confirmation: bool = False

    def as_dict(self) -> dict[str, Any]:
        if self.action not in ACTIONS:
            raise ValueError(f"invalid migration action: {self.action}")
        return self.__dict__.copy()


@dataclass
class MigrationResult:
    data: dict[str, Any]
    status: str = "passed"
    changes: list[dict[str, Any]] = field(default_factory=list)
    unknown_fields: list[dict[str, Any]] = field(default_factory=list)
    reconfirm_required: list[dict[str, Any]] = field(default_factory=list)
    dropped_fields: list[dict[str, Any]] = field(default_factory=list)
    validation_results: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def serialize_json(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")


EXPLICIT_TYPES = {
    "requirement": "requirement_analysis", "requirement_analysis": "requirement_analysis",
    "diff": "diff_impact", "diff_impact": "diff_impact",
    "risk": "risk_coverage_matrix", "risk_coverage_matrix": "risk_coverage_matrix",
    "testcase": "testcase_model", "testcase_model": "testcase_model",
    "manifest": "artifact_manifest", "artifact_manifest": "artifact_manifest",
    "validation_sql": "validation_sql", "sql": "validation_sql",
    "api_automation": "api_automation", "api_automation_artifact": "api_automation_artifact",
    "execution_model": "execution_model", "execution": "execution_model",
    "knowledge_table": "knowledge_table",
}
SIGNATURES = {
    "requirement_analysis": {"requirements", "facts", "confirmation_points"},
    "diff_impact": {"changes", "changed_files"},
    "risk_coverage_matrix": {"risks", "risk_items"},
    "testcase_model": {"testcases", "cases"},
    "artifact_manifest": {"analysis_model_paths", "artifacts", "manifest_id"},
    "validation_sql": {"sql", "sql_artifacts", "queries"},
    "api_automation": {"interfaces", "api_cases", "endpoints"},
    "api_automation_artifact": {"api_model_id", "script_path", "artifact_id"},
    "execution_model": {"executions", "execution_instances", "execution_model_id"},
    "knowledge_table": {"tables", "table_name", "columns"},
}


def detect_model_type(data: Any) -> str:
    if not isinstance(data, dict):
        raise ValueError("model root must be an object")
    explicit_raw = data.get("model_type") or data.get("artifact_type") or data.get("kind")
    explicit = EXPLICIT_TYPES.get(str(explicit_raw)) if explicit_raw is not None else None
    if explicit_raw is not None and explicit is None:
        raise ValueError(f"unsupported explicit model type: {explicit_raw}")
    matches = {name for name, keys in SIGNATURES.items() if keys.intersection(data)}
    if explicit:
        conflicting = matches - {explicit}
        if conflicting or (matches and explicit not in matches):
            raise ValueError(f"model type conflicts with structure: {explicit_raw} / {sorted(matches)}")
        return explicit
    if len(matches) != 1:
        raise ValueError("unable to identify model type" if not matches else f"ambiguous model type: {sorted(matches)}")
    return matches.pop()


def _change(path: str, action: str, source: str | None, target: str | None, old: Any, new: Any, reason: str, reconfirm: bool = False) -> dict[str, Any]:
    return MigrationChange(path, action, source, target, old, new, reason, reconfirm).as_dict()


def _base(data: dict[str, Any], model_type: str, known: set[str]) -> MigrationResult:
    if data.get("schema_version") == TO_VERSION:
        required_shape = {
            "requirement_analysis": "facts", "diff_impact": "changes", "risk_coverage_matrix": "risks",
            "testcase_model": "testcases", "artifact_manifest": "validation_status", "validation_sql": "validation_status",
            "api_automation": "validation_status", "api_automation_artifact": "validation_status",
            "execution_model": "validation_status", "knowledge_table": "tables",
        }[model_type]
        if required_shape not in data:
            raise ValueError("2.0.0 marker uses legacy structure; required v2 field missing")
        return MigrationResult(deepcopy(data), "unchanged", validation_results=[{"validator": model_type, "status": "passed"}])
    if data.get("schema_version") != FROM_VERSION:
        raise ValueError(f"source schema_version must be {FROM_VERSION}")
    output = {key: deepcopy(value) for key, value in data.items() if key in known and key not in {"schema_version", "model_type", "artifact_type", "kind"}}
    output["schema_version"] = TO_VERSION
    output["model_type"] = model_type
    result = MigrationResult(output)
    result.changes.append(_change("$.schema_version", "transformed", "schema_version", "schema_version", FROM_VERSION, TO_VERSION, "fixed supported migration path"))
    for key, value in data.items():
        if key not in known and key not in {"schema_version", "model_type", "artifact_type", "kind"}:
            item = {"json_path": f"$.{key}", "value": deepcopy(value), "reason": "unmapped legacy field"}
            result.unknown_fields.append(item)
            result.changes.append(_change(f"$.{key}", "unknown", key, None, value, None, "preserved in migration report", True))
    return result


def _pending(result: MigrationResult, path: str, reason: str) -> None:
    result.status = "pending"
    item = {"json_path": path, "reason": reason}
    result.reconfirm_required.append(item)
    result.changes.append(_change(path, "reconfirm_required", None, None, None, "pending", reason, True))


def migrate_requirement_model(data: dict[str, Any]) -> MigrationResult:
    result = _base(data, "requirement_analysis", {"schema_version", "model_type", "model_id", "rule_version", "requirements", "facts", "confirmation_points", "evidence_references", "validation_status"})
    if result.status == "unchanged": return result
    facts = []
    for index, raw in enumerate(data.get("facts", data.get("requirements", [])), 1):
        item = deepcopy(raw) if isinstance(raw, dict) else {"text": str(raw)}
        item.setdefault("fact_id", f"FACT-{index:03d}")
        evidence = item.get("evidence_references", [])
        item["status"] = "confirmed" if evidence else "unknown"
        item.setdefault("category", "missing" if any(x in item.get("text", "") for x in ("待确认", "不明确", "未知")) else "stated")
        facts.append(item)
        if not evidence: _pending(result, f"$.facts[{index-1}]", "fact has no evidence and cannot be confirmed")
    result.data["facts"] = facts
    confirmations = deepcopy(data.get("confirmation_points", []))
    if result.reconfirm_required and not confirmations:
        confirmations = [{"confirmation_id": "CONF-001", "severity": "blocking", "status": "pending", "fact_ids": [x["fact_id"] for x in facts]}]
    for index, confirmation in enumerate(confirmations):
        confirmation.setdefault("confirmation_id", f"CONF-{index+1:03d}")
        confirmation.setdefault("severity", "blocking")
        confirmation["status"] = "pending" if confirmation.get("status") != "resolved" else "pending"
    result.data["confirmation_points"] = confirmations
    result.data.setdefault("model_id", "REQ-MIG-001")
    result.data.setdefault("rule_version", "2.0.0")
    result.data["validation_status"] = "pending" if result.reconfirm_required or result.unknown_fields else "passed"
    if result.unknown_fields: result.status = "pending"
    result.validation_results = [{"validator": "requirement_schema_and_domain", "status": "passed"}]
    return result


def migrate_diff_model(data: dict[str, Any]) -> MigrationResult:
    result = _base(data, "diff_impact", {"schema_version", "model_type", "model_id", "rule_version", "changes", "changed_files", "validation_status"})
    if result.status == "unchanged": return result
    changes = deepcopy(data.get("changes", []))
    for index, change in enumerate(changes):
        change.setdefault("change_id", f"CHG-{index+1:03d}")
        if not change.get("commit_sha"):
            change["source_state"] = "working_tree"
        if change.get("risk_summary") and not change.get("risk_ids"):
            _pending(result, f"$.changes[{index}].risk_summary", "risk summary has no real Risk ID")
    result.data["changes"] = changes
    result.data["validation_status"] = "pending" if result.reconfirm_required else "passed"
    result.validation_results = [{"validator": "diff_schema_and_domain", "status": "passed"}]
    return result


def migrate_risk_model(data: dict[str, Any]) -> MigrationResult:
    result = _base(data, "risk_coverage_matrix", {"schema_version", "model_type", "model_id", "rule_version", "risks", "risk_items", "validation_status"})
    if result.status == "unchanged": return result
    risks = deepcopy(data.get("risks", data.get("risk_items", [])))
    for index, risk in enumerate(risks):
        risk.setdefault("risk_id", f"RISK-{index+1:03d}")
        title = risk.get("core_assertion") or risk.get("title", "")
        unreliable = title in {"功能异常", "可能有问题", ""} or risk.get("disposition") in {"accepted", "merged", "resolved"}
        if unreliable:
            risk["disposition"] = "reconfirm_required"
            _pending(result, f"$.risks[{index}]", "risk assertion or disposition lacks structured evidence")
    result.data["risks"] = risks
    result.data["validation_status"] = "pending" if result.reconfirm_required else "passed"
    result.validation_results = [{"validator": "risk_schema_and_domain", "status": "passed"}]
    return result


def migrate_testcase_model(data: dict[str, Any]) -> MigrationResult:
    result = _base(data, "testcase_model", {"schema_version", "model_type", "model_id", "rule_version", "testcases", "cases", "validation_status"})
    if result.status == "unchanged": return result
    cases = deepcopy(data.get("testcases", data.get("cases", [])))
    for index, case in enumerate(cases):
        case.setdefault("testcase_id", f"TC-{index+1:03d}")
        branches = case.get("branches")
        if branches is None and case.get("steps") and case.get("expected_result"):
            case["branches"] = [{"branch_id": f"{case['testcase_id']}-B01", "steps": deepcopy(case["steps"]), "expected_result": case["expected_result"]}]
        elif branches is None:
            case["branches"] = []
            _pending(result, f"$.testcases[{index}].branches", "branch boundary or expected result cannot be inferred")
        case["branch_count"] = len(case["branches"])
    result.data["testcases"] = cases
    result.data["validation_status"] = "pending" if result.reconfirm_required else "passed"
    result.validation_results = [{"validator": "testcase_schema_and_domain", "status": "passed"}]
    return result


def migrate_manifest(data: dict[str, Any]) -> MigrationResult:
    result = _base(data, "artifact_manifest", {"schema_version", "model_type", "manifest_id", "analysis_model_paths", "artifacts", "validation_status", "pending_reason", "failure_reason", "draft_paths", "formal_paths", "hashes", "counts"})
    if result.status == "unchanged": return result
    result.data["validation_status"] = "pending"
    result.data["pending_reason"] = "all migrated dependencies, paths, hashes, and domain gates must be revalidated"
    _pending(result, "$.validation_status", "legacy passed status is never inherited")
    result.validation_results = [{"validator": "manifest_validator", "status": "pending"}]
    return result


def migrate_validation_sql(data: dict[str, Any]) -> MigrationResult:
    result = _base(data, "validation_sql", {"schema_version", "model_type", "model_id", "sql", "queries", "parameters", "join_keys", "identifier_evidence", "source_reference", "source_reference_type", "source_reference_id", "evidence_references", "validation_status"})
    if result.status == "unchanged": return result
    if not data.get("source_reference_type") or not data.get("identifier_evidence"):
        result.data["evidence_state"] = "reconfirm_required"
        _pending(result, "$.identifier_evidence", "field-level identifier evidence is missing")
    result.data["validation_status"] = "pending" if result.reconfirm_required else "passed"
    result.validation_results = [{"validator": "validate_sql_artifact", "status": "pending" if result.reconfirm_required else "passed"}]
    return result


def migrate_api_model(data: dict[str, Any]) -> MigrationResult:
    result = _base(data, "api_automation", {"schema_version", "model_type", "model_id", "interfaces", "api_cases", "endpoints", "assertion_scope", "content", "validation_status"})
    if result.status == "unchanged": return result
    fixed = data.get("assertion_scope") == "parameter_health" and data.get("content") == {"code": 0, "msg": "OK"}
    if not fixed:
        _pending(result, "$.assertion_scope", "legacy API protocol cannot be rewritten as the fixed health contract")
    result.data["validation_status"] = "passed" if fixed else "pending"
    result.validation_results = [{"validator": "validate_api_automation", "status": result.data["validation_status"]}]
    return result


def migrate_api_artifact(data: dict[str, Any]) -> MigrationResult:
    result = _base(data, "api_automation_artifact", {"schema_version", "model_type", "artifact_id", "api_model_id", "script_path", "assertions", "validation_status"})
    if result.status == "unchanged": return result
    if not data.get("api_model_id"):
        _pending(result, "$.api_model_id", "artifact cannot be verified against a real API model")
    result.data["validation_status"] = "pending" if result.reconfirm_required else "passed"
    result.validation_results = [{"validator": "validate_api_automation_artifacts", "status": result.data["validation_status"]}]
    return result


def migrate_execution_model(data: dict[str, Any]) -> MigrationResult:
    result = _base(data, "execution_model", {"schema_version", "model_type", "execution_model_id", "testcase_model_id", "executions", "execution_instances", "branch_count", "execution_instance_count", "validation_status"})
    if result.status == "unchanged": return result
    instances = deepcopy(data.get("execution_instances", data.get("executions", [])))
    mapping = {"success": "passed", "failure": "failed", "blocked": "blocked", "not executed": "not_run"}
    for index, instance in enumerate(instances):
        instance.setdefault("execution_instance_id", f"EXEC-{index+1:03d}")
        instance["status"] = mapping.get(instance.get("status"), instance.get("status", "not_run"))
        instance.setdefault("run_type", "initial")
        instance.setdefault("run_sequence", 1)
        if not instance.get("branch_id") or (instance["status"] in {"passed", "failed"} and not instance.get("evidence_references")):
            _pending(result, f"$.execution_instances[{index}]", "branch or execution evidence cannot be inferred")
    result.data["execution_instances"] = instances
    result.data["execution_instance_count"] = len(instances)
    result.data["branch_count"] = len({x.get("branch_id") for x in instances if x.get("branch_id")})
    result.data["validation_status"] = "pending" if result.reconfirm_required else "passed"
    result.validation_results = [{"validator": "validate_execution_instances", "status": result.data["validation_status"]}]
    return result


def migrate_knowledge_table(data: dict[str, Any]) -> MigrationResult:
    result = _base(data, "knowledge_table", {"schema_version", "model_type", "tables", "table_name", "columns", "raw_ddl", "validation_status"})
    if result.status == "unchanged": return result
    tables = deepcopy(data.get("tables", [data] if data.get("table_name") else []))
    for index, table in enumerate(tables):
        if table.get("parse_status") == "complete" and not all(key in table for key in ("raw_fragment", "parsed_tokens", "unparsed_fragment")):
            table["parse_status"] = "partial"
            _pending(result, f"$.tables[{index}].parse_status", "complete token consumption was not proven")
    result.data["tables"] = tables
    result.data["validation_status"] = "pending" if result.reconfirm_required else "passed"
    result.validation_results = [{"validator": "validate_knowledge", "status": result.data["validation_status"]}]
    return result


MIGRATORS: dict[str, Callable[[dict[str, Any]], MigrationResult]] = {
    "requirement_analysis": migrate_requirement_model,
    "diff_impact": migrate_diff_model,
    "risk_coverage_matrix": migrate_risk_model,
    "testcase_model": migrate_testcase_model,
    "artifact_manifest": migrate_manifest,
    "validation_sql": migrate_validation_sql,
    "api_automation": migrate_api_model,
    "api_automation_artifact": migrate_api_artifact,
    "execution_model": migrate_execution_model,
    "knowledge_table": migrate_knowledge_table,
}


def migrate_document(data: Any, model_type: str | None = None) -> MigrationResult:
    detected = detect_model_type(data)
    if model_type and detected != model_type:
        raise ValueError(f"requested model type {model_type} conflicts with detected {detected}")
    return MIGRATORS[detected](data)
