#!/usr/bin/env python3
"""Render the confirmation-only chat response from a Requirement checkpoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qa_contracts import load_json, validate_requirement_model


def _evidence_root(path: Path) -> Path:
    resolved = path.resolve()
    for candidate in (resolved.parent, *resolved.parents):
        if (candidate / "RULE_VERSION").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    return resolved.parent


def render_confirmation_summary(model: dict, *, evidence_root: Path | None = None) -> str:
    if model.get("workflow_stage") != "confirmation_only":
        raise ValueError("仅 confirmation_only 阶段可渲染集中确认回复")
    errors = validate_requirement_model(model, evidence_root=evidence_root)
    if errors:
        raise ValueError("Requirement checkpoint 无效：" + "; ".join(errors))

    facts = model.get("facts", [])
    confirmed = [item for item in facts if item.get("category") == "confirmed"]
    uncertain = [item for item in facts if item.get("category") in {"missing", "conflicting", "inferred"}]
    lines = [
        "## 分析范围", "", f"- {model['analysis_scope']}", "",
        "## 需求理解", "", f"- 业务目标：{model['business_goal']}", f"- 验收依据：{model['acceptance_basis']}", "",
        "## 已确认规则", "",
    ]
    lines.extend(f"- {item['fact_id']}：{item['statement']}" for item in confirmed)
    if not confirmed:
        lines.append("- 无")
    lines.extend(["", "## 缺失和冲突", ""])
    lines.extend(f"- {item['fact_id']}（{item['category']}）：{item['statement']}" for item in uncertain)
    if not uncertain:
        lines.append("- 无")
    lines.extend(["", "## 风险方向", ""])
    lines.extend(f"- {item}" for item in model.get("risk_directions", []))
    if not model.get("risk_directions"):
        lines.append("- 无")
    lines.extend(["", "## 回归范围", ""])
    lines.extend(f"- {item}" for item in model.get("regression_scope", []))
    lines.extend(["", "## 全部确认问题", ""])
    points = model.get("confirmation_points", [])
    pending_points = [point for point in points if point.get("status") == "pending"]
    processed_ids = [
        point.get("confirmation_id")
        for point in points
        if point.get("status") in {"resolved", "skipped"}
    ]
    if processed_ids:
        lines.extend([f"- 已处理确认 ID：{'、'.join(processed_ids)}", ""])
    for point in pending_points:
        lines.extend([
            f"### {point['confirmation_id']}", "",
            f"- confirmation_id：{point['confirmation_id']}",
            f"- 问题：{point['question']}",
            f"- 当前证据：{point['current_evidence']}",
            f"- 不确定点：{point['uncertainty']}",
            f"- 影响范围：{'、'.join(point['impact_scope'])}",
        ])
        if point.get("answer_options"):
            lines.append(f"- 可选答案：{'；'.join(point['answer_options'])}")
        lines.extend([f"- 当前处理状态：{point['status']}；{point['current_handling']}", ""])
    if not pending_points:
        lines.append("- 无待回答 Confirmation。")
    lines.extend([
        "## 当前暂停状态", "",
        "- 第一阶段扫描已完成；当前暂停在 confirmation_only。",
        "- Risk Coverage Matrix、Testcase Model、XMind、正式报告、Manifest 和 Index 均未生成。",
        "- 可一次回复多个 Confirmation；全部 blocking 问题解决后将自动续跑原始任务。",
    ])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="渲染 confirmation_only 集中确认回复")
    parser.add_argument("--requirement", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(
            render_confirmation_summary(
                load_json(args.requirement), evidence_root=_evidence_root(args.requirement),
            ),
            end="",
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
