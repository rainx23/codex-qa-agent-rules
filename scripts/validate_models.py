#!/usr/bin/env python3
"""Validate the actual structured models produced for one analysis run."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from qa_contracts import (
    load_json, validate_diff_model, validate_model_links, validate_requirement_model,
    validate_risk_matrix, validate_testcase_model,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _iter_evidence_references(value: object):
    if isinstance(value, dict):
        if {"source_type", "content_hash", "evidence_status"}.issubset(value):
            yield value
        for item in value.values():
            yield from _iter_evidence_references(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_evidence_references(item)


def _validate_evidence_freshness(models: list[dict | None], root: Path) -> list[str]:
    errors: list[str] = []
    for model in models:
        if not model:
            continue
        for evidence in _iter_evidence_references(model):
            source_path = evidence.get("source_path")
            expected = evidence.get("content_hash")
            if not source_path or not expected:
                continue
            path = Path(source_path)
            if not path.is_absolute():
                path = root / path
            if not path.is_file():
                continue
            raw = path.read_bytes()
            actual = f"sha256:{hashlib.sha256(raw).hexdigest()}"
            if actual != expected and evidence.get("evidence_status") == "current":
                errors.append(
                    f"证据 {source_path} 内容哈希已变化；必须将 evidence_status 标记为 stale/reconfirm_required，"
                    "或重新采集证据"
                )
            line_start = evidence.get("line_start")
            line_end = evidence.get("line_end")
            try:
                lines = raw.decode("utf-8-sig").splitlines()
            except UnicodeDecodeError:
                lines = []
            if lines and isinstance(line_start, int) and isinstance(line_end, int):
                if line_end > len(lines):
                    errors.append(f"证据 {source_path} 行号超出文件范围：{line_start}-{line_end}/{len(lines)}")
                elif evidence.get("excerpt") not in "\n".join(lines[line_start - 1:line_end]):
                    errors.append(f"证据 {source_path}:{line_start}-{line_end} 的 excerpt 与原文不一致")
    return errors


def validate_files(requirement: Path | None, diff: Path | None, risk: Path, testcase: Path) -> list[str]:
    errors: list[str] = []
    try:
        requirement_data = load_json(requirement) if requirement else None
        diff_data = load_json(diff) if diff else None
        risk_data = load_json(risk)
        testcase_data = load_json(testcase)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    if requirement_data:
        errors.extend(f"requirement: {item}" for item in validate_requirement_model(requirement_data))
    if diff_data:
        errors.extend(f"diff: {item}" for item in validate_diff_model(diff_data))
    errors.extend(f"risk: {item}" for item in validate_risk_matrix(risk_data))
    errors.extend(f"testcase: {item}" for item in validate_testcase_model(testcase_data))
    modes = {model.get("report_mode") for model in (requirement_data, diff_data) if model}
    expected_mode = "combined" if requirement_data and diff_data else "requirement" if requirement_data else "diff"
    if modes != {expected_mode}:
        errors.append(f"report_mode 必须为 {expected_mode}，实际为 {sorted(str(item) for item in modes)}")
    errors.extend(validate_model_links(requirement_data, diff_data, risk_data, testcase_data))
    errors.extend(_validate_evidence_freshness([requirement_data, diff_data, risk_data, testcase_data], REPOSITORY_ROOT))
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="校验本次生成的 Requirement/Diff/Risk/Testcase 模型")
    parser.add_argument("--requirement", type=Path)
    parser.add_argument("--diff", type=Path)
    parser.add_argument("--risk", required=True, type=Path)
    parser.add_argument("--testcase", required=True, type=Path)
    args = parser.parse_args()
    if not args.requirement and not args.diff:
        parser.error("--requirement 与 --diff 至少提供一个")
    errors = validate_files(args.requirement, args.diff, args.risk, args.testcase)
    for error in errors:
        print(f"FAIL {error}", file=sys.stderr)
    if not errors:
        print("PASS actual structured models are valid")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
