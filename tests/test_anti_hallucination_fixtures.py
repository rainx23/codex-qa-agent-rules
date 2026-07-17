from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from parse_chat_ddl import parse_ddl
from qa_contracts import load_json, validate_api_automation, validate_diff_model, validate_requirement_model, validate_testcase_model, validate_validation_sql
from validate_manifest import validate_manifest_data

FIXTURES = ROOT / "tests/fixtures/anti_hallucination"


def set_path(data: dict, path: str, value=None, remove: bool = False) -> None:
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    if remove:
        current.pop(parts[-1], None)
    else:
        current[parts[-1]] = value


class AntiHallucinationFixtureTests(unittest.TestCase):
    def test_all_categories_have_valid_invalid_reason_and_golden(self):
        expected = {"confirmed_inference", "blocking_gate", "ddl_partial", "vague_assertion", "missing_evidence", "fake_identifier", "suspected_defect", "api_health_scope"}
        self.assertEqual(expected, {path.stem for path in FIXTURES.glob("*.json")})
        for path in FIXTURES.glob("*.json"):
            spec = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("expected_failure", spec, path.name)
            self.assertIn("golden", spec, path.name)
            self.assert_fixture(spec, path.name)

    def assert_fixture(self, spec: dict, name: str) -> None:
        kind = spec["kind"]
        if kind == "ddl":
            self.assertEqual(spec["golden"]["valid_scope"], parse_ddl(spec["valid_input"])["tables"][0]["schema_scope"])
            self.assertEqual(spec["golden"]["invalid_scope"], parse_ddl(spec["invalid_input"])["tables"][0]["schema_scope"])
            return
        data = load_json(ROOT / spec["base"])
        validators = {"requirement": validate_requirement_model, "testcase": validate_testcase_model, "api": validate_api_automation}
        if kind in validators:
            self.assertEqual([], validators[kind](data), name)
            invalid = copy.deepcopy(data)
            mutation = spec["invalid"]
            set_path(invalid, mutation.get("path") or mutation["remove"], mutation.get("value"), "remove" in mutation)
            self.assertTrue(any(spec["expected_failure"] in error for error in validators[kind](invalid)), name)
            return
        if kind == "manifest":
            valid = copy.deepcopy(data); valid.update(spec["valid"])
            invalid = copy.deepcopy(data); invalid.update(spec["invalid"])
            self.assertFalse(any(spec["expected_failure"] in error for error in validate_manifest_data(valid, ROOT / spec["base"])), name)
            self.assertTrue(any(spec["expected_failure"] in error for error in validate_manifest_data(invalid, ROOT / spec["base"])), name)
            return
        if kind == "validation_sql":
            model = {"schema_version": data["schema_version"], "sql_items": data["sql_items"]}
            self.assertEqual([], validate_validation_sql(model), name)
            invalid = copy.deepcopy(model)
            invalid["sql_items"][0]["identifier_evidence"] = [item for item in invalid["sql_items"][0]["identifier_evidence"] if item["identifier"] != spec["invalid"]["remove_identifier"]]
            self.assertTrue(any(spec["expected_failure"] in error for error in validate_validation_sql(invalid)), name)
            return
        if kind == "suspected_defect":
            evidence = copy.deepcopy(data["change_items"][0]["evidence_references"])
            defect = {"defect_id":"DEF001","title":"过滤失败","requirement_fact_ids":["FACT-001"],"change_ids":[spec["valid_change_id"]],"evidence_state":"已确认","observed_behavior":"未过滤","expected_behavior":"精确过滤","impact":"返回错误记录","confidence":"high","handling":"修复","evidence_references":evidence}
            data["suspected_defects"] = [defect]
            self.assertEqual([], validate_diff_model(data), name)
            data["suspected_defects"][0]["change_ids"] = [spec["invalid_change_id"]]
            self.assertTrue(any(spec["expected_failure"] in error for error in validate_diff_model(data)), name)


if __name__ == "__main__":
    unittest.main()
