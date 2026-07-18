#!/usr/bin/env python3
"""Scan and validate every formal passed QA artifact bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from validate_manifest import validate_manifest_file
from validate_testcase_index import validate_index


def discover_passed_manifests(testcase_root: Path) -> tuple[list[Path], list[str]]:
    manifests: list[Path] = []
    errors: list[str] = []
    if not testcase_root.is_dir():
        return [], [f"正式产物目录不存在：{testcase_root}"]
    for path in sorted(testcase_root.glob("**/manifest.json")):
        relative_parts = path.relative_to(testcase_root).parts
        if relative_parts and relative_parts[0] == "drafts":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Manifest 无法读取：{path}: {exc}")
            continue
        if data.get("validation_status") == "passed":
            manifests.append(path)
    return manifests, errors


def validate_formal_artifacts(testcase_root: Path, index_path: Path) -> tuple[list[Path], list[str]]:
    manifests, errors = discover_passed_manifests(testcase_root)
    for path in manifests:
        _, manifest_errors = validate_manifest_file(path)
        errors.extend(f"{path}: {error}" for error in manifest_errors)
    errors.extend(f"{index_path}: {error}" for error in validate_index(index_path))
    return manifests, list(dict.fromkeys(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="扫描并校验全部 passed 正式测试产物")
    parser.add_argument("--testcase-root", type=Path, default=Path("testcases"))
    parser.add_argument("--index", type=Path, default=Path("testcases/index.md"))
    args = parser.parse_args(argv)
    manifests, errors = validate_formal_artifacts(args.testcase_root, args.index)
    for error in errors:
        print(f"FAIL {error}", file=sys.stderr)
    if not errors:
        for path in manifests:
            print(f"PASS {path}: formal artifact bundle valid")
        print(f"PASS {args.index}: formal artifact index valid")
    print(f"SUMMARY passed={0 if errors else len(manifests) + 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
