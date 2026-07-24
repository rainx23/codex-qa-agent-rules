from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import md_to_xmind
import validate_delivery_summary
import validate_models
import validate_task


class OnePassPipelineTests(unittest.TestCase):
    def test_validate_models_loads_each_model_once(self):
        requirement = Path("requirement.json")
        diff = Path("diff.json")
        risk = Path("risk.json")
        testcase = Path("testcase.json")
        payloads = [
            {"facts": []},
            {"change_items": []},
            {"risk_items": []},
            {"cases": []},
        ]
        with patch.object(validate_models, "load_json", side_effect=payloads) as loader, patch.object(
            validate_models, "_evidence_root", return_value=ROOT
        ):
            loaded = validate_models.load_models(requirement, diff, risk, testcase)
        self.assertEqual(4, loader.call_count)
        self.assertEqual(payloads, list(loaded[:4]))

    def test_md_to_xmind_main_parses_markdown_once(self):
        outline = SimpleNamespace(warnings=[], root=SimpleNamespace(title="Root"), tc_nodes=[])
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "case_xmind.md"
            output = Path(directory) / "case.xmind"
            source.write_text("# Root\n", encoding="utf-8")
            with patch.object(md_to_xmind, "validate_markdown_file", return_value=outline) as parser, patch.object(
                md_to_xmind, "convert_outline", return_value=output
            ) as converter:
                result = md_to_xmind.main([str(source), "-o", str(output)])
        self.assertEqual(0, result)
        parser.assert_called_once()
        converter.assert_called_once()

    def test_delivery_summary_validation_does_not_render_again(self):
        summary = "\n".join([
            "## 处理结果", "validation_status：failed", "sql_status：不适用",
            "## 待确认点", "- 无",
            "## 主要交付文件", "- 未生成",
            "## 追踪和校验文件", "- 未生成",
            "## 测试维度覆盖", "- 不适用",
            "## 校验结果", "- Manifest：失败",
            "## 未执行事项", "- 未执行",
        ])
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({
                "validation_status": "failed",
                "analysis_model_paths": [],
                "testcase_model_path": None,
                "draft_testcase_model_path": None,
                "xmind_md_path": None,
                "draft_xmind_md_path": None,
                "xmind_path": None,
            }), encoding="utf-8")
            errors = validate_delivery_summary.validate_summary(summary, manifest)
        self.assertEqual([], errors)

    def test_validate_task_records_actual_stages_and_captures_subprocess_output(self):
        completed = SimpleNamespace(returncode=0, stdout="PASS\n", stderr="")
        records: list[dict] = []
        with patch.object(validate_task, "validate_manifest_file", return_value=({"validation_status": "pending"}, [])), patch.object(
            validate_task.subprocess, "run", return_value=completed
        ) as runner:
            errors = validate_task.run_task_validation(
                Path("manifest.json"), Path("index.md"), ["tests.test_example"], records
            )
        self.assertEqual([], errors)
        self.assertEqual(
            ["validate_manifest_bundle", "validate_current_index_entry", "unittest:tests.test_example", "git_diff_check"],
            [record["stage"] for record in records],
        )
        self.assertTrue(all(record["status"] == "passed" for record in records))
        self.assertTrue(all(call.kwargs.get("capture_output") is True for call in runner.call_args_list))

    def test_daily_skill_excludes_release_only_full_scans(self):
        text = (ROOT / "skills/qa-artifact-validation/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("日常业务交付最终只运行一次", text)
        self.assertIn("validate_schemas.py` 只用于规则发布和 CI", text)
        self.assertIn("不得执行 `validate_testcase_index.py` 全量扫描历史 Manifest", text)


if __name__ == "__main__":
    unittest.main()
