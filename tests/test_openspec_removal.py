from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa_contracts import SOURCE_TYPES, schema_documents


def source_type_enums(value: Any) -> list[list[str]]:
    enums: list[list[str]] = []
    if isinstance(value, dict):
        properties = value.get("properties")
        source_type = properties.get("source_type") if isinstance(properties, dict) else None
        if isinstance(source_type, dict) and isinstance(source_type.get("enum"), list):
            enums.append(source_type["enum"])
        for child in value.values():
            enums.extend(source_type_enums(child))
    elif isinstance(value, list):
        for child in value:
            enums.extend(source_type_enums(child))
    return enums


def find_source_type(value: Any, expected: str) -> bool:
    if isinstance(value, dict):
        return value.get("source_type") == expected or any(
            find_source_type(child, expected) for child in value.values()
        )
    if isinstance(value, list):
        return any(find_source_type(child, expected) for child in value)
    return False


class OpenSpecRemovalTests(unittest.TestCase):
    def test_source_types_remove_openspec_and_keep_supported_sources(self):
        self.assertNotIn("openspec", SOURCE_TYPES)
        retained = {
            "requirement", "markdown", "pasted_text", "screenshot", "zentao_section_3",
            "user_confirmation", "diff", "acceptance_criteria", "formal_change_record",
            "api_document", "sql_definition", "complete_ddl", "knowledge_table",
            "historical_defect", "chat_snapshot",
        }
        self.assertTrue(retained.issubset(SOURCE_TYPES))

    def test_current_route_and_requirement_skill_do_not_advertise_openspec(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8-sig").casefold()
        skill = (ROOT / "skills/qa-requirement-analysis/SKILL.md").read_text(
            encoding="utf-8-sig"
        ).casefold()
        self.assertNotIn("openspec", agents)
        self.assertNotIn("openspec", skill)

    def test_generated_enums_and_historical_json_do_not_use_openspec(self):
        enums = [
            enum
            for schema in schema_documents(ROOT).values()
            for enum in source_type_enums(schema)
        ]
        self.assertTrue(enums)
        self.assertTrue(all("openspec" not in enum for enum in enums))
        for relative in ("testcases", "tests/fixtures", "tests/golden", "qa-knowledge"):
            for path in (ROOT / relative).rglob("*.json"):
                with self.subTest(path=path.relative_to(ROOT)):
                    data = json.loads(path.read_text(encoding="utf-8-sig"))
                    self.assertFalse(find_source_type(data, "openspec"))


if __name__ == "__main__":
    unittest.main()
