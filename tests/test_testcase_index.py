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

from build_testcase_index import HEADER, build_row
from md_to_xmind import convert_file
from qa_contracts import DIMENSIONS, read_rule_version, stable_source_hash
from validate_testcase_index import _cells, validate_index


class TestcaseIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copy2(ROOT / "RULE_VERSION", self.root / "RULE_VERSION")
        shutil.copy2(ROOT / "AGENTS.md", self.root / "AGENTS.md")
        self.testcases = self.root / "testcases"
        self.directory = self.testcases / "generic-contract-20260720"
        self.directory.mkdir(parents=True)
        fixture_root = self.root / "tests/fixtures"
        (fixture_root / "sources").mkdir(parents=True)
        (fixture_root / "models").mkdir(parents=True)
        (fixture_root / "reports").mkdir(parents=True)
        for name in ("requirement.md", "customer-query.java"):
            shutil.copy2(ROOT / "tests/fixtures/sources" / name, fixture_root / "sources" / name)
        for name in ("requirement-analysis.json", "diff-impact.json", "risk-coverage-matrix.json", "testcase-model.json"):
            shutil.copy2(ROOT / "tests/fixtures/models" / name, fixture_root / "models" / name)
        shutil.copy2(ROOT / "tests/fixtures/reports/combined_consistent.md", fixture_root / "reports/combined_consistent.md")
        shutil.copy2(ROOT / "tests/fixtures/valid_case_xmind.md", fixture_root / "valid_case_xmind.md")
        requirement_path = fixture_root / "models/requirement-analysis.json"
        requirement = json.loads(requirement_path.read_text(encoding="utf-8"))
        requirement["test_dimension_assessment"] = []
        for dimension in DIMENSIONS:
            covered = dimension in {"功能测试", "数据测试"}
            suffix = "001" if dimension == "功能测试" else "002"
            requirement["test_dimension_assessment"].append({
                "dimension": dimension, "status": "covered" if covered else "not_applicable",
                "reason": "通用 Fixture 已覆盖" if covered else "通用 Fixture 范围不涉及该维度",
                "fact_ids": [f"FACT-{suffix}" if covered else "FACT-001"],
                "risk_ids": [f"RISK-{suffix}"] if covered else [], "confirmation_ids": [],
                "testcase_ids": [f"TC{suffix}"] if covered else [], "evidence_references": [],
            })
        requirement_path.write_text(json.dumps(requirement, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path = fixture_root / "reports/combined_consistent.md"
        report_path.write_text(
            report_path.read_text(encoding="utf-8") + "\n## 测试维度扫描\n\n" + "\n".join(f"- {item}" for item in DIMENSIONS) + "\n",
            encoding="utf-8",
        )
        workbook = self.directory / "case.xmind"
        convert_file(fixture_root / "valid_case_xmind.md", workbook)
        self.manifest = self.directory / "manifest.json"
        source_files = ["tests/fixtures/sources/requirement.md"]
        manifest_data = {
            "schema_version": "2.0.0", "artifact_id": "QA-TEST-001", "source_type": "unit",
            "source_id": "REQ-1", "source_files": source_files, "source_snapshot_path": None,
            "source_hash_algorithm": "sha256", "source_hash": stable_source_hash(self.root, source_files),
            "requirement_id": "REQ-1", "commit_range": "abc123..def456",
            "rule_version": read_rule_version(self.root), "generated_at": "2026-07-20 00:00:00",
            "generated_timezone": "Asia/Shanghai", "report_mode": "combined",
            "report_path": "tests/fixtures/reports/combined_consistent.md",
            "analysis_model_paths": ["tests/fixtures/models/requirement-analysis.json", "tests/fixtures/models/diff-impact.json"],
            "risk_matrix_path": "tests/fixtures/models/risk-coverage-matrix.json",
            "testcase_model_path": "tests/fixtures/models/testcase-model.json",
            "xmind_md_path": "tests/fixtures/valid_case_xmind.md",
            "xmind_path": self.directory.relative_to(self.root).as_posix() + "/case.xmind",
            "draft_report_path": None, "draft_risk_matrix_path": None,
            "draft_testcase_model_path": None, "draft_xmind_md_path": None,
            "case_count": 2, "p0_count": 1, "p0_risk_count": 1, "p0_case_count": 1,
            "pending_count": 0, "blocking_pending_count": 0, "nonblocking_pending_count": 0,
            "suggested_pending_count": 0, "validation_status": "passed", "relation": "新增",
            "supersedes": None, "failure_reason": None, "pending_reason": None,
        }
        self.manifest.write_text(
            json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.index = self.testcases / "index.md"

    def tearDown(self):
        self.temp.cleanup()

    def load_manifest(self) -> dict:
        return json.loads(self.manifest.read_text(encoding="utf-8"))

    def write_manifest(self, data: dict) -> None:
        self.manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def row(self, data: dict | None = None, manifest_value: str | None = None) -> str:
        data = data or self.load_manifest()
        relative = manifest_value or self.manifest.relative_to(self.root).as_posix()
        return build_row(data, Path(relative)) + "\n"

    def write_index(self, *rows: str) -> None:
        self.index.write_text(HEADER + "".join(rows), encoding="utf-8")

    def mutate_cell(self, row: str, field: str, value: str) -> str:
        header = _cells(HEADER.splitlines()[2])
        cells = _cells(row)
        cells[header.index(field)] = value
        return "| " + " | ".join(cells) + " |\n"

    def test_complete_passed_manifest_is_uniquely_registered(self):
        self.write_index(self.row())
        self.assertEqual([], validate_index(self.index))

    def test_passed_manifest_missing_from_index_fails(self):
        self.write_index()
        self.assertTrue(any("PASSED_MANIFEST_NOT_UNIQUELY_INDEXED" in error for error in validate_index(self.index)))

    def test_invalid_passed_manifest_fails_even_when_indexed(self):
        data = self.load_manifest()
        data["case_count"] += 1
        self.write_manifest(data)
        self.write_index(self.row(data))
        self.assertTrue(any("Manifest 校验失败" in error for error in validate_index(self.index)))

    def test_every_core_index_field_must_match_manifest(self):
        mismatches = {
            "生成时间": "2020-01-01 00:00:00", "来源类型": "wrong", "分析范围": "WRONG",
            "规则版本": "9.9.9", "版本关系": "补充", "报告": "testcases/wrong.md",
            "XMind Markdown": "testcases/wrong.xmind.md", "Workbook": "testcases/wrong.xmind",
        }
        for field, value in mismatches.items():
            with self.subTest(field=field):
                self.write_index(self.mutate_cell(self.row(), field, value))
                self.assertTrue(any("INDEX_MANIFEST_FIELD_MISMATCH" in error for error in validate_index(self.index)))

    def test_note_counts_and_artifact_id_must_match_manifest(self):
        for token, replacement in (
            ("artifact_id=QA-TEST-001", "artifact_id=WRONG"),
            ("cases=2", "cases=99"), ("P0_risks=1", "P0_risks=99"),
            ("P0_cases=1", "P0_cases=99"), ("pending=0", "pending=99"),
        ):
            with self.subTest(token=token):
                self.write_index(self.row().replace(token, replacement))
                self.assertTrue(any("INDEX_MANIFEST_NOTE_MISMATCH" in error for error in validate_index(self.index)))

    def test_duplicate_artifact_id_and_manifest_path_fail(self):
        row = self.row()
        self.write_index(row, row)
        errors = validate_index(self.index)
        self.assertTrue(any("artifact_id 重复" in error for error in errors))
        self.assertTrue(any("Manifest 路径重复" in error for error in errors))

    def test_pending_manifest_does_not_require_registration(self):
        data = self.load_manifest()
        data["validation_status"] = "pending"
        self.write_manifest(data)
        self.write_index()
        self.assertEqual([], validate_index(self.index))

    def test_failed_manifest_cannot_masquerade_as_validated(self):
        data = self.load_manifest()
        data["validation_status"] = "failed"
        self.write_manifest(data)
        row = self.mutate_cell(self.row(data), "校验状态", "已校验")
        self.write_index(row)
        errors = validate_index(self.index)
        self.assertTrue(any("Manifest 校验失败" in error or "validation_status" in error for error in errors))

    def test_missing_registered_manifest_fails(self):
        row = self.row(manifest_value="testcases/missing/manifest.json")
        self.write_index(row)
        self.assertTrue(any("文件不存在" in error for error in validate_index(self.index)))

    def test_windows_and_posix_manifest_paths_compare_equally(self):
        row = self.row().replace(
            "testcases/generic-contract-20260720/manifest.json",
            r"testcases\generic-contract-20260720\manifest.json",
        )
        self.write_index(row)
        self.assertEqual([], validate_index(self.index))

    def test_drafts_and_test_fixtures_are_not_production_registration_targets(self):
        drafts = self.testcases / "drafts/example"
        fixtures = self.root / "tests/fixtures/testcases/example"
        drafts.mkdir(parents=True)
        fixtures.mkdir(parents=True)
        shutil.copy2(self.manifest, drafts / "manifest.json")
        shutil.copy2(self.manifest, fixtures / "manifest.json")
        self.write_index(self.row())
        self.assertEqual([], validate_index(self.index))


    def test_cells_preserves_windows_paths_and_only_unescapes_markdown_tokens(self):
        row = (
            r"| value | testcases\clearance-permission-20260718\manifest.json "
            r"| escaped\|pipe | doubled\\slash |"
        )

        cells = _cells(row)

        self.assertEqual("value", cells[0])
        self.assertEqual(
            r"testcases\clearance-permission-20260718\manifest.json",
            cells[1],
        )
        self.assertEqual("escaped|pipe", cells[2])
        self.assertEqual(r"doubled\slash", cells[3])


if __name__ == "__main__":
    unittest.main()
