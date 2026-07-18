#!/usr/bin/env python3
"""Migrate and atomically update the QA artifact index."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from validate_manifest import validate_manifest_file


HEADER = (
    "# 测试分析输出索引\n\n"
    "| 生成时间 | 来源类型 | 分析范围 | 规则版本 | 版本关系 | 校验状态 | 报告 | XMind Markdown | Workbook | Manifest | 备注 |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
)
STATUS_LABEL = {"passed": "已校验", "failed": "校验失败", "pending": "待校验"}


def _escape(value: object) -> str:
    return str(value).replace("|", "\\|")


def _row(fields: list[object]) -> str:
    return "| " + " | ".join(_escape(value) for value in fields) + " |"


def build_row(data: dict, manifest_path: Path) -> str:
    scope = data.get("requirement_id") or data.get("commit_range") or data["source_id"]
    note_parts = [
        f"artifact_id={data['artifact_id']}", f"cases={data['case_count']}",
        f"P0_risks={data['p0_risk_count']}", f"P0_cases={data['p0_case_count']}",
        f"pending={data['pending_count']}",
    ]
    if data.get("supersedes"):
        note_parts.append(f"supersedes={data['supersedes']}")
    fields = [
        data["generated_at"], data["source_type"], scope, data["rule_version"], data["relation"],
        STATUS_LABEL[data["validation_status"]], data.get("report_path") or "未生成",
        data.get("xmind_md_path") or "未生成", data.get("xmind_path") or "未生成",
        manifest_path.as_posix(), "; ".join(note_parts),
    ]
    return _row(fields)


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def migrate_index_text(text: str) -> str:
    """Add governance metadata without changing historical artifact files."""

    if "| 规则版本 | 版本关系 | 校验状态 |" in text:
        return text.rstrip() + "\n"
    lines = text.splitlines()
    migrated: list[str] = []
    old_header_seen = False
    for line in lines:
        if line.startswith("| 生成时间 | 来源类型 | 分析范围 | 版本状态 |"):
            migrated.extend(HEADER.rstrip().splitlines()[2:3])
            old_header_seen = True
            continue
        if old_header_seen and line.startswith("| ---"):
            migrated.append(HEADER.rstrip().splitlines()[3])
            old_header_seen = False
            continue
        if line.startswith("|") and len(_cells(line)) == 8:
            generated, source, scope, legacy_status, report, markdown, workbook, note = _cells(line)
            metadata = (
                f"legacy_rule_version=unknown; current_validation_status=未按当前规则校验; "
                f"migration_status=未迁移; legacy_business_status={legacy_status}"
            )
            migrated.append(_row([generated, source, scope, "unknown", "未记录", "未按当前规则校验", report, markdown, workbook, "未生成", f"{note}; {metadata}".strip("; ")]))
            continue
        migrated.append(line)
    return "\n".join(migrated).rstrip() + "\n"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def migrate(index: Path) -> None:
    text = index.read_text(encoding="utf-8-sig") if index.exists() else HEADER
    _atomic_write(index, migrate_index_text(text))


def update(index: Path, manifest: Path) -> None:
    data, errors = validate_manifest_file(manifest)
    if errors:
        raise ValueError("；".join(errors))
    root = index.resolve().parent.parent if index.resolve().parent.name == "testcases" else index.resolve().parent
    try:
        indexed_manifest = manifest.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"Manifest 必须位于索引所属仓库内：{manifest}") from exc
    row = build_row(data, Path(indexed_manifest))
    text = index.read_text(encoding="utf-8-sig") if index.exists() else HEADER
    lines = migrate_index_text(text).splitlines()
    marker = f"artifact_id={data['artifact_id']}"
    positions = [position for position, line in enumerate(lines) if marker in line]
    if len(positions) > 1:
        raise ValueError(f"索引中 artifact_id 重复：{data['artifact_id']}")
    manifest_positions = [
        position for position, line in enumerate(lines)
        if len(_cells(line)) == 11 and _cells(line)[9].replace("\\", "/") == indexed_manifest
    ]
    if len(manifest_positions) > 1 or (manifest_positions and manifest_positions != positions):
        raise ValueError(f"索引中 Manifest 路径重复或绑定其他 artifact_id：{indexed_manifest}")
    if positions:
        lines[positions[0]] = row
    else:
        lines.append(row)
    _atomic_write(index, "\n".join(lines).rstrip() + "\n")
    if sum(marker in line for line in index.read_text(encoding="utf-8").splitlines()) != 1:
        raise ValueError("索引原子更新后 artifact_id 唯一性校验失败")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="迁移或更新测试产物索引")
    parser.add_argument("index", type=Path)
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument("--migrate-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.migrate_only:
            migrate(args.index)
        elif args.manifest is None:
            parser.error("更新索引时必须提供 manifest")
        else:
            update(args.index, args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, f"FAIL {args.index}: {exc}\n")
    print(f"PASS {args.index}")
    print("SUMMARY passed=1 warning=0 failed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
