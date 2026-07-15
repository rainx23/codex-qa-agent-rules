#!/usr/bin/env python3
"""Validate evidence, traceability, and risk contracts in QA reports."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from qa_validation import ValidationError, validate_markdown_file

REQUIRED_SECTIONS = {
    "本次分析范围": ("本次分析范围", "分析范围"),
    "需求或 Diff 理解": ("需求理解", "Diff 理解", "diff 理解", "核心改动点"),
    "证据来源": ("证据来源",),
    "待确认点": ("待确认点",),
    "风险点": ("风险点", "疑似风险点"),
    "疑似缺陷": ("疑似缺陷",),
    "测试点摘要": ("测试点摘要", "测试点"),
    "回归范围": ("回归范围",),
}
TRACE_FIELDS = ("需求点", "需求证据", "Diff 实现", "覆盖", "风险", "测试点")


def _headings(text: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", text)]


def _section(text: str, names: tuple[str, ...]) -> str:
    pattern = r"(?ms)^#{1,6}\s+(?:" + "|".join(re.escape(name) for name in names) + r")\s*$\n(.*?)(?=^#{1,6}\s+|\Z)"
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _is_combined(text: str, headings: list[str]) -> bool:
    has_requirement = any("需求理解" in heading for heading in headings) or bool(re.search(r"来源[:：].*需求", text))
    has_diff = any("diff 理解" in heading.lower() or "核心改动点" in heading for heading in headings) or bool(re.search(r"来源[:：].*diff", text, re.IGNORECASE))
    scope_combined = bool(re.search(r"需求\s*(?:与|和|\+).*diff", text, re.IGNORECASE))
    return (has_requirement and has_diff) or (scope_combined and has_diff)


def validate(path: Path, require_traceability: bool | None = None, xmind_md: Path | None = None) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    headings = _headings(text)
    errors: list[str] = []

    for label, names in REQUIRED_SECTIONS.items():
        if not any(any(name.lower() in heading.lower() for name in names) for heading in headings):
            errors.append(f"缺少章节：{label}")

    evidence = _section(text, ("证据来源",))
    if evidence and not re.search(r"需求原文|用户补充|OpenSpec|截图|Markdown|Diff|代码上下文|接口说明|SQL 口径|历史缺陷|推断", evidence, re.IGNORECASE):
        errors.append("证据来源章节未使用允许的来源标识")

    combined = _is_combined(text, headings) if require_traceability is None else require_traceability
    if combined:
        trace = _section(text, ("需求-Diff-测试点追踪矩阵",))
        if not trace:
            errors.append("需求与 Diff 并存时缺少需求-Diff-测试点追踪矩阵")
        else:
            missing_fields = [field for field in TRACE_FIELDS if field not in trace]
            if missing_fields:
                errors.append(f"追踪矩阵缺少字段：{missing_fields}")

    defect = _section(text, ("疑似缺陷",))
    if defect:
        no_defect = "未发现明确疑似缺陷" in defect
        if not no_defect and not ("需求证据" in defect and re.search(r"Diff 证据", defect, re.IGNORECASE)):
            errors.append("疑似缺陷必须同时包含需求证据和 Diff 证据")
    elif any("疑似缺陷" in heading for heading in headings):
        errors.append("疑似缺陷章节必须明确结论")

    risk = _section(text, ("风险点", "疑似风险点"))
    summary = _section(text, ("测试点摘要", "测试点"))
    trace = _section(text, ("需求-Diff-测试点追踪矩阵",))
    p0_risks = len(re.findall(r"风险等级[:：]\s*P0|\bP0\b", risk))
    mapped_tc = set(re.findall(r"TC\d{3,}", summary + "\n" + trace))
    if p0_risks and not mapped_tc and not re.search(r"P0\s*测试点[:：]\s*\S+", summary):
        errors.append("P0 风险未映射到具体测试点或 TC")

    if xmind_md is not None:
        try:
            outline = validate_markdown_file(xmind_md)
            existing = {node.title for node in outline.tc_nodes}
            missing = sorted(mapped_tc - existing)
            if missing:
                errors.append(f"报告引用了不存在的 TC：{missing}")
        except (OSError, ValidationError) as exc:
            errors.append(f"关联 XMind Markdown 无效：{exc}")

    if re.search(r"纯文档|无业务变更|仅文档|格式化变更", text) and not re.search(r"不生成(?:低价值)?业务(?:测试)?用例|不生成业务 TC", text, re.IGNORECASE):
        errors.append("无业务 Diff 必须明确不生成业务用例")

    return list(dict.fromkeys(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验测试分析报告")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--require-traceability", action="store_true")
    parser.add_argument("--xmind-md", type=Path)
    args = parser.parse_args(argv)
    failed = 0
    mode: bool | None = True if args.require_traceability else None
    for path in args.files:
        try:
            errors = validate(path, mode, args.xmind_md)
        except OSError as exc:
            errors = [str(exc)]
        if errors:
            failed += 1
            print(f"FAIL {path}: " + "；".join(errors), file=sys.stderr)
        else:
            print(f"PASS {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

