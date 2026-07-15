from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_analysis_report import validate

REPORTS = ROOT / "tests/fixtures/reports"


class AnalysisWorkflowTests(unittest.TestCase):
    def test_13_pure_document_diff(self):
        path = REPORTS / "pure_document_diff.md"
        self.assertEqual([], validate(path))
        bad = path.read_text(encoding="utf-8").replace("不生成业务用例", "检查业务功能")
        self.assertIn("无业务 Diff 必须明确不生成业务用例", self._validate_text(bad))

    def test_14_requirement_and_diff_consistent(self):
        self.assertEqual([], validate(REPORTS / "combined_consistent.md"))

    def test_15_requirement_and_diff_inconsistent(self):
        path = REPORTS / "combined_inconsistent.md"
        self.assertEqual([], validate(path))
        bad = path.read_text(encoding="utf-8").replace("Diff 证据：实现使用前缀匹配。", "实现使用前缀匹配。")
        self.assertIn("疑似缺陷必须同时包含需求证据和 Diff 证据", self._validate_text(bad))

    def test_16_evidence_insufficient(self):
        text = (REPORTS / "evidence_insufficient.md").read_text(encoding="utf-8")
        self.assertEqual([], validate(REPORTS / "evidence_insufficient.md"))
        self.assertIn("阻塞类", text)
        self.assertNotIn("默认过滤", text)

    def test_18_finance_precision(self):
        path = REPORTS / "finance_precision.md"
        self.assertEqual([], validate(path))
        text = path.read_text(encoding="utf-8")
        for token in ("聚合", "舍入", "P0", "TC001"):
            self.assertIn(token, text)

    def test_19_personalization(self):
        path = REPORTS / "personalization.md"
        self.assertEqual([], validate(path))
        text = path.read_text(encoding="utf-8")
        for token in ("字段设置", "个人模板", "刷新", "模板搜索"):
            self.assertIn(token, text)

    def test_golden_report_results(self):
        golden = json.loads((ROOT / "tests/golden/scenario_results.json").read_text(encoding="utf-8"))
        actual = {path.stem: validate(path) for path in REPORTS.glob("*.md")}
        self.assertEqual(golden, actual)

    def test_missing_defect_conclusion_fails(self):
        text = (REPORTS / "personalization.md").read_text(encoding="utf-8").replace(
            "- 未发现明确疑似缺陷。", ""
        )
        self.assertIn("疑似缺陷章节必须明确结论", self._validate_text(text))

    def test_p0_without_mapping_fails(self):
        text = (REPORTS / "finance_precision.md").read_text(encoding="utf-8").replace(
            "- TC001：验证批次聚合层级和最终舍入。", "- 暂无测试点。"
        )
        self.assertIn("P0 风险未映射到具体测试点或 TC", self._validate_text(text))

    def test_combined_mode_is_automatic(self):
        text = (REPORTS / "combined_consistent.md").read_text(encoding="utf-8")
        marker = "## 需求-Diff-测试点追踪矩阵"
        text = text[: text.index(marker)]
        self.assertIn("需求与 Diff 并存时缺少需求-Diff-测试点追踪矩阵", self._validate_text(text))

    def _validate_text(self, text: str) -> list[str]:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
            handle.write(text)
            path = Path(handle.name)
        try:
            return validate(path)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()

