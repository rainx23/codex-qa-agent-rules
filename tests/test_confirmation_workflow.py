from __future__ import annotations

import copy
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from file_hash_utils import stable_file_content_hash
from qa_contracts import (
    DIMENSIONS, load_json, manifest_schema, read_rule_version,
    validate_requirement_model, validate_schema_shape,
)
from qa_workflow import (
    WorkflowError, apply_confirmation_answers, parse_confirmation_answers,
    prepare_confirmation_checkpoint,
)
from render_confirmation_summary import render_confirmation_summary
from validate_manifest import validate_manifest_file
from validate_release import release_commands
from validate_task import run_task_validation


class ConfirmationWorkflowTests(unittest.TestCase):
    def base_model(self) -> dict:
        data = load_json(ROOT / "tests/fixtures/models/requirement-analysis.json")
        data["condition_matrix_applicability"] = {
            "status": "not_required", "dimension_ids": [],
            "reason": "通用 Fixture 未列出两个及以上组合条件维度",
            "evidence_references": [],
        }
        return data

    def original_scope(self) -> dict:
        return {
            "request_id": "REQ-ORIGINAL-001",
            "request_text": "根据指定规则路径，对以下需求进行分析和编写测试用例。",
            "rule_paths": ["rules/core"],
            "source_ids": ["REQ-001"],
            "requested_deliverables": [
                "requirement_analysis", "risk_coverage_matrix", "testcase_model",
                "xmind_markdown", "xmind_workbook", "manifest", "index",
            ],
            "authorized_at": "2026-07-22 10:00:00",
            "continuation_policy": "auto_resume",
        }

    def pending_model(self) -> dict:
        data = self.base_model()
        evidence = copy.deepcopy(data["facts"][0]["evidence_references"])
        for number, statement in ((3, "核心入口尚未确认"), (4, "核心状态口径尚未确认")):
            fact = copy.deepcopy(data["facts"][0])
            fact.update(
                fact_id=f"FACT-{number:03d}", category="missing", statement=statement,
                handling="等待集中确认", affects_core_expectation=True,
            )
            data["facts"].append(fact)
        data["confirmation_points"] = [
            {
                "confirmation_id": "CONF-001", "severity": "blocking", "statement": "确认入口",
                "question": "核心入口是什么？", "current_evidence": "材料仅说明存在查询入口",
                "uncertainty": "无法确定入口 A 或 B", "impact_scope": ["FACT-003", "condition_matrix", "TC"],
                "answer_options": ["A", "B"], "current_handling": "暂停下游生成",
                "fact_ids": ["FACT-003"], "status": "pending",
            },
            {
                "confirmation_id": "CONF-002", "severity": "blocking", "statement": "确认状态口径",
                "question": "状态以哪个口径为准？", "current_evidence": "两处材料口径不同",
                "uncertainty": "无法确定优先级", "impact_scope": ["FACT-004", "acceptance_criteria", "TC"],
                "answer_options": [], "current_handling": "暂停下游生成",
                "fact_ids": ["FACT-004"], "status": "pending",
            },
        ]
        data["condition_matrix_applicability"] = {
            "status": "blocked", "dimension_ids": ["entry", "state"],
            "reason": "入口与状态口径待确认", "evidence_references": evidence,
            "confirmation_ids": ["CONF-001", "CONF-002"], "missing_fact_ids": ["FACT-003", "FACT-004"],
        }
        checkpoint, ready = prepare_confirmation_checkpoint(
            data, self.original_scope(), checkpoint_id="RAC-001", created_at="2026-07-22 10:01:00",
        )
        self.assertFalse(ready)
        return checkpoint

    def reply_evidence(self) -> list[dict]:
        path = ROOT / "tests/fixtures/evidence/confirmation-reply.txt"
        return [{
            "source_type": "user_confirmation", "storage_type": "snapshot",
            "source_path": None, "snapshot_path": path.relative_to(ROOT).as_posix(),
            "source_record_id": "chat:reply-001", "line_start": 1, "line_end": 2,
            "commit_sha": None, "content_hash": stable_file_content_hash(path),
            "excerpt": path.read_text(encoding="utf-8").rstrip("\n"),
            "captured_at": "2026-07-22 10:05:00", "captured_timezone": "Asia/Shanghai",
            "evidence_status": "current", "stale_reason": None, "working_tree_evidence": False,
        }]

    def fact_updates(self) -> dict:
        evidence = self.reply_evidence()
        return {
            "FACT-003": {"category": "confirmed", "statement": "用户确认核心入口为 A", "source_type": "user_confirmation", "source_reference": "chat:reply-001", "confidence": "high", "handling": None, "evidence_references": evidence},
            "FACT-004": {"category": "confirmed", "statement": "用户确认按产品口径处理状态", "source_type": "user_confirmation", "source_reference": "chat:reply-001", "confidence": "high", "handling": None, "evidence_references": evidence},
        }

    def test_one_request_preserves_complete_original_scope(self):
        model = self.pending_model()
        self.assertEqual(self.original_scope(), model["original_task_scope"])

    def test_no_confirmation_auto_enters_phase_two(self):
        model, ready = prepare_confirmation_checkpoint(
            self.base_model(), self.original_scope(), checkpoint_id="RAC-002", created_at="2026-07-22 10:01:00",
        )
        self.assertTrue(ready)
        self.assertEqual("formal_generation", model["workflow_stage"])

    def test_first_stage_does_not_resume_when_requirement_model_is_invalid(self):
        data = self.base_model()
        data["facts"][0]["evidence_references"][0]["content_hash"] = "sha256:" + "0" * 64
        model, ready = prepare_confirmation_checkpoint(
            data, self.original_scope(), checkpoint_id="RAC-INVALID", created_at="2026-07-22 10:01:00",
        )
        self.assertFalse(ready)
        self.assertEqual("confirmation_only", model["workflow_stage"])

    def test_confirmation_only_has_no_risk_matrix(self):
        self.assertNotIn("risk_matrix_path", self.pending_model())

    def test_confirmation_only_has_no_testcase_model(self):
        self.assertNotIn("testcase_model_path", self.pending_model())

    def test_confirmation_only_has_no_xmind_or_workbook(self):
        model = self.pending_model()
        self.assertFalse(any(key in model for key in ("xmind_md_path", "xmind_path")))

    def test_confirmation_only_has_no_manifest_or_index(self):
        model = self.pending_model()
        self.assertFalse(any(key in model for key in ("manifest_path", "index_path")))
        self.assertEqual([], model["confirmation_checkpoint"]["downstream_artifacts_generated"])

    def test_scan_continues_after_first_problem_and_renders_all(self):
        model = self.pending_model()
        self.assertTrue(model["confirmation_checkpoint"]["confirmation_scan_completed"])
        self.assertEqual(set(DIMENSIONS), set(model["confirmation_checkpoint"]["test_dimensions_scanned"]))
        text = render_confirmation_summary(model)
        self.assertLess(text.index("CONF-001"), text.index("CONF-002"))

    def test_multi_answer_auto_resumes(self):
        model = self.pending_model()
        answers = parse_confirmation_answers("CONF-001=A；CONF-002=按产品口径；")
        updated, transition = apply_confirmation_answers(
            model, answers, reply_evidence=self.reply_evidence(), resolved_at="2026-07-22 10:05:00",
            fact_updates=self.fact_updates(),
        )
        self.assertTrue(transition["auto_resume"])
        self.assertEqual("formal_generation", updated["workflow_stage"])
        self.assertEqual([], validate_requirement_model(updated))

    def test_answer_without_core_fact_update_does_not_auto_resume(self):
        updated, transition = apply_confirmation_answers(
            self.pending_model(), parse_confirmation_answers("CONF-001=A；CONF-002=按产品口径；"),
            reply_evidence=self.reply_evidence(), resolved_at="2026-07-22 10:05:00",
        )
        self.assertFalse(transition["auto_resume"])
        self.assertEqual("confirmation_only", updated["workflow_stage"])
        self.assertEqual(2, transition["readiness_summary"]["unresolved_core_fact_count"])
        self.assertTrue(transition["validation_errors"])

    def test_partial_answer_leaves_omitted_confirmation_pending(self):
        model = self.pending_model()
        updated, transition = apply_confirmation_answers(
            model, parse_confirmation_answers("CONF-001=A"), reply_evidence=self.reply_evidence(),
            resolved_at="2026-07-22 10:05:00", fact_updates={"FACT-003": self.fact_updates()["FACT-003"]},
        )
        self.assertFalse(transition["auto_resume"])
        self.assertEqual("pending", next(item for item in updated["confirmation_points"] if item["confirmation_id"] == "CONF-002")["status"])

    def test_partial_answer_rerender_only_details_pending_confirmation(self):
        updated, _ = apply_confirmation_answers(
            self.pending_model(), parse_confirmation_answers("CONF-001=A"),
            reply_evidence=self.reply_evidence(), resolved_at="2026-07-22 10:05:00",
            fact_updates={"FACT-003": self.fact_updates()["FACT-003"]},
        )
        text = render_confirmation_summary(updated)
        self.assertIn("已处理确认 ID：CONF-001", text)
        self.assertNotIn("### CONF-001", text)
        self.assertNotIn("核心入口是什么？", text)
        self.assertIn("### CONF-002", text)
        self.assertIn("状态以哪个口径为准？", text)

    def test_skipped_confirmation_is_only_listed_in_processed_summary(self):
        updated, transition = apply_confirmation_answers(
            self.pending_model(), parse_confirmation_answers("CONF-001=跳过并保留风险"),
            reply_evidence=self.reply_evidence(), resolved_at="2026-07-22 10:05:00",
        )
        text = render_confirmation_summary(updated)
        self.assertFalse(transition["auto_resume"])
        self.assertIn("已处理确认 ID：CONF-001", text)
        self.assertNotIn("### CONF-001", text)
        self.assertIn("### CONF-002", text)

    def test_answer_does_not_require_reauthorization(self):
        model = self.pending_model()
        updated, _ = apply_confirmation_answers(
            model, parse_confirmation_answers("CONF-001=A"), reply_evidence=self.reply_evidence(),
            resolved_at="2026-07-22 10:05:00", fact_updates={"FACT-003": self.fact_updates()["FACT-003"]},
        )
        self.assertEqual(self.original_scope(), updated["original_task_scope"])

    def test_only_affected_fact_can_be_updated(self):
        with self.assertRaises(WorkflowError):
            apply_confirmation_answers(
                self.pending_model(), parse_confirmation_answers("CONF-001=A"),
                reply_evidence=self.reply_evidence(), resolved_at="2026-07-22 10:05:00",
                fact_updates={"FACT-001": {"statement": "不得修改"}},
            )

    def test_confirmation_only_keeps_historical_pending_manifest_contract(self):
        fixture = load_json(ROOT / "tests/fixtures/anti_hallucination/pending_draft_manifest.json")
        data = load_json(ROOT / "testcases/manifest.example.json")
        data.update(fixture["valid"])
        self.assertNotIn("workflow_stage", data)
        self.assertEqual([], validate_schema_shape(data, manifest_schema(read_rule_version(ROOT))))

    def test_confirmation_only_keeps_existing_passed_artifact_valid(self):
        _, errors = validate_manifest_file(ROOT / "testcases/manifest.example.json")
        self.assertEqual([], errors)

    @patch("validate_task.validate_manifest_file", return_value=({"validation_status": "pending"}, []))
    @patch("validate_task.subprocess.run")
    def test_fast_validation_does_not_run_full_suite_or_history(self, run, _manifest):
        run.return_value = subprocess.CompletedProcess([], 0)
        errors = run_task_validation(ROOT / "testcases/manifest.example.json", ROOT / "testcases/index.md", [])
        self.assertEqual([], errors)
        commands = [" ".join(call.args[0]) for call in run.call_args_list]
        self.assertFalse(any("unittest discover" in command or "validate_formal_artifacts" in command for command in commands))

    def test_release_validation_retains_full_gates(self):
        commands = [" ".join(command) for command in release_commands()]
        for token in (
            "unittest discover -s tests -v", "validate_formal_artifacts.py", "generate_schemas.py --check",
            "validate_skill_contracts.py", "validate_rule_version.py", "validate_repository_docs.py",
            "validate_knowledge.py", "validate_ci_workflow.py",
        ):
            self.assertTrue(any(token in command for command in commands), token)

    def test_first_phase_chat_has_no_formal_artifact_paths(self):
        text = render_confirmation_summary(self.pending_model())
        for forbidden in (".xmind`", "manifest.json", "testcases/index.md", "risk-coverage-matrix.json"):
            self.assertNotIn(forbidden, text)
        self.assertIn("均未生成", text)

    def test_second_phase_still_uses_existing_manifest_chain(self):
        data, errors = validate_manifest_file(ROOT / "testcases/manifest.example.json")
        self.assertEqual("passed", data["validation_status"])
        self.assertEqual([], errors)

    def test_rule_version_is_2_18_0(self):
        self.assertEqual("2.19.0", read_rule_version(ROOT))


if __name__ == "__main__":
    unittest.main()
