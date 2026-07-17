from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_rule_consistency import CANONICAL_PRIORITY, validate_repository_rules
from qa_contracts import PENDING_SEVERITIES, PENDING_STATUSES, RISK_DISPOSITIONS, VALIDATION_STATUSES


class RuleConsistencyTests(unittest.TestCase):
    def test_repository_rules_are_consistent(self):
        self.assertEqual([], validate_repository_rules(ROOT))

    def test_zentao_priority_has_one_authoritative_definition(self):
        profile = (ROOT / "rules/profiles/zentao.md").read_text(encoding="utf-8")
        canonical = " > ".join(CANONICAL_PRIORITY)
        self.assertEqual(1, profile.count(canonical))
        for path in [ROOT / "AGENTS.md", ROOT / "README.md", ROOT / "skills/qa-requirement-analysis/SKILL.md"]:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(canonical, text, path.as_posix())
            self.assertIn("rules/profiles/zentao.md", text, path.as_posix())

    def test_canonical_contract_contains_cross_rule_values(self):
        data = json.loads((ROOT / "rules/core/canonical-rules.json").read_text(encoding="utf-8"))
        self.assertEqual("2.0.0", data["schema_version"])
        self.assertEqual(["current", "stale", "reconfirm_required"], data["evidence_status"])
        self.assertEqual({"assertion_scope": "parameter_health", "checks": ["content.code = 0", "content.msg = OK"]}, data["api_health"])
        self.assertEqual(["not_run", "passed", "failed", "blocked", "skipped"], data["execution_status"])
        self.assertEqual(["initial", "rerun"], data["execution_run_type"])
        self.assertEqual(list(PENDING_SEVERITIES), data["confirmation_severity"])
        self.assertEqual(list(PENDING_STATUSES), data["confirmation_status"])
        self.assertEqual(list(RISK_DISPOSITIONS), data["risk_disposition"])
        self.assertEqual(list(VALIDATION_STATUSES), data["manifest_validation_status"])

    def test_workflow_has_consistency_gates(self):
        workflow = (ROOT / ".github/workflows/qa-rules-validation.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/validate_rule_consistency.py", workflow)
        self.assertIn("python scripts/validate_fixture_layout.py", workflow)


if __name__ == "__main__":
    unittest.main()
