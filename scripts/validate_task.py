#!/usr/bin/env python3
"""Fast validation for one current QA artifact bundle."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from build_testcase_index import build_row
from validate_manifest import validate_manifest_file
from validate_testcase_index import EXPECTED_HEADER, _cells, _normalize_path

T = TypeVar("T")
MAX_CONSOLE_ERRORS = 10
MAX_LOG_TAIL_LINES = 20


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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _compact_output(value: str) -> list[str]:
    lines = [line for line in value.splitlines() if line.strip()]
    return lines[-MAX_LOG_TAIL_LINES:]


def _run_stage(
    records: list[dict[str, Any]],
    name: str,
    action: Callable[[], T],
) -> T:
    started_at = _utc_now()
    started = time.perf_counter()
    try:
        result = action()
    except Exception as exc:
        records.append({
            "stage": name,
            "started_at": started_at,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "status": "failed",
            "error_count": 1,
            "error_summary": [str(exc)],
        })
        raise
    error_count = len(result) if isinstance(result, list) else 0
    records.append({
        "stage": name,
        "started_at": started_at,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "status": "failed" if error_count else "passed",
        "error_count": error_count,
        "error_summary": [str(item) for item in result[:MAX_CONSOLE_ERRORS]] if isinstance(result, list) else [],
    })
    return result


def _run_command(root: Path, command: list[str]) -> tuple[int, list[str]]:
    result = subprocess.run(
        command,
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    return result.returncode, _compact_output(output)


def run_task_validation(
    manifest: Path,
    index: Path,
    tests: list[str],
    audit_records: list[dict[str, Any]] | None = None,
) -> list[str]:
    root = _repository_root(manifest)
    records = audit_records if audit_records is not None else []
    data: dict[str, Any] = {}

    def validate_manifest_stage() -> list[str]:
        nonlocal data
        data, manifest_errors = validate_manifest_file(manifest)
        return manifest_errors

    errors = list(_run_stage(records, "validate_manifest_bundle", validate_manifest_stage))
    if data:
        errors.extend(
            _run_stage(
                records,
                "validate_current_index_entry",
                lambda: validate_current_index_entry(index, manifest, data),
            )
        )

    for target in tests:
        def run_test(target: str = target) -> list[str]:
            returncode, log_tail = _run_command(
                root,
                [sys.executable, "-m", "unittest", target, "-v"],
            )
            if returncode:
                suffix = f"；日志末尾：{' | '.join(log_tail)}" if log_tail else ""
                return [f"相关测试失败：{target}{suffix}"]
            return []

        errors.extend(_run_stage(records, f"unittest:{target}", run_test))

    def check_diff() -> list[str]:
        returncode, log_tail = _run_command(root, ["git", "diff", "--check"])
        if returncode:
            suffix = f"；日志末尾：{' | '.join(log_tail)}" if log_tail else ""
            return [f"git diff --check 失败{suffix}"]
        return []

    errors.extend(_run_stage(records, "git_diff_check", check_diff))
    return list(dict.fromkeys(errors))


def _safe_audit_path(path: Path, root: Path) -> Path:
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"audit 路径必须位于仓库内：{path}")
    return resolved


def write_audit(path: Path, root: Path, manifest: Path, records: list[dict[str, Any]], errors: list[str]) -> None:
    resolved = _safe_audit_path(path, root)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = json.loads(resolved.read_text(encoding="utf-8-sig")) if resolved.is_file() else {}
    except (OSError, json.JSONDecodeError):
        existing = {}
    runs = existing.get("runs", []) if isinstance(existing.get("runs"), list) else []
    runs.append({
        "run_id": f"validate-task-{len(runs) + 1:04d}",
        "generated_by": "scripts/validate_task.py",
        "recorded_at": _utc_now(),
        "manifest": manifest.resolve().relative_to(root.resolve()).as_posix(),
        "status": "failed" if errors else "passed",
        "stage_count": len(records),
        "failed_stage_count": sum(item.get("status") == "failed" for item in records),
        "stages": records,
    })
    payload = {
        "schema_version": "1.0.0",
        "generated_by": "scripts/validate_task.py",
        "run_count": len(runs),
        "runs": runs,
    }
    resolved.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="快速校验当前任务产物，不扫描历史产物或运行全量单元测试")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--test", action="append", default=[], help="本次改动直接相关的 unittest 模块或用例，可重复")
    parser.add_argument("--audit", type=Path, help="可选：由真实执行代码追加写入 pipeline audit JSON")
    args = parser.parse_args()
    root = _repository_root(args.manifest)
    index = args.index or root / "testcases/index.md"
    records: list[dict[str, Any]] = []
    try:
        errors = run_task_validation(args.manifest, index, args.test, records)
        if args.audit:
            write_audit(args.audit, root, args.manifest, records, errors)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        errors = [str(exc)]

    for error in errors[:MAX_CONSOLE_ERRORS]:
        print(f"FAIL {error}", file=sys.stderr)
    if len(errors) > MAX_CONSOLE_ERRORS:
        print(
            f"FAIL 其余 {len(errors) - MAX_CONSOLE_ERRORS} 条错误已省略；使用 --audit 查看阶段摘要",
            file=sys.stderr,
        )
    if not errors:
        print(f"PASS current task artifact bundle valid: {args.manifest}")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)} stages={len(records)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
