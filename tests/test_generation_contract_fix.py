from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from describe_model_contract import describe
from qa_contracts import (
    validate_model_links,
    validate_requirement_model,
    validate_testcase_model,
)
from update_task_model import update_model
from validate_models import validate_files


MODELS = ROOT / "tests" / "fixtures" / "generation_pipeline" / "models"


class GenerationContractFixTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((MODELS / name).read_text(encoding="utf-8"))

    def models(self) -> tuple[dict, dict, dict]:
        return (
            self.load("requirement-analysis.json"),
            self.load("risk-coverage-matrix.json"),
            self.load("testcase-model.json"),
        )

    def link_errors(self, requirement: dict, testcase: dict) -> list[str]:
        risk = self.load("risk-coverage-matrix.json")
        return validate_model_links(requirement, None, risk, testcase)

    def test_requirement_combination_rejects_condition_coverage(self):
        requirement, _, _ = self.models()
        requirement["condition_matrix"]["required_combinations"][0]["condition_coverage"] = []
        errors = validate_requirement_model(requirement, evidence_root=ROOT)
        self.assertTrue(any(
            "$.condition_matrix.required_combinations[0]" in item
            and "condition_coverage" in item
            for item in errors
        ))

    def test_testcase_cases_condition_coverage_is_schema_legal(self):
        _, _, testcase = self.models()
        self.assertEqual([], validate_testcase_model(testcase))
        self.assertTrue(all(case.get("condition_coverage") for case in testcase["cases"]))

    def test_required_combination_without_behavior_coverage_fails(self):
        requirement, _, testcase = self.models()
        testcase["cases"][0]["condition_coverage"] = [
            coverage for coverage in testcase["cases"][0]["condition_coverage"]
            if coverage["combination_id"] != "COMB-01"
        ]
        errors = self.link_errors(requirement, testcase)
        self.assertTrue(any("REQUIRED_COMBINATION_UNCOVERED: COMB-01" in item for item in errors))

    def test_unknown_combination_reference_fails(self):
        requirement, _, testcase = self.models()
        testcase["cases"][0]["condition_coverage"][0]["combination_id"] = "COMB-99"
        errors = self.link_errors(requirement, testcase)
        self.assertTrue(any("CONDITION_COVERAGE_UNKNOWN_COMBINATION: COMB-99" in item for item in errors))

    def test_unknown_testcase_reverse_reference_fails(self):
        requirement, _, testcase = self.models()
        requirement["condition_matrix"]["required_combinations"][0]["covered_by_tc_ids"] = ["TC999"]
        errors = self.link_errors(requirement, testcase)
        self.assertTrue(any("REQUIRED_COMBINATION_UNKNOWN_TESTCASE: COMB-01" in item for item in errors))

    def test_testcase_to_requirement_reverse_index_missing_fails(self):
        requirement, _, testcase = self.models()
        requirement["condition_matrix"]["required_combinations"][0]["covered_by_tc_ids"] = []
        errors = self.link_errors(requirement, testcase)
        self.assertTrue(any("CONDITION_COVERAGE_REVERSE_INDEX_MISSING" in item for item in errors))

    def test_requirement_to_testcase_forward_coverage_missing_fails(self):
        requirement, _, testcase = self.models()
        testcase["cases"][0]["condition_coverage"] = [
            coverage for coverage in testcase["cases"][0]["condition_coverage"]
            if coverage["combination_id"] != "COMB-01"
        ]
        errors = self.link_errors(requirement, testcase)
        self.assertTrue(any("REQUIRED_COMBINATION_FORWARD_COVERAGE_MISSING" in item for item in errors))

    def test_bidirectional_six_combination_mapping_passes(self):
        requirement, _, testcase = self.models()
        self.assertEqual([], self.link_errors(requirement, testcase))
        expected = {
            "TC001": {"COMB-01", "COMB-04"},
            "TC002": {"COMB-02", "COMB-05"},
            "TC003": {"COMB-03", "COMB-06"},
        }
        actual = {
            case["tc_id"]: {coverage["combination_id"] for coverage in case["condition_coverage"]}
            for case in testcase["cases"]
        }
        self.assertEqual(expected, actual)

    def test_duplicate_combination_within_one_testcase_fails(self):
        _, _, testcase = self.models()
        testcase["cases"][0]["condition_coverage"].append(
            copy.deepcopy(testcase["cases"][0]["condition_coverage"][0])
        )
        self.assertTrue(any(
            "condition_coverage.combination_id 重复" in item
            for item in validate_testcase_model(testcase)
        ))

    def test_duplicate_covered_by_testcase_id_fails(self):
        requirement, _, _ = self.models()
        requirement["condition_matrix"]["required_combinations"][0]["covered_by_tc_ids"] = [
            "TC001", "TC001"
        ]
        errors = validate_requirement_model(requirement, evidence_root=ROOT)
        self.assertTrue(any("不得包含重复项" in item for item in errors))

    def test_requirement_compact_contract_is_definition_only(self):
        contract = describe("requirement")
        text = json.dumps(contract, ensure_ascii=False)
        focused = contract["focused_schema_legal_example"]["required_combination"]
        self.assertNotIn("condition_coverage", focused)
        self.assertIn("禁止 condition_coverage", text)
        self.assertEqual(
            ["combination_id", "dimension_values", "covered_by_tc_ids"],
            contract["field_semantics"]["allowed_fields"],
        )

    def test_testcase_compact_contract_exposes_cases_condition_coverage(self):
        contract = describe("testcase")
        text = json.dumps(contract, ensure_ascii=False)
        self.assertIn("$.cases[].condition_coverage[]", text)
        example = contract["focused_schema_legal_example"]
        self.assertEqual("TC001", example["tc_id"])
        self.assertEqual(["COMB-01", "COMB-04"], [
            item["combination_id"] for item in example["condition_coverage"]
        ])

    def test_validate_models_error_contains_file_pointer_code_and_message(self):
        requirement, risk, testcase = self.models()
        requirement["condition_matrix"]["required_combinations"][0]["condition_coverage"] = {}
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            directory = Path(temporary)
            paths = []
            for name, model in (
                ("requirement-analysis.json", requirement),
                ("risk-coverage-matrix.json", risk),
                ("testcase-model.json", testcase),
            ):
                path = directory / name
                path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
                paths.append(path)
            errors = validate_files(paths[0], None, paths[1], paths[2])
        located = next(item for item in errors if "SCHEMA_UNKNOWN_PROPERTY" in item)
        self.assertIn("model=requirement", located)
        self.assertIn("file=requirement-analysis.json", located)
        self.assertIn(
            "json_pointer=/condition_matrix/required_combinations/0/condition_coverage",
            located,
        )
        self.assertIn("message=", located)

    def test_official_update_tool_rejects_unknown_field_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "testcase-model.json"
            shutil.copy2(MODELS / "testcase-model.json", path)
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "不允许的模型字段"):
                update_model(
                    ROOT, path, "testcase",
                    [{"op": "add", "path": "/cases/0/unknown_field", "value": True}],
                )
            self.assertEqual(before, path.read_bytes())
            self.assertEqual([], list(path.parent.glob("*.model.tmp")))

    def test_official_update_tool_rejects_requirement_coverage_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "requirement-analysis.json"
            shutil.copy2(MODELS / "requirement-analysis.json", path)
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "condition_coverage 只能写入"):
                update_model(
                    ROOT, path, "requirement",
                    [{
                        "op": "add",
                        "path": "/condition_matrix/required_combinations/0/condition_coverage",
                        "value": [],
                    }],
                )
            self.assertEqual(before, path.read_bytes())

    def test_desensitized_formal_fixture_passes_validate_models_first_call(self):
        calls = 0

        def validate_once() -> list[str]:
            nonlocal calls
            calls += 1
            return validate_files(
                MODELS / "requirement-analysis.json",
                None,
                MODELS / "risk-coverage-matrix.json",
                MODELS / "testcase-model.json",
            )

        self.assertEqual([], validate_once())
        self.assertEqual(1, calls)
        self.assertFalse((ROOT / "tmp_build_models.py").is_file())


if __name__ == "__main__":
    unittest.main()
