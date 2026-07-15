#!/usr/bin/env python3
"""Atomically append or update testcases/index.md from a valid Manifest."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from validate_manifest import validate_manifest_file

HEADER = (
    "# 测试分析输出索引\n\n"
    "| 生成时间 | 来源类型 | 分析范围 | 版本状态 | 分析报告路径 | XMind Markdown 路径 | XMind Workbook 路径 | 备注 |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
)
STATUS_LABEL = {"passed": "已确认", "failed": "待确认", "pending": "草稿"}


def build_row(data: dict, manifest_path: Path) -> str:
    scope = data.get("requirement_id") or data.get("commit_range") or data["source_id"]
    note_parts = [
        f"artifact_id={data['artifact_id']}",
        f"rule={data['rule_version']}",
        f"cases={data['case_count']}",
        f"P0={data['p0_count']}",
        f"pending={data['pending_count']}",
        f"relation={data['relation']}",
        f"manifest={manifest_path.as_posix()}",
    ]
    if data.get("supersedes"):
        note_parts.append(f"supersedes={data['supersedes']}")
    fields = [
        data["generated_at"], data["source_type"], scope,
        STATUS_LABEL[data["validation_status"]], data["report_path"],
        data["xmind_md_path"], data["xmind_path"], "; ".join(note_parts),
    ]
    return "| " + " | ".join(str(value).replace("|", "\\|") for value in fields) + " |"


def update(index: Path, manifest: Path) -> None:
    data, errors = validate_manifest_file(manifest)
    if errors:
        raise ValueError("；".join(errors))
    row = build_row(data, manifest)
    text = index.read_text(encoding="utf-8-sig") if index.exists() else HEADER
    lines = text.splitlines()
    marker = f"artifact_id={data['artifact_id']}"
    positions = [position for position, line in enumerate(lines) if marker in line]
    if len(positions) > 1:
        raise ValueError(f"索引中 artifact_id 重复：{data['artifact_id']}")
    if positions:
        lines[positions[0]] = row
    else:
        lines.append(row)
    result = "\n".join(lines).rstrip() + "\n"
    index.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=index.parent, suffix=".tmp") as handle:
        handle.write(result)
        temporary = Path(handle.name)
    temporary.replace(index)
    if sum(marker in line for line in index.read_text(encoding="utf-8").splitlines()) != 1:
        raise ValueError("索引原子更新后 artifact_id 唯一性校验失败")


def main() -> int:
    parser = argparse.ArgumentParser(description="由已校验 Manifest 更新测试产物索引")
    parser.add_argument("index", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        update(args.index, args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f"FAIL {args.index}: {exc}\n")
    print(f"PASS {args.index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

