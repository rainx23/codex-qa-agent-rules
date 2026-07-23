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
    if data.get("validation_status") != "passed":
        raise ValueError("只有 validation_status=passed 的正式 Manifest 才能更新 Index")
    resolved_index = index.resolve()
    root = next(
        (
            candidate for candidate in (resolved_index.parent, *resolved_index.parents)
            if (candidate / "RULE_VERSION").is_file() and (candidate / "AGENTS.md").is_file()
        ),
        resolved_index.parent.parent if resolved_index.parent.name == "testcases" else resolved_index.parent,
    )
    try:
        indexed_manifest = manifest.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"Manifest 必须位于索引所属仓库内：{manifest}") from exc
    row = build_row(data, Path(indexed_manifest))
    text = index.read_text(encoding="utf-8-sig") if index.exists() else HEADER
    lines = migrate_index_text(text).splitlines()
    marker = f"artifact_id={data['artifact_id']}"
    positions = [position for position, line in enumerate(lines) if marker in line]
    if positions:
        raise ValueError(f"索引中 artifact_id 已存在，禁止重复写入：{data['artifact_id']}")
    manifest_positions = [
        position for position, line in enumerate(lines)
        if len(_cells(line)) == 11 and _cells(line)[9].replace("\\", "/") == indexed_manifest
    ]
    if manifest_positions:
        raise ValueError(f"索引中 Manifest 路径重复或绑定其他 artifact_id：{indexed_manifest}")
    lines.append(row)
    candidate_text = "\n".join(lines).rstrip() + "\n"
    index.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, dir=index.parent, suffix=".index.tmp"
        ) as handle:
            handle.write(candidate_text)
            temporary = Path(handle.name)
        from validate_testcase_index import validate_index

        canonical_index = root / "testcases/index.md"
        validation_errors = validate_index(temporary) if index.resolve() == canonical_index.resolve() else []
        if validation_errors:
            raise ValueError("Index 更新后校验失败：" + "；".join(validation_errors))
        temporary.replace(index)
        temporary = None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


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
