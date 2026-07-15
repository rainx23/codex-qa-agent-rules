from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_testcase_index import update
from md_to_xmind import convert_file
from repair_text_encoding import merge_reference_index, repair_text
from validate_manifest import validate_manifest_data, validate_manifest_file
from validate_skill_contracts import validate_skill


class ArtifactGovernanceTests(unittest.TestCase):
    def test_manifest_example_is_valid_pending(self):
        _, errors = validate_manifest_file(ROOT / "testcases/manifest.example.json")
        self.assertEqual([], errors)

    def test_invalid_manifest_counts_and_relation_fail(self):
        data = json.loads((ROOT / "testcases/manifest.example.json").read_text(encoding="utf-8"))
        data.update(case_count=-1, p0_count=-2, pending_count=-3, relation="任意")
        errors = validate_manifest_data(data, ROOT / "testcases/manifest.example.json")
        self.assertTrue(any("非负整数" in error for error in errors))
        self.assertTrue(any("relation" in error for error in errors))

    def test_passed_manifest_revalidates_artifacts_and_index(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            report = directory / "report.md"
            markdown = directory / "case_xmind_20260715.md"
            workbook = directory / "case_workbook_20260715.xmind"
            manifest = directory / "manifest.json"
            index = directory / "index.md"
            report.write_text(
                (ROOT / "tests/fixtures/reports/combined_consistent.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            markdown.write_text(
                (ROOT / "tests/fixtures/valid_case_xmind.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            convert_file(markdown, workbook)
            data = {
                "artifact_id": "QA-TEST-001",
                "source_type": "unit",
                "source_id": "REQ-1",
                "source_hash": "sha256:" + "0" * 64,
                "requirement_id": "REQ-1",
                "commit_range": "",
                "rule_version": "2.1.0",
                "generated_at": "2026-07-15 00:00:00",
                "report_path": str(report),
                "xmind_md_path": str(markdown),
                "xmind_path": str(workbook),
                "case_count": 2,
                "p0_count": 1,
                "pending_count": 0,
                "validation_status": "passed",
                "relation": "新增",
                "supersedes": None,
            }
            manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            self.assertEqual([], validate_manifest_file(manifest)[1])
            data["p0_count"] = 0
            manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(any("报告 P0 风险数" in error for error in validate_manifest_file(manifest)[1]))
            data["p0_count"] = 1
            manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            update(index, manifest)
            update(index, manifest)
            text = index.read_text(encoding="utf-8")
            self.assertEqual(1, text.count("artifact_id=QA-TEST-001"))

    def test_encoding_repair_is_reversible_and_cell_safe(self):
        text = "# 娴嬭瘯鍒嗘瀽杈撳嚭绱㈠紩\n| 禅道需求 | 绂呴亾闇€姹?|\n"
        repaired = repair_text(text)
        self.assertIn("测试分析输出索引", repaired)
        self.assertIn("禅道需求", repaired)
        reference = "# 测试分析输出索引\n| 生成时间 | 来源类型 |\n| 2026-01-01 00:00:00 | 禅道需求 |\n"
        broken = "# 娴嬭瘯鍒嗘瀽杈撳嚭绱㈠紩\n| 鐢熸垚鏃堕棿 | 鏉ユ簮绫诲瀷 |\n| 2026-01-01 00:00:00 | 绂呴亾闇€姹?|\n"
        merged = merge_reference_index(broken, reference)
        self.assertEqual(reference, merged)

    def test_all_skills_have_valid_contracts(self):
        for skill in (ROOT / "skills").iterdir():
            if skill.is_dir():
                self.assertEqual([], validate_skill(skill), skill.name)


if __name__ == "__main__":
    unittest.main()
