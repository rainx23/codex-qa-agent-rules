from __future__ import annotations

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
    format_testcase_value_assessment,
    stable_normalized_file_hash,
)
from validate_testcase_quality import main  # noqa: E402

XMIND = ROOT / "tests" / "fixtures" / "valid_case_xmind.md"
VALID_ASSESSMENT = ROOT / "tests" / "fixtures" / "value-assessment" / "testcase-value-assessment-valid.json"
GOLDEN = ROOT / "tests" / "fixtures" / "value-assessment" / "golden" / "testcase-value-assessment-cli.txt"


def normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


class TestcaseValueGoldenTests(unittest.TestCase):
    def capture(self, assessment: Path):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main([str(XMIND), "--value-assessment", str(assessment)])
        output = normalize_newlines(stdout.getvalue())
        marker = output.index("ASSESSMENT ")
        return result, output[marker:], normalize_newlines(stderr.getvalue())

    def capture_model(self, assessment: dict):
        output = "\n".join(format_testcase_value_assessment(assessment)) + "\n"
        return 0, output, ""

    def case(self, tc_id: str, risk_ids: list[str]):
        return {
            "tc_id": tc_id,
            "test_point": "customer page reachability",
            "steps": ["open customer page"],
            "expected_results": ["page opens and button is clickable"],
            "entry_branches": [],
            "risk_ids": risk_ids,
            "historical_defect_ids": [],
            "evidence_state": "待确认",
            "regression_scope": "冒烟回归",
            "deduplication_key": f"case-{tc_id}",
        }

    def risk(self, risk_id: str, priority: str, merge_key: str):
        return {
            "risk_id": risk_id,
            "business_impact": "low",
            "test_priority": priority,
            "testcase_ids": ["TC001"],
            "merge_key": merge_key,
            "fact_ids": [f"FACT-{risk_id}"],
            "evidence_state": "待确认",
            "evidence_references": [{"evidence_status": "stale"}],
        }

    def write_mixed_bundle(self, directory: Path, *, reverse_cases: bool = False, reverse_risks: bool = False):
        directory.mkdir(parents=True, exist_ok=True)
        cases = [
            self.case("TC001", ["RISK-P0", "RISK-A", "RISK-B"]),
            self.case("TC002", ["RISK-UNKNOWN"]),
        ]
        risks = [
            self.risk("RISK-P0", "P0", "p0"),
            self.risk("RISK-A", "P2", "a"),
            self.risk("RISK-B", "P2", "b"),
        ]
        if reverse_cases:
            cases.reverse()
        if reverse_risks:
            risks.reverse()
        testcase_model = {"model_id": "TC-MODEL-GOLDEN", "cases": cases}
        risk_model = {"matrix_id": "MATRIX-GOLDEN", "risk_items": risks}
        maintenance_inputs = {
            "TC001": {
                "external_system_dependency_count": 8,
                "mutable_shared_data_dependency_count": 0,
                "manual_oracle_count": 0,
                "environment_specific_dependency_count": 0,
            }
        }
        testcase_path = directory / "testcase.json"
        risk_path = directory / "risk.json"
        testcase_path.write_bytes((json.dumps(testcase_model, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        risk_path.write_bytes((json.dumps(risk_model, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        calculated = calculate_testcase_value_assessments(testcase_model, risk_model, None, maintenance_inputs)
        assessment = {
            "schema_version": "2.0.0",
            "assessment_model_id": "TVA-700",
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
        assessment_path.write_bytes((json.dumps(assessment, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        return assessment_path, assessment

    def test_cli_assessment_output_matches_golden_exactly(self):
        result, actual, stderr = self.capture(VALID_ASSESSMENT)
        expected = GOLDEN.read_text(encoding="utf-8")
        self.assertEqual(0, result)
        self.assertEqual("", stderr)
        self.assertEqual(expected, actual)

    def test_golden_is_utf8_without_bom_and_uses_single_lf_ending(self):
        raw = GOLDEN.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", raw)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertFalse(raw.endswith(b"\n\n"))
        self.assertEqual(raw, raw.decode("utf-8").encode("utf-8"))

    def test_same_cli_input_is_byte_stable_across_two_runs(self):
        self.assertEqual(self.capture(VALID_ASSESSMENT), self.capture(VALID_ASSESSMENT))

    def test_golden_contains_complete_computed_results(self):
        text = GOLDEN.read_text(encoding="utf-8")
        self.assertRegex(text, r"ASSESSMENT TC001 status=computed score=\d+ band=\w+")
        self.assertIn("DIMENSIONS TC001", text)
        self.assertIn("SUMMARY testcase_value_assessment computed=2 insufficient=0", text)

    def test_golden_contains_no_unstable_or_destructive_content(self):
        text = GOLDEN.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(?:[A-Za-z]:[\\/]|/tmp/|AppData|<[^>]+ at 0x[0-9a-fA-F]+>)")
        self.assertNotRegex(text, r"\b\d+\.\d+\b")
        self.assertNotRegex(text.lower(), r"\b(delete|drop|remove|downgrade)\b|自动合并")

    def test_computed_and_insufficient_statuses_are_stable(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            _, model = self.write_mixed_bundle(Path(directory))
            result, output, stderr = self.capture_model(model)
        self.assertEqual(0, result)
        self.assertEqual("", stderr)
        self.assertRegex(output, r"ASSESSMENT TC001 status=computed score=\d+ band=\w+")
        self.assertIn("ASSESSMENT TC002 status=insufficient_inputs score=null band=null", output)
        self.assertIn("GUARDRAIL TC001 p0_mapped", output)

    def test_reversing_cases_keeps_assessment_output_identical(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            root = Path(directory)
            _, forward = self.write_mixed_bundle(root / "forward")
            _, reverse = self.write_mixed_bundle(root / "reverse", reverse_cases=True)
            self.assertEqual(self.capture_model(forward), self.capture_model(reverse))

    def test_reversing_risks_keeps_assessment_output_identical(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            root = Path(directory)
            _, forward = self.write_mixed_bundle(root / "forward")
            _, reverse = self.write_mixed_bundle(root / "reverse", reverse_risks=True)
            self.assertEqual(self.capture_model(forward), self.capture_model(reverse))

    def test_warning_and_suggestion_order_is_fixed_and_nonblocking(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            _, model = self.write_mixed_bundle(Path(directory))
            result, output, _ = self.capture_model(model)
        advisory = [line for line in output.splitlines() if line.startswith(("WARNING TC001", "SUGGESTION TC001"))]
        self.assertEqual(0, result)
        self.assertEqual([
            "WARNING TC001 LOW_EVIDENCE_CONFIDENCE",
            "WARNING TC001 P0_LOW_SCORE_GUARDED",
            "WARNING TC001 MULTI_RISK_DIAGNOSTIC_WEAKNESS",
            "SUGGESTION TC001 SPLIT_FOR_DIAGNOSIS",
            "SUGGESTION TC001 RECONFIRM_PRIORITY_EVIDENCE",
            "SUGGESTION TC001 RETAIN_GUARDED_AND_IMPROVE",
        ], advisory)

    def test_assessment_output_has_stable_tc_and_reason_order(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            _, model = self.write_mixed_bundle(Path(directory), reverse_cases=True, reverse_risks=True)
            _, output, _ = self.capture_model(model)
        ids = [line.split()[1] for line in output.splitlines() if line.startswith("ASSESSMENT ")]
        self.assertEqual(["TC001", "TC002"], ids)
        reasons = [line for line in output.splitlines() if line.startswith("REASON TC001")]
        self.assertEqual(reasons, list(dict.fromkeys(reasons)))


if __name__ == "__main__":
    unittest.main()
