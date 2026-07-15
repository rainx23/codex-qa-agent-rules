#!/usr/bin/env python3
"""Validate generated schemas and repository model fixtures without jsonschema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from generate_schemas import render
from qa_contracts import MODEL_VALIDATORS, load_json, schema_documents, validate_model_links


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors: list[str] = []
    for name, expected in schema_documents(root).items():
        path = root / "rules/schemas" / name
        try:
            actual = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: {exc}")
            continue
        if actual != expected or path.read_text(encoding="utf-8-sig") != render(expected):
            errors.append(f"{path}: 与 Python 契约源不一致")
    fixture_dir = root / "tests/fixtures/models"
    fixture_names = {
        "requirement": "requirement-analysis.json",
        "diff": "diff-impact.json",
        "risk": "risk-coverage-matrix.json",
        "testcase": "testcase-model.json",
    }
    models: dict[str, dict] = {}
    for kind, name in fixture_names.items():
        path = fixture_dir / name
        if not path.is_file():
            errors.append(f"缺少模型 Fixture：{path}")
            continue
        try:
            models[kind] = load_json(path)
            errors.extend(f"{path}: {error}" for error in MODEL_VALIDATORS[kind](models[kind]))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: {exc}")
    if {"requirement", "diff", "risk", "testcase"}.issubset(models):
        errors.extend(
            f"模型交接：{error}"
            for error in validate_model_links(
                models["requirement"], models["diff"], models["risk"], models["testcase"]
            )
        )
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
    else:
        print("PASS schemas and model fixtures")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
