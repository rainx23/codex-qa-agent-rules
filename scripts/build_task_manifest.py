#!/usr/bin/env python3
"""Build, validate, and atomically publish one deterministic passed Manifest."""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from qa_contracts import SCHEMA_VERSION, load_json, read_rule_version, stable_source_hash, summarize_confirmations
from validate_manifest import validate_manifest_file
from validate_models import validate_files


def _timezone(name: str) -> timezone:
    return timezone(timedelta(hours=8)) if name == "Asia/Shanghai" else timezone.utc


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"正式产物必须位于仓库内：{path}") from exc


def _evidence_sources(model: dict[str, Any]) -> tuple[list[str], list[str]]:
    files: set[str] = set()
    snapshots: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("storage_type") == "file" and value.get("source_path"):
                files.add(str(value["source_path"]))
            if value.get("storage_type") == "snapshot" and value.get("snapshot_path"):
                snapshots.add(str(value["snapshot_path"]))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(model)
    return sorted(files), sorted(snapshots)


def build_manifest(
    root: Path,
    output: Path,
    *,
    requirement_path: Path | None,
    diff_path: Path | None,
    risk_path: Path,
    testcase_path: Path,
    report_path: Path,
    xmind_md_path: Path,
    xmind_path: Path,
    relation: str,
    supersedes: str | None,
    timezone_name: str,
) -> dict[str, Any]:
    model_errors = validate_files(requirement_path, diff_path, risk_path, testcase_path)
    if model_errors:
        raise ValueError("模型校验失败，禁止创建 Manifest：" + "；".join(model_errors))

    requirement = load_json(requirement_path) if requirement_path else None
    diff = load_json(diff_path) if diff_path else None
    risk = load_json(risk_path)
    testcase = load_json(testcase_path)
    source_model = requirement or diff or {}
    source_files, snapshots = _evidence_sources(source_model)
    if source_files:
        snapshot = None
        hash_inputs = source_files
    elif len(snapshots) == 1:
        snapshot = snapshots[0]
        hash_inputs = snapshots
    else:
        raise ValueError("模型必须提供 source_files，或恰好一个可复验 source_snapshot_path")

    report_mode = "combined" if requirement and diff else "requirement" if requirement else "diff"
    source_ids = source_model.get("source_ids", [])
    source_id = str(source_ids[0]) if source_ids else str(
        source_model.get("analysis_id") or source_model.get("model_id")
    )
    cases = testcase.get("cases", [])
    risks = risk.get("risk_items", [])
    summary = summarize_confirmations(requirement or {})
    generated_at = datetime.now(_timezone(timezone_name)).strftime("%Y-%m-%d %H:%M:%S")
    analysis_paths = [
        _relative(root, path) for path in (requirement_path, diff_path) if path is not None
    ]
    artifact_id = str(testcase.get("model_id") or f"QA-{source_id}")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": artifact_id,
        "source_type": str(source_model.get("source_type") or "diff"),
        "source_id": source_id,
        "source_files": source_files,
        "source_snapshot_path": snapshot,
        "source_hash_algorithm": "sha256",
        "source_hash": stable_source_hash(root, hash_inputs),
        "requirement_id": source_id if requirement else None,
        "commit_range": (diff or {}).get("comparison_expression"),
        "rule_version": read_rule_version(root),
        "generated_at": generated_at,
        "generated_timezone": timezone_name,
        "report_mode": report_mode,
        "report_path": _relative(root, report_path),
        "analysis_model_paths": analysis_paths,
        "risk_matrix_path": _relative(root, risk_path),
        "testcase_model_path": _relative(root, testcase_path),
        "xmind_md_path": _relative(root, xmind_md_path),
        "xmind_path": _relative(root, xmind_path),
        "draft_report_path": None,
        "draft_risk_matrix_path": None,
        "draft_testcase_model_path": None,
        "draft_xmind_md_path": None,
        "case_count": len(cases),
        "branch_count": int(testcase.get("branch_count", 0)),
        "execution_instance_count": int(testcase.get("execution_instance_count", 0)),
        "p0_count": sum(case.get("test_priority") == "P0" for case in cases),
        "p0_risk_count": sum(item.get("test_priority") == "P0" for item in risks),
        "p0_case_count": sum(case.get("test_priority") == "P0" for case in cases),
        "pending_count": summary["pending_count"],
        "blocking_pending_count": summary["blocking_pending_count"],
        "nonblocking_pending_count": summary["nonblocking_pending_count"],
        "suggested_pending_count": summary["suggested_pending_count"],
        "validation_status": "passed",
        "relation": relation,
        "supersedes": supersedes,
        "failure_reason": None,
        "pending_reason": None,
    }
    return manifest


def publish(output: Path, data: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, dir=output.parent, suffix=".manifest.tmp"
        ) as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temporary = Path(handle.name)
        _, errors = validate_manifest_file(temporary)
        if errors:
            raise ValueError("Manifest 校验失败：" + "；".join(errors))
        temporary.replace(output)
        temporary = None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从正式模型和文件确定性构建 Manifest")
    parser.add_argument("--requirement-model", type=Path)
    parser.add_argument("--diff-model", type=Path)
    parser.add_argument("--risk-matrix", required=True, type=Path)
    parser.add_argument("--testcase-model", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--xmind-md", required=True, type=Path)
    parser.add_argument("--xmind", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--relation", choices=("新增", "补充", "替代", "废弃"), default="新增")
    parser.add_argument("--supersedes")
    parser.add_argument("--timezone", choices=("Asia/Shanghai", "UTC"), default="Asia/Shanghai")
    args = parser.parse_args(argv)
    if not args.requirement_model and not args.diff_model:
        parser.error("--requirement-model 与 --diff-model 至少提供一个")
    root = Path(__file__).resolve().parents[1]
    try:
        data = build_manifest(
            root, args.output, requirement_path=args.requirement_model, diff_path=args.diff_model,
            risk_path=args.risk_matrix, testcase_path=args.testcase_model, report_path=args.report,
            xmind_md_path=args.xmind_md, xmind_path=args.xmind, relation=args.relation,
            supersedes=args.supersedes, timezone_name=args.timezone,
        )
        publish(args.output, data)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f"FAIL {exc}\n")
    print(f"PASS {args.output}: manifest generated and validated")
    print("SUMMARY passed=1 warning=0 failed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
