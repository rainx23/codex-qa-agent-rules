from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa_contracts import load_json
from validate_traceability import validate_files


class TraceabilityTests(unittest.TestCase):
    def setUp(self):
        self.report_text = (ROOT / "tests/fixtures/reports/combined_consistent.md").read_text(encoding="utf-8")
        self.xmind = ROOT / "tests/fixtures/valid_case_xmind.md"
        self.risk = ROOT / "tests/fixtures/models/risk-coverage-matrix.json"
        self.testcase = ROOT / "tests/fixtures/models/testcase-model.json"

    def validate_text(self, text: str, risk: Path | None = None, testcase: Path | None = None) -> list[str]:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
            handle.write(text)
            report = Path(handle.name)
        try:
            return validate_files(report, self.xmind, "combined", risk or self.risk, testcase or self.testcase)[0]
        finally:
            report.unlink()

    def test_valid_row_level_mapping(self):
        self.assertEqual([], self.validate_text(self.report_text))

    def test_tc_only_in_plain_text_fails(self):
        text = self.report_text.replace("| REQ-POINT-002 | 需求原文 | CHG-002 | 已覆盖 | RISK-002 | TC002 |\n", "")
        self.assertTrue(any("普通正文" in error or "未被追踪" in error for error in self.validate_text(text)))

    def test_combined_row_requires_requirement_evidence_and_change_id(self):
        for old, token in (("| REQ-POINT-001 | 需求原文 |", "需求证据"), ("| CHG-001 | 已覆盖 |", "Diff 变更 ID")):
            text = self.report_text.replace(old, old.replace("需求原文", "") if "需求原文" in old else old.replace("CHG-001", ""))
            self.assertTrue(any(token in error for error in self.validate_text(text)), token)

    def test_p0_risk_without_tc_fails(self):
        data = load_json(self.risk)
        data["risk_items"][0]["testcase_ids"] = []
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            import json
            json.dump(data, handle, ensure_ascii=False)
            path = Path(handle.name)
        try:
            self.assertTrue(any("P0 风险" in error for error in self.validate_text(self.report_text, risk=path)))
        finally:
            path.unlink()

    def test_report_reference_missing_tc_and_xmind_untracked_tc_fail(self):
        text = self.report_text.replace("TC002 |", "TC003 |")
        errors = self.validate_text(text)
        self.assertTrue(any("不存在的 TC" in error for error in errors))
        self.assertTrue(any("未被追踪" in error for error in errors))

    def test_one_tc_can_cover_multiple_risks_explicitly(self):
        text = self.report_text.replace(
            "| REQ-POINT-002 | 需求原文 | CHG-002 | 已覆盖 | RISK-002 | TC002 |",
            "| REQ-POINT-002 | 需求原文 | CHG-002 | 已覆盖 | RISK-002 | TC002 |\n"
            "| REQ-POINT-002 | 需求原文 | CHG-002 | 已覆盖 | RISK-002 | TC001 |",
        )
        risk_data = load_json(self.risk)
        risk_data["risk_items"][1]["testcase_ids"].append("TC001")
        testcase_data = load_json(self.testcase)
        testcase_data["cases"][0]["risk_ids"].append("RISK-002")
        testcase_data["cases"][0]["requirement_ids"].append("REQ-POINT-002")
        testcase_data["cases"][0]["change_ids"].append("CHG-002")
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as risk_handle:
            json.dump(risk_data, risk_handle, ensure_ascii=False)
            risk_path = Path(risk_handle.name)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as case_handle:
            json.dump(testcase_data, case_handle, ensure_ascii=False)
            case_path = Path(case_handle.name)
        try:
            self.assertEqual([], self.validate_text(text, risk=risk_path, testcase=case_path))
        finally:
            risk_path.unlink()
            case_path.unlink()

    def test_tc_range_cannot_replace_rows(self):
        text = self.report_text.replace("TC001 |", "TC001-TC002 |")
        self.assertTrue(any("模糊 TC 范围" in error for error in self.validate_text(text)))

    def test_testcase_model_and_markdown_mismatch(self):
        data = load_json(self.testcase)
        data["cases"] = data["cases"][:1]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            import json
            json.dump(data, handle, ensure_ascii=False)
            path = Path(handle.name)
        try:
            self.assertTrue(any("集合不一致" in error or "连续" in error for error in self.validate_text(self.report_text, testcase=path)))
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
