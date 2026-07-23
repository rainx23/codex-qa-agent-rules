#!/usr/bin/env python3
"""Initialize evidence and non-fictional top-level QA model skeletons."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from file_hash_utils import stable_file_content_hash
from qa_contracts import SCHEMA_VERSION, read_rule_version


def _timezone(name: str) -> timezone:
    return timezone(timedelta(hours=8)) if name == "Asia/Shanghai" else timezone.utc


def _atomic_json(path: Path, data: dict) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp"
    ) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def initialize(
    root: Path,
    task_dir: Path,
    source: Path,
    *,
    mode: str,
    report_mode: str,
    source_type: str,
    source_id: str,
    timezone_name: str,
) -> list[Path]:
    if task_dir.exists():
        raise ValueError(f"任务目录已存在，禁止覆盖：{task_dir}")
    task_dir.mkdir(parents=True)
    evidence_dir = task_dir / "evidence"
    evidence_dir.mkdir()
    suffix = source.suffix if source.suffix else ".txt"
    snapshot = evidence_dir / f"user-requirement{suffix}"
    shutil.copyfile(source, snapshot)

    now = datetime.now(_timezone(timezone_name))
    captured_at = now.strftime("%Y-%m-%d %H:%M:%S")
    rule_version = read_rule_version(root)
    snapshot_hash = stable_file_content_hash(snapshot)
    try:
        snapshot_relative = snapshot.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("任务目录必须位于规则仓库内") from exc
    evidence = {
        "source_type": source_type,
        "storage_type": "snapshot",
        "source_path": None,
        "snapshot_path": snapshot_relative,
        "source_record_id": source_id,
        "line_start": 1 if snapshot.suffix.lower() not in {".png", ".jpg", ".jpeg", ".pdf"} else None,
        "line_end": len(snapshot.read_text(encoding="utf-8-sig").splitlines()) or 1
        if snapshot.suffix.lower() not in {".png", ".jpg", ".jpeg", ".pdf"} else None,
        "commit_sha": None,
        "content_hash": snapshot_hash,
        "excerpt": "",
        "captured_at": captured_at,
        "captured_timezone": timezone_name,
        "evidence_status": "current",
    }
    _atomic_json(evidence_dir / "snapshot.json", evidence)

    shared_metadata = {
        "schema_version": SCHEMA_VERSION,
        "report_mode": report_mode,
        "workflow_stage": mode,
        "rule_version": rule_version,
        "generated_at": captured_at,
        "generated_timezone": timezone_name,
    }
    requirement = {
        **shared_metadata,
        "analysis_id": f"AN-{source_id}",
        "model_id": f"REQMODEL-{source_id}",
        "source_type": source_type,
        "source_ids": [source_id],
        "analysis_scope": "",
        "business_goal": "",
        "acceptance_basis": "",
        "facts": [],
        "confirmation_points": [],
        "risks": [],
        "acceptance_criteria": [],
        "regression_scope": [],
        "matched_profiles": [],
        "data_validation_required": "blocked",
        "data_validation_reason": "待从 Evidence Snapshot 分析",
        "recommended_validation_method": "blocked",
        "sql_generation_status": "blocked",
        "validation_missing_information": [],
        "condition_matrix_required": False,
        "test_dimension_assessment": [],
        "original_task_scope": {
            "request_id": source_id,
            "request_text": "",
            "rule_paths": ["AGENTS.md"],
            "source_ids": [source_id],
            "requested_deliverables": [
                "requirement_analysis", "risk_coverage_matrix", "testcase_model",
                "xmind_markdown", "xmind_workbook", "manifest", "index",
            ],
            "authorized_at": captured_at,
            "continuation_policy": "auto_resume",
        },
        "confirmation_checkpoint": {
            "checkpoint_id": f"CHECKPOINT-{source_id}",
            "created_at": captured_at,
            "scan_completed": False,
            "evidence_saved": True,
            "requirement_aspects_scanned": [],
            "test_dimensions_scanned": [],
            "condition_matrix_assessed": False,
            "confirmation_scan_completed": False,
            "downstream_artifacts_generated": [],
        },
        "risk_directions": [],
    }
    risk = {
        **shared_metadata,
        "matrix_id": f"MATRIX-{source_id}",
        "model_id": f"RISKMODEL-{source_id}",
        "analysis_ids": [requirement["analysis_id"]],
        "risk_items": [],
        "coverage_summary": {"risk_count": 0, "p0_risk_count": 0, "covered_risk_count": 0},
    }
    testcase = {
        **shared_metadata,
        "model_id": f"TCMODEL-{source_id}",
        "root_title": "",
        "cases": [],
        "branch_count": 0,
        "execution_instance_count": 0,
        "execution_instances": [],
    }
    outputs = [
        task_dir / "requirement-analysis.json",
        task_dir / "risk-coverage-matrix.json",
        task_dir / "testcase-model.json",
    ]
    for path, data in zip(outputs, (requirement, risk, testcase)):
        _atomic_json(path, data)
    return [snapshot, evidence_dir / "snapshot.json", *outputs]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="初始化当前 QA 任务模型与 Evidence Snapshot")
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--mode", choices=("confirmation_only", "formal_generation"), required=True)
    parser.add_argument("--report-mode", choices=("requirement", "combined"), default="requirement")
    parser.add_argument("--source-type", default="pasted_text")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--timezone", choices=("Asia/Shanghai", "UTC"), default="Asia/Shanghai")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        outputs = initialize(
            root, args.task_dir, args.source, mode=args.mode, report_mode=args.report_mode,
            source_type=args.source_type, source_id=args.source_id, timezone_name=args.timezone,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(1, f"FAIL {exc}\n")
    for path in outputs:
        print(f"PASS {path}")
    print(
        "NEXT use scripts/update_task_model.py with JSON Patch data; "
        "do not create temporary model-building scripts"
    )
    print("SUMMARY passed=1 warning=0 failed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
