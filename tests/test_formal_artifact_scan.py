from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_formal_artifacts import discover_passed_manifests


class FormalArtifactScanTests(unittest.TestCase):
    def test_discovers_all_passed_manifests_and_skips_drafts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            passed = root / "formal-a" / "manifest.json"
            pending = root / "formal-b" / "manifest.json"
            draft = root / "drafts" / "draft-a" / "manifest.json"
            for path, status in ((passed, "passed"), (pending, "pending"), (draft, "passed")):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"validation_status": status}), encoding="utf-8")
            manifests, errors = discover_passed_manifests(root)
            self.assertEqual([], errors)
            self.assertEqual([passed], manifests)

    def test_invalid_formal_manifest_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid = root / "formal" / "manifest.json"
            invalid.parent.mkdir(parents=True)
            invalid.write_text("{", encoding="utf-8")
            manifests, errors = discover_passed_manifests(root)
            self.assertEqual([], manifests)
            self.assertTrue(any("Manifest 无法读取" in item for item in errors))

    def test_repository_current_passed_manifest_is_discovered(self):
        manifests, errors = discover_passed_manifests(ROOT / "testcases")
        self.assertEqual([], errors)
        self.assertTrue(any(path.name == "manifest.json" for path in manifests))


if __name__ == "__main__":
    unittest.main()
