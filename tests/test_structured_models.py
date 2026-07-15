from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa_contracts import (
    load_json, validate_diff_model, validate_requirement_model, validate_risk_matrix,
    validate_model_links, validate_testcase_model,
)

MODELS = ROOT / "tests/fixtures/models"
GOLDEN = ROOT / "tests/golden"


class StructuredModelTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return load_json(MODELS / name)

    def test_valid_models(self):
        self.assertEqual([], validate_requirement_model(self.load("requirement-analysis.json")))
        self.assertEqual([], validate_diff_model(self.load("diff-impact.json")))
        self.assertEqual([], validate_risk_matrix(self.load("risk-coverage-matrix.json")))
        self.assertEqual([], validate_testcase_model(self.load("testcase-model.json")))

    def test_conflicting_fact_requires_confirmation_point(self):
        data = self.load("requirement-analysis.json")
        data["facts"][0]["category"] = "conflicting"
        self.assertTrue(any("未关联待确认点" in error for error in validate_requirement_model(data)))

    def test_schema_required_field_and_fact_enum_are_enforced_without_jsonschema(self):
        data = self.load("requirement-analysis.json")
        del data["facts"][0]["source_reference"]
        data["facts"][1]["category"] = "known"
        errors = validate_requirement_model(data)
        self.assertTrue(any("source_reference" in error and "缺少必填字段" in error for error in errors))
        self.assertTrue(any("category" in error and "枚举值非法" in error for error in errors))

    def test_inferred_fact_cannot_enter_acceptance_criteria(self):
        data = self.load("requirement-analysis.json")
        data["facts"][0]["category"] = "inferred"
        self.assertTrue(any("不得进入确定性验收" in error for error in validate_requirement_model(data)))

    def test_acceptance_criterion_requires_fact_id(self):
        data = self.load("requirement-analysis.json")
        data["acceptance_criteria"][0]["fact_ids"] = []
        self.assertTrue(any("未关联 fact_id" in error for error in validate_requirement_model(data)))

    def test_invalid_diff_coverage_status(self):
        data = self.load("diff-impact.json")
        data["coverage_results"][0]["coverage_status"] = "完成"
        self.assertTrue(any("覆盖状态非法" in error for error in validate_diff_model(data)))

    def test_p0_risk_requires_tc(self):
        data = self.load("risk-coverage-matrix.json")
        data["risk_items"][0]["testcase_ids"] = []
        self.assertTrue(any("P0 风险" in error for error in validate_risk_matrix(data)))

    def test_testcase_requires_risk_and_source(self):
        data = self.load("testcase-model.json")
        data["cases"][0]["risk_ids"] = []
        data["cases"][0]["requirement_ids"] = []
        data["cases"][0]["change_ids"] = []
        self.assertTrue(any("未关联风险" in error for error in validate_testcase_model(data)))
        self.assertTrue(any("未关联需求、Diff" in error for error in validate_testcase_model(data)))

    def test_testcase_model_rejects_vague_expected_result(self):
        data = self.load("testcase-model.json")
        data["cases"][0]["expected_results"] = ["页面正常展示"]
        self.assertTrue(any("模糊断言" in error for error in validate_testcase_model(data)))

    def test_multi_entry_testcase_model_requires_branch_only_steps(self):
        data = self.load("testcase-model-multi-entry.json")
        self.assertEqual([], validate_testcase_model(data))
        data["cases"][0]["steps"] = ["误放在顶层的统一步骤"]
        self.assertTrue(any("顶层 steps" in error for error in validate_testcase_model(data)))
        data = self.load("testcase-model-multi-entry.json")
        data["cases"][0]["entry_branches"][1]["entry_name"] = data["cases"][0]["entry_branches"][0]["entry_name"]
        self.assertTrue(any("entry_name 必须唯一" in error for error in validate_testcase_model(data)))
        data = self.load("testcase-model-multi-entry.json")
        data["cases"][0]["entry_branches"][0]["entry_name"] = "入口A"
        self.assertTrue(any("缺少业务语义" in error for error in validate_testcase_model(data)))

    def test_cross_model_links_are_bidirectional(self):
        requirement = self.load("requirement-analysis.json")
        diff = self.load("diff-impact.json")
        risk = self.load("risk-coverage-matrix.json")
        testcase = self.load("testcase-model.json")
        self.assertEqual([], validate_model_links(requirement, diff, risk, testcase))
        testcase["cases"][0]["risk_ids"] = ["RISK-UNKNOWN"]
        errors = validate_model_links(requirement, diff, risk, testcase)
        self.assertTrue(any("不存在风险" in error for error in errors))
        self.assertTrue(any("双向映射不一致" in error for error in errors))

    def test_golden_requirement_analysis_content(self):
        data = self.load("requirement-analysis.json")
        actual = {
            "analysis_id": data["analysis_id"],
            "confirmed_fact_ids": [fact["fact_id"] for fact in data["facts"] if fact["category"] == "confirmed"],
            "risk_ids": [risk["risk_id"] for risk in data["risks"]],
            "criterion_fact_links": {item["criterion_id"]: item["fact_ids"] for item in data["acceptance_criteria"]},
        }
        self.assertEqual(load_json(GOLDEN / "requirement_analysis_expected.json"), actual)

    def test_golden_diff_risk_and_testcase_content(self):
        diff = self.load("diff-impact.json")
        actual_diff = {
            "analysis_id": diff["analysis_id"],
            "change_ids": [item["change_id"] for item in diff["change_items"]],
            "coverage": {item["requirement_id"]: item["coverage_status"] for item in diff["coverage_results"]},
            "risk_ids": sorted({risk for item in diff["coverage_results"] for risk in item["risk_ids"]}),
        }
        self.assertEqual(load_json(GOLDEN / "diff_impact_expected.json"), actual_diff)

        risk = self.load("risk-coverage-matrix.json")
        actual_risk = {
            "matrix_id": risk["matrix_id"],
            "risk_to_tc": {item["risk_id"]: item["testcase_ids"] for item in risk["risk_items"]},
            "p0_risk_ids": [item["risk_id"] for item in risk["risk_items"] if item["test_priority"] == "P0"],
            "coverage_summary": risk["coverage_summary"],
        }
        self.assertEqual(load_json(GOLDEN / "risk_matrix_expected.json"), actual_risk)

        testcase = self.load("testcase-model.json")
        actual_testcase = {
            "root_title": testcase["root_title"],
            "tc_order": [case["tc_id"] for case in testcase["cases"]],
            "test_points": [case["test_point"] for case in testcase["cases"]],
            "expected_results": [result for case in testcase["cases"] for result in case["expected_results"]],
            "risk_links": {case["tc_id"]: case["risk_ids"] for case in testcase["cases"]},
        }
        self.assertEqual(load_json(GOLDEN / "testcase_model_expected.json"), actual_testcase)

    def test_manifest_golden_is_not_empty(self):
        example = load_json(ROOT / "testcases/manifest.example.json")
        actual = {
            "rule_version": example["rule_version"], "validation_status": example["validation_status"],
            "counts": {key: example[key] for key in ("case_count", "p0_risk_count", "p0_case_count", "pending_count")},
            "relation": example["relation"], "pending_reason": example["pending_reason"],
        }
        self.assertEqual(load_json(GOLDEN / "manifest_expected.json"), actual)


if __name__ == "__main__":
    unittest.main()
