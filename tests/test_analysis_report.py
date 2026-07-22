from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa_contracts import load_json, validate_model_links, validate_risk_matrix
from validate_analysis_report import validate
from validate_manifest import validate_manifest_data


MODELS = ROOT / "tests/fixtures/models"
REPORT = ROOT / "tests/fixtures/reports/combined_consistent.md"


class StrictAnalysisReportTests(unittest.TestCase):
    def model(self, name: str) -> dict:
        return load_json(MODELS / name)

    def test_missing_schema_version_cannot_bypass_fake_fact_id(self):
        text = REPORT.read_text(encoding="utf-8-sig").replace("FACT-001", "FACT-999")
        text = text.replace("Schema Version: 2.0.0\n", "").replace("Rule Version: 2.6.0\n", "")
        self.assertNotIn("Schema Version", text)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            path.write_text(text, encoding="utf-8")
            errors = validate(
                path,
                mode="combined",
                known_ids={"fact_ids": {"FACT-001", "FACT-002"}},
            )
        self.assertTrue(any("FACT-999" in error for error in errors), errors)

    def test_manifest_passes_known_model_ids_to_report_validator(self):
        manifest_path = ROOT / "testcases/manifest.example.json"
        manifest = load_json(manifest_path)
        with patch("validate_manifest.validate_current_rule_dimension_assessment", return_value=[]), \
                patch("validate_manifest.validate_analysis_report", return_value=[]) as report_validator:
            errors = validate_manifest_data(manifest, manifest_path)
        self.assertEqual([], errors)
        self.assertIn("known_ids", report_validator.call_args.kwargs)
        self.assertTrue(report_validator.call_args.kwargs["known_ids"]["fact_ids"])

    def test_vague_core_assertion_is_rejected(self):
        risk = self.model("risk-coverage-matrix.json")
        risk["risk_items"][0]["core_assertion"] = "功能异常"
        self.assertTrue(any("core_assertion" in error for error in validate_risk_matrix(risk)))

    def test_merged_target_must_exist(self):
        risk = self.model("risk-coverage-matrix.json")
        item = risk["risk_items"][1]
        item.update(disposition_status="merged", merged_to=["RISK-999"])
        self.assertTrue(any("RISK-999" in error for error in validate_risk_matrix(risk)))

    def test_diff_risk_disposition_must_match_matrix(self):
        requirement = self.model("requirement-analysis.json")
        diff = self.model("diff-impact.json")
        risk = self.model("risk-coverage-matrix.json")
        testcase = self.model("testcase-model.json")
        risk["risk_items"][0].update(
            disposition_status="accepted",
            decision_evidence=copy.deepcopy(risk["risk_items"][0]["evidence_references"]),
        )
        errors = validate_model_links(requirement, diff, risk, testcase)
        self.assertTrue(any("disposition" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
