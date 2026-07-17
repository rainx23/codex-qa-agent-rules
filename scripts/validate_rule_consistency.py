#!/usr/bin/env python3
"""Static rule consistency gate; it does not change business validators."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from qa_contracts import PENDING_SEVERITIES, PENDING_STATUSES, RISK_DISPOSITIONS, VALIDATION_STATUSES

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "rules/core/canonical-rules.json"
CANONICAL_PRIORITY = [
    "用户本轮明确确认", "第三部分产品实现方案", "明确验收标准", "正式变更记录",
    "正式接口/字段/数据口径", "第二部分补充", "第一部分背景", "截图", "当前代码",
]
FORBIDDEN_DESCRIPTIONS = {
    "除非用户提供其他成功协议": "API health protocol must be fixed",
    "HTTP 200 即成功": "HTTP status alone is not the fixed API health contract",
    "default null 可推断 nullable": "nullable requires an explicit null/not null token",
    "字段名合理即可使用": "SQL identifiers require evidence",
    "重跑可覆盖原失败": "reruns must preserve their predecessor",
    "旧 passed 保持 passed": "migration must revalidate legacy passed state",
    "Pending 可以正式生成 XMind": "pending cannot create a formal workbook",
}


def _texts(root: Path):
    for base in (root / "rules", root / "skills"):
        yield from base.rglob("*.md")
    yield root / "AGENTS.md"
    yield root / "README.md"


def validate_repository_rules(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    contract_path = root / "rules/core/canonical-rules.json"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except Exception as error:
        return [f"canonical rules cannot be read: {error}"]
    if contract.get("schema_version") != "2.0.0":
        errors.append("canonical Schema Version must be 2.0.0")
    if contract.get("zentao_evidence_priority") != CANONICAL_PRIORITY:
        errors.append("canonical Zentao priority differs from the required order")
    implementation_values = {
        "confirmation_severity": list(PENDING_SEVERITIES),
        "confirmation_status": list(PENDING_STATUSES),
        "risk_disposition": list(RISK_DISPOSITIONS),
        "manifest_validation_status": list(VALIDATION_STATUSES),
    }
    for name, expected in implementation_values.items():
        if contract.get(name) != expected:
            errors.append(f"canonical {name} differs from qa_contracts.py: {contract.get(name)} != {expected}")
    canonical_line = " > ".join(CANONICAL_PRIORITY)
    occurrences: list[str] = []
    for path in _texts(root):
        text = path.read_text(encoding="utf-8")
        if canonical_line in text:
            occurrences.append(path.relative_to(root).as_posix())
        for phrase, reason in FORBIDDEN_DESCRIPTIONS.items():
            if phrase in text:
                errors.append(f"{path.relative_to(root).as_posix()}: deprecated rule '{phrase}': {reason}")
        if re.search(r"(?<!Migration )(?<!迁移)Schema(?: Version)?\s*(?:=|为|使用)\s*1\.0\.0", text):
            errors.append(f"{path.relative_to(root).as_posix()}: 1.0.0 may only describe migration input")
    if occurrences != ["rules/profiles/zentao.md"]:
        errors.append(f"Zentao priority must have one authority; found {occurrences}")
    profile = (root / "rules/profiles/zentao.md").read_text(encoding="utf-8")
    required = [
        "Fact.category = conflicting", "blocking Confirmation", "代码是现状证据，不是需求真值",
        "confirmed Fact 至少需要一条真实 current Evidence",
    ]
    for phrase in required:
        if phrase not in profile:
            errors.append(f"Zentao profile missing conflict/evidence rule: {phrase}")
    workflow = (root / ".github/workflows/qa-rules-validation.yml").read_text(encoding="utf-8")
    if "|| true" in workflow:
        errors.append("CI must not use || true")
    return errors


def main() -> int:
    errors = validate_repository_rules(ROOT)
    for error in errors:
        print(f"FAIL {error}")
    print(f"SUMMARY passed={int(not errors)} warning=0 failed={int(bool(errors))}")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
