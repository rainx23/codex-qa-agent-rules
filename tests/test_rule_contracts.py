from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_repository_mode import validate_mode


class RuleContractTests(unittest.TestCase):
    def test_all_mirrored_rule_assets_match(self):
        mode, errors = validate_mode(ROOT / "rules-repository.json")
        self.assertIn(mode, {"standalone", "integrated"})
        self.assertEqual([], errors)

    def test_profile_capabilities_are_preserved(self):
        web = (ROOT / "rules/profiles/web-ui.md").read_text(encoding="utf-8")
        sql = (ROOT / "rules/profiles/sql-data.md").read_text(encoding="utf-8")
        finance = (ROOT / "rules/profiles/finance-trading.md").read_text(encoding="utf-8")
        nonfunctional = (ROOT / "rules/profiles/nonfunctional.md").read_text(encoding="utf-8")
        for token in ("查询", "固定列", "拖动排序", "另存为", "快捷查询", "弹窗", "下钻", "导出"):
            self.assertIn(token, web)
        for token in ("聚合", "去重", "迁移", "回填", "分页稳定排序"):
            self.assertIn(token, sql)
        for token in ("金额", "舍入", "部分成交", "正式与模拟"):
            self.assertIn(token, finance)
        for token in ("消息重复", "最终一致性", "熔断", "夏令时"):
            self.assertIn(token, nonfunctional)

    def test_scenario_catalog_has_exact_20_required_scenarios(self):
        scenarios = json.loads((ROOT / "tests/fixtures/analysis_scenarios.json").read_text(encoding="utf-8"))
        self.assertEqual(list(range(1, 21)), [item["id"] for item in scenarios])
        self.assertEqual(20, len({item["name"] for item in scenarios}))

    def test_legacy_docs_are_pointers_not_duplicate_sources(self):
        for path in (ROOT / "docs/codex").glob("*.md"):
            if path.name == "rule-validation-checklist.md":
                continue
            text = path.read_text(encoding="utf-8")
            self.assertLess(len(text.splitlines()), 20, path.name)
            self.assertTrue("兼容" in text or "验收清单" in text, path.name)

    def test_report_contract_and_zentao_profile_are_routed(self):
        contract = ROOT / "rules/core/analysis-report-contract.md"
        zentao = ROOT / "rules/profiles/zentao.md"
        self.assertTrue(contract.is_file())
        self.assertTrue(zentao.is_file())
        for skill_name in ("qa-requirement-analysis", "qa-diff-impact-analysis", "qa-artifact-validation"):
            text = (ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("analysis-report-contract.md", text)
        requirement_skill = (ROOT / "skills/qa-requirement-analysis/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("profiles/zentao.md", requirement_skill)

    def test_readme_links_and_real_inventory(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", readme):
            target = match.group(1).split("#", 1)[0]
            if not target or "://" in target:
                continue
            self.assertTrue((ROOT / target).exists(), target)
        for skill in sorted(path.name for path in (ROOT / "skills").iterdir() if path.is_dir()):
            self.assertIn(skill, readme)
        for profile in sorted(path.name for path in (ROOT / "rules/profiles").glob("*.md")):
            self.assertIn(profile, readme)
        for script in (
            "validate_analysis_report.py",
            "validate_xmind_md.py",
            "md_to_xmind.py",
            "validate_manifest.py",
            "build_testcase_index.py",
            "render_delivery_summary.py",
            "validate_delivery_summary.py",
        ):
            self.assertIn(script, readme)

    def test_conversation_delivery_contract_is_loaded_by_all_qa_delivery_skills(self):
        contract = ROOT / "rules/core/conversation-delivery-contract.md"
        self.assertTrue(contract.is_file())
        for skill_name in ("qa-requirement-analysis", "qa-testcase-design", "qa-artifact-validation"):
            text = (ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("conversation-delivery-contract.md", text)

    def test_artifact_skill_runs_deterministic_delivery_renderer(self):
        artifact = (ROOT / "skills/qa-artifact-validation/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("render_delivery_summary.py", artifact)
        self.assertIn("--check", artifact)
        self.assertIn("最终聊天回复主体", artifact)

    def test_readme_has_two_valid_mermaid_flows_and_no_sort_dimension(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```mermaid\n(.*?)```", readme, re.DOTALL)
        self.assertEqual(2, len(blocks))
        self.assertTrue(all(block.lstrip().startswith("flowchart TD") for block in blocks))
        quality = (ROOT / "rules/core/testcase-quality-rules.md").read_text(encoding="utf-8")
        self.assertNotIn("排序测试\n", quality)
        self.assertIn("排序属于“功能测试”", readme)

    def test_confirmation_resolution_resumes_original_delivery_chain(self):
        gate = (ROOT / "rules/core/confirmation-gate.md").read_text(encoding="utf-8")
        requirement = (ROOT / "skills/qa-requirement-analysis/SKILL.md").read_text(encoding="utf-8")
        testcase = (ROOT / "skills/qa-testcase-design/SKILL.md").read_text(encoding="utf-8")
        artifact = (ROOT / "skills/qa-artifact-validation/SKILL.md").read_text(encoding="utf-8")
        for token in ("原始任务", "blocking_pending_count=0", "不要求用户再次", "Risk Coverage Matrix", "XMind Workbook", "Manifest", "index"):
            self.assertIn(token, gate)
        self.assertIn("确认回复", requirement)
        self.assertIn("自动交接", requirement)
        self.assertIn("重新计算 Risk Coverage Matrix", testcase)
        self.assertIn("不得仅更新 `.xmind.md`", testcase)
        self.assertIn("缺少任一项不得声明完成", artifact)

    def test_xmind_compaction_contract_has_no_hard_length_limit(self):
        quality = (ROOT / "rules/core/testcase-quality-rules.md").read_text(encoding="utf-8")
        for token in ("不设置", "固定字符上限", "不得自动截断", "role_type=30 AND enabled_flag=1", "(A AND B) OR C"):
            self.assertIn(token, quality)
        for forbidden in ("MAX_TEST_POINT_LENGTH", "MAX_STEP_LENGTH", "MAX_EXPECTED_LENGTH"):
            self.assertNotIn(forbidden, quality)

    def test_ci_enforces_formal_artifact_governance_on_all_platforms(self):
        workflow = (ROOT / ".github/workflows/qa-rules-validation.yml").read_text(encoding="utf-8")
        self.assertEqual(2, workflow.count('- "testcases/**/*.xmind"'))
        for command in (
            "python scripts/validate_formal_artifacts.py",
            'python scripts/verify_xmind.py "$output" --markdown tests/fixtures/valid_case_xmind.md',
        ):
            self.assertIn(command, workflow)
        self.assertNotIn("testcases/clearance-permission-20260718/manifest.json", workflow)
        self.assertIn("artifact-governance-compatibility:", workflow)
        self.assertIn("os: [ubuntu-latest, windows-latest]", workflow)
        self.assertIn('python-version: ["3.10", "3.12"]', workflow)


if __name__ == "__main__":
    unittest.main()
