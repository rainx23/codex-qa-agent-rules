from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_fixture_layout import validate_fixture_layout


class FixtureGovernanceTests(unittest.TestCase):
    def test_fixture_layout_is_clean(self):
        self.assertEqual([], validate_fixture_layout(ROOT))

    def test_customer_query_is_only_a_fixture(self):
        self.assertFalse((ROOT / "src/customer-query.java").exists())
        fixture = ROOT / "tests/fixtures/sources/customer-query.java"
        self.assertTrue(fixture.is_file())
        self.assertIn("TEST FIXTURE ONLY", fixture.read_text(encoding="utf-8"))

    def test_ci_never_updates_golden(self):
        workflow = (ROOT / ".github/workflows/qa-rules-validation.yml").read_text(encoding="utf-8")
        self.assertNotIn("--update-golden", workflow)


if __name__ == "__main__":
    unittest.main()
