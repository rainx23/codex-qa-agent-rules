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
from validate_models import validate_files


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
                    "observable_result": relation + "/" + target + "：" + {
                        "包含于": "任一满足时股票可见；全部不满足时股票不可见",
                        "不包含": "任一命中被排除集合时股票不可见；全部不命中时股票可见",
                        "完全包含于": "全部满足时股票可见；部分满足或全部不满足时股票不可见",
                    }.get(relation, "满足条件的股票可见且不满足条件的股票不可见"),
                    "branch_id": "TC001-B01",
                    "step_index": len(coverage) + 1,
                    "expected_index": len(coverage) + 1,
                })
        requirement["condition_matrix_required"] = True
        requirement["condition_matrix"] = {
            "dimensions": [
                {"dimension_id": "relation", "dimension_name": "关系", "values": ["等于", "不等于", "包含于", "不包含", "完全包含于"]},
                {"dimension_id": "target_scope", "dimension_name": "目标范围", "values": ["自己", "所有下级", "直属上级", "直属下级"]},
            ],
            "combination_generation": {
                "mode": "grouped_cross_product",
                "groups": [{
                    "group_id": "five_by_four",
                    "fixed_values": {},
                    "variable_dimensions": [
                        {"dimension_id": "relation", "values": ["等于", "不等于", "包含于", "不包含", "完全包含于"]},
                        {"dimension_id": "target_scope", "values": ["自己", "所有下级", "直属上级", "直属下级"]},
                    ],
                    "expected_combination_count": 20,
                    "constraints": [],
                }],
            },
            "required_combinations": combinations,
            "excluded_combinations": [],
            "coverage_summary": {
                "required_combination_count": 20,
                "covered_combination_count": 20,
                "excluded_combination_count": 0,
            },
        }
        case = testcase["cases"][0]
        case["steps"] = []
        case["expected_results"] = []
        expected_results = [item["observable_result"] for item in coverage]
        case["entry_branches"] = [
            {
                "branch_id": "TC001-B01", "entry_name": "模拟交易清仓股弹窗",
                "steps": [f"执行条件组合 {index}" for index in range(1, 21)],
                "expected_results": expected_results,
            },
            {
                "branch_id": "TC001-B02", "entry_name": "正式交易清仓股弹窗",
                "steps": ["打开正式交易清仓股弹窗"],
                "expected_results": ["返回集合仅包含有权限股票行"],
            },
        ]
        case["condition_coverage"] = coverage
        testcase["branch_count"] = 2

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

    def test_requirement_source_missing_combination_fails_even_when_summary_and_testcase_match(self):
        requirement, risk, testcase = self.models()
        self.add_matrix(requirement, testcase)
        matrix = requirement["condition_matrix"]
        missing_index = next(
            index for index, item in enumerate(matrix["required_combinations"])
            if item["dimension_values"] == {"relation": "不等于", "target_scope": "直属上级"}
        )
        removed = matrix["required_combinations"].pop(missing_index)
        testcase["cases"][0]["condition_coverage"] = [
            item for item in testcase["cases"][0]["condition_coverage"]
            if item["combination_id"] != removed["combination_id"]
        ]
        matrix["coverage_summary"]["required_combination_count"] = 19
        matrix["coverage_summary"]["covered_combination_count"] = 19
        errors = self.errors(requirement, risk, testcase)
        self.assertTrue(any("REQUIRED_COMBINATION_UNCOVERED" in item for item in errors))

    def test_missing_business_entry_combination_fails(self):
        requirement, _, testcase = self.models()
        self.add_matrix(requirement, testcase)
        matrix = requirement["condition_matrix"]
        matrix["dimensions"].append({
            "dimension_id": "business_entry", "dimension_name": "入口", "values": ["模拟", "正式"],
        })
        group = matrix["combination_generation"]["groups"][0]
        group["variable_dimensions"].append({"dimension_id": "business_entry", "values": ["模拟", "正式"]})
        group["expected_combination_count"] = 40
        for item in matrix["required_combinations"]:
            item["dimension_values"]["business_entry"] = "模拟"
        errors = validate_requirement_model(requirement)
        self.assertTrue(any("REQUIRED_COMBINATION_UNCOVERED" in item for item in errors))

    def test_unexpected_combination_fails(self):
        requirement, _, testcase = self.models()
        self.add_matrix(requirement, testcase)
        extra = copy.deepcopy(requirement["condition_matrix"]["required_combinations"][0])
        extra["combination_id"] = "COMBO-999"
        extra["dimension_values"]["relation"] = "未声明关系"
        requirement["condition_matrix"]["required_combinations"].append(extra)
        errors = validate_requirement_model(requirement)
        self.assertTrue(any("UNEXPECTED_CONDITION_COMBINATION" in item for item in errors))

    def test_required_and_excluded_duplicate_fails(self):
        requirement, _, testcase = self.models()
        self.add_matrix(requirement, testcase)
        duplicate = copy.deepcopy(requirement["condition_matrix"]["required_combinations"][0])
        duplicate["combination_id"] = "EXCLUDED-001"
        duplicate.pop("covered_by_tc_ids")
        duplicate["exclusion_reason"] = "重复验证"
        requirement["condition_matrix"]["excluded_combinations"].append(duplicate)
        errors = validate_requirement_model(requirement)
        self.assertTrue(any("CONDITION_COMBINATION_DUPLICATED" in item for item in errors))

    def test_group_fixed_values_mismatch_fails(self):
        requirement, _, testcase = self.models()
        self.add_matrix(requirement, testcase)
        group = requirement["condition_matrix"]["combination_generation"]["groups"][0]
        group["fixed_values"] = {"relation": "等于"}
        group["variable_dimensions"] = [group["variable_dimensions"][1]]
        group["expected_combination_count"] = 4
        errors = validate_requirement_model(requirement)
        self.assertTrue(any("UNEXPECTED_CONDITION_COMBINATION" in item for item in errors))

    def test_expected_combination_count_mismatch_fails(self):
        requirement, _, testcase = self.models()
        self.add_matrix(requirement, testcase)
        requirement["condition_matrix"]["combination_generation"]["groups"][0]["expected_combination_count"] = 19
        errors = validate_requirement_model(requirement)
        self.assertTrue(any("CONDITION_GENERATION_COUNT_MISMATCH" in item for item in errors))

    def test_wrong_branch_reference_fails(self):
        requirement, risk, testcase = self.models()
        self.add_matrix(requirement, testcase)
        testcase["cases"][0]["condition_coverage"][0]["branch_id"] = "TC001-B99"
        self.assertTrue(any("CONDITION_COVERAGE_BRANCH_MISMATCH" in item for item in self.errors(requirement, risk, testcase)))

    def test_step_index_out_of_range_fails(self):
        requirement, risk, testcase = self.models()
        self.add_matrix(requirement, testcase)
        testcase["cases"][0]["condition_coverage"][0]["step_index"] = 99
        self.assertTrue(any("CONDITION_COVERAGE_STEP_REFERENCE_INVALID" in item for item in self.errors(requirement, risk, testcase)))

    def test_multiple_combinations_cannot_share_one_step(self):
        requirement, risk, testcase = self.models()
        self.add_matrix(requirement, testcase)
        testcase["cases"][0]["condition_coverage"][1]["step_index"] = 1
        testcase["cases"][0]["condition_coverage"][1]["expected_index"] = 1
        self.assertTrue(any("CONDITION_COVERAGE_NOT_INDEPENDENT" in item for item in self.errors(requirement, risk, testcase)))

    def test_include_and_not_include_cannot_use_same_oracle(self):
        requirement, risk, testcase = self.models()
        self.add_matrix(requirement, testcase)
        coverages = testcase["cases"][0]["condition_coverage"]
        by_values = {
            (item["dimension_values"]["relation"], item["dimension_values"]["target_scope"]): item
            for item in coverages
        }
        branch = testcase["cases"][0]["entry_branches"][0]
        for target in ("自己", "所有下级", "直属上级", "直属下级"):
            include = by_values[("包含于", target)]
            excluded = by_values[("不包含", target)]
            excluded["observable_result"] = include["observable_result"]
            branch["expected_results"][excluded["expected_index"] - 1] = include["observable_result"]
        errors = self.errors(requirement, risk, testcase)
        self.assertTrue(any("RELATION_ORACLE_NOT_DISTINCT" in item for item in errors))

    def test_complete_include_requires_partial_match_scenario(self):
        requirement, risk, testcase = self.models()
        self.add_matrix(requirement, testcase)
        branch = testcase["cases"][0]["entry_branches"][0]
        for coverage in testcase["cases"][0]["condition_coverage"]:
            if coverage["dimension_values"]["relation"] == "完全包含于":
                result = coverage["observable_result"].replace("部分满足", "中间状态").replace("只有部分", "中间状态")
                coverage["observable_result"] = result
                branch["expected_results"][coverage["expected_index"] - 1] = result
        errors = self.errors(requirement, risk, testcase)
        self.assertTrue(any("RELATION_SCENARIO_INCOMPLETE" in item and "部分满足" in item for item in errors))

    def test_include_requires_any_match_and_all_miss_scenarios(self):
        requirement, risk, testcase = self.models()
        self.add_matrix(requirement, testcase)
        branch = testcase["cases"][0]["entry_branches"][0]
        for coverage in testcase["cases"][0]["condition_coverage"]:
            if coverage["dimension_values"]["relation"] == "包含于":
                result = coverage["observable_result"].replace("任一满足", "命中").replace("任一角色", "某角色").replace("全部不满足", "未命中").replace("所有角色均不属于", "均未命中")
                coverage["observable_result"] = result
                branch["expected_results"][coverage["expected_index"] - 1] = result
        errors = self.errors(requirement, risk, testcase)
        self.assertTrue(any("RELATION_SCENARIO_INCOMPLETE" in item for item in errors))

    def test_current_112_combination_generation_is_complete(self):
        requirement = json.loads((ROOT / "testcases/clearance-permission-20260718-v2/requirement-analysis.json").read_text(encoding="utf-8"))
        self.assertEqual(112, len(requirement["condition_matrix"]["required_combinations"]))
        self.assertEqual([], validate_requirement_model(requirement))

    def test_current_v2_models_pass_complete_validation(self):
        artifact = ROOT / "testcases/clearance-permission-20260718-v2"
        self.assertEqual([], validate_files(
            artifact / "requirement-analysis.json",
            None,
            artifact / "risk-coverage-matrix.json",
            artifact / "testcase-model.json",
        ))

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

    def test_assertion_mappings_count_one_combination_and_require_all_expectations(self):
        requirement, risk, testcase = self.models()
        self.add_matrix(requirement, testcase)
        case = testcase["cases"][0]
        coverage = case["condition_coverage"][0]
        expected = ["断言一", "断言二", "断言三"]
        case["entry_branches"][0].update(steps=["步骤一", "步骤二", "步骤三"], expected_results=expected)
        coverage.pop("step_index")
        coverage.pop("expected_index")
        coverage.pop("observable_result")
        coverage["assertion_mappings"] = [
            {"step_index": index, "expected_index": index, "observable_result": result}
            for index, result in enumerate(expected, 1)
        ]
        requirement["condition_matrix"]["dimensions"] = [
            {"dimension_id": key, "dimension_name": key, "values": [value]}
            for key, value in coverage["dimension_values"].items()
        ]
        requirement["condition_matrix"]["combination_generation"]["groups"] = [{
            "group_id": "single", "fixed_values": {"target_scope": coverage["dimension_values"]["target_scope"]},
            "variable_dimensions": [{"dimension_id": "relation", "values": [coverage["dimension_values"]["relation"]]}],
            "expected_combination_count": 1, "constraints": [],
        }]
        requirement["condition_matrix"]["required_combinations"] = [requirement["condition_matrix"]["required_combinations"][0]]
        requirement["condition_matrix"]["coverage_summary"] = {
            "required_combination_count": 1, "covered_combination_count": 1, "excluded_combination_count": 0,
        }
        case["condition_coverage"] = [coverage]
        self.assertEqual([], self.errors(requirement, risk, testcase))
        coverage["assertion_mappings"].pop()
        self.assertTrue(any("ASSERTION_MAPPING_INCOMPLETE" in item for item in self.errors(requirement, risk, testcase)))

    def test_assertion_mapping_conflict_duplicate_and_out_of_range_fail(self):
        requirement, risk, testcase = self.models()
        self.add_matrix(requirement, testcase)
        coverage = testcase["cases"][0]["condition_coverage"][0]
        original = {key: coverage.pop(key) for key in ("step_index", "expected_index", "observable_result")}
        coverage["assertion_mappings"] = [dict(original)]
        coverage.update(original)
        self.assertTrue(any("MAPPING_CONFLICT" in item for item in self.errors(requirement, risk, testcase)))
        for key in original:
            coverage.pop(key)
        coverage["assertion_mappings"] = [dict(original), dict(original)]
        self.assertTrue(any("ASSERTION_MAPPING_DUPLICATED" in item for item in self.errors(requirement, risk, testcase)))
        coverage["assertion_mappings"] = [{"step_index": 99, "expected_index": 1, "observable_result": original["observable_result"]}]
        self.assertTrue(any("STEP_REFERENCE_INVALID" in item for item in self.errors(requirement, risk, testcase)))

    def test_polling_tc010_uses_two_combinations_and_six_assertions(self):
        artifact = ROOT / "testcases" / "polling-row-sync-20260720"
        requirement = json.loads((artifact / "requirement-analysis.json").read_text(encoding="utf-8"))
        testcase = json.loads((artifact / "testcase-model.json").read_text(encoding="utf-8"))
        tc010 = next(case for case in testcase["cases"] if case["tc_id"] == "TC010")
        coverage = [item for item in tc010["condition_coverage"] if item["combination_id"].startswith("CM-TC010-")]
        self.assertEqual(2, len(coverage))
        self.assertEqual([3, 3], [len(item["assertion_mappings"]) for item in coverage])
        self.assertEqual(56, len(requirement["condition_matrix"]["required_combinations"]))
        self.assertEqual(21, len(testcase["cases"]))
        self.assertEqual(42, testcase["branch_count"])


if __name__ == "__main__":
    unittest.main()
