from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from migration_contracts import detect_model_type, migrate_document, serialize_json


class SchemaMigrationTests(unittest.TestCase):
    def setUp(self):
        self.v1 = ROOT / "tests/fixtures/migration/v1"

    def test_real_requirement_migration_is_conservative(self):
        source = json.loads((self.v1 / "requirement-pending.json").read_text(encoding="utf-8"))
        result = migrate_document(source, "requirement_analysis")
        self.assertEqual("2.0.0", result.data["schema_version"])
        self.assertEqual("pending", result.data["validation_status"])
        self.assertEqual("unknown", result.data["facts"][0]["status"])
        self.assertEqual("pending", result.data["confirmation_points"][0]["status"])
        self.assertEqual("blocking", result.data["confirmation_points"][0]["severity"])
        self.assertEqual("legacy", result.unknown_fields[0]["value"])
        self.assertTrue(result.reconfirm_required)

    def test_detection_rejects_root_unknown_ambiguous_and_conflict(self):
        with self.assertRaises(ValueError):
            detect_model_type([])
        with self.assertRaises(ValueError):
            detect_model_type({"schema_version": "1.0.0", "mystery": []})
        with self.assertRaises(ValueError):
            detect_model_type({"schema_version": "1.0.0", "requirements": [], "changes": []})
        with self.assertRaises(ValueError):
            detect_model_type({"schema_version": "1.0.0", "model_type": "diff_impact", "requirements": []})

    def test_all_model_types_have_distinct_migrators(self):
        expected = {
            "requirement_analysis", "diff_impact", "risk_coverage_matrix", "testcase_model",
            "artifact_manifest", "validation_sql", "api_automation", "api_automation_artifact",
            "execution_model", "knowledge_table",
        }
        from migration_contracts import MIGRATORS
        self.assertEqual(expected, set(MIGRATORS))
        self.assertEqual(len(expected), len({id(value) for value in MIGRATORS.values()}))

    def test_version_only_v2_structure_is_rejected(self):
        bad = {"schema_version": "2.0.0", "requirements": ["old shape"]}
        with self.assertRaises(ValueError):
            migrate_document(bad, "requirement_analysis")

    def test_idempotent_v2_is_byte_identical(self):
        source = json.loads((self.v1 / "requirement-complete.json").read_text(encoding="utf-8"))
        first = migrate_document(source, "requirement_analysis")
        second = migrate_document(first.data, "requirement_analysis")
        self.assertEqual("unchanged", second.status)
        self.assertEqual([], second.changes)
        self.assertEqual(serialize_json(first.data), serialize_json(second.data))

    def test_model_specific_guardrails(self):
        cases = {
            "risk_coverage_matrix": ({"schema_version": "1.0.0", "risks": [{"title": "可能有问题", "disposition": "accepted"}]}, "reconfirm_required"),
            "validation_sql": ({"schema_version": "1.0.0", "sql": "select x", "source_reference": "table"}, "pending"),
            "api_automation": ({"schema_version": "1.0.0", "interfaces": [{"protocol": "HTTP 200"}]}, "pending"),
            "execution_model": ({"schema_version": "1.0.0", "executions": [{"testcase_id": "TC-1", "status": "success"}]}, "pending"),
            "knowledge_table": ({"schema_version": "1.0.0", "tables": [{"parse_status": "complete"}]}, "partial"),
        }
        for model_type, (source, expected) in cases.items():
            with self.subTest(model_type=model_type):
                result = migrate_document(source, model_type)
                self.assertIn(expected, json.dumps(result.data, ensure_ascii=False))
                self.assertTrue(result.reconfirm_required)

    def test_cli_single_dry_run_idempotence_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "requirement.json"
            report = Path(directory) / "report.json"
            cmd = [sys.executable, str(ROOT / "scripts/migrate_schema.py"), "--input", str(self.v1 / "requirement-complete.json"), "--output", str(out), "--report", str(report), "--strict"]
            checked = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(0, checked.returncode, checked.stderr)
            first = out.read_bytes()
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual("passed", payload["status"])
            self.assertRegex(payload["source_hash"], r"^sha256:[0-9a-f]{64}$")
            self.assertRegex(payload["destination_hash"], r"^sha256:[0-9a-f]{64}$")
            self.assertTrue(payload["destination_written"])
            second = Path(directory) / "second.json"
            second_report = Path(directory) / "second-report.json"
            checked = subprocess.run([sys.executable, str(ROOT / "scripts/migrate_schema.py"), "--input", str(out), "--output", str(second), "--report", str(second_report), "--strict"], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(0, checked.returncode, checked.stderr)
            self.assertEqual(first, second.read_bytes())
            self.assertEqual("unchanged", json.loads(second_report.read_text(encoding="utf-8"))["status"])
            dry = Path(directory) / "dry.json"
            checked = subprocess.run([sys.executable, str(ROOT / "scripts/migrate_schema.py"), "--input", str(self.v1 / "requirement-pending.json"), "--output", str(dry), "--report", str(Path(directory) / "dry-report.json"), "--dry-run", "--best-effort"], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(0, checked.returncode, checked.stderr)
            self.assertFalse(dry.exists())

    def test_cli_failure_leaves_no_target(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "bad.json"
            checked = subprocess.run([sys.executable, str(ROOT / "scripts/migrate_schema.py"), "--input", str(self.v1 / "unrecognized.json"), "--output", str(target), "--report", str(Path(directory) / "failed.json"), "--strict"], cwd=ROOT, text=True, capture_output=True)
            self.assertNotEqual(0, checked.returncode)
            self.assertFalse(target.exists())

    def test_cli_bundle_and_workflow_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle"
            report = Path(directory) / "bundle-report.json"
            checked = subprocess.run([sys.executable, str(ROOT / "scripts/migrate_schema.py"), "--input-dir", str(self.v1 / "bundle"), "--output-dir", str(output), "--report", str(report), "--strict"], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(0, checked.returncode, checked.stderr)
            self.assertEqual("passed", json.loads(report.read_text(encoding="utf-8"))["status"])
        workflow = (ROOT / ".github/workflows/qa-rules-validation.yml").read_text(encoding="utf-8")
        self.assertIn("test_schema_migration.py", workflow)
        self.assertIn("migrate_schema.py", workflow)
        self.assertNotIn("migrate_schema.py", "\n".join(line for line in workflow.splitlines() if "best-effort" in line))


if __name__ == "__main__":
    unittest.main()
