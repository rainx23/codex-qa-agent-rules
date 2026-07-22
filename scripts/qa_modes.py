#!/usr/bin/env python3
"""Explicit pre-review routing and read-only knowledge-candidate extraction."""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from qa_contracts import (
    SCHEMA_VERSION, summarize_confirmations, validate_knowledge_candidate,
    validate_requirement_model,
)


PRE_REVIEW_PATTERNS = (
    r"需求(?:预审|评审)",
    r"检查需求(?:是否)?完整",
    r"检查.{0,12}(?:缺失|冲突|歧义)",
    r"只分析需求问题.{0,12}(?:暂不|不要|不)(?:生成|编写)测试用例",
)
EXTRACT_CANDIDATE_PATTERNS = (r"提取(?:为)?知识候选", r"提取知识候选")
FORBIDDEN_REUSABLE_SOURCE_TOKENS = (
    "临时数据", "测试数据", "环境地址", "环境信息", "测试环境", "代码行为", "敏感信息",
)
KNOWLEDGE_CANDIDATE_PROMPT = "本次存在可能可复用的已确认规则，是否提取为知识候选？"


class ModeError(ValueError):
    """Raised when an explicit mode would violate its source boundary."""


def detect_requirement_mode(request_text: str) -> str:
    """Enter pre_review only for an explicit review-only intent."""

    return "pre_review" if any(re.search(pattern, request_text) for pattern in PRE_REVIEW_PATTERNS) else "delivery"


def is_extract_candidate_requested(request_text: str) -> bool:
    """Return true only for an explicit knowledge-candidate extraction request."""

    return any(re.search(pattern, request_text) for pattern in EXTRACT_CANDIDATE_PATTERNS)


def prepare_pre_review(
    requirement_model: dict[str, Any], issues: list[dict[str, Any]], conclusion: str,
) -> dict[str, Any]:
    """Create a pre-review result without entering or preparing formal delivery."""

    model = copy.deepcopy(requirement_model)
    risk_directions = [
        str(item.get("statement")) for item in model.get("risks", [])
        if isinstance(item, dict) and item.get("statement")
    ]
    model["risks"] = []
    model["risk_directions"] = risk_directions
    model["workflow_stage"] = "pre_review"
    model["pre_review_issues"] = copy.deepcopy(issues)
    model["pre_review_conclusion"] = conclusion
    model.pop("original_task_scope", None)
    model.pop("confirmation_checkpoint", None)
    matrix = model.get("condition_matrix")
    if isinstance(matrix, dict):
        for combination in matrix.get("required_combinations", []):
            if isinstance(combination, dict):
                combination["covered_by_tc_ids"] = []
        coverage = matrix.get("coverage_summary")
        if isinstance(coverage, dict):
            coverage["covered_combination_count"] = 0
    for assessment in model.get("test_dimension_assessment", []):
        if isinstance(assessment, dict):
            assessment["risk_ids"] = []
            assessment["testcase_ids"] = []
    return model


def render_pre_review_summary(requirement_model: dict[str, Any]) -> str:
    """Render the fixed review-only chat sections without artifact paths."""

    if requirement_model.get("workflow_stage") != "pre_review":
        raise ModeError("仅 pre_review 模式可渲染需求预审摘要")
    facts = requirement_model.get("facts", [])
    confirmed = [item.get("statement") for item in facts if isinstance(item, dict) and item.get("category") == "confirmed"]
    unresolved = [item.get("statement") for item in facts if isinstance(item, dict) and item.get("category") in {"missing", "conflicting", "inferred"}]
    lines = [
        "## 预审范围", str(requirement_model.get("analysis_scope", "")), "",
        "## 需求理解", str(requirement_model.get("business_goal", "")), "",
        "## 已明确内容", *(f"- {item}" for item in confirmed), "",
        "## 缺失、冲突和歧义", *(f"- {item}" for item in unresolved), "",
        "## 边界、异常和可测试性问题",
    ]
    issues = requirement_model.get("pre_review_issues", [])
    for issue in issues:
        lines.extend([
            f"### {issue.get('issue_id')}",
            f"- issue_type：{issue.get('issue_type')}",
            f"- severity：{issue.get('severity')}",
            f"- statement：{issue.get('statement')}",
            f"- current_evidence：{issue.get('current_evidence')}",
            f"- impact：{issue.get('impact')}",
            f"- confirmation_question：{issue.get('confirmation_question')}",
        ])
    lines.extend(["", "## 待确认问题"])
    confirmations = requirement_model.get("confirmation_points", [])
    lines.extend(
        f"- {item.get('confirmation_id')}：{item.get('question') or item.get('statement')}"
        for item in confirmations if isinstance(item, dict) and item.get("status") == "pending"
    )
    lines.extend([
        "", "## 风险影响", *(f"- {item}" for item in requirement_model.get("risk_directions", [])),
        "", "## 结论", str(requirement_model.get("pre_review_conclusion", "")),
    ])
    return "\n".join(lines).rstrip() + "\n"


def _selected_sources(
    requirement_model: dict[str, Any], fact_ids: list[str], confirmation_ids: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    facts = {item.get("fact_id"): item for item in requirement_model.get("facts", []) if isinstance(item, dict)}
    confirmations = {
        item.get("confirmation_id"): item
        for item in requirement_model.get("confirmation_points", []) if isinstance(item, dict)
    }
    selected_facts: list[dict[str, Any]] = []
    selected_confirmations: list[dict[str, Any]] = []
    for fact_id in fact_ids:
        fact = facts.get(fact_id)
        if fact is None or fact.get("category") != "confirmed":
            raise ModeError(f"{fact_id} 不是 confirmed Fact，不能形成知识候选")
        if fact.get("source_type") == "code_context" or any(
            token in str(fact.get("statement", "")) for token in FORBIDDEN_REUSABLE_SOURCE_TOKENS
        ):
            raise ModeError(f"{fact_id} 属于禁止的临时、环境、代码或敏感来源")
        selected_facts.append(fact)
    for confirmation_id in confirmation_ids:
        confirmation = confirmations.get(confirmation_id)
        if confirmation is None or confirmation.get("status") != "resolved":
            raise ModeError(f"{confirmation_id} 不是 resolved Confirmation，不能形成知识候选")
        selected_confirmations.append(confirmation)
    return selected_facts, selected_confirmations


def should_offer_candidate_extraction(
    requirement_model: dict[str, Any], *, reusable_fact_ids: list[str] | None = None,
    reusable_confirmation_ids: list[str] | None = None, formal_validation_passed: bool,
    prompt_already_shown: bool = False, user_opted_out: bool = False,
    evidence_root: Path | None = None,
) -> bool:
    """Decide whether to show the one-line prompt; never search or extract."""

    if prompt_already_shown or user_opted_out or not formal_validation_passed:
        return False
    if requirement_model.get("workflow_stage") != "completed":
        return False
    summary = summarize_confirmations(requirement_model)
    if any(summary[key] for key in ("blocking_pending_count", "skipped_core_count", "unresolved_core_fact_count")):
        return False
    if validate_requirement_model(requirement_model, evidence_root=evidence_root):
        return False
    fact_ids = reusable_fact_ids or []
    confirmation_ids = reusable_confirmation_ids or []
    if not fact_ids and not confirmation_ids:
        return False
    try:
        _selected_sources(requirement_model, fact_ids, confirmation_ids)
    except ModeError:
        return False
    return True


def extract_candidates(
    requirement_model: dict[str, Any], candidate_specs: list[dict[str, Any]], *,
    explicitly_requested: bool, evidence_root: Path | None = None,
) -> dict[str, Any]:
    """Build a candidate-only list from confirmed/resolved sources; never persist it."""

    if not explicitly_requested:
        raise ModeError("未明确要求提取知识候选")
    if requirement_model.get("workflow_stage") == "pre_review":
        raise ModeError("pre_review 结果禁止形成知识候选")
    action_by_result = {
        "missing": "create", "consistent": "merge", "conflicting": "reconfirm",
        "superseding": "supersede",
    }
    candidates: list[dict[str, Any]] = []
    for index, spec in enumerate(candidate_specs, 1):
        fact_ids = list(spec.get("source_fact_ids", []))
        confirmation_ids = list(spec.get("source_confirmation_ids", []))
        facts, confirmations = _selected_sources(requirement_model, fact_ids, confirmation_ids)
        evidence: list[dict[str, Any]] = []
        for fact in facts:
            evidence.extend(copy.deepcopy(fact.get("evidence_references", [])))
        for confirmation in confirmations:
            evidence.extend(copy.deepcopy(confirmation.get("resolution_evidence_references", [])))
        comparison_result = spec.get("comparison_result")
        action = spec.get("recommended_action") or action_by_result.get(comparison_result)
        candidate = {
            "candidate_id": f"KC-{index:03d}",
            "knowledge_type": spec.get("knowledge_type"),
            "statement": spec.get("statement"),
            "source_fact_ids": fact_ids,
            "source_confirmation_ids": confirmation_ids,
            "evidence_references": evidence,
            "applicable_scope": spec.get("applicable_scope"),
            "existing_knowledge_ids": list(spec.get("existing_knowledge_ids", [])),
            "comparison_result": comparison_result,
            "recommended_action": action,
            "conflict_reason": spec.get("conflict_reason"),
            "status": "candidate",
        }
        candidates.append(candidate)
    result = {
        "schema_version": SCHEMA_VERSION,
        "extraction_mode": "extract_candidate",
        "candidates": candidates,
    }
    errors = validate_knowledge_candidate(result, evidence_root=evidence_root)
    if errors:
        raise ModeError("；".join(errors))
    return result
