from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_ci_workflow import validate_workflow
from validate_repository_mode import validate_mode


class CiAndRepositoryModeTests(unittest.TestCase):
    def test_ci_workflow_static_contract(self):
        path = ROOT / ".github/workflows/qa-rules-validation.yml"
        self.assertTrue(path.is_file())
        self.assertEqual([], validate_workflow(path))

    def test_standalone_does_not_require_nested_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "rules-repository.json"
            config.write_text(json.dumps({"repository_mode": "standalone"}), encoding="utf-8")
            mode, errors = validate_mode(config)
            self.assertEqual("standalone", mode)
            self.assertEqual([], errors)

    def test_integrated_missing_template_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "rules-repository.json"
            config.write_text(json.dumps({"repository_mode": "integrated", "template_path": "missing"}), encoding="utf-8")
            mode, errors = validate_mode(config)
            self.assertEqual("integrated", mode)
            self.assertTrue(any("不存在" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
