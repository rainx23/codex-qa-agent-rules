from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from file_hash_utils import stable_file_content_hash
from qa_contracts import load_json, validate_model_links, validate_requirement_model
from validate_evidence import evidence_precision_warnings, validate_evidence_reference

MODELS = ROOT / "tests/fixtures/models"


class EvidencePrecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.md"
        self.source.write_text(
            "客户编号支持精确查询。\n分页保留筛选条件。\n字段片段包含 enabled_flag。\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def load(self, name: str) -> dict:
        return load_json(MODELS / name)

    def evidence(self, line: int, excerpt: str, *, status: str = "current") -> dict:
        item = {
            "source_type": "requirement", "storage_type": "file", "source_path": "source.md",
            "snapshot_path": None, "source_record_id": "REQ-PRECISION", "line_start": line,
            "line_end": line, "commit_sha": None,
            "content_hash": stable_file_content_hash(self.source, normalize_text_newlines=True),
            "excerpt": excerpt, "captured_at": "2026-07-18 00:00:00",
            "captured_timezone": "Asia/Shanghai", "evidence_status": status,
        }
        if status != "current":
            item["stale_reason"] = "等待重新确认"
        return item

    def snapshot_evidence(self, start: int, end: int, excerpt: str, *, path: str = "snapshot.md") -> dict:
        snapshot = self.root / path
        if not snapshot.exists() and path == "snapshot.md":
            snapshot.write_bytes("\ufeff第一行\r\n\r\n第三行\r\n第四行\r\n".encode("utf-8"))
        return {
            "source_type": "pasted_text", "storage_type": "snapshot", "source_path": None,
            "snapshot_path": path, "source_record_id": "snapshot:LINE-RANGE",
            "line_start": start, "line_end": end, "commit_sha": None,
            "content_hash": stable_file_content_hash(snapshot, normalize_text_newlines=True) if snapshot.exists() else "sha256:" + "0" * 64,
            "excerpt": excerpt, "captured_at": "2026-07-20 00:00:00",
            "captured_timezone": "Asia/Shanghai", "evidence_status": "current",
        }

    def test_exact_snapshot_line_range_passes(self):
        self.assertEqual([], validate_evidence_reference(
            self.snapshot_evidence(1, 3, "第一行\n\n第三行"), root=self.root
        ))

    def test_line_start_offset_fails_with_stable_code(self):
        errors = validate_evidence_reference(self.snapshot_evidence(2, 3, "第一行\n\n第三行"), root=self.root)
        self.assertTrue(any("EVIDENCE_EXCERPT_LINE_RANGE_MISMATCH" in error for error in errors), errors)

    def test_line_end_offset_fails_with_stable_code(self):
        errors = validate_evidence_reference(self.snapshot_evidence(1, 2, "第一行\n\n第三行"), root=self.root)
        self.assertTrue(any("EVIDENCE_EXCERPT_LINE_RANGE_MISMATCH" in error for error in errors), errors)

    def test_excerpt_content_mismatch_fails_with_stable_code(self):
        errors = validate_evidence_reference(self.snapshot_evidence(1, 1, "不是第一行"), root=self.root)
        self.assertTrue(any("EVIDENCE_EXCERPT_LINE_RANGE_MISMATCH" in error for error in errors), errors)

    def test_crlf_lf_difference_is_normalized(self):
        self.assertEqual([], validate_evidence_reference(
            self.snapshot_evidence(1, 3, "第一行\r\n\r\n第三行"), root=self.root
        ))

    def test_blank_line_participates_in_physical_line_numbers(self):
        self.assertEqual([], validate_evidence_reference(self.snapshot_evidence(2, 3, "\n第三行"), root=self.root))

    def test_invalid_and_overflow_ranges_fail(self):
        for start, end, marker in ((0, 1, "行号范围非法"), (3, 2, "行号范围非法"), (1, 99, "line_end 超出")):
            with self.subTest(start=start, end=end):
                errors = validate_evidence_reference(self.snapshot_evidence(start, end, "第一行"), root=self.root)
                self.assertTrue(any(marker in error for error in errors), errors)

    def test_missing_snapshot_path_fails(self):
        errors = validate_evidence_reference(
            self.snapshot_evidence(1, 1, "第一行", path="missing.md"), root=self.root
        )
        self.assertTrue(any("snapshot_path 文件不存在" in error for error in errors), errors)

    def requirement(self) -> dict:
        data = self.load("requirement-analysis.json")
        refs = [self.evidence(1, "客户编号支持精确查询。"), self.evidence(2, "分页保留筛选条件。")]
        for index, fact in enumerate(data["facts"]):
            fact.update(statement=("客户编号支持精确查询" if index == 0 else "分页保留筛选条件"))
            fact["evidence_references"] = [copy.deepcopy(refs[index])]
        for index, criterion in enumerate(data["acceptance_criteria"]):
            criterion["evidence_references"] = [copy.deepcopy(refs[index])]
        return data

    def test_precise_different_line_references_pass(self):
        self.assertEqual([], validate_requirement_model(self.requirement(), evidence_root=self.root))

    def test_overconcentrated_first_line_references_warn(self):
        data = self.requirement()
        third = copy.deepcopy(data["facts"][0])
        third["fact_id"] = "FACT-003"
        data["facts"].append(third)
        for fact in data["facts"]:
            fact["evidence_references"] = [self.evidence(1, "客户编号支持精确查询。")]
        warnings = evidence_precision_warnings(data["facts"], root=self.root)
        self.assertTrue(any("EVIDENCE_REFERENCE_OVERCONCENTRATED" in warning for warning in warnings))

    def test_excerpt_outside_range_and_range_overflow_fail(self):
        item = self.evidence(1, "分页保留筛选条件。")
        self.assertTrue(any("EVIDENCE_EXCERPT_LINE_RANGE_MISMATCH" in error for error in validate_evidence_reference(item, root=self.root)))
        item = self.evidence(1, "客户编号支持精确查询。")
        item["line_end"] = 99
        self.assertTrue(any("line_end 超出" in error for error in validate_evidence_reference(item, root=self.root)))

    def test_acceptance_evidence_must_derive_from_linked_fact(self):
        data = self.requirement()
        data["acceptance_criteria"][0]["evidence_references"] = [self.evidence(3, "字段片段包含 enabled_flag。")]
        errors = validate_requirement_model(data, evidence_root=self.root)
        self.assertTrue(any("ACCEPTANCE_EVIDENCE_NOT_DERIVED_FROM_FACT" in error for error in errors))

    def test_risk_evidence_must_derive_from_linked_fact_or_criterion(self):
        requirement = self.requirement()
        risk = self.load("risk-coverage-matrix.json")
        risk["risk_items"][0]["evidence_references"] = [self.evidence(3, "字段片段包含 enabled_flag。")]
        errors = validate_model_links(requirement, self.load("diff-impact.json"), risk, self.load("testcase-model.json"))
        self.assertTrue(any("EVIDENCE_REFERENCE_NOT_DERIVED_FROM_LINKED_FACT" in error for error in errors))

    def test_confirmed_fact_requires_current_evidence(self):
        data = self.requirement()
        data["facts"][0]["evidence_references"] = [self.evidence(1, "客户编号支持精确查询。", status="stale")]
        data["acceptance_criteria"][0]["evidence_references"] = copy.deepcopy(data["facts"][0]["evidence_references"])
        errors = validate_requirement_model(data, evidence_root=self.root)
        self.assertTrue(any("CONFIRMED_FACT_WITHOUT_CURRENT_EVIDENCE" in error for error in errors))

    def test_confirmed_testcase_rejects_unconfirmed_risk(self):
        requirement = self.requirement()
        risk = self.load("risk-coverage-matrix.json")
        risk["risk_items"][0]["evidence_state"] = "待确认"
        errors = validate_model_links(requirement, self.load("diff-impact.json"), risk, self.load("testcase-model.json"))
        self.assertTrue(any("CONFIRMED_TESTCASE_WITH_UNCONFIRMED_LINK" in error for error in errors))

    def test_one_fact_can_use_multiple_precise_references(self):
        data = self.requirement()
        refs = [self.evidence(1, "客户编号支持精确查询。"), self.evidence(2, "分页保留筛选条件。")]
        data["facts"][0]["evidence_references"] = copy.deepcopy(refs)
        data["acceptance_criteria"][0]["evidence_references"] = copy.deepcopy(refs)
        self.assertEqual([], validate_requirement_model(data, evidence_root=self.root))

    def test_field_structure_cannot_confirm_business_behavior(self):
        data = self.requirement()
        data["facts"][0]["statement"] = "enabled_flag=false 的记录不参与统计"
        data["facts"][0]["evidence_references"] = [self.evidence(3, "字段片段包含 enabled_flag。")]
        data["acceptance_criteria"][0]["evidence_references"] = copy.deepcopy(data["facts"][0]["evidence_references"])
        errors = validate_requirement_model(data, evidence_root=self.root)
        self.assertTrue(any("EVIDENCE_CAPABILITY_CANNOT_CONFIRM_BEHAVIOR" in error for error in errors))

    def test_multiple_user_field_cannot_imply_automatic_deduplication(self):
        self.source.write_text("可追加多个用户。\n分页保留筛选条件。\n字段片段包含 enabled_flag。\n", encoding="utf-8")
        data = self.requirement()
        data["facts"][0]["statement"] = "多个用户选择后自动去重"
        data["facts"][0]["evidence_references"] = [self.evidence(1, "可追加多个用户。")]
        data["acceptance_criteria"][0]["evidence_references"] = copy.deepcopy(data["facts"][0]["evidence_references"])
        self.assertTrue(any(
            "EVIDENCE_CAPABILITY_CANNOT_CONFIRM_BEHAVIOR" in error
            for error in validate_requirement_model(data, evidence_root=self.root)
        ))

    def test_multiple_user_capacity_cannot_imply_duplicate_rejection_or_saved_dedup(self):
        for evidence_text, statement in (
            ("支持多个用户。", "重复用户不可选择"),
            ("可多选。", "保存后自动去重"),
        ):
            self.source.write_text(f"{evidence_text}\n分页保留筛选条件。\n字段片段包含 enabled_flag。\n", encoding="utf-8")
            data = self.requirement()
            data["facts"][0]["statement"] = statement
            data["facts"][0]["evidence_references"] = [self.evidence(1, evidence_text)]
            data["acceptance_criteria"][0]["evidence_references"] = copy.deepcopy(data["facts"][0]["evidence_references"])
            self.assertTrue(any(
                "EVIDENCE_CAPABILITY_CANNOT_CONFIRM_BEHAVIOR" in error
                for error in validate_requirement_model(data, evidence_root=self.root)
            ))

    def test_explicit_deduplication_behavior_with_capacity_passes(self):
        text = "支持追加多个用户，重复用户自动去重。"
        self.source.write_text(f"{text}\n分页保留筛选条件。\n字段片段包含 enabled_flag。\n", encoding="utf-8")
        data = self.requirement()
        data["facts"][0]["statement"] = "多个用户选择后自动去重"
        data["facts"][0]["evidence_references"] = [self.evidence(1, text)]
        data["acceptance_criteria"][0]["evidence_references"] = copy.deepcopy(data["facts"][0]["evidence_references"])
        self.assertEqual([], validate_requirement_model(data, evidence_root=self.root))

    def test_explicit_behavior_evidence_can_confirm_behavior(self):
        self.source.write_text(
            "enabled_flag=0 的记录不参与权限判断。\n分页保留筛选条件。\n字段片段包含 enabled_flag。\n",
            encoding="utf-8",
        )
        data = self.requirement()
        data["facts"][0]["statement"] = "enabled_flag=0 不参与权限"
        data["facts"][0]["evidence_references"] = [self.evidence(1, "enabled_flag=0 的记录不参与权限判断。")]
        data["acceptance_criteria"][0]["evidence_references"] = copy.deepcopy(data["facts"][0]["evidence_references"])
        self.assertEqual([], validate_requirement_model(data, evidence_root=self.root))


if __name__ == "__main__":
    unittest.main()
