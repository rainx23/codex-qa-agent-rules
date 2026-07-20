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
from qa_contracts import DIMENSIONS, read_rule_version, stable_source_hash
from repair_text_encoding import merge_reference_index, repair_text
from validate_manifest import artifact_workspace_root, resolve_safe_path, validate_manifest_file
from validate_models import _evidence_root
from validate_skill_contracts import validate_skill


class ArtifactGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "testcases", prefix=".contract-test-")
        self.directory = Path(self.temp.name)
        self.pending_temp = tempfile.TemporaryDirectory(dir=ROOT / "tests/fixtures/drafts", prefix="contract-test-")
        self.pending_directory = Path(self.pending_temp.name)

    def tearDown(self):
        self.pending_temp.cleanup()
        self.temp.cleanup()

    def _copy(self, source: Path, name: str) -> Path:
        target = self.directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return target

    def _copy_pending(self, source: Path, name: str) -> Path:
        target = self.pending_directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return target

    def _relative(self, path: Path) -> str:
        return path.relative_to(ROOT).as_posix()

    def _add_current_dimension_contract(self, requirement: Path, report: Path) -> None:
        data = json.loads(requirement.read_text(encoding="utf-8"))
        data["test_dimension_assessment"] = []
        for dimension in DIMENSIONS:
            covered = dimension in {"功能测试", "数据测试"}
            suffix = "001" if dimension == "功能测试" else "002"
            data["test_dimension_assessment"].append({
                "dimension": dimension,
                "status": "covered" if covered else "not_applicable",
                "reason": "通用 Fixture 已覆盖" if covered else "通用 Fixture 范围不涉及该维度",
                "fact_ids": [f"FACT-{suffix}" if covered else "FACT-001"],
                "risk_ids": [f"RISK-{suffix}"] if covered else [],
                "confirmation_ids": [],
                "testcase_ids": [f"TC{suffix}"] if covered else [],
                "evidence_references": [],
            })
        requirement.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        table = "\n## 测试维度扫描\n\n| 维度 | 状态 |\n| --- | --- |\n" + "".join(
            f"| {dimension} | {'covered' if dimension in {'功能测试', '数据测试'} else 'not_applicable'} |\n"
            for dimension in DIMENSIONS
        )
        report.write_text(report.read_text(encoding="utf-8") + table, encoding="utf-8")

    def make_passed_manifest(self) -> tuple[Path, dict]:
        report = self._copy(ROOT / "tests/fixtures/reports/combined_consistent.md", "report.md")
        markdown = self._copy(ROOT / "tests/fixtures/valid_case_xmind.md", "case_xmind.md")
        source = self._copy(ROOT / "tests/fixtures/sources/requirement.md", "source.md")
        requirement = self._copy(ROOT / "tests/fixtures/models/requirement-analysis.json", "requirement-analysis.json")
        diff = self._copy(ROOT / "tests/fixtures/models/diff-impact.json", "diff-impact.json")
        risk = self._copy(ROOT / "tests/fixtures/models/risk-coverage-matrix.json", "risk-coverage-matrix.json")
        testcase = self._copy(ROOT / "tests/fixtures/models/testcase-model.json", "testcase-model.json")
        self._add_current_dimension_contract(requirement, report)
        workbook = self.directory / "case_workbook.xmind"
        workbook.unlink(missing_ok=True)
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
            "draft_report_path": None,
            "draft_risk_matrix_path": None,
            "draft_testcase_model_path": None,
            "draft_xmind_md_path": None,
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

    def make_pending_manifest(self) -> tuple[Path, dict, Path, Path]:
        report = self._copy_pending(ROOT / "tests/fixtures/reports/combined_consistent.md", "pending-report.md")
        report.write_text(
            report.read_text(encoding="utf-8").replace(
                "- 无。",
                "- [CONF-001][FACT-003] severity=blocking status=pending：请确认收益率分母。",
            ),
            encoding="utf-8",
        )
        requirement = self._copy_pending(ROOT / "tests/fixtures/models/requirement-analysis.json", "requirement-analysis.json")
        requirement_data = json.loads(requirement.read_text(encoding="utf-8"))
        missing = copy.deepcopy(requirement_data["facts"][0])
        missing.update(
            fact_id="FACT-003", category="missing", statement="收益率分母尚未确认",
            handling="等待产品确认",
        )
        requirement_data["facts"].append(missing)
        requirement_data["confirmation_points"] = [{
            "confirmation_id": "CONF-001", "severity": "blocking",
            "statement": "请确认收益率分母", "fact_ids": ["FACT-003"], "status": "pending",
        }]
        requirement.write_text(json.dumps(requirement_data, ensure_ascii=False, indent=2), encoding="utf-8")
        diff = self._copy_pending(ROOT / "tests/fixtures/models/diff-impact.json", "diff-impact.json")
        risk = self._copy_pending(ROOT / "tests/fixtures/models/risk-coverage-matrix.json", "pending-risk.json")
        testcase = self._copy_pending(ROOT / "tests/fixtures/models/testcase-model.json", "pending-testcase.json")
        data = {
            "schema_version": "2.0.0", "artifact_id": "QA-PENDING-001",
            "source_type": "unit", "source_id": "REQ-1", "source_files": [],
            "source_snapshot_path": None, "source_hash_algorithm": "sha256",
            "source_hash": "sha256:" + "0" * 64, "requirement_id": "REQ-1", "commit_range": None,
            "rule_version": read_rule_version(ROOT), "generated_at": "2026-07-17 12:00:00",
            "generated_timezone": "Asia/Shanghai", "report_mode": "combined",
            "report_path": None,
            "analysis_model_paths": [self._relative(requirement), self._relative(diff)],
            "risk_matrix_path": None, "testcase_model_path": None, "xmind_md_path": None, "xmind_path": None,
            "draft_report_path": self._relative(report), "draft_risk_matrix_path": self._relative(risk),
            "draft_testcase_model_path": self._relative(testcase), "draft_xmind_md_path": None,
            "case_count": 2, "p0_count": 1, "p0_risk_count": 1, "p0_case_count": 1,
            "pending_count": 1, "blocking_pending_count": 1,
            "nonblocking_pending_count": 0, "suggested_pending_count": 0,
            "validation_status": "pending", "relation": "新增", "supersedes": None,
            "failure_reason": None, "pending_reason": "核心收益率分母待产品确认，确认前不生成 XMind Markdown。",
        }
        manifest = self.directory / "pending-manifest.json"
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest, data, requirement, report

    def errors_for(self, manifest: Path, data: dict) -> list[str]:
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return validate_manifest_file(manifest)[1]

    def test_manifest_example_is_valid_passed(self):
        _, errors = validate_manifest_file(ROOT / "testcases/manifest.example.json")
        self.assertTrue(any("TEST_DIMENSION_ASSESSMENT_REQUIRED" in error for error in errors), errors)

    def test_external_workspace_root_artifacts_and_evidence_resolve_locally(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            manifest = workspace / "delivery-manifest.json"
            artifact = workspace / "delivery-report.md"
            artifact.write_text("# report\n", encoding="utf-8")
            manifest.write_text("{}", encoding="utf-8")
            self.assertEqual(workspace.resolve(), artifact_workspace_root(manifest))
            resolved, error = resolve_safe_path(artifact.name, manifest)
            self.assertIsNone(error)
            self.assertEqual(artifact.resolve(), resolved)
            self.assertEqual(workspace.resolve(), _evidence_root(workspace / "requirement.json"))

    def test_passed_manifest_revalidates_every_artifact(self):
        manifest, _ = self.make_passed_manifest()
        self.assertEqual([], validate_manifest_file(manifest)[1])

    def test_real_passed_manifest_source_hash_survives_text_line_endings_and_bom(self):
        manifest, data = self.make_passed_manifest()
        source = ROOT / data["source_files"][0]
        normalized = source.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        for payload in (
            normalized.replace("\n", "\r\n").encode("utf-8"),
            normalized.replace("\n", "\r").encode("utf-8"),
            b"\xef\xbb\xbf" + normalized.encode("utf-8"),
        ):
            with self.subTest(prefix=payload[:3]):
                source.write_bytes(payload)
                self.assertEqual([], validate_manifest_file(manifest)[1])

    def test_passed_artifacts_allow_sql_blocked_as_an_independent_state(self):
        manifest, data = self.make_passed_manifest()
        data.update(sql_status="blocked", validation_sql=None, execution_evidence=None)
        self.assertEqual([], self.errors_for(manifest, data))

    def test_sql_blocked_rejects_fake_sql_or_execution_evidence(self):
        manifest, data = self.make_passed_manifest()
        data.update(sql_status="blocked", validation_sql="validation.sql", execution_evidence="not-run")
        errors = self.errors_for(manifest, data)
        self.assertTrue(any("validation_sql 必须为 null" in error for error in errors))
        self.assertTrue(any("execution_evidence 必须为 null" in error for error in errors))

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

    def test_pending_manifest_validates_drafts_without_workbook(self):
        manifest, _, _, _ = self.make_pending_manifest()
        self.assertEqual([], validate_manifest_file(manifest)[1])

    def test_pending_rejects_formal_paths_and_missing_reason(self):
        manifest, data, _, _ = self.make_pending_manifest()
        changed = copy.deepcopy(data)
        changed["xmind_path"] = "testcases/formal.xmind"
        self.assertTrue(any("xmind_path 必须为 null" in error for error in self.errors_for(manifest, changed)))
        changed = copy.deepcopy(data)
        changed["pending_reason"] = None
        self.assertTrue(any("pending_reason" in error for error in self.errors_for(manifest, changed)))

    def test_pending_rejects_missing_absolute_and_parent_draft_paths(self):
        manifest, data, _, _ = self.make_pending_manifest()
        for value, token in (
            ("tests/fixtures/drafts/not-found.md", "路径不存在"),
            (str((ROOT / "tests/fixtures/drafts/not-found.md").resolve()), "绝对路径"),
            ("tests/fixtures/drafts/../outside.md", "../"),
        ):
            changed = copy.deepcopy(data)
            changed["draft_report_path"] = value
            self.assertTrue(any(token in error for error in self.errors_for(manifest, changed)), value)

    def test_pending_rejects_invalid_requirement_and_count_mismatch(self):
        manifest, data, requirement, _ = self.make_pending_manifest()
        invalid = json.loads(requirement.read_text(encoding="utf-8"))
        invalid["confirmation_points"] = []
        requirement.write_text(json.dumps(invalid, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertTrue(any("核心缺失事实" in error for error in self.errors_for(manifest, data)))
        manifest, data, _, _ = self.make_pending_manifest()
        data["pending_count"] = 2
        self.assertTrue(any("Requirement Model 不一致" in error for error in self.errors_for(manifest, data)))

    def test_pending_rejects_report_confirmation_count_mismatch(self):
        manifest, data, _, report = self.make_pending_manifest()
        report.write_text(
            report.read_text(encoding="utf-8").replace(
                "- [CONF-001][FACT-003] severity=blocking status=pending：请确认收益率分母。",
                "- 无。",
            ),
            encoding="utf-8",
        )
        self.assertTrue(any("草稿报告待确认数量" in error for error in self.errors_for(manifest, data)))

    def test_passed_rejects_unresolved_skipped_and_missing_core_states(self):
        for state, token in (("pending", "unresolved blocking"), ("skipped", "skipped"), ("resolved", "missing/conflicting")):
            manifest, data = self.make_passed_manifest()
            requirement = ROOT / data["analysis_model_paths"][0]
            requirement_data = json.loads(requirement.read_text(encoding="utf-8"))
            missing = copy.deepcopy(requirement_data["facts"][0])
            missing.update(fact_id="FACT-003", category="missing", handling="等待确认")
            requirement_data["facts"].append(missing)
            point = {
                "confirmation_id": "CONF-001", "severity": "blocking", "statement": "确认核心口径",
                "fact_ids": ["FACT-003"], "status": state,
            }
            if state == "skipped":
                point.update(skip_reason="本轮跳过", decision_evidence=copy.deepcopy(missing["evidence_references"]))
            if state == "resolved":
                point.update(
                    resolution="已确认", resolution_evidence_references=copy.deepcopy(missing["evidence_references"]),
                    resolved_at="2026-07-17 12:00:00",
                )
            requirement_data["confirmation_points"] = [point]
            requirement.write_text(json.dumps(requirement_data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.assertTrue(any(token in error for error in self.errors_for(manifest, data)), state)

    def test_passed_allows_resolved_confirmation_with_updated_fact(self):
        manifest, data = self.make_passed_manifest()
        requirement = ROOT / data["analysis_model_paths"][0]
        requirement_data = json.loads(requirement.read_text(encoding="utf-8"))
        confirmed = copy.deepcopy(requirement_data["facts"][0])
        confirmed.update(fact_id="FACT-003", statement="收益率分母为期初资产")
        confirmed["affects_core_expectation"] = False
        requirement_data["facts"].append(confirmed)
        requirement_data["confirmation_points"] = [{
            "confirmation_id": "CONF-001", "severity": "blocking", "statement": "确认收益率分母",
            "fact_ids": ["FACT-003"], "status": "resolved", "resolution": "分母为期初资产",
            "resolution_evidence_references": copy.deepcopy(confirmed["evidence_references"]),
            "resolved_at": "2026-07-17 12:00:00",
        }]
        requirement.write_text(json.dumps(requirement_data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertEqual([], self.errors_for(manifest, data))

    def test_failed_requires_reason_and_cannot_replace_normal_pending(self):
        manifest, data, _, _ = self.make_pending_manifest()
        failed = copy.deepcopy(data)
        failed.update(validation_status="failed", failure_reason=None, pending_reason=None)
        self.assertTrue(any("failure_reason" in error for error in self.errors_for(manifest, failed)))
        failed["failure_reason"] = "等待业务确认"
        self.assertTrue(any("应使用 pending" in error for error in self.errors_for(manifest, failed)))

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
