from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from md_to_xmind import convert_file
from qa_validation import ValidationError, validate_markdown_file, validate_xmind_archive


class LegacyMigrationTests(unittest.TestCase):
    def setUp(self):
        fixtures = ROOT / "tests/fixtures/legacy"
        self.original = fixtures / "human_buy_sell_original_xmind.md"
        self.migrated = fixtures / "human_buy_sell_migrated_xmind.md"
        self.golden = json.loads(
            (ROOT / "tests/golden/legacy_migration_expected.json").read_text(encoding="utf-8")
        )

    def test_real_legacy_copy_exposes_current_rule_violations(self):
        digest = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.assertEqual(self.golden["source_sha256"], digest)
        with self.assertRaises(ValidationError) as context:
            validate_markdown_file(self.original)
        message = str(context.exception)
        self.assertIn("同规则重复用例", message)
        self.assertIn("模糊断言", message)

    def test_migrated_fixture_merges_duplicate_and_preserves_p0_coverage(self):
        original_text = self.original.read_text(encoding="utf-8")
        migrated_text = self.migrated.read_text(encoding="utf-8")
        migrated = validate_markdown_file(self.migrated)
        self.assertEqual(self.golden["source_case_count"], original_text.count("- TC"))
        self.assertEqual(self.golden["migrated_case_count"], len(migrated.tc_nodes))
        for fragment in self.golden["merged_cases"]["TC024"]:
            self.assertIn(fragment, migrated_text)
        for term in self.golden["p0_coverage_terms"]:
            self.assertIn(term, original_text)
            self.assertIn(term, migrated_text)
        for phrase in self.golden["removed_fuzzy_assertions"]:
            self.assertIn(phrase, original_text)
            self.assertNotIn(phrase, migrated_text)
        self.assertGreater(len(migrated.warnings), 0, "疑似重复必须保留为可审计 WARNING")
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "human_buy_sell_migrated_workbook.xmind"
            convert_file(self.migrated, workbook)
            verified = validate_xmind_archive(workbook, migrated.root.title, len(migrated.tc_nodes))
            self.assertEqual(self.golden["migrated_case_count"], verified["tc_count"])


if __name__ == "__main__":
    unittest.main()
