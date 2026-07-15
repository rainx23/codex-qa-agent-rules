#!/usr/bin/env python3
"""Validate QA artifact manifests without third-party dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from qa_validation import ValidationError, count_tree_nodes, validate_markdown_file, validate_xmind_archive
from validate_analysis_report import validate as validate_analysis_report

REQUIRED = {
    "artifact_id", "source_type", "source_id", "source_hash", "rule_version",
    "generated_at", "report_path", "xmind_md_path", "xmind_path",
    "case_count", "p0_count", "pending_count", "validation_status",
    "relation", "supersedes",
}
STATUSES = {"passed", "failed", "pending"}
RELATIONS = {"新增", "补充", "替代", "废弃"}


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "AGENTS.md").exists():
            return candidate
    return Path.cwd().resolve()


def resolve_artifact_path(value: str, manifest_path: Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return find_repo_root(manifest_path.parent) / candidate


def validate_manifest_data(data: dict, manifest_path: Path) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED - set(data))
    if missing:
        return [f"Manifest 缺少字段：{missing}"]

    for key in ("artifact_id", "source_type", "source_id", "source_hash", "rule_version", "generated_at"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            errors.append(f"{key} 必须是非空字符串")
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", str(data.get("source_hash", ""))):
        errors.append("source_hash 必须使用 sha256: 加 64 位十六进制")
    if not data.get("requirement_id") and not data.get("commit_range"):
        errors.append("requirement_id 和 commit_range 至少填写一个")

    for key in ("case_count", "p0_count", "pending_count"):
        value = data.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{key} 必须是非负整数")
    if isinstance(data.get("case_count"), int) and isinstance(data.get("p0_count"), int) and data["p0_count"] > data["case_count"]:
        errors.append("p0_count 不得超过 case_count")
    if data.get("validation_status") not in STATUSES:
        errors.append(f"validation_status 只允许 {sorted(STATUSES)}")
    if data.get("relation") not in RELATIONS:
        errors.append(f"relation 只允许 {sorted(RELATIONS)}")
    if data.get("relation") in {"替代", "废弃"} and not data.get("supersedes"):
        errors.append("替代或废弃关系必须填写 supersedes")
    if data.get("validation_status") == "failed" and not data.get("failure_reason"):
        errors.append("failed 状态必须填写 failure_reason")

    if errors or data.get("validation_status") != "passed":
        return errors

    paths = {
        key: resolve_artifact_path(str(data.get(key, "")), manifest_path)
        for key in ("report_path", "xmind_md_path", "xmind_path")
    }
    for key, path in paths.items():
        if not path.is_file():
            errors.append(f"{key} 路径不存在：{path}")
    if errors:
        return errors

    try:
        outline = validate_markdown_file(paths["xmind_md_path"])
        report_errors = validate_analysis_report(
            paths["report_path"],
            xmind_md=paths["xmind_md_path"],
        )
        errors.extend(f"分析报告复验失败：{error}" for error in report_errors)
        report_text = paths["report_path"].read_text(encoding="utf-8-sig")
        report_p0 = len(re.findall(r"风险等级[:：]\s*P0", report_text))
        if report_p0 != data["p0_count"]:
            errors.append(f"p0_count={data['p0_count']} 与报告 P0 风险数 {report_p0} 不一致")
        if len(outline.tc_nodes) != data["case_count"]:
            errors.append(f"case_count={data['case_count']} 与 Markdown TC 数 {len(outline.tc_nodes)} 不一致")
        validate_xmind_archive(paths["xmind_path"], outline.root.title, len(outline.tc_nodes), count_tree_nodes(outline.root))
    except (OSError, ValidationError) as exc:
        errors.append(f"用例或 Workbook 复验失败：{exc}")

    return errors


def validate_manifest_file(path: Path) -> tuple[dict, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"Manifest 无法读取：{exc}"]
    if not isinstance(data, dict):
        return {}, ["Manifest 根对象必须是 JSON object"]
    return data, validate_manifest_data(data, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 QA 产物 Manifest")
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    failed = 0
    for path in args.files:
        _, errors = validate_manifest_file(path)
        if errors:
            failed += 1
            print(f"FAIL {path}: " + "；".join(errors), file=sys.stderr)
        else:
            print(f"PASS {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
