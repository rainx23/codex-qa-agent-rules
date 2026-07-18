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

from qa_contracts import (  # noqa: E402
    VALUE_ASSESSMENT_ALGORITHM_VERSION,
    VALUE_ASSESSMENT_REASON_CODES,
    calculate_testcase_value_assessments,
    format_testcase_value_assessment,
    load_json,
    schema_documents,
    stable_normalized_file_hash,
    testcase_value_assessment_schema,
    validate_risk_matrix,
    validate_testcase_model,
    validate_testcase_value_assessment,
)
from validate_execution_instances import _sha as execution_file_hash  # noqa: E402

VALUE_FIXTURES = ROOT / "tests" / "fixtures" / "value-assessment"


class TestcaseValueAssessmentTests(unittest.TestCase):
    def case(self, tc_id: str = "TC001", risk_ids: list[str] | None = None, **updates):
        value = {
            "tc_id": tc_id,
            "test_point": "按客户编号查询",
            "steps": ["输入客户编号并查询"],
            "expected_results": ["返回集合仅包含目标客户记录"],
            "entry_branches": [],
            "risk_ids": risk_ids or ["RISK-001"],
            "historical_defect_ids": [],
            "evidence_state": "已确认",
            "regression_scope": "核心回归",
            "deduplication_key": "客户查询|目标客户|精确过滤",
        }
        value.update(updates)
        return value

    def risk(self, risk_id: str = "RISK-001", testcase_ids: list[str] | None = None, **updates):
        value = {
            "risk_id": risk_id,
            "business_impact": "critical",
            "test_priority": "P0",
            "testcase_ids": testcase_ids or ["TC001"],
            "merge_key": "客户查询|精确过滤",
            "fact_ids": ["FACT-001"],
            "evidence_state": "已确认",
            "evidence_references": [{"evidence_status": "current"}],
        }
        value.update(updates)
        return value

    def requirement(self):
        return {
            "facts": [{
                "fact_id": "FACT-001",
                "category": "confirmed",
                "evidence_references": [{"evidence_status": "current"}],
            }]
        }

    def calculate(self, cases=None, risks=None, requirement=True, maintenance_inputs=None):
        testcase_model = {"cases": cases or [self.case()]}
        risk_model = {"risk_items": risks or [self.risk()]}
        requirement_model = self.requirement() if requirement is True else None if requirement is False else requirement
        return calculate_testcase_value_assessments(
            testcase_model,
            risk_model,
            requirement_model,
            maintenance_inputs,
        )

    def assessment(self, **kwargs):
        return self.calculate(**kwargs)["assessments"][0]

    def load_assessment_fixture(self, name: str):
        return load_json(VALUE_FIXTURES / name)

    def write_bundle(self, root: Path, *, requirement: bool = True, two_cases: bool = False):
        models = VALUE_FIXTURES / "computed"
        testcase_model = load_json(models / "testcase-model.json")
        risk_model = load_json(models / "risk-coverage-matrix.json")
        requirement_model = load_json(models / "requirement-analysis.json") if requirement else None
        source_target = root / "tests/fixtures/sources"
        source_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / "tests/fixtures/sources", source_target)

        testcase_path = root / "testcase.json"
        risk_path = root / "risk.json"
        requirement_path = root / "requirement.json"
        testcase_path.write_bytes((json.dumps(testcase_model, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        risk_path.write_bytes((json.dumps(risk_model, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        if requirement_model is not None:
            requirement_path.write_bytes((json.dumps(requirement_model, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

        calculated = calculate_testcase_value_assessments(testcase_model, risk_model, requirement_model)
        model = {
            "schema_version": "2.0.0",
            "assessment_model_id": "TVA-900",
            "algorithm_version": VALUE_ASSESSMENT_ALGORITHM_VERSION,
            "testcase_model_reference": {
                "model_id": testcase_model["model_id"],
                "path": testcase_path.name,
                "content_hash": stable_normalized_file_hash(testcase_path),
            },
            "risk_matrix_reference": {
                "matrix_id": risk_model["matrix_id"],
                "path": risk_path.name,
                "content_hash": stable_normalized_file_hash(risk_path),
            },
            "requirement_model_reference": None,
            "assessments": calculated["assessments"],
        }
        if requirement_model is not None:
            model["requirement_model_reference"] = {
                "analysis_id": requirement_model["analysis_id"],
                "path": requirement_path.name,
                "content_hash": stable_normalized_file_hash(requirement_path),
            }
        return model

    def test_p0_core_case_has_high_coverage_and_guardrail(self):
        result = self.assessment()
        self.assertEqual(VALUE_ASSESSMENT_ALGORITHM_VERSION, "1.0.0")
        self.assertEqual(5, result["dimensions"]["risk_coverage_value"])
        self.assertIn("p0_mapped", result["guardrails"])
        self.assertEqual("retain_guarded", result["recommendation"])
        self.assertEqual("high_value_core", result["value_band"])

    def test_historical_defect_case_is_guarded(self):
        case = self.case(historical_defect_ids=["BUG-001"], regression_scope="冒烟回归")
        risk = self.risk(test_priority="P2", business_impact="low")
        result = self.assessment(cases=[case], risks=[risk])
        self.assertEqual(5, result["dimensions"]["regression_value"])
        self.assertIn("historical_defect_regression", result["guardrails"])
        self.assertIn(result["recommendation"], {"retain_guarded", "retain_guarded_and_improve"})

    def test_reachability_only_low_risk_case_has_low_diagnostic_value(self):
        case = self.case(expected_results=["页面打开且按钮可点击"], regression_scope="冒烟回归")
        risk = self.risk(test_priority="P2", business_impact="low")
        result = self.assessment(cases=[case], risks=[risk], requirement=False)
        self.assertEqual(1, result["dimensions"]["diagnostic_value"])
        self.assertIn("LOW_VALUE_REACHABILITY_ASSERTION", result["reason_codes"])

    def test_missing_requirement_model_caps_evidence_confidence(self):
        result = self.assessment(requirement=False)
        self.assertEqual(4, result["dimensions"]["evidence_confidence"])
        self.assertNotEqual(5, result["dimensions"]["evidence_confidence"])

    def test_missing_valid_risk_is_insufficient(self):
        result = self.assessment(cases=[self.case(risk_ids=["RISK-UNKNOWN"])], risks=[])
        self.assertEqual("insufficient_inputs", result["score_status"])
        self.assertIsNone(result["total_score"])
        self.assertIsNone(result["value_band"])
        self.assertEqual("insufficient_inputs", result["recommendation"])

    def test_insufficient_inputs_formatter_emits_no_value_based_advice(self):
        assessment = self.assessment(cases=[self.case(risk_ids=["RISK-UNKNOWN"])], risks=[])
        lines = format_testcase_value_assessment({"assessments": [assessment]})
        output = "\n".join(lines)
        self.assertIn("status=insufficient_inputs", output)
        self.assertIn("INSUFFICIENT_INPUTS", output)
        for forbidden in (
            "REVIEW_LOW_VALUE_SMOKE", "REVIEW_SIMPLIFICATION", "REVIEW_DUPLICATE",
            "SPLIT_FOR_DIAGNOSIS", "P0_LOW_SCORE_GUARDED",
        ):
            self.assertNotIn(forbidden, output)

    def test_valid_fixture_is_computed_not_insufficient(self):
        model = self.load_assessment_fixture("testcase-value-assessment-valid.json")
        self.assertTrue(all(item["score_status"] == "computed" for item in model["assessments"]))
        self.assertTrue(all(item["total_score"] is not None and item["value_band"] for item in model["assessments"]))

    def test_invalid_referenced_model_links_block_persisted_assessment(self):
        for target, mutate, token in (
            ("risk", lambda data: data["risk_items"][0].update(testcase_ids=["TC999"]), "不存在 TC"),
            ("testcase", lambda data: data["cases"][0].update(risk_ids=["RISK-UNKNOWN"]), "不存在风险"),
            ("requirement", lambda data: data["facts"][0].update(category="inferred"), "Requirement Model 非法"),
        ):
            with self.subTest(target=target), tempfile.TemporaryDirectory(dir=ROOT / "tests/fixtures/value-assessment") as directory:
                bundle = Path(directory)
                computed = VALUE_FIXTURES / "computed"
                paths = {
                    "testcase": bundle / "testcase-model.json",
                    "risk": bundle / "risk-coverage-matrix.json",
                    "requirement": bundle / "requirement-analysis.json",
                }
                for key, path in paths.items():
                    shutil.copy2(computed / path.name, path)
                data = load_json(paths[target])
                mutate(data)
                paths[target].write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                model = self.load_assessment_fixture("testcase-value-assessment-valid.json")
                for key, reference_key in (
                    ("testcase", "testcase_model_reference"),
                    ("risk", "risk_matrix_reference"),
                    ("requirement", "requirement_model_reference"),
                ):
                    model[reference_key]["path"] = paths[key].relative_to(ROOT).as_posix()
                    model[reference_key]["content_hash"] = stable_normalized_file_hash(paths[key])
                errors = validate_testcase_value_assessment(model, root=ROOT)
                self.assertTrue(any(token in error for error in errors), errors)

    def test_multi_entry_increases_maintenance_without_increasing_case_count(self):
        single = self.case("TC001")
        multi = self.case(
            "TC002",
            steps=[],
            expected_results=[],
            deduplication_key="多入口客户查询",
            entry_branches=[
                {"branch_id": "TC002-B02", "entry_name": "入口二", "steps": ["查询"], "expected_results": ["返回目标记录"]},
                {"branch_id": "TC002-B01", "entry_name": "入口一", "steps": ["查询"], "expected_results": ["返回目标记录"]},
            ],
        )
        risk = self.risk(testcase_ids=["TC001", "TC002"])
        assessments = self.calculate(cases=[single, multi], risks=[risk])["assessments"]
        by_id = {item["tc_id"]: item for item in assessments}
        self.assertEqual(2, len(assessments))
        self.assertGreater(
            by_id["TC002"]["dimensions"]["maintenance_cost"],
            by_id["TC001"]["dimensions"]["maintenance_cost"],
        )

    def test_high_maintenance_does_not_cancel_p0_guardrail(self):
        maintenance = {"TC001": {"external_system_dependency_count": 8}}
        result = self.assessment(maintenance_inputs=maintenance)
        self.assertEqual(5, result["dimensions"]["maintenance_cost"])
        self.assertIn("p0_mapped", result["guardrails"])
        self.assertNotIn(result["recommendation"], {"delete", "drop", "downgrade"})

    def test_duplicate_only_produces_review_recommendation(self):
        first = self.case("TC001")
        second = self.case("TC002")
        risk = self.risk(test_priority="P1", business_impact="medium", testcase_ids=["TC001", "TC002"])
        assessments = self.calculate(cases=[first, second], risks=[risk])["assessments"]
        for result in assessments:
            self.assertEqual(5, result["dimensions"]["redundancy_penalty"])
            self.assertEqual("review_duplicate", result["recommendation"])
            self.assertNotIn(result["recommendation"], {"delete", "drop", "downgrade"})

    def test_identical_inputs_produce_identical_results(self):
        first = self.calculate()
        second = self.calculate()
        self.assertEqual(first, second)
        self.assertEqual(
            json.dumps(first, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            json.dumps(second, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )

    def test_case_order_does_not_change_per_tc_results(self):
        cases = [self.case("TC001"), self.case("TC002", deduplication_key="不同用例", test_point="按名称查询")]
        risk = self.risk(testcase_ids=["TC001", "TC002"])
        forward = self.calculate(cases=cases, risks=[risk])
        reverse = self.calculate(cases=list(reversed(cases)), risks=[risk])
        self.assertEqual(forward, reverse)

    def test_risk_order_does_not_change_results(self):
        case = self.case(risk_ids=["RISK-001", "RISK-002"])
        first = self.risk("RISK-001", merge_key="risk-a")
        second = self.risk(
            "RISK-002",
            merge_key="risk-b",
            fact_ids=["FACT-001"],
            test_priority="P1",
            business_impact="high",
        )
        forward = self.calculate(cases=[case], risks=[first, second])
        reverse = self.calculate(cases=[case], risks=[second, first])
        self.assertEqual(forward, reverse)

    def test_line_endings_do_not_create_hash_or_score_dependency(self):
        lf = self.case(steps=["输入条件\n执行查询"])
        crlf = self.case(steps=["输入条件\r\n执行查询"])
        lf_result = self.calculate(cases=[lf])
        crlf_result = self.calculate(cases=[crlf])
        self.assertEqual(lf_result, crlf_result)
        self.assertNotIn("hash", json.dumps(lf_result).lower())

    def test_invalid_maintenance_values_are_rejected(self):
        for value in (True, -1, "1"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "非负整数"):
                    self.calculate(maintenance_inputs={"TC001": {"manual_oracle_count": value}})

    def test_all_dimensions_are_integers_between_zero_and_five(self):
        dimensions = self.assessment()["dimensions"]
        self.assertEqual(7, len(dimensions))
        for value in dimensions.values():
            self.assertIs(type(value), int)
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 5)

    def test_computed_total_score_is_integer_in_range(self):
        result = self.assessment()
        self.assertEqual("computed", result["score_status"])
        self.assertIs(type(result["total_score"]), int)
        self.assertGreaterEqual(result["total_score"], 0)
        self.assertLessEqual(result["total_score"], 100)

    def test_result_contains_no_floats(self):
        result = self.calculate()

        def values(value):
            if isinstance(value, dict):
                for item in value.values():
                    yield from values(item)
            elif isinstance(value, list):
                for item in value:
                    yield from values(item)
            else:
                yield value

        self.assertFalse(any(isinstance(value, float) for value in values(result)))

    def test_reason_code_order_is_stable_and_closed(self):
        maintenance = {"TC001": {"external_system_dependency_count": 8}}
        first = self.assessment(maintenance_inputs=maintenance)["reason_codes"]
        second = self.assessment(maintenance_inputs=maintenance)["reason_codes"]
        self.assertEqual(first, second)
        positions = [VALUE_ASSESSMENT_REASON_CODES.index(code) for code in first]
        self.assertEqual(sorted(positions), positions)
        self.assertEqual(len(first), len(set(first)))

    def test_assessments_are_sorted_by_tc_id(self):
        cases = [
            self.case("TC003", deduplication_key="case-3"),
            self.case("TC001", deduplication_key="case-1"),
            self.case("TC002", deduplication_key="case-2"),
        ]
        risk = self.risk(testcase_ids=["TC001", "TC002", "TC003"])
        result = self.calculate(cases=cases, risks=[risk])
        self.assertEqual(["TC001", "TC002", "TC003"], [item["tc_id"] for item in result["assessments"]])

    def test_generated_schema_is_registered_and_current(self):
        generated = schema_documents(ROOT)["testcase-value-assessment.schema.json"]
        self.assertEqual(generated, testcase_value_assessment_schema(generated["x-rule-version"]))
        self.assertEqual(generated, load_json(ROOT / "rules" / "schemas" / "testcase-value-assessment.schema.json"))

    def test_valid_persisted_fixture_passes(self):
        model = self.load_assessment_fixture("testcase-value-assessment-valid.json")
        self.assertEqual([], validate_testcase_value_assessment(model, root=ROOT))

    def test_invalid_reference_hash_is_rejected(self):
        model = self.load_assessment_fixture("testcase-value-assessment-hash-invalid.json")
        errors = validate_testcase_value_assessment(model, root=ROOT)
        self.assertTrue(any("content_hash" in error for error in errors), errors)

    def test_mismatched_testcase_model_id_is_rejected(self):
        model = self.load_assessment_fixture("testcase-value-assessment-valid.json")
        model["testcase_model_reference"]["model_id"] = "TC-MODEL-WRONG"
        errors = validate_testcase_value_assessment(model, root=ROOT)
        self.assertTrue(any("model_id" in error for error in errors), errors)

    def test_mismatched_risk_matrix_id_is_rejected(self):
        model = self.load_assessment_fixture("testcase-value-assessment-valid.json")
        model["risk_matrix_reference"]["matrix_id"] = "MATRIX-WRONG"
        errors = validate_testcase_value_assessment(model, root=ROOT)
        self.assertTrue(any("matrix_id" in error for error in errors), errors)

    def test_unknown_tc_fixture_is_rejected(self):
        model = self.load_assessment_fixture("testcase-value-assessment-unknown-tc.json")
        errors = validate_testcase_value_assessment(model, root=ROOT)
        self.assertTrue(any("TC999" in error for error in errors), errors)

    def test_missing_assessment_tc_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = self.write_bundle(root, two_cases=True)
            model["assessments"] = model["assessments"][:1]
            errors = validate_testcase_value_assessment(model, root=root)
        self.assertTrue(any("TC002" in error for error in errors), errors)

    def test_duplicate_assessment_tc_is_rejected(self):
        model = self.load_assessment_fixture("testcase-value-assessment-valid.json")
        model["assessments"].append(copy.deepcopy(model["assessments"][0]))
        errors = validate_testcase_value_assessment(model, root=ROOT)
        self.assertTrue(any("tc_id" in error for error in errors), errors)

    def test_tampered_total_score_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = self.write_bundle(root)
            model["assessments"][0]["total_score"] += 1
            errors = validate_testcase_value_assessment(model, root=root)
        self.assertTrue(any("total_score" in error for error in errors), errors)

    def test_tampered_dimension_fixture_is_rejected(self):
        model = self.load_assessment_fixture("testcase-value-assessment-score-tampered.json")
        errors = validate_testcase_value_assessment(model, root=ROOT)
        self.assertTrue(any("dimensions" in error for error in errors), errors)

    def test_tampered_value_band_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = self.write_bundle(root)
            model["assessments"][0]["value_band"] = "low_value_review"
            errors = validate_testcase_value_assessment(model, root=root)
        self.assertTrue(any("value_band" in error for error in errors), errors)

    def test_tampered_guardrails_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = self.write_bundle(root)
            model["assessments"][0]["guardrails"] = []
            errors = validate_testcase_value_assessment(model, root=root)
        self.assertTrue(any("guardrails" in error for error in errors), errors)

    def test_tampered_reason_codes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = self.write_bundle(root)
            model["assessments"][0]["reason_codes"] = []
            errors = validate_testcase_value_assessment(model, root=root)
        self.assertTrue(any("reason_codes" in error for error in errors), errors)

    def test_tampered_recommendation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = self.write_bundle(root)
            model["assessments"][0]["recommendation"] = "standard_maintain"
            errors = validate_testcase_value_assessment(model, root=root)
        self.assertTrue(any("recommendation" in error for error in errors), errors)

    def test_assessment_order_does_not_affect_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = self.write_bundle(root, two_cases=True)
            model["assessments"].reverse()
            self.assertEqual([], validate_testcase_value_assessment(model, root=root))

    def test_missing_reference_path_is_rejected(self):
        model = self.load_assessment_fixture("testcase-value-assessment-valid.json")
        model["testcase_model_reference"]["path"] = "tests/fixtures/models/not-found.json"
        errors = validate_testcase_value_assessment(model, root=ROOT)
        self.assertTrue(errors)

    def test_parent_traversal_reference_path_is_rejected(self):
        model = self.load_assessment_fixture("testcase-value-assessment-valid.json")
        model["testcase_model_reference"]["path"] = "../outside.json"
        errors = validate_testcase_value_assessment(model, root=ROOT)
        self.assertTrue(errors)

    def test_windows_absolute_reference_path_is_rejected(self):
        model = self.load_assessment_fixture("testcase-value-assessment-valid.json")
        model["testcase_model_reference"]["path"] = "C:/outside.json"
        errors = validate_testcase_value_assessment(model, root=ROOT)
        self.assertTrue(errors)

    def test_posix_absolute_reference_path_is_rejected(self):
        model = self.load_assessment_fixture("testcase-value-assessment-valid.json")
        model["testcase_model_reference"]["path"] = "/outside.json"
        errors = validate_testcase_value_assessment(model, root=ROOT)
        self.assertTrue(errors)

    def test_reference_hash_normalizes_lf_crlf_and_cr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / "lf.json", root / "crlf.json", root / "cr.json"]
            paths[0].write_bytes(b'{"value": 1}\n')
            paths[1].write_bytes(b'{"value": 1}\r\n')
            paths[2].write_bytes(b'{"value": 1}\r')
            hashes = [stable_normalized_file_hash(path) for path in paths]
        self.assertEqual(1, len(set(hashes)))

    def test_execution_and_assessment_share_public_hash_implementation(self):
        self.assertIs(stable_normalized_file_hash, execution_file_hash)

    def test_reference_hash_changes_when_content_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.json"
            second = root / "second.json"
            first.write_bytes(b'{"value": 1}\n')
            second.write_bytes(b'{"value": 2}\n')
            self.assertNotEqual(stable_normalized_file_hash(first), stable_normalized_file_hash(second))

    def test_null_requirement_reference_recomputes_successfully(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = self.write_bundle(root, requirement=False)
            self.assertIsNone(model["requirement_model_reference"])
            self.assertEqual([], validate_testcase_value_assessment(model, root=root))

    def test_invalid_persisted_maintenance_values_are_rejected(self):
        for value in (True, -1, "1"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                model = self.write_bundle(root)
                model["maintenance_inputs"] = {
                    "TC001": {
                        "manual_oracle_count": value,
                        "external_system_dependency_count": 0,
                        "mutable_shared_data_dependency_count": 0,
                        "environment_specific_dependency_count": 0,
                    }
                }
                self.assertTrue(validate_testcase_value_assessment(model, root=root))

    def test_value_assessment_is_not_required_by_existing_model_validators(self):
        testcase = load_json(ROOT / "tests" / "fixtures" / "models" / "testcase-model-multi-entry.json")
        risk = load_json(ROOT / "tests" / "fixtures" / "models" / "risk-coverage-matrix.json")
        self.assertEqual([], validate_testcase_model(testcase))
        self.assertEqual([], validate_risk_matrix(risk))

    def test_integer_recomputation_is_repeatable_without_float_values(self):
        first = self.calculate()
        second = self.calculate()
        self.assertEqual(first, second)

        def walk(value):
            if isinstance(value, dict):
                for item in value.values():
                    yield from walk(item)
            elif isinstance(value, list):
                for item in value:
                    yield from walk(item)
            else:
                yield value

        self.assertFalse(any(isinstance(value, float) for value in walk(first)))


if __name__ == "__main__":
    unittest.main()
