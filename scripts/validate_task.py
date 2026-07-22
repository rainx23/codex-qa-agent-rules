#!/usr/bin/env python3
"""Fast validation for one current QA artifact bundle."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from build_testcase_index import build_row
from validate_manifest import validate_manifest_file
from validate_testcase_index import EXPECTED_HEADER, _cells, _normalize_path


def _repository_root(path: Path) -> Path:
    resolved = path.resolve()
    for candidate in (resolved.parent, *resolved.parents):
        if (candidate / "RULE_VERSION").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    return resolved.parent


def validate_current_index_entry(index: Path, manifest: Path, data: dict) -> list[str]:
    """Validate only the row for the supplied Manifest, never the historical index set."""

    if data.get("validation_status") != "passed":
        return []
    if not index.is_file():
        return [f"当前 Index 不存在：{index}"]
    root = _repository_root(manifest)
    manifest_relative = manifest.resolve().relative_to(root.resolve()).as_posix()
    rows = []
    for line in index.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = _cells(line)
        if len(cells) != len(EXPECTED_HEADER) or cells[0] in {EXPECTED_HEADER[0], "---"}:
            continue
        try:
            candidate = _normalize_path(cells[9])
        except ValueError:
            continue
        if candidate == manifest_relative:
            rows.append(cells)
    if len(rows) != 1:
        return [f"当前 Manifest 必须在 Index 唯一登记，实际 {len(rows)} 行：{manifest_relative}"]
    expected = _cells(build_row(data, Path(manifest_relative)))
    return [
        f"当前 Index 记录与 Manifest 不一致：{field}={actual!r}，expected={wanted!r}"
        for field, actual, wanted in zip(EXPECTED_HEADER, rows[0], expected)
        if actual != wanted
    ]


def run_task_validation(manifest: Path, index: Path, tests: list[str]) -> list[str]:
    root = _repository_root(manifest)
    data, errors = validate_manifest_file(manifest)
    errors.extend(validate_current_index_entry(index, manifest, data))
    for target in tests:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", target, "-v"], cwd=root, check=False,
        )
        if result.returncode:
            errors.append(f"相关测试失败：{target}")
    diff = subprocess.run(["git", "diff", "--check"], cwd=root, check=False)
    if diff.returncode:
        errors.append("git diff --check 失败")
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="快速校验当前任务产物，不扫描历史产物或运行全量单元测试")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--test", action="append", default=[], help="本次改动直接相关的 unittest 模块或用例，可重复")
    args = parser.parse_args()
    root = _repository_root(args.manifest)
    index = args.index or root / "testcases/index.md"
    errors = run_task_validation(args.manifest, index, args.test)
    for error in errors:
        print(f"FAIL {error}", file=sys.stderr)
    if not errors:
        print(f"PASS current task artifact bundle valid: {args.manifest}")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
