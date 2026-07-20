from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))

from validate_analysis_report import validate  # noqa: E402

BASE = (ROOT / "tests/fixtures/reports/combined_consistent.md").read_text(encoding="utf-8-sig")


class AnalysisReportContentValidationTests(unittest.TestCase):
    def errors(self, text: str, *, status: str | None = None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            path.write_text(text, encoding="utf-8")
            return validate(path, mode="combined", strict=False, validation_status=status)

    def test_duplicate_fact_primary_summary_fails(self):
        text = BASE.replace("## Diff 理解", "## 规则拆解\n\n- FACT-001：客户编号规则。\n- FACT-001：重复摘要。\n\n## Diff 理解")
        self.assertTrue(any("DUPLICATE_REPORT_FACT_SUMMARY" in e for e in self.errors(text)))

    def test_duplicate_risk_primary_summary_fails(self):
        text = BASE.replace("- [RISK-002]", "- [RISK-001][FACT-002][CHG-002] 重复风险摘要。\n- [RISK-002]")
        self.assertTrue(any("DUPLICATE_REPORT_RISK_SUMMARY" in e for e in self.errors(text)))

    def test_duplicate_confirmation_primary_summary_fails(self):
        text = BASE.replace("- 无。", "- CONF-001 FACT-001 severity=nonblocking status=pending：待确认。\n- CONF-001 FACT-001 severity=nonblocking status=pending：重复。")
        self.assertTrue(any("DUPLICATE_REPORT_CONFIRMATION_SUMMARY" in e for e in self.errors(text)))

    def test_references_outside_primary_sections_do_not_count_as_duplicates(self):
        text = BASE.replace("## 回归范围", "## 测试维度扫描\n\n| 测试维度 | 风险 |\n| --- | --- |\n| 功能测试 | RISK-001、FACT-001 |\n\n普通正文再次引用 RISK-001、FACT-001。\n\n## 回归范围")
        self.assertFalse(any("DUPLICATE_REPORT" in e for e in self.errors(text)))

    def test_different_ids_in_one_primary_item_do_not_false_positive(self):
        text = BASE.replace("- [RISK-001][FACT-001][CHG-001]", "- [RISK-001][RISK-002][FACT-001][CHG-001]")
        text = text.replace("- [RISK-002][FACT-002][CHG-002]", "- [RISK-003][FACT-002][CHG-002]")
        self.assertFalse(any("DUPLICATE_REPORT_RISK_SUMMARY" in e for e in self.errors(text)))

    def test_passed_draft_wording_fails(self):
        for wording in ("23 个草稿 TC", "草稿用例", "草稿测试用例"):
            with self.subTest(wording=wording):
                text = BASE.replace("验证客户编号过滤。", f"{wording}验证客户编号过滤。")
                self.assertTrue(any("PASSED_REPORT_CONTAINS_DRAFT_WORDING" in e for e in self.errors(text, status="passed")))

    def test_passed_formal_tc_and_pending_draft_wording_pass(self):
        formal = BASE.replace("验证客户编号过滤。", "23 个正式 TC 验证客户编号过滤。")
        pending = BASE.replace("验证客户编号过滤。", "23 个草稿 TC 验证客户编号过滤。")
        self.assertFalse(any("PASSED_REPORT_CONTAINS_DRAFT_WORDING" in e for e in self.errors(formal, status="passed")))
        self.assertFalse(any("PASSED_REPORT_CONTAINS_DRAFT_WORDING" in e for e in self.errors(pending, status="pending")))

    def test_contract_phrase_draft_path_empty_does_not_false_positive(self):
        text = BASE + "\n\n草稿路径为空。\n"
        self.assertFalse(any("PASSED_REPORT_CONTAINS_DRAFT_WORDING" in e for e in self.errors(text, status="passed")))


if __name__ == "__main__":
    unittest.main()
