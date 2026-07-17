from __future__ import annotations

import copy
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa_contracts import (  # noqa: E402
    VALUE_ASSESSMENT_ALGORITHM_VERSION,
    calculate_testcase_value_assessments,
    load_json,
    stable_normalized_file_hash,
)
from validate_testcase_quality import main  # noqa: E402

XMIND = ROOT / "tests" / "fixtures" / "valid_case_xmind.md"
VALUE_FIXTURES = ROOT / "tests" / "fixtures" / "value-assessment"


class TestcaseValueCliTests(unittest.TestCase):
    def invoke(self, assessment: Path | None = None):
        argv = [str(XMIND)]
        if assessment is not None:
            argv.extend(["--value-assessment", str(assessment)])
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(argv)
        return result, stdout.getvalue(), stderr.getvalue()

    def case(self, tc_id: str, *, risk_ids: list[str], historical: bool = False):
        return {
            "tc_id": tc_id,
            "test_point": "open customer page",
            "steps": ["open page"],
            "expected_results": ["page opens and button is clickable"],
            "entry_branches": [],
            "risk_ids": risk_ids,
            "historical_defect_ids": ["BUG-001"] if historical else [],
            "evidence_state": "待确认",
            "regression_scope": "冒烟回归",
            "deduplication_key": "same-smoke-case" if tc_id in {"TC001", "TC002"} else "multi-risk-case",
        }

    def risk(self, risk_id: str, *, priority: str, testcase_ids: list[str], merge_key: str):
        return {
            "risk_id": risk_id,
            "business_impact": "low",
            "test_priority": priority,
            "testcase_ids": testcase_ids,
            "merge_key": merge_key,
            "fact_ids": [f"FACT-{risk_id}"],
            "evidence_state": "待确认",
            "evidence_references": [{"evidence_status": "stale"}],
        }

    def write_advisory_bundle(self, directory: Path):
        testcase_model = {
            "model_id": "TC-MODEL-CLI",
            "cases": [
                self.case("TC001", risk_ids=["RISK-P0"]),
                self.case("TC002", risk_ids=["RISK-P0"], historical=True),
                self.case("TC003", risk_ids=["RISK-A", "RISK-B", "RISK-C"]),
            ],
        }
        risk_model = {
            "matrix_id": "MATRIX-CLI",
            "risk_items": [
                self.risk("RISK-P0", priority="P0", testcase_ids=["TC001", "TC002"], merge_key="p0"),
                self.risk("RISK-A", priority="P2", testcase_ids=["TC003"], merge_key="a"),
                self.risk("RISK-B", priority="P2", testcase_ids=["TC003"], merge_key="b"),
                self.risk("RISK-C", priority="P2", testcase_ids=["TC003"], merge_key="c"),
            ],
        }
        maintenance_inputs = {
            "TC002": {
                "external_system_dependency_count": 8,
                "mutable_shared_data_dependency_count": 0,
                "manual_oracle_count": 0,
                "environment_specific_dependency_count": 0,
            },
            "TC003": {
                "external_system_dependency_count": 8,
                "mutable_shared_data_dependency_count": 0,
                "manual_oracle_count": 0,
                "environment_specific_dependency_count": 0,
            }
        }
        testcase_path = directory / "testcase.json"
        risk_path = directory / "risk.json"
        testcase_path.write_bytes((json.dumps(testcase_model, ensure_ascii=False, indent=2) + "\n").encode())
        risk_path.write_bytes((json.dumps(risk_model, ensure_ascii=False, indent=2) + "\n").encode())
        calculated = calculate_testcase_value_assessments(
            testcase_model, risk_model, None, maintenance_inputs
        )
        model = {
            "schema_version": "2.0.0",
            "assessment_model_id": "TVA-800",
            "algorithm_version": VALUE_ASSESSMENT_ALGORITHM_VERSION,
            "testcase_model_reference": {
                "model_id": testcase_model["model_id"],
                "path": testcase_path.relative_to(ROOT).as_posix(),
                "content_hash": stable_normalized_file_hash(testcase_path),
            },
            "risk_matrix_reference": {
                "matrix_id": risk_model["matrix_id"],
                "path": risk_path.relative_to(ROOT).as_posix(),
                "content_hash": stable_normalized_file_hash(risk_path),
            },
            "requirement_model_reference": None,
            "maintenance_inputs": maintenance_inputs,
            "assessments": calculated["assessments"],
        }
        assessment_path = directory / "assessment.json"
        assessment_path.write_bytes((json.dumps(model, ensure_ascii=False, indent=2) + "\n").encode())
        return assessment_path, model

    def temporary_advisory_bundle(self):
        return tempfile.TemporaryDirectory(dir=ROOT / "tests")

    def test_without_value_assessment_preserves_original_cli_output(self):
        result, stdout, stderr = self.invoke()
        self.assertEqual(0, result)
        self.assertEqual("", stderr)
        self.assertNotIn("testcase_value_assessment", stdout)
        self.assertNotIn("ASSESSMENT ", stdout)

    def test_valid_assessment_returns_zero(self):
        result, _, _ = self.invoke(VALUE_FIXTURES / "testcase-value-assessment-valid.json")
        self.assertEqual(0, result)

    def test_valid_assessment_prints_assessment_dimensions_and_summary(self):
        _, stdout, _ = self.invoke(VALUE_FIXTURES / "testcase-value-assessment-valid.json")
        self.assertIn("ASSESSMENT TC001", stdout)
        self.assertIn("DIMENSIONS TC001", stdout)
        self.assertIn("SUMMARY testcase_value_assessment", stdout)

    def test_hash_invalid_returns_one_without_score_summary(self):
        result, stdout, stderr = self.invoke(VALUE_FIXTURES / "testcase-value-assessment-hash-invalid.json")
        self.assertEqual(1, result)
        self.assertIn("ERROR testcase_value_assessment", stderr)
        self.assertNotIn("ASSESSMENT TC", stdout)

    def test_score_tampered_returns_one(self):
        result, _, stderr = self.invoke(VALUE_FIXTURES / "testcase-value-assessment-score-tampered.json")
        self.assertEqual(1, result)
        self.assertIn("dimensions", stderr)

    def test_unknown_tc_returns_one(self):
        result, _, stderr = self.invoke(VALUE_FIXTURES / "testcase-value-assessment-unknown-tc.json")
        self.assertEqual(1, result)
        self.assertIn("TC999", stderr)

    def test_missing_json_file_returns_one(self):
        result, _, stderr = self.invoke(ROOT / "tests" / "does-not-exist-assessment.json")
        self.assertEqual(1, result)
        self.assertIn("FILE_NOT_FOUND", stderr)

    def test_invalid_json_returns_one(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_bytes(b"{")
            result, _, stderr = self.invoke(path)
        self.assertEqual(1, result)
        self.assertIn("INVALID_JSON", stderr)

    def test_warning_does_not_change_exit_code(self):
        with self.temporary_advisory_bundle() as directory:
            path, _ = self.write_advisory_bundle(Path(directory))
            result, stdout, _ = self.invoke(path)
        self.assertEqual(0, result)
        self.assertIn("WARNING TC001 LOW_EVIDENCE_CONFIDENCE", stdout)

    def test_suggestion_does_not_change_exit_code(self):
        result, stdout, _ = self.invoke(VALUE_FIXTURES / "testcase-value-assessment-valid.json")
        self.assertEqual(0, result)
        self.assertIn("SUGGESTION TC001 REVIEW_SIMPLIFICATION", stdout)

    def test_insufficient_inputs_uses_null_score(self):
        _, stdout, _ = self.invoke(VALUE_FIXTURES / "testcase-value-assessment-valid.json")
        line = next(line for line in stdout.splitlines() if line.startswith("ASSESSMENT TC001"))
        self.assertIn("status=insufficient_inputs score=null band=null", line)

    def test_p0_guarded_case_never_prints_delete_or_downgrade(self):
        with self.temporary_advisory_bundle() as directory:
            path, _ = self.write_advisory_bundle(Path(directory))
            result, stdout, _ = self.invoke(path)
        self.assertEqual(0, result)
        self.assertIn("P0_LOW_SCORE_GUARDED", stdout)
        self.assertNotRegex(stdout.lower(), r"\b(delete|drop|remove|downgrade)\b")

    def test_historical_defect_guarded_case_never_prints_delete_or_downgrade(self):
        with self.temporary_advisory_bundle() as directory:
            path, _ = self.write_advisory_bundle(Path(directory))
            result, stdout, _ = self.invoke(path)
        self.assertEqual(0, result)
        self.assertIn("HISTORICAL_DEFECT_LOW_SCORE_GUARDED", stdout)
        self.assertNotRegex(stdout.lower(), r"\b(delete|drop|remove|downgrade)\b")

    def test_duplicate_only_prints_review_advice(self):
        with self.temporary_advisory_bundle() as directory:
            path, _ = self.write_advisory_bundle(Path(directory))
            _, stdout, _ = self.invoke(path)
        self.assertIn("POSSIBLE_DUPLICATE_REVIEW_REQUIRED", stdout)
        self.assertIn("REVIEW_DUPLICATE", stdout)
        self.assertNotRegex(stdout.lower(), r"\b(delete|drop|remove|downgrade)\b")

    def test_reversed_assessment_input_has_stable_sorted_output(self):
        with self.temporary_advisory_bundle() as directory:
            root = Path(directory)
            forward_path, model = self.write_advisory_bundle(root)
            _, forward, _ = self.invoke(forward_path)
            reversed_model = copy.deepcopy(model)
            reversed_model["assessments"].reverse()
            reversed_path = root / "assessment-reversed.json"
            reversed_path.write_bytes((json.dumps(reversed_model, ensure_ascii=False, indent=2) + "\n").encode())
            _, reverse, _ = self.invoke(reversed_path)
        self.assertEqual(forward, reverse)
        assessment_ids = [line.split()[1] for line in forward.splitlines() if line.startswith("ASSESSMENT ")]
        self.assertEqual(sorted(assessment_ids), assessment_ids)

    def test_dimensions_use_fixed_field_order(self):
        _, stdout, _ = self.invoke(VALUE_FIXTURES / "testcase-value-assessment-valid.json")
        line = next(line for line in stdout.splitlines() if line.startswith("DIMENSIONS TC001"))
        fields = [part.split("=")[0] for part in line.split()[2:]]
        self.assertEqual([
            "business_impact", "risk_coverage_value", "regression_value", "diagnostic_value",
            "evidence_confidence", "maintenance_cost", "redundancy_penalty",
        ], fields)

    def test_reason_codes_use_kernel_order(self):
        model = load_json(VALUE_FIXTURES / "testcase-value-assessment-valid.json")
        _, stdout, _ = self.invoke(VALUE_FIXTURES / "testcase-value-assessment-valid.json")
        actual = [line.split()[2] for line in stdout.splitlines() if line.startswith("REASON TC001 ")]
        self.assertEqual(model["assessments"][0]["reason_codes"], actual)

    def test_same_command_twice_has_identical_output(self):
        first = self.invoke(VALUE_FIXTURES / "testcase-value-assessment-valid.json")
        second = self.invoke(VALUE_FIXTURES / "testcase-value-assessment-valid.json")
        self.assertEqual(first, second)

    def test_output_contains_no_current_time(self):
        _, stdout, stderr = self.invoke(VALUE_FIXTURES / "testcase-value-assessment-valid.json")
        self.assertIsNone(re.search(r"\b20\d{2}-\d{2}-\d{2}[ T]", stdout + stderr))

    def test_output_does_not_expose_temporary_assessment_path(self):
        with self.temporary_advisory_bundle() as directory:
            path, _ = self.write_advisory_bundle(Path(directory))
            _, stdout, stderr = self.invoke(path)
            self.assertNotIn(str(Path(directory)), stdout + stderr)

    def test_output_contains_no_floating_point_score(self):
        with self.temporary_advisory_bundle() as directory:
            path, _ = self.write_advisory_bundle(Path(directory))
            _, stdout, _ = self.invoke(path)
        self.assertIsNone(re.search(r"\b(?:score|[a-z_]+)=\d+\.\d+\b", stdout))

    def test_exit_code_rules_have_no_platform_branch(self):
        valid = self.invoke(VALUE_FIXTURES / "testcase-value-assessment-valid.json")[0]
        invalid = self.invoke(VALUE_FIXTURES / "testcase-value-assessment-hash-invalid.json")[0]
        self.assertEqual((0, 1), (valid, invalid))

    def test_multi_risk_warning_and_split_suggestion_are_nonblocking(self):
        with self.temporary_advisory_bundle() as directory:
            path, _ = self.write_advisory_bundle(Path(directory))
            result, stdout, _ = self.invoke(path)
        self.assertEqual(0, result)
        self.assertIn("WARNING TC003 MULTI_RISK_DIAGNOSTIC_WEAKNESS", stdout)
        self.assertIn("SUGGESTION TC003 SPLIT_FOR_DIAGNOSIS", stdout)

    def test_all_phase_one_advisory_codes_are_emitted_deterministically(self):
        with self.temporary_advisory_bundle() as directory:
            path, _ = self.write_advisory_bundle(Path(directory))
            result, stdout, _ = self.invoke(path)
        self.assertEqual(0, result)
        for code in (
            "LOW_EVIDENCE_CONFIDENCE", "P0_LOW_SCORE_GUARDED",
            "HISTORICAL_DEFECT_LOW_SCORE_GUARDED", "POSSIBLE_DUPLICATE_REVIEW_REQUIRED",
            "MULTI_RISK_DIAGNOSTIC_WEAKNESS", "REVIEW_LOW_VALUE_SMOKE",
            "REVIEW_SIMPLIFICATION", "REVIEW_DUPLICATE", "SPLIT_FOR_DIAGNOSIS",
            "RECONFIRM_PRIORITY_EVIDENCE", "RETAIN_GUARDED_AND_IMPROVE",
        ):
            self.assertIn(code, stdout)


if __name__ == "__main__":
    unittest.main()
