#!/usr/bin/env python3
"""Deterministic observable-oracle checks shared by model and XMind validators."""

from __future__ import annotations


EXISTING_RULE_PHRASES = ("按现有统计口径一致", "按现有口径处理", "保持现有逻辑")
BASELINE_PHRASES = (
    "未发生本需求之外的变化", "其他功能不受影响", "与原来一致", "没有其他影响", "保持不变", "不受影响",
)
BASELINE_MARKERS = ("变更前", "基线", "同一账号", "同账号", "同一查询条件", "同查询条件", "快照")
OBSERVABLE_MARKERS = (
    "逐字段", "逐项", "行数", "可见范围", "金额", "数量", "字段", "状态", "结果集", "列表", "汇总",
)
COMPARISON_MARKERS = ("一致", "对比", "比较", "相同", "等于")
AGGREGATION_SOURCE_MARKERS = ("可见股票行", "可见行", "明细行", "列表行")
AGGREGATION_ORACLE_MARKERS = ("汇总行", "汇总字段", "对应字段")
AGGREGATION_ACTION_MARKERS = ("求和", "逐项汇总", "分别汇总", "汇总后")
VAGUE_RELATION_ORACLE_PHRASES = (
    "按关系判断", "按关系得到可观察结果", "根据关系判断可见性",
    "根据对应关系处理", "关系生效", "权限结果正确", "按配置结果展示",
)


def expectation_quality_error(expected: str, context: str = "") -> str | None:
    combined = f"{context} {expected}"
    if any(phrase in expected for phrase in VAGUE_RELATION_ORACLE_PHRASES):
        return "VAGUE_RELATION_ORACLE"
    if any(phrase in expected for phrase in EXISTING_RULE_PHRASES):
        has_oracle = (
            any(marker in combined for marker in AGGREGATION_SOURCE_MARKERS)
            and any(marker in combined for marker in AGGREGATION_ORACLE_MARKERS)
            and any(marker in combined for marker in AGGREGATION_ACTION_MARKERS)
            and any(marker in combined for marker in OBSERVABLE_MARKERS)
        )
        if not has_oracle:
            return "VAGUE_EXISTING_RULE_ASSERTION"
    if any(phrase in expected for phrase in BASELINE_PHRASES):
        has_baseline = (
            any(marker in combined for marker in BASELINE_MARKERS)
            and any(marker in combined for marker in OBSERVABLE_MARKERS)
            and any(marker in combined for marker in COMPARISON_MARKERS)
        )
        if not has_baseline:
            return "VAGUE_BASELINE_ASSERTION"
    return None
