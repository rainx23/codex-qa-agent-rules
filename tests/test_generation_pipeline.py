from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_task_manifest import build_manifest, publish
from describe_model_contract import describe
from init_task_models import initialize
from qa_contracts import (
    manifest_schema, requirement_schema, risk_matrix_schema, testcase_schema,
    read_rule_version, validate_schema_shape,
)
from run_generation_pipeline import run_pipeline


class GenerationPipelineTests(unittest.TestCase):
    def test_desensitized_simple_ui_fixture_covers_required_regression_shape(self):
        fixture = json.loads(
            (ROOT / "tests/fixtures/generation_pipeline/simple-ui-scenario.json").read_text(encoding="utf-8")
        )
        self.assertEqual(2, len(fixture["environments"]))
        self.assertEqual(3, len(fixture["metrics"]))
        self.assertEqual(3, len(fixture["shared_entry_scopes"]))
        self.assertTrue(all(scope["leaf_entries"] >= 6 for scope in fixture["shared_entry_scopes"]))
        self.assertEqual(6, len(fixture["required_combinations"]))
        self.assertTrue(fixture["condition_coverage_required"])
        self.assertFalse(fixture["production_index_update"])

    def test_compact_contract_examples_are_schema_legal_and_stable(self):
        version = read_rule_version(ROOT)
        schemas = {
            "requirement": requirement_schema(version),
            "risk": risk_matrix_schema(version),
            "testcase": testcase_schema(version),
            "manifest": manifest_schema(version),
        }
        for kind, schema in schemas.items():
            with self.subTest(kind=kind):
                first = describe(kind)
                second = describe(kind)
                self.assertEqual(first, second)
                self.assertEqual(
                    [], validate_schema_shape(first["minimal_schema_legal_example"], schema)
                )
                self.assertNotIn("$schema", json.dumps(first, ensure_ascii=False))

    def test_initializer_creates_only_snapshot_and_empty_model_skeletons(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copy2(ROOT / "RULE_VERSION", root / "RULE_VERSION")
            source = root / "input.md"
            source.write_text("简单 UI 样式需求\n", encoding="utf-8")
            task = root / "tests/fixtures/runtime/task"
            outputs = initialize(
                root, task, source, mode="confirmation_only", report_mode="requirement",
                source_type="pasted_text", source_id="REQ-PIPE-001",
                timezone_name="Asia/Shanghai",
            )
            self.assertEqual(5, len(outputs))
            self.assertFalse((task / "manifest.json").exists())
            self.assertFalse((root / "testcases/index.md").exists())
            requirement = json.loads((task / "requirement-analysis.json").read_text(encoding="utf-8"))
            risk = json.loads((task / "risk-coverage-matrix.json").read_text(encoding="utf-8"))
            testcase = json.loads((task / "testcase-model.json").read_text(encoding="utf-8"))
            self.assertEqual([], requirement["facts"])
            self.assertEqual([], risk["risk_items"])
            self.assertEqual([], testcase["cases"])
            for model in (requirement, risk, testcase):
                self.assertEqual("2.18.0", model["rule_version"])
                self.assertEqual("confirmation_only", model["workflow_stage"])
                self.assertEqual("Asia/Shanghai", model["generated_timezone"])

    def test_invalid_models_cannot_create_manifest_and_bad_temp_is_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "manifest.json"
            with self.assertRaisesRegex(ValueError, "Manifest 校验失败"):
                publish(output, {"custom": "wrong"})
            self.assertFalse(output.exists())
            self.assertEqual([], list(output.parent.glob("*.manifest.tmp")))

            testcase = Path(temporary) / "testcase.json"
            testcase.write_text('{"schema_version":"2.0.0","root_title":"x","cases":[]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "模型校验失败"):
                build_manifest(
                    ROOT, output,
                    requirement_path=ROOT / "tests/fixtures/models/requirement-analysis.json",
                    diff_path=ROOT / "tests/fixtures/models/diff-impact.json",
                    risk_path=ROOT / "tests/fixtures/models/risk-coverage-matrix.json",
                    testcase_path=testcase,
                    report_path=ROOT / "tests/fixtures/reports/combined_consistent.md",
                    xmind_md_path=ROOT / "tests/fixtures/valid_case_xmind.md",
                    xmind_path=ROOT / "tests/fixtures/valid_case.xmind",
                    relation="新增", supersedes=None, timezone_name="Asia/Shanghai",
                )
            self.assertFalse(output.exists())

    def _pipeline_kwargs(self) -> dict:
        return {
            "requirement": ROOT / "tests/fixtures/models/requirement-analysis.json",
            "diff": ROOT / "tests/fixtures/models/diff-impact.json",
            "risk": ROOT / "tests/fixtures/models/risk-coverage-matrix.json",
            "testcase": ROOT / "tests/fixtures/models/testcase-model.json",
            "report": ROOT / "tests/fixtures/reports/combined_consistent.md",
            "xmind_md": ROOT / "tests/fixtures/valid_case_xmind.md",
            "xmind": ROOT / "tests/fixtures/valid_case.xmind",
            "manifest": ROOT / "tests/fixtures/not-created-manifest.json",
            "index": ROOT / "tests/fixtures/not-created-index.md",
            "relation": "新增",
            "supersedes": None,
        }

    def test_pipeline_stops_immediately_after_model_failure(self):
        calls: list[list[str]] = []

        def fail_models(command: list[str], cwd: Path) -> int:
            calls.append(command)
            return 1

        code, audit = run_pipeline(ROOT, executor=fail_models, **self._pipeline_kwargs())
        self.assertEqual(1, code)
        self.assertEqual(["requirement_validation", "risk_validation", "validate_models"], [
            item["stage"] for item in audit
        ])
        self.assertEqual(1, len(calls))
        self.assertFalse(any("build_task_manifest.py" in " ".join(command) for command in calls))
        self.assertFalse(any("build_testcase_index.py" in " ".join(command) for command in calls))

    def test_execution_audit_enforces_call_budgets_and_final_task_validation(self):
        calls: list[list[str]] = []

        def pass_all(command: list[str], cwd: Path) -> int:
            calls.append(command)
            return 0

        code, audit = run_pipeline(ROOT, executor=pass_all, **self._pipeline_kwargs())
        self.assertEqual(0, code)
        command_text = [" ".join(command) for command in calls]
        self.assertEqual(1, sum("validate_models.py" in item for item in command_text))
        self.assertEqual(1, sum("validate_xmind_md.py" in item for item in command_text))
        self.assertEqual(1, sum("md_to_xmind.py" in item for item in command_text))
        self.assertEqual(1, sum("build_task_manifest.py" in item for item in command_text))
        self.assertEqual(1, sum("build_testcase_index.py" in item for item in command_text))
        self.assertEqual(1, sum("validate_task.py" in item for item in command_text))
        self.assertFalse(any("validate_release.py" in item for item in command_text))
        self.assertEqual("delivery_summary", audit[-1]["stage"])
        self.assertTrue(all(item["repair_attempts"] <= 1 for item in audit))
        expected = json.loads(
            (ROOT / "tests/fixtures/generation_pipeline/expected-execution-audit.json").read_text(encoding="utf-8")
        )
        for stage, maximum in expected["maximum_calls"].items():
            self.assertLessEqual(sum(stage in item for item in command_text), maximum)
        self.assertEqual(expected["required_final_stage"], audit[-1]["stage"])

    def test_repository_has_no_daily_temporary_scripts(self):
        self.assertEqual([], sorted((ROOT / "scripts").glob("_*.py")))


if __name__ == "__main__":
    unittest.main()
