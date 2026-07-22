#!/usr/bin/env python3
"""Run the complete repository gate for rule changes and releases."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def release_commands() -> tuple[tuple[str, ...], ...]:
    python = sys.executable
    return (
        (python, "-m", "compileall", "-q", "scripts", "tests"),
        (python, "scripts/validate_skill_contracts.py", "skills"),
        (python, "scripts/generate_schemas.py", "--check"),
        (python, "scripts/validate_schemas.py"),
        (python, "scripts/validate_rule_version.py"),
        (python, "scripts/validate_repository_docs.py"),
        (python, "scripts/validate_repository_mode.py"),
        (python, "scripts/validate_rule_consistency.py"),
        (python, "scripts/validate_fixture_layout.py"),
        (python, "scripts/validate_ci_workflow.py"),
        (python, "scripts/validate_models.py", "--requirement", "tests/fixtures/models/requirement-analysis.json", "--diff", "tests/fixtures/models/diff-impact.json", "--risk", "tests/fixtures/models/risk-coverage-matrix.json", "--testcase", "tests/fixtures/models/testcase-model.json"),
        (python, "scripts/validate_knowledge.py", "qa-knowledge/examples"),
        (python, "scripts/build_knowledge_index.py", "qa-knowledge/examples", "--check"),
        (python, "scripts/validate_data_validation.py", "tests/fixtures/models/data-validation-valid.json"),
        (python, "scripts/validate_sql_style.py", "tests/fixtures/sql/valid_validation_sql.sql", "--strict"),
        (python, "scripts/validate_sql_artifact.py", "--artifact", "tests/fixtures/artifacts/validation-sql-manifest.json", "--requirement", "tests/fixtures/models/requirement-analysis.json", "--diff", "tests/fixtures/models/diff-impact.json", "--risk", "tests/fixtures/models/risk-coverage-matrix.json", "--testcase", "tests/fixtures/models/testcase-model.json", "--knowledge", "qa-knowledge/examples"),
        (python, "scripts/validate_api_automation.py", "--model", "tests/fixtures/models/api-automation-valid.json"),
        (python, "scripts/validate_api_automation_artifacts.py", "--artifact", "tests/fixtures/api/api-artifact-valid.json", "--model", "tests/fixtures/models/api-automation-valid.json"),
        (python, "scripts/validate_execution_instances.py", "--execution", "tests/fixtures/execution/execution-model-valid.json", "--testcase", "tests/fixtures/models/testcase-model-multi-entry.json", "--risk", "tests/fixtures/models/risk-coverage-matrix.json", "--requirement", "tests/fixtures/models/requirement-analysis.json", "--defects", "tests/fixtures/execution/defects.json"),
        (python, "scripts/validate_manifest.py", "testcases/manifest.example.json"),
        (python, "scripts/render_delivery_summary.py", "--manifest", "testcases/clearance-permission-20260718-v2/manifest.json", "--check"),
        (python, "scripts/repair_text_encoding.py", "testcases/index.md", "--check"),
        (python, "scripts/validate_formal_artifacts.py"),
        (python, "scripts/validate_analysis_report.py", "tests/fixtures/reports/requirement_only.md", "--mode", "requirement", "--legacy"),
        (python, "scripts/validate_analysis_report.py", "tests/fixtures/reports/diff_only.md", "--mode", "diff", "--legacy"),
        (python, "scripts/validate_analysis_report.py", "tests/fixtures/reports/requirement_diff_combined.md", "--mode", "combined", "--legacy"),
        (python, "scripts/validate_traceability.py", "tests/fixtures/reports/combined_consistent.md", "tests/fixtures/valid_case_xmind.md", "--mode", "combined", "--risk-matrix", "tests/fixtures/models/risk-coverage-matrix.json", "--testcase-model", "tests/fixtures/models/testcase-model.json"),
        (python, "scripts/validate_xmind_md.py", "tests/fixtures/valid_case_xmind.md"),
        (python, "scripts/validate_xmind_md.py", "tests/fixtures/multi_entry_valid_xmind.md"),
        (python, "scripts/validate_xmind_md.py", "tests/fixtures/multi_entry_direct_valid_xmind.md"),
        (python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_anti_hallucination_fixtures.py", "-v"),
        (python, "-m", "unittest", "discover", "-s", "tests", "-v"),
        ("git", "diff", "--check"),
    )


def run_release_validation(root: Path) -> int:
    for command in release_commands():
        print("RUN " + " ".join(command), flush=True)
        result = subprocess.run(command, cwd=root, check=False)
        if result.returncode:
            print("FAIL release validation stopped", file=sys.stderr)
            return result.returncode
    with tempfile.TemporaryDirectory(prefix="qa-release-xmind-") as temporary:
        workbook = Path(temporary) / "valid_case_workbook.xmind"
        for command in (
            (sys.executable, "scripts/md_to_xmind.py", "tests/fixtures/valid_case_xmind.md", "-o", str(workbook)),
            (sys.executable, "scripts/verify_xmind.py", str(workbook), "--markdown", "tests/fixtures/valid_case_xmind.md"),
        ):
            print("RUN " + " ".join(command), flush=True)
            result = subprocess.run(command, cwd=root, check=False)
            if result.returncode:
                print("FAIL release validation stopped", file=sys.stderr)
                return result.returncode
    print("PASS complete rule release validation")
    return 0


def main() -> int:
    return run_release_validation(Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    raise SystemExit(main())
