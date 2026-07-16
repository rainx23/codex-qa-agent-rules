import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/models/api-automation-valid.json"


class ApiAutomationTests(unittest.TestCase):
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
            checked = self.run_tool("scripts/validate_api_automation_artifacts.py", "--excel", str(excel), "--parameters", str(parameters))
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
            checked = self.run_tool("scripts/validate_api_automation_artifacts.py", "--excel", str(excel), "--parameters", str(parameters))
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
