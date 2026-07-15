#!/usr/bin/env python3
"""Select the authoritative section of a structured Zentao requirement."""

from __future__ import annotations

import re
from dataclasses import dataclass

from heading_utils import MarkdownSection, heading_key, parse_markdown_sections


BACKGROUND_TITLES = {heading_key(title) for title in ("需求背景", "背景")}
PRODUCT_TITLES = {
    heading_key(title)
    for title in (
        "产品实现方案、规则",
        "产品实现方案",
        "产品方案",
        "实现方案",
        "产品规则",
        "实现规则",
        "产品实现方案及规则",
        "产品实现方案与规则",
    )
}
ALTERNATIVE_TITLES = {
    heading_key(title)
    for title in ("验收标准", "字段说明", "接口说明", "数据口径", "产品方案补充")
}


@dataclass(frozen=True)
class ZentaoSelection:
    """Deterministic section selection; semantic conclusions remain an agent responsibility."""

    background: str
    acceptance_basis: str
    basis_title: str | None
    basis_kind: str
    blocking: bool
    risks: tuple[str, ...]
    questions: tuple[str, ...]


def _first(sections: list[MarkdownSection], keys: set[str]) -> MarkdownSection | None:
    return next((section for section in sections if heading_key(section.title) in keys), None)


def _requested(sections: list[MarkdownSection], requested_scope: str) -> MarkdownSection | None:
    if re.search(r"第一部分|需求背景", requested_scope):
        return _first(sections, BACKGROUND_TITLES)
    requested = heading_key(requested_scope)
    return next(
        (
            section
            for section in sections
            if heading_key(section.title) == requested
            or requested in heading_key(section.title)
            or heading_key(section.title) in requested
        ),
        None,
    )


def _conflicting_keys(body: str) -> list[str]:
    values: dict[str, set[str]] = {}
    for line in body.splitlines():
        match = re.match(r"\s*(?:[-*+]\s*)?([^|：:]{1,40})[：:]\s*(\S.*?)\s*$", line)
        if not match:
            continue
        key = re.sub(r"\s+", "", match.group(1))
        value = match.group(2).strip()
        values.setdefault(key, set()).add(value)
    return sorted(key for key, options in values.items() if len(options) > 1)


def select_zentao_acceptance_basis(text: str, requested_scope: str | None = None) -> ZentaoSelection:
    """Apply user scope first, then product-plan priority, then explicit alternatives."""

    sections = parse_markdown_sections(text)
    background = _first(sections, BACKGROUND_TITLES)
    questions: list[str] = []
    risks: list[str] = []

    if requested_scope:
        selected = _requested(sections, requested_scope)
        if selected is None:
            return ZentaoSelection(
                background.body if background else "",
                "",
                None,
                "user-scope-missing",
                True,
                (),
                (f"用户指定的分析范围未找到：{requested_scope}",),
            )
        return ZentaoSelection(
            background.body if background else "",
            selected.body,
            selected.title,
            "user-specified",
            False,
            (),
            (),
        )

    selected = _first(sections, PRODUCT_TITLES)
    kind = "product-plan"
    if selected is None:
        selected = _first(sections, ALTERNATIVE_TITLES)
        kind = "alternative-rule"
        questions.append("未找到第三部分“产品实现方案、规则”，已检查其他明确产品规则章节。")
    if selected is None:
        return ZentaoSelection(
            background.body if background else "",
            "",
            None,
            "missing",
            True,
            (),
            ("未找到第三部分或其他明确产品规则，核心预期需要确认。",),
        )

    conflicts = _conflicting_keys(selected.body)
    if conflicts:
        questions.append("产品规则内部同一项目存在相反口径：" + "、".join(conflicts))

    if re.search(r"(?:业务)?目标覆盖[：:]\s*(?:否|未覆盖)|无法(?:达到|满足).*业务目标", selected.body):
        risks.append("业务目标偏差风险：产品方案可能无法达到需求背景中的核心业务目标。")

    return ZentaoSelection(
        background.body if background else "",
        selected.body,
        selected.title,
        kind,
        bool(conflicts),
        tuple(risks),
        tuple(questions),
    )
