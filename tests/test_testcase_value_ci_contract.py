from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "qa-rules-validation.yml"


class TestcaseValueCiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        marker = "  value-assessment-compatibility:"
        next_marker = "  artifact-governance-compatibility:"

        start = cls.workflow.index(marker)
        end = cls.workflow.index(next_marker, start)

        cls.value_job = cls.workflow[start:end]

        validate_start = cls.workflow.index("  validate:")
        cls.main_job = cls.workflow[validate_start:start]

    def test_value_assessment_compatibility_job_exists(self):
        self.assertIn("value-assessment-compatibility:", self.workflow)

    def test_matrix_contains_ubuntu_latest(self):
        self.assertIn("ubuntu-latest", self.value_job)

    def test_matrix_contains_windows_latest(self):
        self.assertIn("windows-latest", self.value_job)

    def test_matrix_contains_python_310(self):
        self.assertIn('"3.10"', self.value_job)

    def test_matrix_contains_python_312(self):
        self.assertIn('"3.12"', self.value_job)

    def test_matrix_disables_fail_fast(self):
        self.assertRegex(self.value_job, r"fail-fast:\s*false")

    def test_job_runs_assessment_tests(self):
        self.assertIn('test_testcase_value_assessment.py', self.value_job)

    def test_job_runs_cli_tests(self):
        self.assertIn('test_testcase_value_cli.py', self.value_job)

    def test_job_runs_golden_tests(self):
        self.assertIn('test_testcase_value_golden.py', self.value_job)

    def test_job_runs_legal_optional_assessment_example(self):
        self.assertIn(
            "python scripts/validate_testcase_quality.py tests/fixtures/valid_case_xmind.md "
            "--risk-matrix tests/fixtures/models/risk-coverage-matrix.json "
            "--testcase-model tests/fixtures/models/testcase-model.json "
            "--value-assessment tests/fixtures/value-assessment/testcase-value-assessment-valid.json",
            self.value_job,
        )

    def test_job_checks_generated_schemas(self):
        self.assertIn("python scripts/generate_schemas.py --check", self.value_job)

    def test_job_has_no_value_strict_flag(self):
        self.assertNotIn("--value-strict", self.value_job)

    def test_job_does_not_continue_on_error(self):
        self.assertNotRegex(self.value_job, r"continue-on-error:\s*true")

    def test_job_does_not_scan_all_artifacts_for_assessment(self):
        self.assertNotIn("validate_manifest.py", self.value_job)
        self.assertNotIn("testcases/", self.value_job)
        self.assertNotRegex(self.value_job, r"(?:find|Get-ChildItem|glob)\s+.*assessment")

    def test_main_manifest_validation_does_not_require_assessment(self):
        manifest_lines = [line for line in self.main_job.splitlines() if "validate_manifest.py" in line]
        self.assertTrue(manifest_lines)
        self.assertTrue(all("value-assessment" not in line for line in manifest_lines))

    def test_existing_main_job_keeps_python_matrix_and_core_commands(self):
        self.assertIn("runs-on: ubuntu-latest", self.main_job)
        self.assertIn('python-version: ["3.10", "3.12"]', self.main_job)
        for command in (
            "python -m compileall -q scripts tests",
            "python -m unittest discover -s tests -v",
            "python scripts/validate_manifest.py testcases/manifest.example.json",
            "git diff --exit-code",
        ):
            self.assertIn(command, self.main_job)

    def test_new_job_uses_no_platform_specific_external_commands(self):
        self.assertNotIn("shell:", self.value_job)
        self.assertNotRegex(
            self.value_job,
            r"(?im)^\s*run:\s*(?:grep|sed|awk|diff|sha256sum|Get-FileHash|chmod|cp|rm)\b",
        )
        self.assertNotIn("PowerShell Junction", self.value_job)
        self.assertNotRegex(self.value_job, r"(?m)^\s*run:.*\|")

    def test_matrix_defines_exactly_four_stable_combinations(self):
        os_match = re.search(r"os:\s*\[([^]]+)\]", self.value_job)
        python_match = re.search(r"python-version:\s*\[([^]]+)\]", self.value_job)
        self.assertIsNotNone(os_match)
        self.assertIsNotNone(python_match)
        operating_systems = [item.strip() for item in os_match.group(1).split(",")]
        python_versions = [item.strip().strip('"') for item in python_match.group(1).split(",")]
        self.assertEqual(["ubuntu-latest", "windows-latest"], operating_systems)
        self.assertEqual(["3.10", "3.12"], python_versions)
        self.assertEqual(4, len(operating_systems) * len(python_versions))


if __name__ == "__main__":
    unittest.main()
