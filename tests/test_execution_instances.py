from __future__ import annotations
import copy, json, subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa_contracts import load_json
from validate_execution_instances import validate_execution_model, summarize_execution_model

EXECUTION = ROOT / "tests/fixtures/execution/execution-model-valid.json"

class ExecutionInstanceTests(unittest.TestCase):
    def contexts(self):
        return (load_json(ROOT / "tests/fixtures/models/testcase-model-multi-entry.json"), load_json(ROOT / "tests/fixtures/models/risk-coverage-matrix.json"), load_json(ROOT / "tests/fixtures/models/requirement-analysis.json"), load_json(ROOT / "tests/fixtures/execution/defects.json"))

    def test_valid_execution_and_summary(self):
        model = load_json(EXECUTION); tc, risk, req, defects = self.contexts()
        self.assertEqual([], validate_execution_model(model, testcase_model=tc, risk_model=risk, requirement_model=req, defect_model=defects, root=ROOT))
        summary = summarize_execution_model(model, tc)
        self.assertEqual((3, 4, 3, 1, 3), (summary["branch_count"], summary["execution_instance_count"], summary["initial_count"], summary["rerun_count"], summary["final_passed_count"]))

    def test_missing_counts_and_not_run_payload_fail(self):
        model = load_json(EXECUTION); tc, risk, req, defects = self.contexts()
        for field in ("branch_count", "execution_instance_count", "execution_instances"):
            changed = copy.deepcopy(model); changed.pop(field)
            self.assertTrue(any(field in error for error in validate_execution_model(changed, testcase_model=tc, risk_model=risk, requirement_model=req, defect_model=defects, root=ROOT)))
        changed = copy.deepcopy(model); changed["execution_instances"][0].update(status="not_run", defect_ids=["BUG-001"])
        self.assertTrue(validate_execution_model(changed, testcase_model=tc, risk_model=risk, requirement_model=req, defect_model=defects, root=ROOT))

    def test_rerun_cross_branch_fake_defect_and_confirmation_fail(self):
        model = load_json(EXECUTION); tc, risk, req, defects = self.contexts()
        changed = copy.deepcopy(model); changed["execution_instances"][2]["branch_id"] = "TC001-B03"
        self.assertTrue(any("同一 Testcase/Branch" in error for error in validate_execution_model(changed, testcase_model=tc, risk_model=risk, requirement_model=req, defect_model=defects, root=ROOT)))
        changed = copy.deepcopy(model); changed["execution_instances"][1]["defect_ids"] = ["BUG-999"]
        self.assertTrue(any("BUG-999" in error for error in validate_execution_model(changed, testcase_model=tc, risk_model=risk, requirement_model=req, defect_model=defects, root=ROOT)))
        changed = copy.deepcopy(model); changed["execution_instances"][0].update(status="blocked", confirmation_ids=["CONF-999"], defect_ids=[])
        self.assertTrue(any("CONF-999" in error for error in validate_execution_model(changed, testcase_model=tc, risk_model=risk, requirement_model=req, defect_model=defects, root=ROOT)))

    def test_ci_has_strict_execution_context(self):
        workflow = (ROOT / ".github/workflows/qa-rules-validation.yml").read_text(encoding="utf-8")
        command = next(line for line in workflow.splitlines() if "validate_execution_instances.py" in line)
        for flag in ("--testcase", "--risk", "--requirement", "--defects"):
            self.assertIn(flag, command)
        self.assertNotIn("--draft", command)

if __name__ == "__main__": unittest.main()
