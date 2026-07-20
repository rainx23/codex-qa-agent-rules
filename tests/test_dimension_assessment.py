from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa_contracts import (  # noqa: E402
    DIMENSIONS, validate_model_links, validate_requirement_model,
    validate_testcase_model, validate_test_dimension_warnings,
)
import validate_manifest  # noqa: E402


def load(name: str):
    return json.loads((ROOT / "tests/fixtures/models" / name).read_text(encoding="utf-8"))


class DimensionAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.req = load("requirement-analysis.json")
        self.risk = load("risk-coverage-matrix.json")
        self.tc = load("testcase-model.json")
        fact = self.req["facts"][0]["fact_id"]
        risk = self.risk["risk_items"][0]["risk_id"]
        tc_id = self.tc["cases"][0]["tc_id"]
        primary = self.tc["cases"][0]["dimension"]
        self.req["test_dimension_assessment"] = [
            {"dimension": dim, "status": "covered" if dim == primary else "not_applicable",
             "reason": "核心风险覆盖" if dim == primary else "业务对象不涉及该维度",
             "fact_ids": [fact], "risk_ids": [risk] if dim == primary else [],
             "confirmation_ids": [], "testcase_ids": [tc_id] if dim == primary else [],
             "evidence_references": []}
            for dim in DIMENSIONS
        ]

    def test_complete_assessment_passes(self):
        self.assertFalse(any("TEST_DIMENSION" in e for e in validate_requirement_model(self.req)))

    def test_incomplete_assessment_fails(self):
        self.req["test_dimension_assessment"].pop()
        self.assertTrue(any("TEST_DIMENSION_ASSESSMENT_INCOMPLETE" in e for e in validate_requirement_model(self.req)))

    def test_duplicate_assessment_fails(self):
        self.req["test_dimension_assessment"].append(copy.deepcopy(self.req["test_dimension_assessment"][0]))
        self.assertTrue(any("DUPLICATE_TEST_DIMENSION_ASSESSMENT" in e for e in validate_requirement_model(self.req)))

    def test_covered_without_testcase_fails(self):
        self.req["test_dimension_assessment"][0]["testcase_ids"] = []
        errors = validate_model_links(self.req, None, self.risk, self.tc, validation_status="passed")
        self.assertTrue(any("COVERED_DIMENSION_WITHOUT_TESTCASE" in e for e in errors))

    def test_covered_without_risk_fails(self):
        self.req["test_dimension_assessment"][0]["risk_ids"] = []
        errors = validate_model_links(self.req, None, self.risk, self.tc, validation_status="passed")
        self.assertTrue(any("COVERED_DIMENSION_WITHOUT_RISK" in e for e in errors))

    def test_secondary_duplicates_primary_fails(self):
        self.tc["cases"][0]["secondary_dimensions"] = [self.tc["cases"][0]["dimension"]]
        self.assertTrue(any("SECONDARY_DIMENSION_DUPLICATES_PRIMARY" in e for e in validate_testcase_model(self.tc)))

    def test_unknown_secondary_fails(self):
        self.tc["cases"][0]["secondary_dimensions"] = ["接口测试"]
        self.assertTrue(any("UNKNOWN_SECONDARY_DIMENSION" in e for e in validate_testcase_model(self.tc)))

    def test_secondary_can_satisfy_covered_dimension(self):
        secondary = next(dim for dim in DIMENSIONS if dim != self.tc["cases"][0]["dimension"])
        self.tc["cases"][0]["secondary_dimensions"] = [secondary]
        item = next(x for x in self.req["test_dimension_assessment"] if x["dimension"] == secondary)
        item.update(status="covered", risk_ids=[self.risk["risk_items"][0]["risk_id"]], testcase_ids=[self.tc["cases"][0]["tc_id"]])
        self.assertFalse(any("TESTCASE_PRIMARY_DIMENSION_MISMATCH" in e for e in validate_model_links(self.req, None, self.risk, self.tc)))

    def test_single_primary_dimension_emits_review_warning(self):
        second = next(dim for dim in DIMENSIONS if dim != self.tc["cases"][0]["dimension"])
        self.tc["cases"] = [copy.deepcopy(self.tc["cases"][0]) for _ in range(5)]
        for i, case in enumerate(self.tc["cases"], 1): case["tc_id"] = f"TC{i:03d}"
        next(x for x in self.req["test_dimension_assessment"] if x["dimension"] == second)["status"] = "covered"
        self.assertTrue(any("SINGLE_PRIMARY_DIMENSION_REVIEW_REQUIRED" in e for e in validate_test_dimension_warnings(self.req, self.tc)))


class CurrentRuleManifestDimensionGateTests(unittest.TestCase):
    def setUp(self):
        self.current = (ROOT / "RULE_VERSION").read_text(encoding="utf-8-sig").strip()
        self.manifest = {
            "validation_status": "passed", "testcase_model_path": "testcases/example/testcase-model.json",
            "rule_version": self.current, "report_mode": "requirement",
        }
        self.requirement = {"test_dimension_assessment": [{"dimension": dim} for dim in DIMENSIONS]}

    def errors(self, manifest=None, requirement=...):
        requirement = self.requirement if requirement is ... else requirement
        return validate_manifest.validate_current_rule_dimension_assessment(
            manifest or self.manifest, requirement, self.current
        )

    def test_current_passed_without_any_new_fields_fails(self):
        self.assertTrue(any("TEST_DIMENSION_ASSESSMENT_REQUIRED" in e for e in self.errors(requirement={})))

    def test_current_passed_missing_only_assessment_fails(self):
        requirement = {"condition_matrix_applicability": {"status": "not_required"}, "scope_dispositions": []}
        self.assertTrue(any("TEST_DIMENSION_ASSESSMENT_REQUIRED" in e for e in self.errors(requirement=requirement)))

    def test_complete_eight_dimensions_passes(self):
        self.assertEqual([], self.errors())

    def test_missing_or_duplicate_dimension_fails(self):
        missing = {"test_dimension_assessment": self.requirement["test_dimension_assessment"][:-1]}
        duplicate = {"test_dimension_assessment": self.requirement["test_dimension_assessment"] + [{"dimension": DIMENSIONS[0]}]}
        self.assertTrue(self.errors(requirement=missing))
        self.assertTrue(self.errors(requirement=duplicate))

    def test_old_rule_version_is_compatible(self):
        manifest = {**self.manifest, "rule_version": "2.10.0"}
        self.assertEqual([], self.errors(manifest=manifest, requirement={}))

    def test_pending_and_failed_are_not_forced(self):
        for status in ("pending", "failed"):
            with self.subTest(status=status):
                self.assertEqual([], self.errors(manifest={**self.manifest, "validation_status": status}, requirement={}))

    def test_diff_without_requirement_is_not_forced(self):
        manifest = {**self.manifest, "report_mode": "diff"}
        self.assertEqual([], self.errors(manifest=manifest, requirement=None))


if __name__ == "__main__":
    unittest.main()
