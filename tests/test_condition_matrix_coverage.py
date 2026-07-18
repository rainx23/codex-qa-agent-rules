from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa_contracts import (
    validate_model_links,
    validate_requirement_model,
    validate_testcase_model,
)


MODELS = ROOT / "tests" / "fixtures" / "models"


class ConditionMatrixCoverageTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((MODELS / name).read_text(encoding="utf-8"))

    def models(self) -> tuple[dict, dict, dict]:
        return (
            self.load("requirement-analysis.json"),
            self.load("risk-coverage-matrix.json"),
            self.load("testcase-model.json"),
        )

    def add_matrix(self, requirement: dict, testcase: dict, *, coverage_type: str = "behavior") -> None:
        combinations = []
        coverage = []
        for relation in ("等于", "不等于", "包含于", "不包含", "完全包含于"):
            for target in ("自己", "所有下级", "直属上级", "直属下级"):
                combination_id = f"COMBO-{len(combinations) + 1:03d}"
                values = {"relation": relation, "target_scope": target}
                combinations.append({
                    "combination_id": combination_id,
                    "dimension_values": values,
                    "covered_by_tc_ids": ["TC001"],
                })
                coverage.append({
                    "combination_id": combination_id,
                    "coverage_type": coverage_type,
                    "dimension_values": copy.deepcopy(values),
                    "expected_match_state": "命中与不命中",
                    "observable_result": "命中股票行可见且不命中股票行不可见",
                })
        requirement["condition_matrix_required"] = True
        requirement["condition_matrix"] = {
            "dimensions": [
                {"dimension_id": "relation", "dimension_name": "关系", "values": ["等于", "不等于", "包含于", "不包含", "完全包含于"]},
                {"dimension_id": "target_scope", "dimension_name": "目标范围", "values": ["自己", "所有下级", "直属上级", "直属下级"]},
            ],
            "required_combinations": combinations,
            "excluded_combinations": [],
            "coverage_summary": {
                "required_combination_count": 20,
                "covered_combination_count": 20,
                "excluded_combination_count": 0,
            },
        }
        testcase["cases"][0]["condition_coverage"] = coverage

    def errors(self, requirement: dict, risk: dict, testcase: dict) -> list[str]:
        return [
            *validate_requirement_model(requirement),
            *validate_testcase_model(testcase),
            *validate_model_links(requirement, None, risk, testcase),
        ]

    def test_explicit_dimensions_require_condition_matrix(self):
        requirement, _, _ = self.models()
        requirement["condition_matrix_required"] = True
        self.assertTrue(any("CONDITION_MATRIX_REQUIRED" in item for item in validate_requirement_model(requirement)))

    def test_all_required_combinations_with_behavior_coverage_pass(self):
        requirement, risk, testcase = self.models()
        self.add_matrix(requirement, testcase)
        self.assertEqual([], self.errors(requirement, risk, testcase))

    def test_missing_one_of_five_by_four_combinations_fails(self):
        requirement, risk, testcase = self.models()
        self.add_matrix(requirement, testcase)
        testcase["cases"][0]["condition_coverage"].pop()
        errors = self.errors(requirement, risk, testcase)
        self.assertTrue(any("REQUIRED_COMBINATION_UNCOVERED" in item for item in errors))

    def test_configuration_existence_does_not_count_as_behavior(self):
        requirement, risk, testcase = self.models()
        self.add_matrix(requirement, testcase, coverage_type="configuration")
        errors = self.errors(requirement, risk, testcase)
        self.assertTrue(any("CONFIG_EXISTENCE_IS_NOT_BEHAVIOR_COVERAGE" in item for item in errors))

    def test_excluded_combination_with_reason_passes(self):
        requirement, risk, testcase = self.models()
        self.add_matrix(requirement, testcase)
        removed = requirement["condition_matrix"]["required_combinations"].pop()
        testcase["cases"][0]["condition_coverage"].pop()
        requirement["condition_matrix"]["excluded_combinations"] = [{
            "combination_id": removed["combination_id"],
            "dimension_values": removed["dimension_values"],
            "exclusion_reason": "需求明确排除该组合",
        }]
        requirement["condition_matrix"]["coverage_summary"] = {
            "required_combination_count": 19,
            "covered_combination_count": 19,
            "excluded_combination_count": 1,
        }
        self.assertEqual([], self.errors(requirement, risk, testcase))

    def test_excluded_combination_without_reason_fails(self):
        requirement, _, testcase = self.models()
        self.add_matrix(requirement, testcase)
        removed = requirement["condition_matrix"]["required_combinations"].pop()
        requirement["condition_matrix"]["excluded_combinations"] = [{
            "combination_id": removed["combination_id"],
            "dimension_values": removed["dimension_values"],
            "exclusion_reason": "",
        }]
        requirement["condition_matrix"]["coverage_summary"] = {
            "required_combination_count": 19,
            "covered_combination_count": 19,
            "excluded_combination_count": 1,
        }
        errors = validate_requirement_model(requirement)
        self.assertTrue(any("COMBINATION_EXCLUSION_WITHOUT_REASON" in item for item in errors))

    def test_historical_requirement_without_matrix_remains_compatible(self):
        requirement, _, _ = self.models()
        self.assertEqual([], validate_requirement_model(requirement))


if __name__ == "__main__":
    unittest.main()
