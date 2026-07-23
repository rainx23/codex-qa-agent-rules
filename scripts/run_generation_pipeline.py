#!/usr/bin/env python3
"""Run the formal QA artifact chain once, in fail-fast order, with an audit log."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

from qa_contracts import load_json, validate_requirement_model, validate_risk_matrix


CommandExecutor = Callable[[list[str], Path], int]


def _execute(command: list[str], cwd: Path) -> int:
    return subprocess.run(command, cwd=cwd, check=False).returncode


def run_pipeline(
    root: Path,
    *,
    requirement: Path,
    diff: Path | None,
    risk: Path,
    testcase: Path,
    report: Path,
    xmind_md: Path,
    xmind: Path,
    manifest: Path,
    index: Path,
    relation: str,
    supersedes: str | None,
    executor: CommandExecutor = _execute,
) -> tuple[int, list[dict[str, object]]]:
    audit: list[dict[str, object]] = []

    def record(stage: str, command: list[str] | None, exit_code: int, reason: str = "") -> bool:
        audit.append({
            "stage": stage,
            "command": command or [],
            "exit_code": exit_code,
            "status": "PASS" if exit_code == 0 else "FAIL",
            "failure_reason": reason,
            "repair_attempts": 0,
        })
        return exit_code == 0

    try:
        requirement_errors = validate_requirement_model(load_json(requirement), evidence_root=root)
    except (OSError, ValueError) as exc:
        requirement_errors = [str(exc)]
    if not record("requirement_validation", [], 1 if requirement_errors else 0, "；".join(requirement_errors)):
        return 1, audit

    try:
        risk_errors = validate_risk_matrix(load_json(risk), evidence_root=root)
    except (OSError, ValueError) as exc:
        risk_errors = [str(exc)]
    if not record("risk_validation", [], 1 if risk_errors else 0, "；".join(risk_errors)):
        return 1, audit

    commands: list[tuple[str, list[str]]] = []
    validate_models = [
        sys.executable, "scripts/validate_models.py", "--requirement", str(requirement),
        "--risk", str(risk), "--testcase", str(testcase),
    ]
    if diff:
        validate_models.extend(["--diff", str(diff)])
    commands.append(("validate_models", validate_models))
    commands.extend([
        ("validate_xmind_md", [sys.executable, "scripts/validate_xmind_md.py", str(xmind_md)]),
        ("validate_testcase_quality", [sys.executable, "scripts/validate_testcase_quality.py", str(xmind_md)]),
        ("md_to_xmind", [sys.executable, "scripts/md_to_xmind.py", str(xmind_md), "--output", str(xmind), "--overwrite"]),
        ("verify_xmind", [sys.executable, "scripts/verify_xmind.py", str(xmind), "--markdown", str(xmind_md)]),
    ])
    build_manifest = [
        sys.executable, "scripts/build_task_manifest.py",
        "--requirement-model", str(requirement), "--risk-matrix", str(risk),
        "--testcase-model", str(testcase), "--report", str(report),
        "--xmind-md", str(xmind_md), "--xmind", str(xmind),
        "--output", str(manifest), "--relation", relation,
    ]
    if diff:
        build_manifest.extend(["--diff-model", str(diff)])
    if supersedes:
        build_manifest.extend(["--supersedes", supersedes])
    commands.extend([
        ("build_task_manifest", build_manifest),
        ("validate_manifest", [sys.executable, "scripts/validate_manifest.py", str(manifest)]),
        ("build_testcase_index", [sys.executable, "scripts/build_testcase_index.py", str(index), str(manifest)]),
        ("validate_testcase_index", [sys.executable, "scripts/validate_testcase_index.py", str(index)]),
        ("validate_task", [sys.executable, "scripts/validate_task.py", "--manifest", str(manifest), "--index", str(index)]),
        ("delivery_summary", [sys.executable, "scripts/render_delivery_summary.py", "--manifest", str(manifest), "--check"]),
    ])
    for stage, command in commands:
        code = executor(command, root)
        if not record(stage, command, code, "" if code == 0 else f"{stage} 退出码 {code}"):
            return code or 1, audit
    return 0, audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按固定顺序执行 QA 正式生成与校验链")
    parser.add_argument("--requirement", required=True, type=Path)
    parser.add_argument("--diff", type=Path)
    parser.add_argument("--risk", required=True, type=Path)
    parser.add_argument("--testcase", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--xmind-md", required=True, type=Path)
    parser.add_argument("--xmind", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--index", type=Path, default=Path("testcases/index.md"))
    parser.add_argument("--relation", choices=("新增", "补充", "替代", "废弃"), default="新增")
    parser.add_argument("--supersedes")
    parser.add_argument("--audit", required=True, type=Path)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    code, audit = run_pipeline(
        root, requirement=args.requirement, diff=args.diff, risk=args.risk,
        testcase=args.testcase, report=args.report, xmind_md=args.xmind_md,
        xmind=args.xmind, manifest=args.manifest, index=args.index,
        relation=args.relation, supersedes=args.supersedes,
    )
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SUMMARY passed={1 if code == 0 else 0} warning=0 failed={0 if code == 0 else 1}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
