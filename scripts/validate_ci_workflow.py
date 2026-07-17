#!/usr/bin/env python3
"""Static validation for the repository's dependency-free GitHub Actions gate."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_COMMANDS = (
    "python -m compileall -q scripts tests",
    "python scripts/validate_skill_contracts.py skills",
    "python scripts/generate_schemas.py --check",
    "python scripts/validate_schemas.py",
    "python scripts/validate_rule_version.py",
    "python scripts/validate_repository_docs.py",
    "python scripts/validate_models.py --requirement tests/fixtures/models/requirement-analysis.json --diff tests/fixtures/models/diff-impact.json --risk tests/fixtures/models/risk-coverage-matrix.json --testcase tests/fixtures/models/testcase-model.json",
    "python scripts/validate_repository_mode.py",
    "python scripts/validate_knowledge.py qa-knowledge/examples",
    "python scripts/build_knowledge_index.py qa-knowledge/examples --check",
    "python scripts/validate_data_validation.py tests/fixtures/models/data-validation-valid.json",
    "python scripts/validate_sql_style.py tests/fixtures/sql/valid_validation_sql.sql --strict",
    "python scripts/validate_sql_artifact.py tests/fixtures/artifacts/validation-sql-manifest.json",
    "python -m unittest discover -s tests -p test_anti_hallucination_fixtures.py -v",
    "python -m unittest discover -s tests -v",
    "python scripts/validate_manifest.py testcases/manifest.example.json",
    "python scripts/repair_text_encoding.py testcases/index.md --check",
    "git diff --exit-code",
)


def validate_workflow(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return [str(exc)]
    errors: list[str] = []
    if "\t" in text:
        errors.append("YAML 禁止 Tab 缩进")
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent % 2:
            errors.append(f"第 {line_no} 行缩进不是 2 空格倍数")
    for trigger in ("push:", "pull_request:", "workflow_dispatch:"):
        if trigger not in text:
            errors.append(f"缺少触发器：{trigger}")
    if not re.search(r"python-version:\s*\[[^\]]*['\"]3\.10['\"]", text):
        errors.append("Python matrix 缺少 3.10")
    for command in REQUIRED_COMMANDS:
        if command not in text:
            errors.append(f"CI 缺少命令：{command}")
    if "RUNNER_TEMP" not in text:
        errors.append("XMind 临时产物未写入 RUNNER_TEMP")
    if re.search(r"(?:>|>>|tee)\s+testcases/(?!manifest\.example\.json)", text):
        errors.append("CI 不得写入历史 testcases 产物")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    path = root / ".github/workflows/qa-rules-validation.yml"
    errors = validate_workflow(path)
    if errors:
        for error in errors:
            print(f"FAIL {path}: {error}", file=sys.stderr)
    else:
        print(f"PASS {path}: workflow static contract valid")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
