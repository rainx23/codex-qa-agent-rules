from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from qa_contracts import load_json, summarize_confirmations  # noqa: E402
from render_delivery_summary import (  # noqa: E402
    DeliverySummaryError,
    SECTION_ORDER,
    _assert_counts,
    _repo_path,
    render_delivery_summary,
)
from validate_delivery_summary import validate_summary  # noqa: E402


PASSED_MANIFEST = ROOT / "testcases/clearance-permission-20260718-v2/manifest.json"


class DeliverySummaryPassedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = render_delivery_summary(PASSED_MANIFEST)
        cls.manifest = load_json(PASSED_MANIFEST)

    def test_passed_has_all_fixed_sections(self):
        for section in SECTION_ORDER:
            self.assertIn(f"## {section}", self.text)

    def test_passed_section_order_is_stable(self):
        positions = [self.text.index(f"## {section}") for section in SECTION_ORDER]
        self.assertEqual(sorted(positions), positions)

    def test_passed_xmind_is_first_primary_file(self):
        body = self.text.split("## 主要交付文件", 1)[1].split("## 追踪和校验文件", 1)[0]
        first = next(line for line in body.splitlines() if line.startswith("- "))
        self.assertIn(self.manifest["xmind_path"], first)

    def test_passed_has_formal_xmind_markdown(self):
        self.assertIn(f"`{self.manifest['xmind_md_path']}`", self.text)

    def test_passed_has_formal_report(self):
        self.assertIn(f"`{self.manifest['report_path']}`", self.text)

    def test_passed_has_requirement_model(self):
        self.assertIn(f"`{self.manifest['analysis_model_paths'][0]}`", self.text)

    def test_passed_has_risk_matrix(self):
        self.assertIn(f"`{self.manifest['risk_matrix_path']}`", self.text)

    def test_passed_has_testcase_model(self):
        self.assertIn(f"`{self.manifest['testcase_model_path']}`", self.text)

    def test_passed_has_manifest_and_index_purposes(self):
        self.assertIn("保存产物路径、版本、来源 Hash、数量和交付状态", self.text)
        self.assertIn("查询正式历史测试产物", self.text)

    def test_passed_has_no_draft_paths(self):
        self.assertNotRegex(self.text, r"`[^`]*(?:^|/)drafts?/[^`]*`")

    def test_resolved_confirmation_is_displayed(self):
        self.assertIn("`CONF-001`", self.text)
        self.assertIn("状态：已解决", self.text)

    def test_confirmation_groups_are_separate(self):
        for heading in ("### 阻塞确认点", "### 非阻塞确认点", "### 建议确认点"):
            self.assertIn(heading, self.text)

    def test_confirmation_empty_groups_say_none(self):
        self.assertGreaterEqual(self.text.count("- 无"), 1)

    def test_validation_and_sql_status_are_separate(self):
        self.assertIn("- validation_status：passed", self.text)
        self.assertIn("- sql_status：blocked", self.text)

    def test_sql_blocked_does_not_make_design_pending(self):
        self.assertIn("- 测试用例设计：已完成", self.text)
        self.assertNotIn("- 测试用例设计：待确认", self.text)

    def test_case_count_comes_from_manifest(self):
        self.assertIn(f"- TC 数量：{self.manifest['case_count']}", self.text)

    def test_p0_case_count_comes_from_manifest(self):
        self.assertIn(f"- P0 TC 数量：{self.manifest['p0_case_count']}", self.text)

    def test_branch_count_is_not_case_count(self):
        self.assertIn(f"- 入口分支数量：{self.manifest['branch_count']}", self.text)
        self.assertNotEqual(self.manifest["case_count"], self.manifest["branch_count"])

    def test_condition_counts_come_from_models(self):
        self.assertIn("- 条件组合总数：112", self.text)
        self.assertIn("- 行为覆盖组合数：112", self.text)

    def test_risk_counts_come_from_models(self):
        self.assertIn("- Risk 总数：15", self.text)
        self.assertIn("- P0 Risk 数量：12", self.text)

    def test_version_relation_and_supersedes_are_displayed(self):
        self.assertIn("- 版本关系：替代", self.text)
        self.assertIn(f"- supersedes：{self.manifest['supersedes']}", self.text)

    def test_paths_use_forward_slashes(self):
        code_paths = re.findall(r"`([^`]+)`", self.text)
        self.assertTrue(code_paths)
        self.assertTrue(all("\\" not in path for path in code_paths))

    def test_output_has_no_ansi(self):
        self.assertNotRegex(self.text, r"\x1b\[")

    def test_actual_validations_are_reported(self):
        for label in ("Requirement Model", "Risk Matrix", "Testcase Model", "XMind Markdown", "XMind Workbook 完整树"):
            self.assertIn(f"- {label}：通过", self.text)
        self.assertIn("- Manifest：通过", self.text)
        self.assertIn("- Index：通过", self.text)

    def test_unrun_validations_are_not_invented(self):
        self.assertIn("- 全量单元测试：本轮未运行", self.text)
        self.assertIn("- git diff --check：本轮未运行", self.text)

    def test_real_execution_is_explicitly_not_run(self):
        self.assertIn("- 真实页面/接口/SQL：未执行", self.text)
        self.assertIn("- 未执行数据库 SQL", self.text)

    def test_summary_validator_accepts_exact_output(self):
        self.assertEqual([], validate_summary(self.text, PASSED_MANIFEST))

    def test_summary_validator_rejects_changed_count(self):
        changed = self.text.replace("- TC 数量：23", "- TC 数量：999")
        self.assertTrue(validate_summary(changed, PASSED_MANIFEST))

    def test_summary_validator_rejects_missing_section(self):
        changed = self.text.replace("## 未执行事项", "## 其他")
        self.assertTrue(any("未执行事项" in error for error in validate_summary(changed, PASSED_MANIFEST)))

    def test_summary_validator_rejects_vague_phrase(self):
        changed = self.text + "\n相关文件\n"
        self.assertTrue(any("模糊" in error for error in validate_summary(changed, PASSED_MANIFEST)))


class DeliverySummaryStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_entries = {path.name for path in (ROOT / "tests/fixtures/drafts").iterdir()}
        self.temp = tempfile.TemporaryDirectory(prefix="delivery-summary-")
        self.workspace = Path(self.temp.name) / "workspace"
        self.workspace.mkdir()
        (self.workspace / "RULE_VERSION").write_text((ROOT / "RULE_VERSION").read_text(encoding="utf-8-sig"), encoding="utf-8")
        (self.workspace / "AGENTS.md").write_text("temporary test workspace\n", encoding="utf-8")
        self.directory = self.workspace / "tests/fixtures/drafts/case"
        self.directory.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()
        self.assertEqual(self.fixture_entries, {path.name for path in (ROOT / "tests/fixtures/drafts").iterdir()})

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.workspace).as_posix()

    def _write_json(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def pending_manifest(self) -> Path:
        manifest = copy.deepcopy(load_json(PASSED_MANIFEST))
        requirement = load_json(ROOT / manifest["analysis_model_paths"][0])
        requirement["confirmation_points"].append({
            "confirmation_id": "CONF-003", "severity": "blocking", "statement": "确认核心入口",
            "fact_ids": ["FACT-001"], "status": "pending", "resolution_evidence_references": [],
            "decision_evidence": [], "resolution": None, "resolved_at": None, "skip_reason": None,
        })
        model_path = self.directory / "requirement-analysis.json"
        self._write_json(model_path, requirement)
        copies = {
            "draft_report_path": "requirement-analysis.md",
            "draft_risk_matrix_path": "risk-coverage-matrix.json",
            "draft_testcase_model_path": "testcase-model.json",
            "draft_xmind_md_path": "clearance-permission.xmind.md",
        }
        source_fields = {
            "draft_report_path": manifest["report_path"],
            "draft_risk_matrix_path": manifest["risk_matrix_path"],
            "draft_testcase_model_path": manifest["testcase_model_path"],
            "draft_xmind_md_path": manifest["xmind_md_path"],
        }
        for field, name in copies.items():
            (self.directory / name).write_bytes((ROOT / source_fields[field]).read_bytes())
            manifest[field] = self._relative(self.directory / name)
        for field in ("report_path", "risk_matrix_path", "testcase_model_path", "xmind_md_path", "xmind_path"):
            manifest[field] = None
        manifest.update({
            "analysis_model_paths": [self._relative(model_path)], "validation_status": "pending",
            "pending_reason": "CONF-003 未解决，正式 XMind 未生成", "failure_reason": None,
            "pending_count": 2, "blocking_pending_count": 1,
            "nonblocking_pending_count": 1, "suggested_pending_count": 0,
        })
        path = self.directory / "manifest.json"
        self._write_json(path, manifest)
        return path

    def failed_manifest(self) -> Path:
        manifest = copy.deepcopy(load_json(PASSED_MANIFEST))
        for field in (
            "report_path", "risk_matrix_path", "testcase_model_path", "xmind_md_path", "xmind_path",
            "draft_report_path", "draft_risk_matrix_path", "draft_testcase_model_path", "draft_xmind_md_path",
        ):
            manifest[field] = None
        manifest.update({
            "analysis_model_paths": [], "validation_status": "failed", "failure_reason": "Manifest 路径复验失败",
            "pending_reason": None, "case_count": 0, "p0_count": 0, "p0_case_count": 0,
            "p0_risk_count": 0, "branch_count": 0, "pending_count": 0,
            "blocking_pending_count": 0, "nonblocking_pending_count": 0, "suggested_pending_count": 0,
        })
        path = self.directory / "manifest.json"
        self._write_json(path, manifest)
        return path

    def test_pending_displays_blocking_confirmation(self):
        text = render_delivery_summary(self.pending_manifest())
        self.assertIn("`CONF-003`", text)
        self.assertIn("状态：待确认", text)

    def test_runtime_directory_is_in_system_temp_not_repository_fixtures(self):
        self.assertFalse(self.directory.is_relative_to(ROOT / "tests/fixtures"))
        self.assertTrue(self.directory.is_relative_to(Path(tempfile.gettempdir())))

    def test_fixed_fixture_is_preserved(self):
        self.assertTrue((ROOT / "tests/fixtures/drafts/delivery-summary-wjtkg1i6/manifest.json").is_file())

    def test_exception_cleanup_leaves_no_repository_fixture_residue(self):
        before = {path.name for path in (ROOT / "tests/fixtures/drafts").iterdir()}
        with self.assertRaises(RuntimeError):
            with tempfile.TemporaryDirectory(prefix="delivery-summary-exception-") as directory:
                Path(directory, "partial.json").write_text("{}", encoding="utf-8")
                raise RuntimeError("expected")
        self.assertEqual(before, {path.name for path in (ROOT / "tests/fixtures/drafts").iterdir()})

    def test_pending_displays_draft_files(self):
        text = render_delivery_summary(self.pending_manifest())
        self.assertIn("草稿需求分析报告", text)
        self.assertIn("草稿测试用例模型", text)

    def test_pending_marks_formal_xmind_not_generated(self):
        text = render_delivery_summary(self.pending_manifest())
        self.assertIn("- 正式 XMind：未生成", text)
        self.assertIn("被阻塞", text)

    def test_pending_does_not_claim_formal_delivery(self):
        text = render_delivery_summary(self.pending_manifest())
        self.assertNotIn("正式交付完成", text)
        self.assertNotIn("完整交付", text)
        self.assertIn("下一步：请回答上述 blocking Confirmation", text)

    def test_pending_does_not_register_index(self):
        text = render_delivery_summary(self.pending_manifest())
        self.assertIn("- 全局测试产物索引：未生成", text)
        self.assertIn("状态：未登记", text)

    def test_failed_displays_failure_reason(self):
        text = render_delivery_summary(self.failed_manifest())
        self.assertIn("failure_reason：Manifest 路径复验失败", text)
        self.assertIn("失败校验：Manifest 路径复验失败", text)

    def test_failed_does_not_claim_validation_passed(self):
        text = render_delivery_summary(self.failed_manifest())
        self.assertNotIn("校验通过", text)
        self.assertIn("- Manifest：", text)

    def test_no_confirmations_explicitly_says_none(self):
        text = render_delivery_summary(self.failed_manifest())
        self.assertGreaterEqual(text.count("- 无"), 3)

    def test_windows_path_is_normalized(self):
        self.assertEqual("testcases/example/manifest.json", _repo_path(r"testcases\example\manifest.json", field="path"))

    def test_absolute_windows_path_is_rejected(self):
        with self.assertRaises(DeliverySummaryError):
            _repo_path(r"C:\temp\manifest.json", field="path")

    def test_parent_traversal_is_rejected(self):
        with self.assertRaises(DeliverySummaryError):
            _repo_path("../manifest.json", field="path")

    def test_confirmation_count_mismatch_is_rejected(self):
        manifest = load_json(PASSED_MANIFEST)
        requirement = load_json(ROOT / manifest["analysis_model_paths"][0])
        changed = copy.deepcopy(manifest)
        changed["pending_count"] = 99
        with self.assertRaises(DeliverySummaryError):
            _assert_counts(changed, requirement, None, None)

    def test_case_count_mismatch_is_rejected(self):
        manifest = load_json(PASSED_MANIFEST)
        testcase = load_json(ROOT / manifest["testcase_model_path"])
        changed = copy.deepcopy(manifest)
        changed["case_count"] += 1
        with self.assertRaises(DeliverySummaryError):
            _assert_counts(changed, None, None, testcase)

    def test_branch_count_mismatch_is_rejected(self):
        manifest = load_json(PASSED_MANIFEST)
        testcase = load_json(ROOT / manifest["testcase_model_path"])
        changed = copy.deepcopy(manifest)
        changed["branch_count"] += 1
        with self.assertRaises(DeliverySummaryError):
            _assert_counts(changed, None, None, testcase)

    def test_p0_risk_count_mismatch_is_rejected(self):
        manifest = load_json(PASSED_MANIFEST)
        risk = load_json(ROOT / manifest["risk_matrix_path"])
        changed = copy.deepcopy(manifest)
        changed["p0_risk_count"] += 1
        with self.assertRaises(DeliverySummaryError):
            _assert_counts(changed, None, risk, None)

    def test_cli_help_succeeds(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "render_delivery_summary.py"), "--help"],
            cwd=ROOT, text=True, encoding="utf-8", capture_output=True,
        )
        self.assertEqual(0, result.returncode)
        self.assertIn("--output", result.stdout)

    def test_output_option_writes_utf8_without_ansi(self):
        output = self.directory / "summary.md"
        result = subprocess.run([
            sys.executable, str(SCRIPTS / "render_delivery_summary.py"),
            "--manifest", str(PASSED_MANIFEST), "--output", str(output),
        ], cwd=ROOT, capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr.decode("utf-8", errors="replace"))
        content = output.read_text(encoding="utf-8")
        self.assertIn("## 处理结果", content)
        self.assertNotRegex(content, r"\x1b\[")


if __name__ == "__main__":
    unittest.main()
