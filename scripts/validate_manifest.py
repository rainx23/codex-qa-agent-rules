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
    ALLOWED_TIMEZONES, MODEL_VALIDATORS, RELATIONS, SCHEMA_VERSION, VALIDATION_STATUSES, SQL_EXECUTION_STATUSES,
    ZERO_HASH, load_json, manifest_schema, read_rule_version, stable_source_hash, valid_generated_at,
    validate_model_links, validate_risk_matrix, validate_testcase_model,
    validate_schema_shape,
)
from qa_validation import (
    ValidationError, count_tree_nodes, validate_markdown_file, validate_traceability_mapping,
    validate_xmind_archive,
)
from validate_analysis_report import canonical_heading, detect_mode, validate as validate_analysis_report


REQUIRED = {
    "schema_version", "artifact_id", "source_type", "source_id", "source_files", "source_hash_algorithm",
    "source_hash", "rule_version", "generated_at", "generated_timezone", "report_mode", "report_path",
    "analysis_model_paths", "risk_matrix_path", "testcase_model_path", "xmind_md_path", "xmind_path",
    "case_count", "p0_count", "p0_risk_count", "p0_case_count", "pending_count",
    "blocking_pending_count", "nonblocking_pending_count", "suggested_pending_count",
    "validation_status", "relation", "supersedes", "failure_reason", "pending_reason",
}


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "RULE_VERSION").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    return Path.cwd().resolve()


def resolve_safe_path(value: Any, manifest_path: Path, artifact: bool = True) -> tuple[Path | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, str) or not value:
        return None, "路径必须是非空仓库相对路径或 null"
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None, f"路径禁止绝对路径或 ../：{value}"
    root = find_repo_root(manifest_path.parent)
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        return None, f"路径越界：{value}"
    if artifact and candidate.parts and candidate.parts[0] not in {"testcases", "tests"}:
        return None, f"产物路径必须位于 testcases 或 tests：{value}"
    return resolved, None


def _pending_counts(report_text: str) -> tuple[int, int, int, int]:
    body = ""
    for section in parse_markdown_sections(report_text):
        if canonical_heading(section.title) == "待确认点":
            body += "\n" + section.body
    items = []
    for line in body.splitlines():
        match = re.match(r"\s*-\s+(.+)", line)
        if not match:
            continue
        item = match.group(1).strip()
        if item in {"无", "无。", "暂无", "暂无。"}:
            continue
        if re.search(r"已确认|已解决|已完成", item) and not re.search(r"跳过|忽略", item):
            continue
        items.append(item)
    blocking = sum("阻塞类" in item and "非阻塞类" not in item for item in items)
    nonblocking = sum("非阻塞类" in item for item in items)
    suggested = sum("建议确认类" in item for item in items)
    return len(items), blocking, nonblocking, suggested


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
    root = find_repo_root(manifest_path.parent)
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


def _load_analysis_models(paths: list[Path]) -> tuple[list[dict[str, Any]], list[str]]:
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
        errors.extend(f"{path}: {error}" for error in MODEL_VALIDATORS[kind](data))
        models.append(data)
    return models, errors


def validate_manifest_data(data: dict[str, Any], manifest_path: Path) -> list[str]:
    if "schema_version" not in data:
        return ["旧 Manifest 缺少 schema_version；请生成迁移版本，不要覆盖历史文件"]
    errors = [f"Manifest 缺少字段：{field}" for field in sorted(REQUIRED - set(data))]
    if errors:
        return errors
    root = find_repo_root(manifest_path.parent)
    try:
        current_version = read_rule_version(root)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        current_version = None
    if current_version is not None:
        errors.extend(f"Manifest Schema：{error}" for error in validate_schema_shape(data, manifest_schema(current_version)))
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version 必须为 {SCHEMA_VERSION}")
    if data.get("rule_version") != current_version:
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
    for key in ("case_count", "p0_count", "p0_risk_count", "p0_case_count", "pending_count", "blocking_pending_count", "nonblocking_pending_count", "suggested_pending_count", "sql_count", "reconciliation_count"):
        value = data.get(key)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            errors.append(f"{key} 必须是非负整数")
    if data.get("sql_status") is not None and data.get("sql_status") not in SQL_EXECUTION_STATUSES:
        errors.append(f"sql_status 非法：{data.get('sql_status')}")
    if data.get("sql_status") in {"executed", "passed", "failed"} and not data.get("execution_evidence"):
        errors.append("没有用户执行结果时，sql_status 不得标记 executed/passed/failed")
    if data.get("p0_count") != data.get("p0_case_count"):
        errors.append("兼容字段 p0_count 必须等于 p0_case_count")
    pending_sum = sum(data.get(key, 0) for key in ("blocking_pending_count", "nonblocking_pending_count", "suggested_pending_count") if isinstance(data.get(key), int))
    if data.get("pending_count") != pending_sum:
        errors.append("pending_count 必须等于三类待确认点数量之和")
    if not data.get("requirement_id") and not data.get("commit_range"):
        errors.append("requirement_id 和 commit_range 至少填写一个")
    errors.extend(_validate_supersedes(data, manifest_path))

    status = data.get("validation_status")
    if data.get("blocking_pending_count", 0) > 0:
        if status != "pending":
            errors.append("blocking_pending_count > 0 时 validation_status 必须为 pending")
        if not data.get("pending_reason"):
            errors.append("阻塞类待确认点必须在 pending_reason 说明原因")
    if status == "failed":
        if not data.get("failure_reason"):
            errors.append("failed 状态必须填写 failure_reason")
        if data.get("xmind_path"):
            path, path_error = resolve_safe_path(data["xmind_path"], manifest_path)
            if path_error:
                errors.append(path_error)
            elif path is not None and not path.is_file():
                errors.append("failed 状态不得填写不存在的 Workbook 路径")
        return list(dict.fromkeys(errors))
    if status == "pending":
        if not data.get("pending_reason"):
            errors.append("pending 状态必须填写 pending_reason")
        if data.get("xmind_path") is not None:
            errors.append("pending 状态 xmind_path 必须为 null；正式 Workbook 只能在 passed 产物中声明")
        return list(dict.fromkeys(errors))
    if status != "passed" or errors:
        return list(dict.fromkeys(errors))

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

    models, model_errors = _load_analysis_models(analysis_paths)
    errors.extend(model_errors)
    try:
        risk_matrix = load_json(paths["risk_matrix_path"])
        testcase_model = load_json(paths["testcase_model_path"])
        errors.extend(validate_risk_matrix(risk_matrix))
        errors.extend(validate_testcase_model(testcase_model))
        requirement_model = next((model for model in models if "facts" in model), None)
        diff_model = next((model for model in models if "change_items" in model), None)
        if requirement_model:
            core_missing = [fact.get("fact_id") for fact in requirement_model.get("facts", []) if fact.get("category") == "missing" and fact.get("affects_core_expectation")]
            if core_missing:
                errors.append(f"passed 产物仍包含核心 missing Fact，不得正式交付：{core_missing}")
        errors.extend(validate_model_links(requirement_model, diff_model, risk_matrix, testcase_model))
        report_text = paths["report_path"].read_text(encoding="utf-8-sig")
        report_mode = detect_mode(report_text)
        if report_mode != data.get("report_mode"):
            errors.append(f"报告模式 {report_mode} 与 Manifest {data.get('report_mode')} 不一致")
        for model in models:
            if model.get("report_mode") != data.get("report_mode"):
                errors.append(f"结构化模型 {model.get('analysis_id')} report_mode 与 Manifest 不一致")
        report_errors = validate_analysis_report(paths["report_path"], xmind_md=paths["xmind_md_path"], mode=data["report_mode"])
        errors.extend(f"分析报告复验失败：{error}" for error in report_errors)
        outline = validate_markdown_file(paths["xmind_md_path"])
        trace_errors, _, _ = validate_traceability_mapping(report_text, report_mode, outline, risk_matrix, testcase_model)
        errors.extend(f"追踪复验失败：{error}" for error in trace_errors)
        total_pending, blocking, nonblocking, suggested = _pending_counts(report_text)
        actual_pending = (total_pending, blocking, nonblocking, suggested)
        expected_pending = (data["pending_count"], data["blocking_pending_count"], data["nonblocking_pending_count"], data["suggested_pending_count"])
        if actual_pending != expected_pending:
            errors.append(f"待确认点计数不一致：Manifest={expected_pending} report={actual_pending}")
        if total_pending != blocking + nonblocking + suggested:
            errors.append("报告存在未分类待确认点；必须明确 blocking/nonblocking/suggested")
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
        validate_xmind_archive(paths["xmind_path"], outline.root.title, len(outline.tc_nodes), count_tree_nodes(outline.root))
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
