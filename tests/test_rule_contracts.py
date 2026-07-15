from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RuleContractTests(unittest.TestCase):
    def test_all_mirrored_rule_assets_match(self):
        mirror = ROOT / "codex-qa-agent-rules"
        if not mirror.is_dir():
            self.skipTest("standalone template repository")
        roots = ["AGENTS.md", "README.md", "docs", "rules", "skills", "scripts", "tests", "testcases/manifest.example.json"]
        for entry in roots:
            path = ROOT / entry
            files = [path] if path.is_file() else [item for item in path.rglob("*") if item.is_file() and "__pycache__" not in item.parts and item.suffix != ".pyc"]
            for source in files:
                relative = source.relative_to(ROOT)
                target = mirror / relative
                self.assertTrue(target.is_file(), str(relative))
                self.assertEqual(source.read_bytes(), target.read_bytes(), str(relative))

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


if __name__ == "__main__":
    unittest.main()
