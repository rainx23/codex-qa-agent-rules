#!/usr/bin/env python3
"""Validate QA Manifest identity, sources, counts, versions, paths, and artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from heading_utils import parse_markdown_sections
from qa_contracts import (
    ALLOWED_TIMEZONES, DIMENSIONS, RELATIONS, SCHEMA_VERSION, VALIDATION_STATUSES, SQL_EXECUTION_STATUSES,
    ZERO_HASH, build_model_id_index, load_json, manifest_schema, read_rule_version, stable_source_hash, valid_generated_at,
    summarize_confirmations, validate_diff_model, validate_model_links, validate_requirement_model,
    validate_risk_matrix, validate_testcase_model,
    validate_schema_shape,
)
from qa_validation import (
    ValidationError, count_tree_nodes, markdown_tree, validate_markdown_file, validate_traceability_mapping,
    validate_xmind_archive,
)
from validate_analysis_report import canonical_heading, detect_mode, validate as validate_analysis_report


REQUIRED = {
    "schema_version", "artifact_id", "source_type", "source_id", "source_files", "source_hash_algorithm",
    "source_hash", "rule_version", "generated_at", "generated_timezone", "report_mode", "report_path",
    "analysis_model_paths", "risk_matrix_path", "testcase_model_path", "xmind_md_path", "xmind_path",
    "draft_report_path", "draft_risk_matrix_path", "draft_testcase_model_path", "draft_xmind_md_path",
    "case_count", "p0_count", "p0_risk_count", "p0_case_count", "pending_count",
    "blocking_pending_count", "nonblocking_pending_count", "suggested_pending_count",
    "validation_status", "relation", "supersedes", "failure_reason", "pending_reason",
}

LIFECYCLE_STATUSES = {"active", "superseded", "archived"}


def validate_current_rule_dimension_assessment(
    manifest: dict[str, Any],
    requirement_model: dict[str, Any] | None,
    current_rule_version: str,
) -> list[str]:
    """Require the eight-dimension scan for current-rule formal Requirement deliveries."""

    if not (
        manifest.get("validation_status") == "passed"
        and manifest.get("testcase_model_path")
        and manifest.get("rule_version") == current_rule_version
        and manifest.get("report_mode") in {"requirement", "combined"}
        and isinstance(requirement_model, dict)
    ):
        return []
    assessment = requirement_model.get("test_dimension_assessment")
    if not isinstance(assessment, list):
        return [
            "TEST_DIMENSION_ASSESSMENT_REQUIRED: 当前规则版本正式 passed 测试用例产物必须提供 test_dimension_assessment"
        ]
    dimensions = [item.get("dimension") for item in assessment if isinstance(item, dict)]
    expected = set(DIMENSIONS)
    errors: list[str] = []
    if set(dimensions) != expected or len(dimensions) != len(expected):
        errors.append("TEST_DIMENSION_ASSESSMENT_INCOMPLETE: 当前规则版本正式产物必须完整扫描固定八类维度")
    if len(dimensions) != len(set(dimensions)):
        errors.append("DUPLICATE_TEST_DIMENSION_ASSESSMENT: 每个测试分类维度只能出现一次")
    return errors


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "RULE_VERSION").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    return Path.cwd().resolve()


def artifact_workspace_root(manifest_path: Path) -> Path:
    """Resolve external deliveries relative to their own workspace, not the rules repository."""

    contract_root = find_repo_root(manifest_path.parent)
    manifest_parent = manifest_path.resolve().parent
    if manifest_parent == contract_root or contract_root in manifest_parent.parents:
        return contract_root
    return manifest_parent


def resolve_safe_path(value: Any, manifest_path: Path, artifact: bool = True) -> tuple[Path | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, str) or not value:
        return None, "路径必须是非空仓库相对路径或 null"
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None, f"路径禁止绝对路径或 ../：{value}"
    root = artifact_workspace_root(manifest_path)
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        return None, f"路径越界：{value}"
    return resolved, None


def _report_confirmation_summary(
    report_text: str,
    requirement_model: dict[str, Any],
) -> tuple[dict[str, int], list[str]]:
    body = ""
    for section in parse_markdown_sections(report_text):
        if canonical_heading(section.title) == "待确认点":
            body += "\n" + section.body
    entries: list[tuple[str, str, str, set[str]]] = []
    errors: list[str] = []
    for line in body.splitlines():
        match = re.match(r"\s*-\s+(.+)", line)
        if not match:
            continue
        item = match.group(1).strip()
        if item in {"无", "无。", "暂无", "暂无。"}:
            continue
        confirmation_match = re.search(r"\b(CONF-[A-Za-z0-9_.-]+)\b", item)
        severity_match = re.search(r"\bseverity=(blocking|nonblocking|suggested)\b", item)
        status_match = re.search(r"\bstatus=(pending|skipped|resolved)\b", item)
        fact_ids = set(re.findall(r"\bFACT-[A-Za-z0-9_.-]+\b", item))
        if not confirmation_match or not severity_match or not status_match or not fact_ids:
            errors.append("报告待确认点必须稳定标记 CONF ID、Fact ID、severity 和 status")
            continue
        entries.append((confirmation_match.group(1), severity_match.group(1), status_match.group(1), fact_ids))
    core_fact_ids = {
        fact.get("fact_id")
        for fact in requirement_model.get("facts", [])
        if fact.get("affects_core_expectation") is True and isinstance(fact.get("fact_id"), str)
    }
    pending = blocking = nonblocking = suggested = 0
    seen: set[str] = set()
    for confirmation_id, severity, status, fact_ids in entries:
        if confirmation_id in seen:
            errors.append(f"报告待确认点 CONF ID 重复：{confirmation_id}")
        seen.add(confirmation_id)
        skipped_core = status == "skipped" and bool(fact_ids & core_fact_ids)
        if status == "pending" or skipped_core:
            pending += 1
        if severity == "blocking" and (status == "pending" or skipped_core):
            blocking += 1
        if severity == "nonblocking" and status == "pending":
            nonblocking += 1
        if severity == "suggested" and status == "pending":
            suggested += 1
    return {
        "pending_count": pending,
        "blocking_pending_count": blocking,
        "nonblocking_pending_count": nonblocking,
        "suggested_pending_count": suggested,
    }, errors


def _resolve_draft_path(value: Any, manifest_path: Path, field: str) -> tuple[Path | None, str | None]:
    path, error = resolve_safe_path(value, manifest_path)
    if error or path is None:
        return path, error or f"{field} 路径不能为空"
    parts = Path(str(value)).parts
    in_draft_directory = parts[:2] == ("testcases", "drafts") or parts[:3] == ("tests", "fixtures", "drafts")
    if not in_draft_directory:
        return None, f"{field} 必须位于 testcases/drafts 或 tests/fixtures/drafts：{value}"
    if not path.is_file():
        return None, f"{field} 路径不存在：{value}"
    return path, None


def _artifact_registry(root: Path, current: Path) -> tuple[set[str], dict[str, str | None]]:
    ids: set[str] = set()
    graph: dict[str, str | None] = {}
    index = root / "testcases/index.md"
    if index.is_file():
        ids.update(re.findall(r"artifact_id=([A-Za-z0-9_.-]+)", index.read_text(encoding="utf-8-sig")))
    for path in (root / "testcases").rglob("*.json") if (root / "testcases").is_dir() else []:
        if path.resolve() == current.resolve():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and isinstance(data.get("artifact_id"), str):
            artifact_id = data["artifact_id"]
            ids.add(artifact_id)
            graph[artifact_id] = data.get("supersedes")
    return ids, graph


def _is_superseded_by_current_rule(
    root: Path, artifact_id: str, current_rule_version: str, current_path: Path
) -> bool:
    for path in (root / "testcases").glob("**/manifest.json") if (root / "testcases").is_dir() else []:
        if path.resolve() == current_path.resolve() or "drafts" in path.parts:
            continue
        try:
            candidate = load_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if (
            candidate.get("validation_status") in {"passed", "pending"}
            and candidate.get("relation") == "替代"
            and candidate.get("supersedes") == artifact_id
            and candidate.get("rule_version") == current_rule_version
            and (
                candidate.get("validation_status") == "passed"
                or (
                    isinstance(candidate.get("pending_reason"), str)
                    and bool(candidate.get("pending_reason").strip())
                    and int(candidate.get("blocking_pending_count", 0)) > 0
                )
            )
        ):
            return True
    return False


def _validate_supersedes(data: dict[str, Any], manifest_path: Path) -> list[str]:
    relation = data.get("relation")
    supersedes = data.get("supersedes")
    artifact_id = data.get("artifact_id")
    errors: list[str] = []
    if relation not in {"替代", "废弃"}:
        return errors
    if not isinstance(supersedes, str) or not supersedes:
        return ["替代或废弃关系必须填写 supersedes"]
    if supersedes == artifact_id:
        return ["supersedes 不能指向自身"]
    root = artifact_workspace_root(manifest_path)
    ids, graph = _artifact_registry(root, manifest_path)
    if supersedes not in ids:
        errors.append(f"supersedes 指向不存在 artifact_id：{supersedes}")
        return errors
    graph[str(artifact_id)] = supersedes
    seen: set[str] = set()
    current: str | None = str(artifact_id)
    while current:
        if current in seen:
            errors.append("supersedes 形成循环替代关系")
            break
        seen.add(current)
        current = graph.get(current)
    return errors


def _load_analysis_models(paths: list[Path], *, evidence_root: Path | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    models: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in paths:
        try:
            data = load_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"结构化分析模型无法读取：{path}: {exc}")
            continue
        kind = "requirement" if "facts" in data else "diff" if "change_items" in data else None
        if kind is None:
            errors.append(f"无法识别结构化分析模型类型：{path}")
            continue
        validator = validate_requirement_model if kind == "requirement" else validate_diff_model
        errors.extend(f"{path}: {error}" for error in validator(data, evidence_root=evidence_root))
        models.append(data)
    return models, errors


def validate_manifest_data(data: dict[str, Any], manifest_path: Path) -> list[str]:
    if "schema_version" not in data:
        return ["旧 Manifest 缺少 schema_version；请生成迁移版本，不要覆盖历史文件"]
    errors = [f"Manifest 缺少字段：{field}" for field in sorted(REQUIRED - set(data))]
    if errors:
        return errors
    root = artifact_workspace_root(manifest_path)
    contract_root = find_repo_root(manifest_path.parent)
    try:
        current_version = read_rule_version(contract_root)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        current_version = None
    def version_tuple(value: object) -> tuple[int, int, int] | None:
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", str(value))
        return tuple(int(item) for item in match.groups()) if match else None

    manifest_version = version_tuple(data.get("rule_version"))
    current_version_tuple = version_tuple(current_version)
    historical_compatible = bool(
        manifest_version and current_version_tuple and manifest_version < current_version_tuple
    )
    historical_superseded = bool(
        current_version
        and data.get("rule_version") != current_version
        and _is_superseded_by_current_rule(root, str(data.get("artifact_id", "")), current_version, manifest_path)
    )
    lifecycle_status = data.get("lifecycle_status")
    if lifecycle_status is None and historical_superseded:
        lifecycle_status = "superseded"
    if lifecycle_status is not None and lifecycle_status not in LIFECYCLE_STATUSES:
        errors.append(f"lifecycle_status 非法：{lifecycle_status}")
    if lifecycle_status == "active" and data.get("rule_version") != current_version and not historical_compatible:
        errors.append("active 产物必须使用当前 RULE_VERSION")
    contract_version = str(data.get("rule_version")) if historical_superseded or historical_compatible else current_version
    if contract_version is not None:
        errors.extend(f"Manifest Schema：{error}" for error in validate_schema_shape(data, manifest_schema(contract_version)))
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version 必须为 {SCHEMA_VERSION}")
    if data.get("rule_version") != current_version and not historical_superseded and not historical_compatible:
        errors.append(f"rule_version={data.get('rule_version')} 与 RULE_VERSION={current_version} 不一致")
    if data.get("source_hash_algorithm") != "sha256":
        errors.append("source_hash_algorithm 只允许 sha256")
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", str(data.get("source_hash", ""))):
        errors.append("source_hash 格式非法")
    if not valid_generated_at(data.get("generated_at")):
        errors.append("generated_at 必须严格使用 YYYY-MM-DD HH:mm:ss")
    if data.get("generated_timezone") not in ALLOWED_TIMEZONES:
        errors.append(f"generated_timezone 只允许 {list(ALLOWED_TIMEZONES)}")
    if data.get("validation_status") not in VALIDATION_STATUSES:
        errors.append(f"validation_status 非法：{data.get('validation_status')}")
    if data.get("relation") not in RELATIONS:
        errors.append(f"relation 非法：{data.get('relation')}")
    for key in ("case_count", "branch_count", "execution_instance_count", "p0_count", "p0_risk_count", "p0_case_count", "pending_count", "blocking_pending_count", "nonblocking_pending_count", "suggested_pending_count", "sql_count", "reconciliation_count"):
        value = data.get(key)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            errors.append(f"{key} 必须是非负整数")
    if data.get("sql_status") is not None and data.get("sql_status") not in SQL_EXECUTION_STATUSES:
        errors.append(f"sql_status 非法：{data.get('sql_status')}")
    if data.get("sql_status") in {"executed", "passed", "failed"} and not data.get("execution_evidence"):
        errors.append("没有用户执行结果时，sql_status 不得标记 executed/passed/failed")
    if data.get("sql_status") == "blocked":
        if data.get("validation_sql") is not None:
            errors.append("sql_status=blocked 时 validation_sql 必须为 null")
        if data.get("execution_evidence") is not None:
            errors.append("sql_status=blocked 时 execution_evidence 必须为 null")
    if data.get("p0_count") != data.get("p0_case_count"):
        errors.append("兼容字段 p0_count 必须等于 p0_case_count")
    if not data.get("requirement_id") and not data.get("commit_range"):
        errors.append("requirement_id 和 commit_range 至少填写一个")
    errors.extend(_validate_supersedes(data, manifest_path))

    if lifecycle_status in {"superseded", "archived"}:
        hash_inputs = list(data.get("source_files") or [])
        if not hash_inputs and data.get("source_snapshot_path"):
            hash_inputs = [data["source_snapshot_path"]]
        if not hash_inputs:
            errors.append("历史产物必须提供 source_files 或 source_snapshot_path")
        else:
            try:
                if stable_source_hash(root, hash_inputs) != data.get("source_hash"):
                    errors.append("历史产物 source_hash 与来源内容不一致")
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
        for field in ("report_path", "risk_matrix_path", "testcase_model_path", "xmind_md_path", "xmind_path"):
            path, path_error = resolve_safe_path(data.get(field), manifest_path)
            if path_error:
                errors.append(f"{field}: {path_error}")
            elif path is None or not path.is_file():
                errors.append(f"{field} 历史路径不存在：{data.get(field)}")
        return list(dict.fromkeys(errors))

    status = data.get("validation_status")
    formal_path_fields = ("report_path", "risk_matrix_path", "testcase_model_path", "xmind_md_path", "xmind_path")
    draft_path_fields = ("draft_report_path", "draft_risk_matrix_path", "draft_testcase_model_path", "draft_xmind_md_path")
    if data.get("blocking_pending_count", 0) > 0:
        if status != "pending":
            errors.append("blocking_pending_count > 0 时 validation_status 必须为 pending")
        if not data.get("pending_reason"):
            errors.append("阻塞类待确认点必须在 pending_reason 说明原因")
    if status == "failed":
        if not data.get("failure_reason"):
            errors.append("failed 状态必须填写 failure_reason")
        if data.get("pending_reason") is not None:
            errors.append("failed 状态 pending_reason 必须为 null")
        for field in formal_path_fields:
            if data.get(field) is not None:
                errors.append(f"failed 状态不得声明正式成功产物：{field} 必须为 null")
        if data.get("blocking_pending_count", 0) > 0:
            errors.append("正常 blocking 待确认应使用 pending，不应标记 failed")
        return list(dict.fromkeys(errors))
    if status == "pending":
        if not data.get("pending_reason"):
            errors.append("pending 状态必须填写 pending_reason")
        if data.get("failure_reason") is not None:
            errors.append("pending 状态 failure_reason 必须为 null")
        for field in formal_path_fields:
            if data.get(field) is not None:
                errors.append(f"pending 状态 {field} 必须为 null；正式产物只能在 passed 中声明")
        required_drafts = ("draft_report_path", "draft_risk_matrix_path", "draft_testcase_model_path")
        draft_paths: dict[str, Path] = {}
        for field in required_drafts:
            path, path_error = _resolve_draft_path(data.get(field), manifest_path, field)
            if path_error:
                errors.append(path_error)
            elif path is not None:
                draft_paths[field] = path
        if data.get("draft_xmind_md_path") is not None:
            path, path_error = _resolve_draft_path(data.get("draft_xmind_md_path"), manifest_path, "draft_xmind_md_path")
            if path_error:
                errors.append(path_error)
            elif path is not None:
                draft_paths["draft_xmind_md_path"] = path
        elif not re.search(r"(?:XMind|Markdown|未生成|不生成|生成前)", str(data.get("pending_reason", "")), re.I):
            errors.append("draft_xmind_md_path 为 null 时，pending_reason 必须说明未生成原因")

        analysis_paths: list[Path] = []
        if not isinstance(data.get("analysis_model_paths"), list) or not data["analysis_model_paths"]:
            errors.append("pending 状态必须至少包含一个 Requirement Analysis Model")
        else:
            for value in data["analysis_model_paths"]:
                path, path_error = resolve_safe_path(value, manifest_path)
                if path_error:
                    errors.append(f"analysis_model_paths: {path_error}")
                elif path is None or not path.is_file():
                    errors.append(f"结构化分析模型不存在：{value}")
                else:
                    analysis_paths.append(path)
        models, model_errors = _load_analysis_models(analysis_paths, evidence_root=root)
        errors.extend(model_errors)
        requirement_model = next((model for model in models if "facts" in model), None)
        diff_model = next((model for model in models if "change_items" in model), None)
        if requirement_model is None:
            errors.append("pending Requirement 分析必须包含合法 Requirement Analysis Model")
        if not all(field in draft_paths for field in required_drafts) or requirement_model is None:
            return list(dict.fromkeys(errors))
        try:
            risk_matrix = load_json(draft_paths["draft_risk_matrix_path"])
            testcase_model = load_json(draft_paths["draft_testcase_model_path"])
            errors.extend(validate_risk_matrix(risk_matrix, evidence_root=root))
            errors.extend(validate_testcase_model(testcase_model))
            errors.extend(validate_model_links(requirement_model, diff_model, risk_matrix, testcase_model, validation_status="pending"))
            summary = summarize_confirmations(requirement_model)
            manifest_summary = {
                key: data.get(key)
                for key in (
                    "pending_count", "blocking_pending_count",
                    "nonblocking_pending_count", "suggested_pending_count",
                )
            }
            expected_summary = {key: summary[key] for key in manifest_summary}
            if manifest_summary != expected_summary:
                errors.append(f"Manifest 待确认数量与 Requirement Model 不一致：Manifest={manifest_summary} model={expected_summary}")
            report_path = draft_paths["draft_report_path"]
            report_text = report_path.read_text(encoding="utf-8-sig")
            report_mode = detect_mode(report_text)
            if report_mode != data.get("report_mode"):
                errors.append(f"草稿报告模式 {report_mode} 与 Manifest {data.get('report_mode')} 不一致")
            for model in models:
                if model.get("report_mode") != data.get("report_mode"):
                    errors.append(f"结构化模型 {model.get('analysis_id')} report_mode 与 Manifest 不一致")
            report_errors = validate_analysis_report(
                report_path,
                xmind_md=draft_paths.get("draft_xmind_md_path"),
                mode=data.get("report_mode"),
                strict=True,
                known_ids=build_model_id_index(
                    requirement_model=requirement_model,
                    diff_model=diff_model,
                    risk_model=risk_matrix,
                    testcase_model=testcase_model,
                ),
                validation_status="pending",
            )
            errors.extend(f"草稿分析报告复验失败：{error}" for error in report_errors)
            report_summary, report_summary_errors = _report_confirmation_summary(report_text, requirement_model)
            errors.extend(report_summary_errors)
            if report_summary != expected_summary:
                errors.append(f"草稿报告待确认数量与 Requirement Model 不一致：report={report_summary} model={expected_summary}")
            risk_p0 = sum(risk.get("test_priority") == "P0" for risk in risk_matrix.get("risk_items", []))
            case_p0 = sum(case.get("test_priority") == "P0" for case in testcase_model.get("cases", []))
            if len(testcase_model.get("cases", [])) != data.get("case_count"):
                errors.append("case_count 与草稿 Testcase Model 不一致")
            if risk_p0 != data.get("p0_risk_count"):
                errors.append("p0_risk_count 与草稿 Risk Matrix 不一致")
            if case_p0 != data.get("p0_case_count"):
                errors.append("p0_case_count 与草稿 Testcase Model 不一致")
            if "draft_xmind_md_path" in draft_paths:
                validate_markdown_file(draft_paths["draft_xmind_md_path"])
        except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
            errors.append(f"草稿产物复验失败：{exc}")
        return list(dict.fromkeys(errors))
    if status != "passed" or errors:
        return list(dict.fromkeys(errors))

    if data.get("pending_reason") is not None or data.get("failure_reason") is not None:
        errors.append("passed 状态 pending_reason 和 failure_reason 必须为 null")
    for field in draft_path_fields:
        if data.get(field) is not None:
            errors.append(f"passed 状态不得使用草稿路径：{field} 必须为 null")

    if data.get("source_hash") == ZERO_HASH:
        errors.append("正式 passed Manifest 禁止使用全零 source_hash")
    source_files = data.get("source_files") if isinstance(data.get("source_files"), list) else []
    snapshot = data.get("source_snapshot_path")
    hash_inputs = list(source_files) if source_files else ([snapshot] if isinstance(snapshot, str) and snapshot else [])
    if not hash_inputs:
        errors.append("passed 状态必须提供 source_files 或 source_snapshot_path")
    else:
        try:
            actual_hash = stable_source_hash(root, hash_inputs)
            if actual_hash != data.get("source_hash"):
                errors.append(f"source_hash 与来源内容不一致：actual={actual_hash}")
        except (OSError, ValueError) as exc:
            errors.append(str(exc))

    path_fields = ("report_path", "risk_matrix_path", "testcase_model_path", "xmind_md_path", "xmind_path")
    paths: dict[str, Path] = {}
    for key in path_fields:
        path, path_error = resolve_safe_path(data.get(key), manifest_path)
        if path_error:
            errors.append(f"{key}: {path_error}")
        elif path is None or not path.is_file():
            errors.append(f"{key} 路径不存在：{data.get(key)}")
        else:
            paths[key] = path
    optional_paths = {"knowledge_snapshot": False, "data_validation_model": True, "validation_sql": True, "reconciliation_plan": True}
    for key, artifact in optional_paths.items():
        if data.get(key) is None:
            continue
        path, path_error = resolve_safe_path(data.get(key), manifest_path, artifact=artifact)
        if path_error:
            errors.append(f"{key}: {path_error}")
        elif path is None or not path.is_file():
            errors.append(f"{key} 路径不存在：{data.get(key)}")
    analysis_paths: list[Path] = []
    if not isinstance(data.get("analysis_model_paths"), list) or not data["analysis_model_paths"]:
        errors.append("passed 状态必须至少包含一个结构化分析模型")
    else:
        for value in data["analysis_model_paths"]:
            path, path_error = resolve_safe_path(value, manifest_path)
            if path_error:
                errors.append(f"analysis_model_paths: {path_error}")
            elif path is None or not path.is_file():
                errors.append(f"结构化分析模型不存在：{value}")
            else:
                analysis_paths.append(path)
    if errors:
        return list(dict.fromkeys(errors))

    models, model_errors = _load_analysis_models(analysis_paths, evidence_root=root)
    errors.extend(model_errors)
    try:
        risk_matrix = load_json(paths["risk_matrix_path"])
        testcase_model = load_json(paths["testcase_model_path"])
        errors.extend(validate_risk_matrix(risk_matrix, evidence_root=root))
        errors.extend(validate_testcase_model(testcase_model))
        requirement_model = next((model for model in models if "facts" in model), None)
        diff_model = next((model for model in models if "change_items" in model), None)
        if data.get("report_mode") in {"requirement", "combined"} and requirement_model is None:
            errors.append("需求分析交付缺少 Requirement Analysis Model")
        errors.extend(validate_current_rule_dimension_assessment(data, requirement_model, current_version))
        summary = summarize_confirmations(requirement_model or {})
        manifest_summary = {
            key: data.get(key)
            for key in (
                "pending_count", "blocking_pending_count",
                "nonblocking_pending_count", "suggested_pending_count",
            )
        }
        expected_summary = {key: summary[key] for key in manifest_summary}
        if manifest_summary != expected_summary:
            errors.append(f"Manifest 待确认数量与 Requirement Model 不一致：Manifest={manifest_summary} model={expected_summary}")
        if summary["blocking_pending_count"]:
            errors.append("passed 产物仍包含 unresolved blocking Confirmation")
        if summary["skipped_core_count"]:
            errors.append("passed 产物仍包含 skipped 且影响核心预期的 Confirmation")
        if summary["unresolved_core_fact_count"]:
            errors.append("passed 产物仍包含核心 missing/conflicting Fact")
        errors.extend(validate_model_links(requirement_model, diff_model, risk_matrix, testcase_model, validation_status="passed"))
        report_text = paths["report_path"].read_text(encoding="utf-8-sig")
        report_mode = detect_mode(report_text)
        if report_mode != data.get("report_mode"):
            errors.append(f"报告模式 {report_mode} 与 Manifest {data.get('report_mode')} 不一致")
        for model in models:
            if model.get("report_mode") != data.get("report_mode"):
                errors.append(f"结构化模型 {model.get('analysis_id')} report_mode 与 Manifest 不一致")
        report_errors = validate_analysis_report(
            paths["report_path"],
            xmind_md=paths["xmind_md_path"],
            mode=data["report_mode"],
            strict=True,
            known_ids=build_model_id_index(
                requirement_model=requirement_model,
                diff_model=diff_model,
                risk_model=risk_matrix,
                testcase_model=testcase_model,
            ),
            validation_status="passed",
            require_dimension_assessment=isinstance((requirement_model or {}).get("test_dimension_assessment"), list),
        )
        errors.extend(f"分析报告复验失败：{error}" for error in report_errors)
        outline = validate_markdown_file(paths["xmind_md_path"])
        trace_errors, _, _ = validate_traceability_mapping(report_text, report_mode, outline, risk_matrix, testcase_model)
        errors.extend(f"追踪复验失败：{error}" for error in trace_errors)
        report_summary, report_summary_errors = _report_confirmation_summary(report_text, requirement_model or {})
        errors.extend(report_summary_errors)
        if report_summary != expected_summary:
            errors.append(f"报告待确认数量与 Requirement Model 不一致：report={report_summary} model={expected_summary}")
        risk_p0 = sum(risk.get("test_priority") == "P0" for risk in risk_matrix.get("risk_items", []))
        p0_case_ids = {
            case.get("tc_id") for case in testcase_model.get("cases", []) if case.get("test_priority") == "P0"
        }
        p0_risk_tc_ids = {
            tc_id
            for risk in risk_matrix.get("risk_items", [])
            if risk.get("test_priority") == "P0"
            for tc_id in risk.get("testcase_ids", [])
        }
        case_p0 = len(p0_case_ids)
        if risk_p0 != data["p0_risk_count"]:
            errors.append(f"p0_risk_count={data['p0_risk_count']} 与风险矩阵 {risk_p0} 不一致")
        if case_p0 != data["p0_case_count"]:
            errors.append(f"p0_case_count={data['p0_case_count']} 与 Testcase Model {case_p0} 不一致")
        if p0_case_ids != p0_risk_tc_ids:
            errors.append(
                f"P0 用例与 P0 风险映射不一致：cases={sorted(p0_case_ids)} risks={sorted(p0_risk_tc_ids)}"
            )
        xmind_tc_ids = {node.title for node in outline.tc_nodes}
        if not p0_risk_tc_ids.issubset(xmind_tc_ids):
            errors.append(f"P0 风险映射 TC 未全部存在于 XMind：{sorted(p0_risk_tc_ids - xmind_tc_ids)}")
        if len(testcase_model.get("cases", [])) != data["case_count"] or len(outline.tc_nodes) != data["case_count"]:
            errors.append("case_count 与 Testcase Model 或 Markdown TC 数不一致")
        if "branch_count" in data and data.get("branch_count") != testcase_model.get("branch_count", 0):
            errors.append("branch_count 与 Testcase Model 不一致")
        if "execution_instance_count" in data and data.get("execution_instance_count") != testcase_model.get("execution_instance_count", 0):
            errors.append("execution_instance_count 与 Testcase Model 不一致")
        validate_xmind_archive(
            paths["xmind_path"], outline.root.title, len(outline.tc_nodes), count_tree_nodes(outline.root),
            markdown_tree(outline.root),
        )
    except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        errors.append(f"产物复验失败：{exc}")
    return list(dict.fromkeys(errors))


def validate_manifest_file(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        data = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, [f"Manifest 无法读取：{exc}"]
    return data, validate_manifest_data(data, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 QA 产物 Manifest")
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    passed = failed = 0
    for path in args.files:
        _, errors = validate_manifest_file(path)
        if errors:
            failed += 1
            for error in errors:
                print(f"FAIL {path}: {error}", file=sys.stderr)
        else:
            passed += 1
            print(f"PASS {path}: manifest authentic")
    print(f"SUMMARY passed={passed} warning=0 failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
