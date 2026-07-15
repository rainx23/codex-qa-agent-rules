from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from heading_utils import normalize_heading
from validate_analysis_report import detect_mode, validate

REPORTS = ROOT / "tests/fixtures/reports"


class AnalysisWorkflowTests(unittest.TestCase):
    def test_heading_number_formats_normalize_to_one_title(self):
        variants = (
            "风险点",
            "五、风险点",
            "5. 风险点",
            "5．风险点",
            "（五）风险点",
            "(五) 风险点",
            "（5）风险点",
            "(5) 风险点",
            "五 风险点",
            "5 风险点",
            "  五、风险点  ",
        )
        self.assertEqual({"风险点"}, {normalize_heading(value) for value in variants})

    def test_numbered_heading_body_and_p0_mapping_use_same_sections(self):
        source = (REPORTS / "requirement_only.md").read_text(encoding="utf-8")
        for heading in ("## 风险点", "## 五、风险点", "## 5. 风险点", "## （五）风险点"):
            text = source.replace("## 六、风险点", heading)
            self.assertEqual([], self._validate_text(text, mode="requirement"), heading)
            missing_mapping = text.replace("TC001：验证精确匹配和非匹配反例。", "验证精确匹配和非匹配反例。")
            self.assertIn("P0 风险未映射到具体测试点或 TC", self._validate_text(missing_mapping, mode="requirement"))

    def test_numbered_defect_and_trace_sections_are_not_skipped(self):
        source = (REPORTS / "requirement_diff_combined.md").read_text(encoding="utf-8")
        self.assertEqual([], self._validate_text(source, mode="combined"))
        no_diff_proof = source.replace("- Diff 证据：实现使用前缀匹配。\n", "")
        self.assertTrue(any("双重证据" in error for error in self._validate_text(no_diff_proof, mode="combined")))
        bad_trace = source.replace("覆盖状态", "处理结果")
        self.assertTrue(any("追踪矩阵缺少字段" in error for error in self._validate_text(bad_trace, mode="combined")))

    def test_requirement_only_contract_and_failures(self):
        path = REPORTS / "requirement_only.md"
        self.assertEqual([], validate(path, mode="requirement"))
        self.assertEqual("requirement", detect_mode(path.read_text(encoding="utf-8")))
        text = path.read_text(encoding="utf-8")
        for heading, expected in (
            ("## 四、证据来源\n", "证据来源"),
            ("## 六、风险点\n", "风险点"),
            ("## 八、回归范围\n", "回归范围"),
        ):
            errors = self._validate_text(text.replace(heading, "## 其他章节\n"), mode="requirement")
            self.assertTrue(any(expected in error for error in errors), expected)

    def test_diff_only_contract_and_no_trace_requirement(self):
        path = REPORTS / "diff_only.md"
        self.assertEqual([], validate(path, mode="diff"))
        self.assertEqual("diff", detect_mode(path.read_text(encoding="utf-8")))
        text = path.read_text(encoding="utf-8")
        for heading, expected in (
            ("## 2. Commit 或 Diff 对比范围\n", "Commit 或 Diff 对比范围"),
            ("## 4. 核心改动点\n", "核心改动点"),
            ("## 8. 疑似缺陷\n", "疑似缺陷"),
        ):
            errors = self._validate_text(text.replace(heading, "## 其他章节\n"), mode="diff")
            self.assertTrue(any(expected in error for error in errors), expected)
        self.assertFalse(any("追踪矩阵" in error for error in validate(path, mode="diff")))

    def test_combined_contract_requires_both_sides_and_trace(self):
        path = REPORTS / "requirement_diff_combined.md"
        self.assertEqual([], validate(path, mode="combined"))
        self.assertEqual("combined", detect_mode(path.read_text(encoding="utf-8")))
        text = path.read_text(encoding="utf-8")
        for heading, expected in (
            ("## （二）需求理解\n", "需求理解"),
            ("## （三）Diff 理解\n", "Diff 理解"),
            ("## （十）需求-Diff-测试点追踪矩阵\n", "追踪矩阵"),
        ):
            errors = self._validate_text(text.replace(heading, "## 其他章节\n"), mode="combined")
            self.assertTrue(any(expected in error for error in errors), expected)

    def test_explicit_mode_precedes_auto_detection(self):
        text = (REPORTS / "requirement_only.md").read_text(encoding="utf-8")
        self.assertEqual("requirement", detect_mode(text))
        self.assertEqual("diff", detect_mode(text, "diff"))

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
        bad = path.read_text(encoding="utf-8").replace("- Diff 证据：实现使用前缀匹配。\n", "")
        self.assertTrue(any("双重证据" in error for error in self._validate_text(bad)))

    def test_16_evidence_insufficient(self):
        path = REPORTS / "evidence_insufficient.md"
        text = path.read_text(encoding="utf-8")
        self.assertEqual([], validate(path))
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

    def test_p0_without_mapping_fails(self):
        text = (REPORTS / "finance_precision.md").read_text(encoding="utf-8").replace(
            "- TC001：验证批次聚合层级和最终舍入。", "- 暂无测试点。"
        )
        self.assertIn("P0 风险未映射到具体测试点或 TC", self._validate_text(text))

    def _validate_text(self, text: str, mode: str = "auto") -> list[str]:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
            handle.write(text)
            path = Path(handle.name)
        try:
            return validate(path, mode=mode)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
