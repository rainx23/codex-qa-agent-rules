#!/usr/bin/env python3
"""Validate formal testcase index uniqueness and passed-manifest coverage."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath


EXPECTED_HEADER = (
    "生成时间", "来源类型", "分析范围", "规则版本", "版本关系", "校验状态",
    "报告", "XMind Markdown", "Workbook", "Manifest", "备注",
)


def _cells(line: str) -> list[str]:
    value = line.strip().strip("|")
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in value:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


def _repository_root(index: Path) -> Path:
    resolved = index.resolve()
    for candidate in (resolved.parent, *resolved.parents):
        if (candidate / "RULE_VERSION").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    return resolved.parent.parent if resolved.parent.name == "testcases" else resolved.parent


def _safe_path(root: Path, value: str, label: str) -> tuple[Path | None, str | None]:
    native, posix, windows = Path(value), PurePosixPath(value), PureWindowsPath(value)
    if native.is_absolute() or posix.is_absolute() or windows.is_absolute() or windows.drive:
        return None, f"{label} 禁止绝对路径：{value}"
    if ".." in native.parts:
        return None, f"{label} 禁止包含 ../：{value}"
    resolved = (root / native).resolve()
    if resolved != root and root not in resolved.parents:
        return None, f"{label} resolve 后越出仓库：{value}"
    if not resolved.is_file():
        return None, f"{label} 文件不存在：{value}"
    return resolved, None


def validate_index(index: Path) -> list[str]:
    if not index.is_file():
        return [f"索引文件不存在：{index}"]
    root = _repository_root(index)
    lines = index.read_text(encoding="utf-8-sig").splitlines()
    table_lines = [line for line in lines if line.strip().startswith("|")]
    if len(table_lines) < 2:
        return ["索引缺少 Markdown 表头"]
    if tuple(_cells(table_lines[0])) != EXPECTED_HEADER:
        return ["索引表头不符合当前正式契约"]

    errors: list[str] = []
    rows: list[dict[str, str]] = []
    for line_no, line in enumerate(lines, 1):
        if not line.strip().startswith("|") or line == table_lines[0] or re.fullmatch(r"[|:\- ]+", line.strip()):
            continue
        cells = _cells(line)
        if len(cells) != len(EXPECTED_HEADER):
            errors.append(f"索引第 {line_no} 行列数应为 {len(EXPECTED_HEADER)}，实际为 {len(cells)}")
            continue
        row = dict(zip(EXPECTED_HEADER, cells))
        match = re.search(r"(?:^|;\s*)artifact_id=([^;]+)", row["备注"])
        row["artifact_id"] = match.group(1).strip() if match else ""
        row["line_no"] = str(line_no)
        rows.append(row)

    passed_rows = [row for row in rows if row["校验状态"] == "已校验"]
    for field in ("artifact_id", "Manifest"):
        values: dict[str, list[str]] = {}
        for row in passed_rows:
            value = row[field]
            if not value or value == "未生成":
                errors.append(f"已校验索引第 {row['line_no']} 行缺少 {field}")
                continue
            values.setdefault(value.replace("\\", "/"), []).append(row["line_no"])
        for value, positions in values.items():
            if len(positions) > 1:
                errors.append(f"已校验索引 {field} 重复：{value}，行 {', '.join(positions)}")

    for row in passed_rows:
        for field in ("报告", "XMind Markdown", "Workbook", "Manifest"):
            _, path_error = _safe_path(root, row[field], f"索引第 {row['line_no']} 行 {field}")
            if path_error:
                errors.append(path_error)

    indexed = {
        (row["artifact_id"], row["Manifest"].replace("\\", "/")): row for row in passed_rows
    }
    for manifest in (root / "testcases").glob("**/manifest.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Manifest 无法读取：{manifest.relative_to(root).as_posix()}：{exc}")
            continue
        if data.get("validation_status") != "passed":
            continue
        relative = manifest.relative_to(root).as_posix()
        artifact_id = str(data.get("artifact_id", "")).strip()
        if (artifact_id, relative) not in indexed:
            errors.append(
                f"PASSED_MANIFEST_NOT_UNIQUELY_INDEXED: {relative} 的 artifact_id={artifact_id or '<empty>'} 未唯一登记"
            )
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 passed Manifest 的索引唯一性与正式路径")
    parser.add_argument("index", type=Path)
    args = parser.parse_args()
    errors = validate_index(args.index)
    for error in errors:
        print(f"FAIL {error}", file=sys.stderr)
    if not errors:
        print(f"PASS {args.index}")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
