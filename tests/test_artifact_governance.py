from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_testcase_index import migrate_index_text, update
from md_to_xmind import convert_file
from qa_contracts import read_rule_version, stable_source_hash
from repair_text_encoding import merge_reference_index, repair_text
from validate_manifest import validate_manifest_file
from validate_skill_contracts import validate_skill


class ArtifactGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "testcases", prefix=".contract-test-")
        self.directory = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _copy(self, source: Path, name: str) -> Path:
        target = self.directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return target

    def _relative(self, path: Path) -> str:
        return path.relative_to(ROOT).as_posix()

    def make_passed_manifest(self) -> tuple[Path, dict]:
        report = self._copy(ROOT / "tests/fixtures/reports/combined_consistent.md", "report.md")
        markdown = self._copy(ROOT / "tests/fixtures/valid_case_xmind.md", "case_xmind.md")
        source = self._copy(ROOT / "tests/fixtures/sources/requirement.md", "source.md")
        requirement = self._copy(ROOT / "tests/fixtures/models/requirement-analysis.json", "requirement-analysis.json")
        diff = self._copy(ROOT / "tests/fixtures/models/diff-impact.json", "diff-impact.json")
        risk = self._copy(ROOT / "tests/fixtures/models/risk-coverage-matrix.json", "risk-coverage-matrix.json")
        testcase = self._copy(ROOT / "tests/fixtures/models/testcase-model.json", "testcase-model.json")
        workbook = self.directory / "case_workbook.xmind"
        convert_file(markdown, workbook)
        source_files = [self._relative(source)]
        data = {
            "schema_version": "2.0.0",
            "artifact_id": "QA-TEST-001",
            "source_type": "unit",
            "source_id": "REQ-1",
            "source_files": source_files,
            "source_snapshot_path": None,
            "source_hash_algorithm": "sha256",
            "source_hash": stable_source_hash(ROOT, source_files),
            "requirement_id": "REQ-1",
            "commit_range": "abc123..def456",
            "rule_version": read_rule_version(ROOT),
            "generated_at": "2026-07-15 00:00:00",
            "generated_timezone": "Asia/Shanghai",
            "report_mode": "combined",
            "report_path": self._relative(report),
            "analysis_model_paths": [self._relative(requirement), self._relative(diff)],
            "risk_matrix_path": self._relative(risk),
            "testcase_model_path": self._relative(testcase),
            "xmind_md_path": self._relative(markdown),
            "xmind_path": self._relative(workbook),
            "case_count": 2,
            "p0_count": 1,
            "p0_risk_count": 1,
            "p0_case_count": 1,
            "pending_count": 0,
            "blocking_pending_count": 0,
            "nonblocking_pending_count": 0,
            "suggested_pending_count": 0,
            "validation_status": "passed",
            "relation": "新增",
            "supersedes": None,
            "failure_reason": None,
            "pending_reason": None,
        }
        manifest = self.directory / "manifest.json"
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest, data

    def errors_for(self, manifest: Path, data: dict) -> list[str]:
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return validate_manifest_file(manifest)[1]

    def test_manifest_example_is_valid_pending(self):
        _, errors = validate_manifest_file(ROOT / "testcases/manifest.example.json")
        self.assertEqual([], errors)

    def test_passed_manifest_revalidates_every_artifact(self):
        manifest, _ = self.make_passed_manifest()
        self.assertEqual([], validate_manifest_file(manifest)[1])

    def test_source_hash_format_can_pass_while_content_mismatch_fails(self):
        manifest, data = self.make_passed_manifest()
        data["source_hash"] = "sha256:" + "1" * 64
        self.assertTrue(any("来源内容不一致" in error for error in self.errors_for(manifest, data)))

    def test_pending_and_p0_counts_are_independent_and_real(self):
        manifest, data = self.make_passed_manifest()
        for field in ("pending_count", "p0_risk_count", "p0_case_count"):
            changed = copy.deepcopy(data)
            changed[field] += 1
            if field == "p0_case_count":
                changed["p0_count"] += 1
            errors = self.errors_for(manifest, changed)
            self.assertTrue(any(field in error or "待确认点计数" in error for error in errors), field)

    def test_rule_version_and_generated_at_are_strict(self):
        manifest, data = self.make_passed_manifest()
        changed = copy.deepcopy(data)
        changed["rule_version"] = "9.9.9"
        self.assertTrue(any("RULE_VERSION" in error for error in self.errors_for(manifest, changed)))
        changed = copy.deepcopy(data)
        changed["generated_at"] = "2026-07-15"
        self.assertTrue(any("YYYY-MM-DD HH:mm:ss" in error for error in self.errors_for(manifest, changed)))

    def test_supersedes_must_exist_not_self_and_not_cycle(self):
        manifest, data = self.make_passed_manifest()
        for target, token in (("MISSING", "不存在"), (data["artifact_id"], "自身")):
            changed = copy.deepcopy(data)
            changed.update(relation="替代", supersedes=target)
            self.assertTrue(any(token in error for error in self.errors_for(manifest, changed)))
        old = self.directory / "old-manifest.json"
        old.write_text(json.dumps({"artifact_id": "QA-OLD", "supersedes": data["artifact_id"]}), encoding="utf-8")
        changed = copy.deepcopy(data)
        changed.update(relation="替代", supersedes="QA-OLD")
        self.assertTrue(any("循环" in error for error in self.errors_for(manifest, changed)))

    def test_passed_path_escape_and_broken_workbook_fail(self):
        manifest, data = self.make_passed_manifest()
        changed = copy.deepcopy(data)
        changed["report_path"] = "../outside.md"
        self.assertTrue(any("../" in error for error in self.errors_for(manifest, changed)))
        workbook = ROOT / data["xmind_path"]
        workbook.write_bytes(b"broken")
        self.assertTrue(any("产物复验失败" in error for error in self.errors_for(manifest, data)))

    def test_model_and_markdown_count_mismatch_fails(self):
        manifest, data = self.make_passed_manifest()
        changed = copy.deepcopy(data)
        changed["case_count"] = 3
        self.assertTrue(any("case_count" in error for error in self.errors_for(manifest, changed)))

    def test_failed_requires_reason_pending_allows_missing_workbook(self):
        example = json.loads((ROOT / "testcases/manifest.example.json").read_text(encoding="utf-8"))
        manifest = self.directory / "state-manifest.json"
        failed = copy.deepcopy(example)
        failed.update(validation_status="failed", failure_reason=None, pending_reason=None)
        self.assertTrue(any("failure_reason" in error for error in self.errors_for(manifest, failed)))
        pending = copy.deepcopy(example)
        pending["xmind_path"] = None
        self.assertEqual([], self.errors_for(manifest, pending))

    def test_passed_zero_hash_fails(self):
        manifest, data = self.make_passed_manifest()
        data["source_hash"] = "sha256:" + "0" * 64
        self.assertTrue(any("全零" in error for error in self.errors_for(manifest, data)))

    def test_old_manifest_gets_migration_message(self):
        manifest = self.directory / "legacy.json"
        manifest.write_text('{"artifact_id":"OLD"}', encoding="utf-8")
        self.assertTrue(any("迁移版本" in error for error in validate_manifest_file(manifest)[1]))

    def test_index_status_and_legacy_metadata_are_separate(self):
        old = "# 测试分析输出索引\n\n| 生成时间 | 来源类型 | 分析范围 | 版本状态 | 分析报告路径 | XMind Markdown 路径 | XMind Workbook 路径 | 备注 |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n| 2026-01-01 00:00:00 | 禅道需求 | 范围 | 已确认 | report.md | case.md | case.xmind | 旧记录 |\n"
        migrated = migrate_index_text(old)
        self.assertIn("规则版本 | 版本关系 | 校验状态", migrated)
        self.assertIn("legacy_rule_version=unknown", migrated)
        self.assertIn("未按当前规则校验", migrated)

        manifest, _ = self.make_passed_manifest()
        index = self.directory / "index.md"
        update(index, manifest)
        update(index, manifest)
        text = index.read_text(encoding="utf-8")
        self.assertIn("已校验", text)
        self.assertEqual(1, text.count("artifact_id=QA-TEST-001"))

    def test_encoding_repair_is_reversible_and_cell_safe(self):
        text = "# 娴嬭瘯鍒嗘瀽杈撳嚭绱㈠紩\n| 禅道需求 | 绂呴亾闇€姹?|\n"
        repaired = repair_text(text)
        self.assertIn("测试分析输出索引", repaired)
        reference = "# 测试分析输出索引\n| 生成时间 | 来源类型 |\n| 2026-01-01 00:00:00 | 禅道需求 |\n"
        broken = "# 娴嬭瘯鍒嗘瀽杈撳嚭绱㈠紩\n| 鐢熸垚鏃堕棿 | 鏉ユ簮绫诲瀷 |\n| 2026-01-01 00:00:00 | 绂呴亾闇€姹?|\n"
        self.assertEqual(reference, merge_reference_index(broken, reference))

    def test_all_skills_have_valid_contracts(self):
        for skill in (ROOT / "skills").iterdir():
            if skill.is_dir():
                self.assertEqual([], validate_skill(skill), skill.name)


if __name__ == "__main__":
    unittest.main()
