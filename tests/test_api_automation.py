import json
import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/models/api-automation-valid.json"


class ApiAutomationTests(unittest.TestCase):
    def test_validation_must_be_object_and_fixed_exactly(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from qa_contracts import load_json, validate_api_automation
        base = load_json(FIXTURE)
        for value in ([], "[]", 0, None):
            model = copy.deepcopy(base); model["validation"] = value
            self.assertTrue(validate_api_automation(model), value)
        model = copy.deepcopy(base)
        model["validation"]["checks"].append({"path":"data.amount","operator":"equals","expected":1})
        self.assertTrue(validate_api_automation(model))
        model = copy.deepcopy(base); model["validation"]["checks"][0]["expected"] = "0"
        self.assertTrue(validate_api_automation(model))

    def test_model_root_must_be_object(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from qa_contracts import validate_api_automation
        for value in ([], "parameter_health", 0, None):
            self.assertTrue(any("object" in error for error in validate_api_automation(value)))

    def test_ci_contains_strict_api_artifact_validation(self):
        workflow = (ROOT / ".github/workflows/qa-rules-validation.yml").read_text(encoding="utf-8")
        commands = [line for line in workflow.splitlines() if "validate_api_automation_artifacts.py" in line]
        self.assertTrue(commands)
        self.assertIn("--model", commands[0])
        self.assertNotIn("--draft", commands[0])

    def test_artifact_model_consistency_and_non_object_roots(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from qa_contracts import load_json
        from validate_api_automation_artifacts import validate_api_automation_artifact
        artifact = load_json(ROOT / "tests/fixtures/api/api-artifact-valid.json")
        model = load_json(FIXTURE)
        self.assertEqual([], validate_api_automation_artifact(artifact, api_model=model, root=ROOT))
        wrong = copy.deepcopy(artifact); wrong["method"] = "get"
        self.assertTrue(any("method" in error for error in validate_api_automation_artifact(wrong, api_model=model, root=ROOT)))
        for value in ([], "artifact", 0, None):
            self.assertTrue(any("object" in error for error in validate_api_automation_artifact(value, api_model=model, root=ROOT)))

    def test_model_hash_is_stable_across_checkout_line_endings(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from validate_api_automation_artifacts import _sha256
        with tempfile.TemporaryDirectory() as directory:
            lf = Path(directory) / "lf.json"
            crlf = Path(directory) / "crlf.json"
            lf.write_bytes(b'{"model_id":"API-AUTO-001"}\n')
            crlf.write_bytes(b'{"model_id":"API-AUTO-001"}\r\n')
            self.assertEqual(_sha256(lf), _sha256(crlf))

    def test_script_default_value_swallow_and_business_assertions_fail(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from validate_api_automation_artifacts import _validate_script
        artifact = json.loads((ROOT / "tests/fixtures/api/api-artifact-valid.json").read_text(encoding="utf-8"))
        cases = (
            'def validate_response(response):\n assert response.get("content", {}).get("code", 0) == 0\n assert response["content"]["msg"] == "OK"\n',
            'def validate_response(response):\n try:\n  assert response["content"]["code"] == 0\n except AssertionError:\n  pass\n assert response["content"]["msg"] == "OK"\n',
            'def validate_response(response):\n assert response["content"]["code"] == 0\n assert response["data"]["amount"] > 0\n',
        )
        with tempfile.TemporaryDirectory() as directory:
            for index, source in enumerate(cases):
                path = Path(directory) / f"bad-{index}.py"; path.write_text(source, encoding="utf-8")
                self.assertTrue(_validate_script(path, artifact), index)

    def test_artifact_cli_requires_model(self):
        result = self.run_tool("scripts/validate_api_automation_artifacts.py", "--artifact", "tests/fixtures/api/api-artifact-valid.json")
        self.assertNotEqual(0, result.returncode)
    def run_tool(self, *args):
        return subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True)

    def test_model_schema_fixture_is_valid(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from qa_contracts import validate_api_automation, load_json
        self.assertEqual(validate_api_automation(load_json(FIXTURE)), [])

    def test_generate_and_validate_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            excel = directory / "fixture-case.xlsx"
            parameters = directory / "fixture-parameter.txt"
            generated = self.run_tool("scripts/generate_api_automation_excel.py", "--model", str(FIXTURE), "--output", str(excel), "--parameter-output", str(parameters))
            self.assertEqual(generated.returncode, 0, generated.stderr)
            checked = self.run_tool("scripts/validate_api_automation_artifacts.py", "--excel", str(excel), "--parameters", str(parameters), "--model", str(FIXTURE))
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(parameters.read_text(encoding="utf-8"), "参数名：\nisAnalysis\n\n参数值：\n[\"0\",\"1\",\"\"]\n")

    def test_undefined_body_parameter_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            model = json.loads(FIXTURE.read_text(encoding="utf-8"))
            model["excel_case"][0]["body"] = '{"params":{"unknown":"$unknown"}}'
            model_path = directory / "model.json"
            model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
            excel, parameters = directory / "case.xlsx", directory / "parameter.txt"
            self.assertEqual(self.run_tool("scripts/generate_api_automation_excel.py", "--model", str(model_path), "--output", str(excel), "--parameter-output", str(parameters)).returncode, 0)
            checked = self.run_tool("scripts/validate_api_automation_artifacts.py", "--excel", str(excel), "--parameters", str(parameters), "--model", str(model_path))
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("未定义参数", checked.stderr)

    def test_duplicate_interface_rows_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            model = json.loads(FIXTURE.read_text(encoding="utf-8"))
            model["excel_case"].append(dict(model["excel_case"][0], case_name="another"))
            model_path = directory / "model.json"
            model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
            excel, parameters = directory / "case.xlsx", directory / "parameter.txt"
            self.assertEqual(self.run_tool("scripts/generate_api_automation_excel.py", "--model", str(model_path), "--output", str(excel), "--parameter-output", str(parameters)).returncode, 0)
            checked = self.run_tool("scripts/validate_api_automation_artifacts.py", "--excel", str(excel), "--parameters", str(parameters), "--model", str(model_path))
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("重复", checked.stderr)

    def test_blocked_model_requires_questions(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from qa_contracts import validate_api_automation, load_json
        model = load_json(FIXTURE)
        model["automation_action"] = "blocked"
        model["validation_status"] = "pending"
        self.assertTrue(any("blocking_questions" in error for error in validate_api_automation(model)))

    def test_required_scenario_catalog_is_present(self):
        catalog = json.loads((ROOT / "tests/fixtures/api_automation/scenarios.json").read_text(encoding="utf-8"))
        self.assertEqual(16, len(catalog))
        self.assertEqual({"create", "update", "none", "blocked"}, {item["automation_action"] for item in catalog if "automation_action" in item})
        self.assertEqual(["0", "1", ""], catalog[1]["values"])
        self.assertEqual([["1", "2"], ["", "3"], ["2", "1"]], catalog[2]["values"])


if __name__ == "__main__":
    unittest.main()
