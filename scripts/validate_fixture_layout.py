#!/usr/bin/env python3
"""Ensure test-only inputs cannot masquerade as repository source artifacts."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_EXTENSIONS = {".java", ".sql", ".json", ".xmind", ".png"}
ILLEGAL_PATH = re.compile(r"(?:[A-Za-z]:\\|/Users/|/home/|\.\./)")


def validate_fixture_layout(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    forbidden = [root / "src", root / "scripts", root / "rules", root / "qa-knowledge/actual"]
    for base in forbidden:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in FIXTURE_EXTENSIONS and "fixture" in path.name.lower():
                errors.append(f"test fixture is outside tests/fixtures: {path.relative_to(root).as_posix()}")
    source_fixture = root / "tests/fixtures/sources/customer-query.java"
    if not source_fixture.is_file():
        errors.append("customer-query.java fixture is missing")
    elif "TEST FIXTURE ONLY" not in source_fixture.read_text(encoding="utf-8"):
        errors.append("customer-query.java lacks TEST FIXTURE ONLY marker")
    if (root / "src/customer-query.java").exists():
        errors.append("customer-query.java must not remain under src")
    for path in (root / "tests/fixtures").rglob("*"):
        if not path.is_file() or "anti_hallucination" in path.parts:
            continue
        if path.suffix.lower() not in {".json", ".md", ".sql", ".java"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if ILLEGAL_PATH.search(text):
            errors.append(f"fixture contains machine-specific or parent path: {path.relative_to(root).as_posix()}")
    workflow = (root / ".github/workflows/qa-rules-validation.yml").read_text(encoding="utf-8")
    if "--update-golden" in workflow:
        errors.append("CI must never update Golden files")
    return errors


def main() -> int:
    errors = validate_fixture_layout(ROOT)
    for error in errors:
        print(f"FAIL {error}")
    print(f"SUMMARY passed={int(not errors)} warning=0 failed={int(bool(errors))}")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
