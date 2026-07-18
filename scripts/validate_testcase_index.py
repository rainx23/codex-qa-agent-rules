#!/usr/bin/env python3
"""Validate the formal index against fully validated passed Manifests."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

from build_testcase_index import STATUS_LABEL, build_row
from validate_manifest import validate_manifest_file


EXPECTED_HEADER = (
    "生成时间", "来源类型", "分析范围", "规则版本", "版本关系", "校验状态",
    "报告", "XMind Markdown", "Workbook", "Manifest", "备注",
)
FIELD_NAMES = EXPECTED_HEADER[:-1]
NOTE_FIELDS = {
    "artifact_id": "artifact_id", "cases": "case_count", "P0_risks": "p0_risk_count",
    "P0_cases": "p0_case_count", "pending": "pending_count",
}


def _cells(line: str) -> list[str]:
    """Parse a Markdown table row while preserving ordinary backslashes."""

    value = line.strip().strip("|")
    cells: list[str] = []
    current: list[str] = []
    index = 0

    while index < len(value):
        char = value[index]

        # Markdown 表格只对 \| 和 \\ 做转义处理。
        # Windows 路径中的普通反斜杠必须原样保留。
        if (
            char == "\\"
            and index + 1 < len(value)
            and value[index + 1] in {"|", "\\"}
        ):
            current.append(value[index + 1])
            index += 2
            continue

        if char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)

        index += 1

    cells.append("".join(current).strip())
    return cells


def _notes(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in value.split(";"):
        if "=" in part:
            key, item = part.split("=", 1)
            result[key.strip()] = item.strip()
    return result


def _repository_root(index: Path) -> Path:
    resolved = index.resolve()
    for candidate in (resolved.parent, *resolved.parents):
        if (candidate / "RULE_VERSION").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    return resolved.parent.parent if resolved.parent.name == "testcases" else resolved.parent


def _normalize_path(value: str) -> str:
    windows, posix = PureWindowsPath(value), PurePosixPath(value.replace("\\", "/"))
    if windows.is_absolute() or windows.drive or posix.is_absolute() or ".." in posix.parts:
        raise ValueError(f"禁止绝对路径或 ../：{value}")
    return posix.as_posix()


def _normalized_or_raw(value: str) -> str:
    try:
        return _normalize_path(value)
    except ValueError:
        return value


def _safe_file(root: Path, value: str, label: str) -> tuple[Path | None, str | None]:
    try:
        normalized = _normalize_path(value)
    except ValueError as exc:
        return None, f"{label} {exc}"
    resolved = (root / Path(*PurePosixPath(normalized).parts)).resolve()
    if resolved != root and root not in resolved.parents:
        return None, f"{label} resolve 后越出仓库：{value}"
    if not resolved.is_file():
        return None, f"{label} 文件不存在：{value}"
    return resolved, None


def _manifest_relative(root: Path, manifest: Path) -> str:
    return manifest.resolve().relative_to(root.resolve()).as_posix()


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
        row["line_no"] = str(line_no)
        rows.append(row)

    formal_rows = [row for row in rows if row["校验状态"] == STATUS_LABEL["passed"]]
    artifact_bindings: dict[str, set[str]] = {}
    manifest_bindings: dict[str, set[str]] = {}
    manifest_cache: dict[str, tuple[dict, list[str]]] = {}

    for row in formal_rows:
        line_no = row["line_no"]
        notes = _notes(row["备注"])
        artifact_id = notes.get("artifact_id", "")
        manifest_value = row["Manifest"]
        if not artifact_id:
            errors.append(f"已校验索引第 {line_no} 行缺少 artifact_id")
        if not manifest_value or manifest_value == "未生成":
            errors.append(f"已校验索引第 {line_no} 行缺少 Manifest")
            continue
        try:
            manifest_relative = _normalize_path(manifest_value)
        except ValueError as exc:
            errors.append(f"索引第 {line_no} 行 Manifest {exc}")
            continue
        artifact_bindings.setdefault(artifact_id, set()).add(manifest_relative)
        manifest_bindings.setdefault(manifest_relative, set()).add(artifact_id)
        manifest_path, path_error = _safe_file(root, manifest_relative, f"索引第 {line_no} 行 Manifest")
        if path_error or manifest_path is None:
            errors.append(path_error or f"索引第 {line_no} 行 Manifest 不存在")
            continue
        if manifest_relative not in manifest_cache:
            manifest_cache[manifest_relative] = validate_manifest_file(manifest_path)
        data, manifest_errors = manifest_cache[manifest_relative]
        if manifest_errors:
            errors.extend(f"索引第 {line_no} 行 Manifest 校验失败：{error}" for error in manifest_errors)
            continue
        if data.get("validation_status") != "passed":
            errors.append(f"索引第 {line_no} 行已校验，但 Manifest validation_status={data.get('validation_status')}")
            continue
        expected = dict(zip(EXPECTED_HEADER, _cells(build_row(data, Path(manifest_relative)))))
        for field in FIELD_NAMES:
            actual_value = row[field]
            expected_value = expected[field]
            if field in {"报告", "XMind Markdown", "Workbook", "Manifest"}:
                try:
                    actual_value = _normalize_path(actual_value)
                    expected_value = _normalize_path(expected_value)
                except ValueError:
                    pass
            if actual_value != expected_value:
                errors.append(
                    f"INDEX_MANIFEST_FIELD_MISMATCH: 第 {line_no} 行 {field}="
                    f"{row[field]!r}，Manifest={expected[field]!r}"
                )
        for note_key, manifest_key in NOTE_FIELDS.items():
            expected_value = str(data.get(manifest_key, ""))
            if notes.get(note_key) != expected_value:
                errors.append(
                    f"INDEX_MANIFEST_NOTE_MISMATCH: 第 {line_no} 行 {note_key}="
                    f"{notes.get(note_key)!r}，Manifest={expected_value!r}"
                )

    for artifact_id, manifests in artifact_bindings.items():
        if artifact_id and len(manifests) > 1:
            errors.append(f"同一 artifact_id 绑定多个 Manifest：{artifact_id} -> {sorted(manifests)}")
        if artifact_id and sum(
            _notes(row["备注"]).get("artifact_id") == artifact_id for row in formal_rows
        ) > 1:
            errors.append(f"已校验索引 artifact_id 重复：{artifact_id}")
    for manifest_relative, artifact_ids in manifest_bindings.items():
        if len(artifact_ids) > 1:
            errors.append(f"同一 Manifest 绑定多个 artifact_id：{manifest_relative} -> {sorted(artifact_ids)}")
        if sum(
            _normalized_or_raw(row["Manifest"]) == manifest_relative
            for row in formal_rows if row["Manifest"] not in {"", "未生成"}
        ) > 1:
            errors.append(f"已校验索引 Manifest 路径重复：{manifest_relative}")

    indexed_pairs = {
        (_notes(row["备注"]).get("artifact_id", ""), _normalized_or_raw(row["Manifest"]))
        for row in formal_rows if row["Manifest"] not in {"", "未生成"}
    }
    testcase_root = root / "testcases"
    for manifest in testcase_root.glob("**/manifest.json"):
        relative_path = manifest.relative_to(testcase_root)
        if relative_path.parts and relative_path.parts[0] == "drafts":
            continue
        relative = _manifest_relative(root, manifest)
        try:
            raw = json.loads(manifest.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Manifest 无法读取：{relative}：{exc}")
            continue
        if raw.get("validation_status") != "passed":
            continue
        if relative not in manifest_cache:
            manifest_cache[relative] = validate_manifest_file(manifest)
        data, manifest_errors = manifest_cache[relative]
        if manifest_errors:
            errors.extend(f"passed Manifest 校验失败 {relative}：{error}" for error in manifest_errors)
            continue
        pair = (str(data.get("artifact_id", "")), relative)
        if pair not in indexed_pairs:
            errors.append(
                f"PASSED_MANIFEST_NOT_UNIQUELY_INDEXED: {relative} 的 artifact_id={pair[0] or '<empty>'} 未唯一登记"
            )
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 passed Manifest 与正式索引的强一致性")
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
