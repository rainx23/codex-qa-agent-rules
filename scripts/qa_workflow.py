#!/usr/bin/env python3
"""Deterministic state transitions for the two-stage QA workflow."""

from __future__ import annotations

import copy
import re
from typing import Any

from qa_contracts import DIMENSIONS, REQUIREMENT_ASPECTS, summarize_confirmations


class WorkflowError(ValueError):
    """Raised when a workflow transition would lose scope or invent a resolution."""


def parse_confirmation_answers(text: str) -> dict[str, dict[str, str]]:
    """Parse a compact multi-confirmation reply without resolving omitted items."""

    answers: dict[str, dict[str, str]] = {}
    for part in re.split(r"[;；\n]+", text):
        match = re.fullmatch(r"\s*(CONF-[A-Za-z0-9_-]+)\s*[=＝]\s*(.*?)\s*", part)
        if not match or not match.group(2):
            continue
        confirmation_id, answer = match.groups()
        answers[confirmation_id] = {
            "action": "skip" if "跳过" in answer else "resolve",
            "answer": answer,
        }
    return answers


def prepare_confirmation_checkpoint(
    requirement_model: dict[str, Any],
    original_task_scope: dict[str, Any],
    *,
    checkpoint_id: str,
    created_at: str,
) -> tuple[dict[str, Any], bool]:
    """Save the complete first-stage scan and decide whether phase two starts now."""

    model = copy.deepcopy(requirement_model)
    risk_directions = [
        str(item.get("statement"))
        for item in model.get("risks", [])
        if isinstance(item, dict) and item.get("statement")
    ]
    model["risks"] = []
    model["risk_directions"] = risk_directions
    for assessment in model.get("test_dimension_assessment", []):
        if isinstance(assessment, dict):
            assessment["risk_ids"] = []
            assessment["testcase_ids"] = []
    model["original_task_scope"] = copy.deepcopy(original_task_scope)
    model["confirmation_checkpoint"] = {
        "checkpoint_id": checkpoint_id,
        "created_at": created_at,
        "scan_completed": True,
        "evidence_saved": True,
        "requirement_aspects_scanned": list(REQUIREMENT_ASPECTS),
        "test_dimensions_scanned": list(DIMENSIONS),
        "condition_matrix_assessed": True,
        "confirmation_scan_completed": True,
        "downstream_artifacts_generated": [],
    }
    matrix = model.get("condition_matrix")
    if isinstance(matrix, dict):
        for combination in matrix.get("required_combinations", []):
            if isinstance(combination, dict):
                combination["covered_by_tc_ids"] = []
        summary = matrix.get("coverage_summary")
        if isinstance(summary, dict):
            summary["covered_combination_count"] = 0
    blocking = summarize_confirmations(model)["blocking_pending_count"]
    model["workflow_stage"] = "confirmation_only" if blocking else "formal_generation"
    return model, blocking == 0


def apply_confirmation_answers(
    requirement_model: dict[str, Any],
    answers: dict[str, dict[str, str]],
    *,
    reply_evidence: list[dict[str, Any]],
    resolved_at: str,
    fact_updates: dict[str, dict[str, Any]] | None = None,
    acceptance_updates: dict[str, dict[str, Any]] | None = None,
    new_confirmations: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply only explicitly answered confirmations and return the minimal invalidation set."""

    model = copy.deepcopy(requirement_model)
    points = {
        point.get("confirmation_id"): point
        for point in model.get("confirmation_points", [])
        if isinstance(point, dict)
    }
    unknown = set(answers) - set(points)
    if unknown:
        raise WorkflowError(f"未知 Confirmation：{sorted(unknown)}")
    affected_fact_ids: set[str] = set()
    affected_scope: set[str] = set()
    for confirmation_id, payload in answers.items():
        point = points[confirmation_id]
        if point.get("status") != "pending":
            raise WorkflowError(f"{confirmation_id} 当前状态不是 pending")
        answer = str(payload.get("answer", "")).strip()
        if not answer:
            raise WorkflowError(f"{confirmation_id} 缺少回答内容")
        action = payload.get("action", "resolve")
        if action == "skip":
            point.update(
                status="skipped",
                skip_reason=answer,
                decision_evidence=copy.deepcopy(reply_evidence),
            )
        elif action == "resolve":
            point.update(
                status="resolved",
                resolution=answer,
                resolution_evidence_references=copy.deepcopy(reply_evidence),
                resolved_at=resolved_at,
            )
        else:
            raise WorkflowError(f"{confirmation_id} action 非法：{action}")
        affected_fact_ids.update(point.get("fact_ids", []))
        affected_scope.update(point.get("impact_scope", []))

    fact_updates = fact_updates or {}
    unrelated_facts = set(fact_updates) - affected_fact_ids
    if unrelated_facts:
        raise WorkflowError(f"不得更新未受本轮回答影响的 Fact：{sorted(unrelated_facts)}")
    facts = {
        fact.get("fact_id"): fact
        for fact in model.get("facts", [])
        if isinstance(fact, dict)
    }
    for fact_id, update in fact_updates.items():
        if fact_id not in facts:
            raise WorkflowError(f"未知 Fact：{fact_id}")
        facts[fact_id].update(copy.deepcopy(update))

    acceptance_updates = acceptance_updates or {}
    criteria = {
        item.get("criterion_id"): item
        for item in model.get("acceptance_criteria", [])
        if isinstance(item, dict)
    }
    for criterion_id, update in acceptance_updates.items():
        criterion = criteria.get(criterion_id)
        if criterion is None:
            raise WorkflowError(f"未知 Acceptance Criterion：{criterion_id}")
        linked_facts = set(update.get("fact_ids", criterion.get("fact_ids", [])))
        if not linked_facts & affected_fact_ids:
            raise WorkflowError(f"不得更新未受本轮回答影响的 Acceptance Criterion：{criterion_id}")
        criterion.update(copy.deepcopy(update))

    if new_confirmations:
        existing_ids = set(points)
        for point in new_confirmations:
            confirmation_id = point.get("confirmation_id")
            if not confirmation_id or confirmation_id in existing_ids:
                raise WorkflowError(f"新增 Confirmation ID 非法或重复：{confirmation_id}")
            model.setdefault("confirmation_points", []).append(copy.deepcopy(point))
            existing_ids.add(confirmation_id)

    ready = summarize_confirmations(model)["blocking_pending_count"] == 0
    model["workflow_stage"] = "formal_generation" if ready else "confirmation_only"
    transition = {
        "answered_confirmation_ids": sorted(answers),
        "affected_fact_ids": sorted(affected_fact_ids),
        "affected_scope": sorted(affected_scope),
        "unanswered_confirmation_ids": sorted(
            point.get("confirmation_id")
            for point in model.get("confirmation_points", [])
            if isinstance(point, dict) and point.get("status") == "pending"
        ),
        "invalidate_downstream_models": sorted(affected_scope),
        "auto_resume": ready,
        "next_stage": model["workflow_stage"],
    }
    return model, transition
