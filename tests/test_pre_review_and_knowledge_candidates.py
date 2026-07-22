from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from file_hash_utils import stable_file_content_hash
from qa_contracts import load_json, validate_knowledge_candidate, validate_requirement_model
from qa_modes import (
    KNOWLEDGE_CANDIDATE_PROMPT, ModeError, detect_requirement_mode,
    extract_candidates, is_extract_candidate_requested, prepare_pre_review,
    render_candidate_extraction_offer, render_pre_review_summary,
    should_offer_candidate_extraction,
)
from qa_workflow import WorkflowError, prepare_confirmation_checkpoint


class PreReviewAndKnowledgeCandidateTests(unittest.TestCase):
    def base_model(self) -> dict:
        return load_json(ROOT / "tests/fixtures/models/requirement-analysis.json")

    def completed_model(self) -> dict:
        model = self.base_model()
        model["workflow_stage"] = "completed"
        return model

    def pre_review_model(self) -> dict:
        issues = [{
            "issue_id": "ISSUE-001", "issue_type": "missing", "severity": "blocking",
            "statement": "角色权限未定义", "current_evidence": "材料只描述查询行为",
            "impact": "无法判断访问边界", "confirmation_question": "哪些角色可以访问？",
        }]
        return prepare_pre_review(self.base_model(), issues, "conditionally_ready")

    def candidate_spec(self, *, fact_id: str = "FACT-001") -> dict:
        return {
            "knowledge_type": "field_rule", "statement": "客户编号使用精确过滤",
            "source_fact_ids": [fact_id], "source_confirmation_ids": [],
            "applicable_scope": "客户查询", "existing_knowledge_ids": [],
            "comparison_result": "missing", "conflict_reason": None,
        }

    def blocking_confirmation(self, *, status: str = "pending", severity: str = "blocking") -> dict:
        point = {
            "confirmation_id": "CONF-001", "severity": severity, "statement": "确认规则",
            "fact_ids": ["FACT-001"], "status": status,
        }
        if status == "skipped":
            point.update(
                skip_reason="用户跳过", decision_evidence=copy.deepcopy(
                    self.base_model()["facts"][0]["evidence_references"]
                ),
            )
        return point

    def test_explicit_review_enters_pre_review_but_delivery_request_does_not(self):
        self.assertEqual("pre_review", detect_requirement_mode("请进行需求预审，检查缺失和歧义"))
        self.assertEqual("pre_review", detect_requirement_mode("只做需求评审，暂不生成用例"))
        self.assertEqual("delivery", detect_requirement_mode("需求评审后生成测试用例"))
        self.assertEqual("delivery", detect_requirement_mode("需求预审并输出 XMind"))
        self.assertEqual("delivery", detect_requirement_mode("分析需求并编写测试用例"))

    def test_pre_review_has_required_output_and_no_downstream_or_auto_resume(self):
        model = self.pre_review_model()
        self.assertEqual([], validate_requirement_model(model))
        self.assertEqual([], model["risks"])
        self.assertNotIn("original_task_scope", model)
        self.assertNotIn("confirmation_checkpoint", model)
        summary = render_pre_review_summary(model)
        for heading in ("预审范围", "需求理解", "已明确内容", "缺失、冲突和歧义", "边界、异常和可测试性问题", "待确认问题", "风险影响", "结论"):
            self.assertIn(f"## {heading}", summary)
        for forbidden in ("Risk Matrix", "Testcase Model", ".xmind", "Manifest", "Index", "SQL"):
            self.assertNotIn(forbidden, summary)
        with self.assertRaises(WorkflowError):
            prepare_confirmation_checkpoint(model, {}, checkpoint_id="RAC-X", created_at="2026-07-22 10:00:00")

    def test_default_does_not_extract_and_success_only_offers_once(self):
        self.assertFalse(is_extract_candidate_requested("分析需求并编写测试用例"))
        self.assertTrue(is_extract_candidate_requested("完成后提取知识候选"))
        self.assertTrue(is_extract_candidate_requested("提取", offer_pending=True))
        self.assertTrue(is_extract_candidate_requested("提取这些", offer_pending=True))
        self.assertFalse(is_extract_candidate_requested("提取", offer_pending=False))
        self.assertFalse(is_extract_candidate_requested("提取报告", offer_pending=True))
        model = self.completed_model()
        self.assertTrue(should_offer_candidate_extraction(
            model, reusable_fact_ids=["FACT-001"], formal_validation_passed=True,
        ))
        self.assertEqual("本次存在可能可复用的已确认规则，是否提取为知识候选？", KNOWLEDGE_CANDIDATE_PROMPT)
        self.assertFalse(should_offer_candidate_extraction(
            model, reusable_fact_ids=["FACT-001"], formal_validation_passed=True,
            prompt_already_shown=True,
        ))
        with self.assertRaises(ModeError):
            extract_candidates(model, [self.candidate_spec()], explicitly_requested=False)

    def test_offer_renders_short_rule_summaries_without_triggering_actions(self):
        model = self.completed_model()
        with patch("qa_modes.extract_candidates") as extract, \
                patch("qa_modes.search", create=True) as search, \
                patch("qa_modes.compare", create=True) as compare, \
                patch("qa_modes.persist", create=True) as persist:
            text = render_candidate_extraction_offer(
                model, reusable_fact_ids=["FACT-001"], formal_validation_passed=True,
            )
        self.assertIn("本次发现 1 条可能可复用的已确认规则", text)
        self.assertIn(model["facts"][0]["statement"], text)
        self.assertIn("是否提取为知识候选？", text)
        for action in (extract, search, compare, persist):
            action.assert_not_called()
        self.assertEqual("", render_candidate_extraction_offer(model, formal_validation_passed=True))
        self.assertEqual("", render_candidate_extraction_offer(
            model, reusable_fact_ids=["FACT-001"], formal_validation_passed=True,
            prompt_already_shown=True,
        ))

    def test_extract_candidate_enforces_completed_valid_unblocked_model(self):
        for stage in ("confirmation_only", "formal_generation"):
            model = self.completed_model()
            model["workflow_stage"] = stage
            with self.subTest(stage=stage), self.assertRaisesRegex(ModeError, "workflow_stage=completed"):
                extract_candidates(model, [self.candidate_spec()], explicitly_requested=True)

        blocking = self.completed_model()
        blocking["confirmation_points"] = [self.blocking_confirmation()]
        with self.assertRaisesRegex(ModeError, "blocking_pending_count=1"):
            extract_candidates(blocking, [self.candidate_spec()], explicitly_requested=True)

        skipped = self.completed_model()
        skipped["confirmation_points"] = [self.blocking_confirmation(status="skipped", severity="nonblocking")]
        with self.assertRaisesRegex(ModeError, "skipped_core_count=1"):
            extract_candidates(skipped, [self.candidate_spec()], explicitly_requested=True)

        unresolved = self.completed_model()
        missing_fact = copy.deepcopy(unresolved["facts"][0])
        missing_fact.update(
            fact_id="FACT-003", category="missing", statement="核心规则未确认",
            handling="等待确认核心规则",
        )
        unresolved["facts"].append(missing_fact)
        unresolved["confirmation_points"] = [{
            "confirmation_id": "CONF-003", "severity": "blocking", "statement": "确认核心规则",
            "fact_ids": ["FACT-003"], "status": "pending",
        }]
        with self.assertRaisesRegex(ModeError, "unresolved_core_fact_count=1"):
            extract_candidates(unresolved, [self.candidate_spec()], explicitly_requested=True)

        invalid = self.completed_model()
        invalid.pop("business_goal")
        with self.assertRaisesRegex(ModeError, "Requirement Analysis Model 校验失败"):
            extract_candidates(invalid, [self.candidate_spec()], explicitly_requested=True)

    def test_resolved_confirmation_with_only_code_context_is_rejected(self):
        model = self.completed_model()
        source = ROOT / "tests/fixtures/sources/customer-query.java"
        evidence = [{
            "source_type": "code_context", "storage_type": "file",
            "source_path": source.relative_to(ROOT).as_posix(), "snapshot_path": None,
            "source_record_id": "code:customer-query", "line_start": 1, "line_end": 1,
            "commit_sha": None, "content_hash": stable_file_content_hash(source),
            "excerpt": source.read_text(encoding="utf-8").splitlines()[0],
            "captured_at": "2026-07-22 10:00:00", "captured_timezone": "Asia/Shanghai",
            "evidence_status": "current", "stale_reason": None, "working_tree_evidence": True,
        }]
        model["confirmation_points"] = [{
            "confirmation_id": "CONF-009", "severity": "nonblocking", "statement": "确认代码行为",
            "fact_ids": ["FACT-001"], "status": "resolved", "resolution": "按当前代码行为处理",
            "resolution_evidence_references": evidence, "resolved_at": "2026-07-22 10:00:00",
        }]
        spec = self.candidate_spec()
        spec["source_fact_ids"] = []
        spec["source_confirmation_ids"] = ["CONF-009"]
        with self.assertRaisesRegex(ModeError, "不得仅由 code_context"):
            extract_candidates(model, [spec], explicitly_requested=True, evidence_root=ROOT)

    def test_prompt_is_suppressed_for_pre_review_blocking_or_no_reusable_rule(self):
        self.assertFalse(should_offer_candidate_extraction(
            self.pre_review_model(), reusable_fact_ids=["FACT-001"], formal_validation_passed=True,
        ))
        model = self.completed_model()
        model["facts"][0]["category"] = "missing"
        model["confirmation_points"] = [{
            "confirmation_id": "CONF-001", "severity": "blocking", "statement": "确认规则",
            "fact_ids": ["FACT-001"], "status": "pending",
        }]
        self.assertFalse(should_offer_candidate_extraction(
            model, reusable_fact_ids=["FACT-001"], formal_validation_passed=True,
        ))
        self.assertFalse(should_offer_candidate_extraction(
            self.completed_model(), formal_validation_passed=True,
        ))

    def test_candidate_accepts_only_confirmed_or_resolved_sources_and_never_persists(self):
        model = self.completed_model()
        result = extract_candidates(
            model, [self.candidate_spec()], explicitly_requested=True, evidence_root=ROOT,
        )
        self.assertEqual([], validate_knowledge_candidate(result, evidence_root=ROOT))
        self.assertEqual("candidate", result["candidates"][0]["status"])
        self.assertEqual("create", result["candidates"][0]["recommended_action"])
        self.assertNotIn("persist", result)

        inferred = copy.deepcopy(model)
        inferred["facts"][0]["category"] = "inferred"
        with self.assertRaises(ModeError):
            extract_candidates(inferred, [self.candidate_spec()], explicitly_requested=True)

        skipped = copy.deepcopy(model)
        skipped["confirmation_points"] = [{
            "confirmation_id": "CONF-009", "severity": "nonblocking", "statement": "跳过规则",
            "fact_ids": ["FACT-001"], "status": "skipped",
        }]
        spec = self.candidate_spec()
        spec["source_fact_ids"] = []
        spec["source_confirmation_ids"] = ["CONF-009"]
        with self.assertRaises(ModeError):
            extract_candidates(skipped, [spec], explicitly_requested=True)


if __name__ == "__main__":
    unittest.main()
