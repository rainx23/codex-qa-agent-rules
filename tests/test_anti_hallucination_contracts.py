from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from parse_chat_ddl import parse_ddl, parse_partial_fields
from qa_contracts import (
    load_json, validate_api_automation, validate_diff_model, validate_model_links,
    validate_requirement_model, validate_risk_matrix, validate_testcase_model,
)
from validate_manifest import validate_manifest_data
from validate_models import validate_files
from validate_sql_style import validate_sql
from validate_evidence import _is_absolute_evidence_path, validate_evidence_reference

MODELS = ROOT / "tests/fixtures/models"


class AntiHallucinationContractTests(unittest.TestCase):
    def test_evidence_path_absolute_detection_is_cross_platform(self):
        for value in ("/outside.md", "C:/outside.md", r"C:\outside.md", r"\\server\share\outside.md"):
            self.assertTrue(_is_absolute_evidence_path(value), value)
        for value in ("tests/fixtures/sources/acceptance-REQ-001.md", "rules/core/evidence-rules.md"):
            self.assertFalse(_is_absolute_evidence_path(value), value)

    def model(self, name: str) -> dict:
        return load_json(MODELS / name)

    def evidence(self, root: Path, *, source_type: str = "requirement", storage_type: str = "file", name: str = "source.md", raw: bytes = b"line one\nobservable value\n") -> dict:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path_field = "source_path" if storage_type == "file" else "snapshot_path"
        return {
            "source_type": source_type,
            "storage_type": storage_type,
            "source_path": name if path_field == "source_path" else None,
            "snapshot_path": name if path_field == "snapshot_path" else None,
            "source_record_id": "attachment:SCREEN-001" if source_type == "screenshot" else "chat:CONV-1:MSG-1" if source_type == "user_confirmation" else "REQ-001",
            "line_start": None if name.endswith(".png") else 1,
            "line_end": None if name.endswith(".png") else 2,
            "commit_sha": "def456a" if source_type in {"diff", "code_context"} else None,
            "content_hash": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "excerpt": "observable value" if not name.endswith(".png") else "截图直接显示客户编号输入框",
            "captured_at": "2026-07-17 12:00:00",
            "captured_timezone": "Asia/Shanghai",
            "evidence_status": "current",
        }

    def test_confirmed_fact_rejects_inference_low_and_guess(self):
        for mutation in (("source_type", "inference"), ("source_type", "code_context"), ("source_type", "screenshot"), ("confidence", "low"), ("source_reference", "根据名称判断")):
            data = self.model("requirement-analysis.json")
            data["facts"][0][mutation[0]] = mutation[1]
            self.assertTrue(validate_requirement_model(data), mutation)

    def test_confirmed_requirement_fact_passes(self):
        self.assertEqual([], validate_requirement_model(self.model("requirement-analysis.json")))

    def test_zentao_current_evidence_requires_real_file_or_snapshot(self):
        data = self.model("requirement-analysis.json")
        fact = data["facts"][0]
        fact["source_type"] = "zentao_section_3"
        fact["source_reference"] = "REQ-001 第三部分"
        fact["evidence_references"] = [{
            "source_type": "zentao_section_3",
            "source_path": None,
            "line_start": None,
            "line_end": None,
            "commit_sha": None,
            "content_hash": None,
            "excerpt": "客户编号采用精确匹配",
            "captured_at": "2026-07-17 12:00:00",
            "captured_timezone": "Asia/Shanghai",
            "evidence_status": "current",
        }]
        self.assertTrue(validate_requirement_model(data))

    def test_evidence_path_safety_and_real_file_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = self.evidence(root)
            self.assertEqual([], validate_evidence_reference(evidence, root=root, confirmed=True))
            for value, token in (
                ("missing.md", "不存在"),
                (str((root / "source.md").resolve()), "绝对路径"),
                ("../outside.md", "../"),
            ):
                changed = copy.deepcopy(evidence)
                changed["source_path"] = value
                self.assertTrue(any(token in error for error in validate_evidence_reference(changed, root=root)), value)
            changed = copy.deepcopy(evidence)
            changed["source_path"] = "directory"
            (root / "directory").mkdir()
            self.assertTrue(any("必须指向文件" in error for error in validate_evidence_reference(changed, root=root)))

    def test_evidence_symlink_or_junction_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(directory)
            outside = Path(outside_directory)
            (outside / "source.md").write_text(
                "line one\nobservable value\n",
                encoding="utf-8",
            )
            link = root / "outside-link"

            if os.name == "nt":
                script = (
                    f"New-Item -ItemType Junction "
                    f"-Path '{link}' -Target '{outside}' | Out-Null"
                )
                completed = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", script],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(0, completed.returncode, completed.stderr)
            else:
                link.symlink_to(outside, target_is_directory=True)

            try:
                evidence = self.evidence(root)
                evidence["source_path"] = "outside-link/source.md"
                self.assertTrue(
                    any(
                        "越出仓库" in error
                        for error in validate_evidence_reference(evidence, root=root)
                    )
                )
            finally:
                if os.name == "nt":
                    os.rmdir(link)
                else:
                    link.unlink()

    def test_current_stale_and_reconfirm_hash_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = self.evidence(root)
            self.assertEqual([], validate_evidence_reference(evidence, root=root, confirmed=True))
            evidence["content_hash"] = "sha256:" + "0" * 64
            self.assertTrue(any("content_hash 与文件不一致" in error for error in validate_evidence_reference(evidence, root=root)))
            for status in ("stale", "reconfirm_required"):
                changed = copy.deepcopy(evidence)
                changed.update(evidence_status=status, stale_reason="来源内容变化")
                errors = validate_evidence_reference(changed, root=root, confirmed=True)
                self.assertTrue(any("不得单独支撑 confirmed" in error for error in errors), status)

    def test_text_line_range_excerpt_and_binary_screenshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = self.evidence(root)
            for mutation, token in (
                ({"line_start": 1, "line_end": 99}, "超出文件范围"),
                ({"line_start": 2, "line_end": 1}, "行号范围非法"),
                ({"excerpt": "not present"}, "excerpt 不在"),
                ({"line_start": None, "line_end": None}, "必须同时提供"),
            ):
                changed = copy.deepcopy(evidence)
                changed.update(mutation)
                self.assertTrue(any(token in error for error in validate_evidence_reference(changed, root=root)), mutation)
            screenshot = self.evidence(
                root, source_type="screenshot", storage_type="file", name="screenshot.png",
                raw=b"\x89PNG\r\n\x1a\nfixture",
            )
            self.assertEqual([], validate_evidence_reference(screenshot, root=root, confirmed=True))
            missing_screenshot = copy.deepcopy(screenshot)
            missing_screenshot["source_path"] = "missing-screenshot.png"
            self.assertTrue(validate_evidence_reference(missing_screenshot, root=root))
            unhashed_screenshot = copy.deepcopy(screenshot)
            unhashed_screenshot["content_hash"] = None
            self.assertTrue(validate_evidence_reference(unhashed_screenshot, root=root))
            screenshot["excerpt"] = "因此可以推断业务处理正确"
            self.assertTrue(any("不得包含推断" in error for error in validate_evidence_reference(screenshot, root=root)))

    def test_snapshot_sources_require_real_content_and_record_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for source_type in ("zentao_section_3", "acceptance_criteria", "formal_change_record"):
                invalid = self.evidence(root, source_type=source_type)
                invalid.update(storage_type="snapshot", source_path=None, snapshot_path=None)
                self.assertTrue(validate_evidence_reference(invalid, root=root), source_type)
            zentao = self.evidence(root, source_type="zentao_section_3", storage_type="snapshot", name="zentao.md")
            self.assertEqual([], validate_evidence_reference(zentao, root=root, confirmed=True))
            confirmation = self.evidence(root, source_type="user_confirmation", storage_type="snapshot", name="chat.md")
            self.assertEqual([], validate_evidence_reference(confirmation, root=root, confirmed=True))
            changed_hash = copy.deepcopy(confirmation)
            changed_hash["content_hash"] = "sha256:" + "0" * 64
            self.assertTrue(any(
                "content_hash 与文件不一致" in error
                for error in validate_evidence_reference(changed_hash, root=root)
            ))
            confirmation["snapshot_path"] = None
            self.assertTrue(validate_evidence_reference(confirmation, root=root))

    def test_fact_source_consistency_and_confirmed_current_gate(self):
        data = self.model("requirement-analysis.json")
        data["facts"][0]["evidence_references"][0]["source_type"] = "markdown"
        self.assertTrue(any("主 source_type" in error for error in validate_requirement_model(data)))
        data = self.model("requirement-analysis.json")
        current = data["facts"][0]["evidence_references"][0]
        stale = copy.deepcopy(current)
        stale.update(evidence_status="stale", content_hash="sha256:" + "0" * 64, stale_reason="旧版本证据")
        data["facts"][0]["evidence_references"] = [current, stale]
        self.assertEqual([], validate_requirement_model(data))
        data["facts"][0]["evidence_references"] = [stale]
        self.assertTrue(any("真实且 current" in error for error in validate_requirement_model(data)))

    def test_diff_evidence_matches_change_file_and_commit(self):
        data = self.model("diff-impact.json")
        self.assertEqual([], validate_diff_model(data))
        changed = copy.deepcopy(data)
        changed["change_items"][0]["evidence_references"][0]["source_path"] = "tests/fixtures/sources/requirement.md"
        self.assertTrue(any("必须等于 change.file" in error for error in validate_diff_model(changed)))
        changed = copy.deepcopy(data)
        changed["changed_files"] = []
        self.assertTrue(any("不在 changed_files" in error for error in validate_diff_model(changed)))
        for commit_sha in (None, "not-a-sha"):
            changed = copy.deepcopy(data)
            changed["change_items"][0]["evidence_references"][0]["commit_sha"] = commit_sha
            self.assertTrue(any("commit_sha" in error for error in validate_diff_model(changed)), commit_sha)
        working_tree = copy.deepcopy(data)
        working_tree_evidence = working_tree["change_items"][0]["evidence_references"][0]
        working_tree_evidence.update(commit_sha=None, working_tree_evidence=True)
        self.assertEqual([], validate_diff_model(working_tree))

    def test_incomplete_ddl_is_not_complete_and_partial_keeps_unknowns(self):
        parsed = parse_ddl("create table demo.a (id bigint, ??? unsupported);")["tables"][0]
        self.assertEqual("partial", parsed["schema_scope"])
        self.assertTrue(parsed["parse_warnings"])
        partial = parse_partial_fields("name varchar(20)", "demo.a")["tables"][0]
        self.assertIsNone(partial["fields"][0]["nullable"])
        self.assertIn("nullable", partial["fields"][0]["unknown_fields"])

    def test_suspected_defect_requires_two_sided_evidence(self):
        requirement = self.model("requirement-analysis.json")
        diff = self.model("diff-impact.json")
        defect = {"defect_id": "DEF001", "title": "过滤条件未生效", "requirement_fact_ids": ["FACT-001"], "change_ids": ["CHG-001"], "evidence_state": "已确认", "observed_behavior": "条件被丢弃", "expected_behavior": "条件被传递", "impact": "返回非目标客户", "confidence": "high", "handling": "需修复", "evidence_references": [copy.deepcopy(diff["change_items"][0]["evidence_references"][0])]}
        diff["suspected_defects"] = [defect]
        self.assertEqual([], validate_diff_model(diff))
        self.assertEqual([], validate_model_links(requirement, diff, self.model("risk-coverage-matrix.json"), self.model("testcase-model.json")))
        diff["suspected_defects"][0]["requirement_fact_ids"] = ["FACT-UNKNOWN"]
        self.assertTrue(any("confirmed Fact" in item for item in validate_model_links(requirement, diff, self.model("risk-coverage-matrix.json"), self.model("testcase-model.json"))))

    def test_risk_without_tc_requires_disposition_and_merged_target(self):
        data = self.model("risk-coverage-matrix.json")
        risk = data["risk_items"][1]
        risk["testcase_ids"] = []
        risk.pop("disposition_status")
        self.assertTrue(any("处置" in item or "必填" in item for item in validate_risk_matrix(data)))
        risk["disposition_status"] = "merged"
        self.assertTrue(any("merged" in item for item in validate_risk_matrix(data)))

    def test_testcase_branch_ids_and_vague_assertions(self):
        data = self.model("testcase-model-multi-entry.json")
        self.assertEqual([], validate_testcase_model(data))
        data["cases"][0]["entry_branches"][1]["branch_id"] = "TC001-B01"
        data["cases"][0]["entry_branches"][0]["expected_results"] = ["返回结果无误"]
        errors = validate_testcase_model(data)
        self.assertTrue(any("branch_id 必须唯一" in item for item in errors))
        self.assertTrue(any("模糊" in item for item in errors))

    def test_blocking_manifest_cannot_pass(self):
        data = load_json(ROOT / "testcases/manifest.example.json")
        data.update({"validation_status": "passed", "blocking_pending_count": 1, "pending_count": 1, "pending_reason": "核心公式未确认"})
        errors = validate_manifest_data(data, ROOT / "testcases/manifest.example.json")
        self.assertTrue(any("必须为 pending" in item for item in errors))
        data["validation_status"] = "pending"
        self.assertFalse(any("必须为 pending" in item for item in validate_manifest_data(data, ROOT / "testcases/manifest.example.json")))

    def test_api_health_check_does_not_claim_business_correctness(self):
        data = self.model("api-automation-valid.json")
        self.assertEqual([], validate_api_automation(data))
        data["evidence"].append("content.code=0 且 content.msg=OK，因此接口业务数据正确")
        self.assertTrue(any("不得宣称业务数据正确" in item for item in validate_api_automation(data)))

    def test_sql_author_comes_from_config(self):
        sql = (ROOT / "tests/fixtures/sql/valid_validation_sql.sql").read_text(encoding="utf-8")
        self.assertEqual([], validate_sql(sql, True, ROOT / "rules-repository.json")[0])
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "rules-repository.json"
            config.write_text(json.dumps({"sql_defaults": {"author": "Other", "timezone": "Asia/Shanghai", "dialect": "starrocks"}}), encoding="utf-8")
            self.assertTrue(validate_sql(sql, True, config)[0])
            self.assertEqual([], validate_sql(sql.replace("author: Rainx", "author: Other"), True, config)[0])

    def test_actual_model_validator(self):
        self.assertEqual([], validate_files(MODELS / "requirement-analysis.json", MODELS / "diff-impact.json", MODELS / "risk-coverage-matrix.json", MODELS / "testcase-model.json"))


if __name__ == "__main__":
    unittest.main()
