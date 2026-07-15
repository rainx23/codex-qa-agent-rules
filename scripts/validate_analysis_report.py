#!/usr/bin/env python3
"""Validate mode-specific QA analysis-report contracts."""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

from heading_utils import MarkdownSection, heading_key, parse_markdown_sections
from qa_validation import ValidationError, parse_traceability_records, validate_markdown_file


MODE_REQUIREMENT = "requirement"
MODE_DIFF = "diff"
MODE_COMBINED = "combined"
MODE_LABELS = {
    MODE_REQUIREMENT: "纯需求",
    MODE_DIFF: "纯 Diff",
    MODE_COMBINED: "需求与 Diff 联动",
}

SECTION_ALIASES = {
    "本次分析范围": ("本次分析范围", "分析范围"),
    "需求理解": ("需求理解", "最终需求理解"),
    "规则拆解": ("规则拆解", "产品规则拆解"),
    "Diff 理解": ("Diff 理解", "diff 理解"),
    "Commit 或 Diff 对比范围": (
        "Commit 或 Diff 对比范围",
        "Commit/Diff 对比范围",
        "Commit 或 Diff 范围",
        "Commit 对比范围",
        "Diff 对比范围",
        "Diff 范围",
        "对比范围",
    ),
    "Diff 涉及文件": ("Diff 涉及文件", "变更文件", "涉及文件"),
    "核心改动点": ("核心改动点",),
    "证据来源": ("证据来源",),
    "待确认点": ("待确认点", "待确认点处理结果"),
    "风险点": ("风险点",),
    "疑似风险点": ("疑似风险点",),
    "疑似缺陷": ("疑似缺陷",),
    "测试点摘要": ("测试点摘要", "测试点"),
    "回归范围": ("回归范围",),
    "需求-Diff-测试点追踪矩阵": ("需求-Diff-测试点追踪矩阵",),
}

REQUIRED_BY_MODE = {
    MODE_REQUIREMENT: (
        "本次分析范围",
        "需求理解",
        "规则拆解",
        "证据来源",
        "待确认点",
        "风险点",
        "测试点摘要",
        "回归范围",
    ),
    MODE_DIFF: (
        "本次分析范围",
        "Commit 或 Diff 对比范围",
        "Diff 涉及文件",
        "核心改动点",
        "证据来源",
        "待确认点",
        "疑似风险点",
        "疑似缺陷",
        "测试点摘要",
        "回归范围",
    ),
    MODE_COMBINED: (
        "本次分析范围",
        "需求理解",
        "Diff 理解",
        "证据来源",
        "待确认点",
        "风险点",
        "疑似缺陷",
        "测试点摘要",
        "回归范围",
        "需求-Diff-测试点追踪矩阵",
    ),
}

TRACE_FIELD_GROUPS = (
    ("需求点ID", "需求点"),
    ("需求证据",),
    ("Diff变更ID", "Diff 实现"),
    ("覆盖状态", "覆盖情况", "覆盖"),
    ("风险ID", "风险"),
    ("测试点或TC", "测试点", "TC"),
)
ALLOWED_COVERAGE = {"已覆盖", "疑似遗漏", "实现不一致", "需求外变更", "无法判断"}
ALLOWED_EVIDENCE = re.compile(
    r"需求原文|用户补充|OpenSpec|截图|Markdown(?: 文件)?|Diff|代码上下文|接口说明|SQL 口径|历史缺陷|推断",
    re.IGNORECASE,
)


def _alias_index() -> dict[str, str]:
    return {
        heading_key(alias): canonical
        for canonical, aliases in SECTION_ALIASES.items()
        for alias in aliases
    }


ALIAS_INDEX = _alias_index()


def canonical_heading(title: str) -> str:
    """Return the report-contract name for a normalized heading alias."""

    return ALIAS_INDEX.get(heading_key(title), title.strip())


def _section_map(text: str) -> tuple[list[MarkdownSection], dict[str, list[str]]]:
    sections = parse_markdown_sections(text)
    bodies: dict[str, list[str]] = {}
    for section in sections:
        bodies.setdefault(canonical_heading(section.title), []).append(section.body)
    return sections, bodies


def _body(bodies: dict[str, list[str]], *names: str) -> str:
    return "\n\n".join(
        body
        for name in names
        for body in bodies.get(name, ())
        if body.strip()
    ).strip()


def _explicit_mode(text: str) -> str | None:
    match = re.search(r"(?im)^\s*报告模式\s*[:：]\s*(\S.*?)\s*$", text)
    if not match:
        return None
    value = re.sub(r"\s+", "", unicodedata.normalize("NFKC", match.group(1))).casefold()
    aliases = {
        "纯需求": MODE_REQUIREMENT,
        "requirement": MODE_REQUIREMENT,
        "纯diff": MODE_DIFF,
        "diff": MODE_DIFF,
        "需求与diff联动": MODE_COMBINED,
        "需求和diff联动": MODE_COMBINED,
        "combined": MODE_COMBINED,
    }
    return aliases.get(value)


def detect_mode(text: str, requested_mode: str = "auto") -> str:
    """Prefer the CLI mode, then an explicit report field, then structural evidence."""

    if requested_mode != "auto":
        return requested_mode
    explicit = _explicit_mode(text)
    if explicit:
        return explicit
    _, bodies = _section_map(text)
    has_requirement = "需求理解" in bodies
    has_diff = any(
        name in bodies
        for name in ("Diff 理解", "核心改动点", "Commit 或 Diff 对比范围", "Diff 涉及文件")
    )
    has_trace = "需求-Diff-测试点追踪矩阵" in bodies
    evidence = _body(bodies, "证据来源")
    evidence_has_requirement = bool(re.search(r"需求|OpenSpec|禅道", evidence, re.IGNORECASE))
    evidence_has_diff = bool(re.search(r"Diff|代码上下文|Commit", evidence, re.IGNORECASE))
    if has_trace or (has_requirement and has_diff) or (
        has_requirement and evidence_has_requirement and evidence_has_diff
    ):
        return MODE_COMBINED
    if has_requirement:
        return MODE_REQUIREMENT
    if has_diff:
        return MODE_DIFF
    raise ValueError("无法自动识别报告模式，请增加“报告模式”字段或使用 --mode")


def _no_defect_conclusion(body: str) -> bool:
    compact = re.sub(r"\s+", "", body)
    return bool(
        re.search(r"未发现(?:明确)?疑似缺陷", compact)
        or re.search(r"本次未发现.*(?:双重证据|需求证据.*Diff证据).*疑似缺陷", compact, re.IGNORECASE)
    )


def _validate_trace_matrix(trace: str) -> list[str]:
    _, errors = parse_traceability_records(trace, "combined")
    return errors


def validate(
    path: Path,
    require_traceability: bool | None = None,
    xmind_md: Path | None = None,
    mode: str = "auto",
) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    _, bodies = _section_map(text)
    errors: list[str] = []

    try:
        resolved_mode = MODE_COMBINED if require_traceability else detect_mode(text, mode)
    except ValueError as exc:
        return [str(exc)]

    for name in REQUIRED_BY_MODE[resolved_mode]:
        if name not in bodies:
            errors.append(f"缺少章节（{MODE_LABELS[resolved_mode]}）：{name}")
        elif not _body(bodies, name):
            errors.append(f"章节正文为空（{MODE_LABELS[resolved_mode]}）：{name}")

    evidence = _body(bodies, "证据来源")
    if evidence and not ALLOWED_EVIDENCE.search(evidence):
        errors.append("证据来源章节未使用允许的来源标识")

    defect_exists = "疑似缺陷" in bodies
    defect = _body(bodies, "疑似缺陷")
    if defect_exists:
        if not defect:
            errors.append("疑似缺陷章节必须明确结论")
        elif not _no_defect_conclusion(defect):
            required_evidence = ("需求证据", "Diff 证据", "证据状态", "影响")
            missing = [field for field in required_evidence if field.lower() not in defect.lower()]
            if missing:
                errors.append(f"疑似缺陷缺少双重证据字段：{missing}")

    if resolved_mode == MODE_REQUIREMENT and defect and not _no_defect_conclusion(defect):
        errors.append("纯需求报告不得仅凭需求歧义认定疑似缺陷")

    trace = _body(bodies, "需求-Diff-测试点追踪矩阵")
    if resolved_mode == MODE_COMBINED and trace:
        errors.extend(_validate_trace_matrix(trace))

    risk_names = ("疑似风险点",) if resolved_mode == MODE_DIFF else ("风险点",)
    risk = _body(bodies, *risk_names)
    summary = _body(bodies, "测试点摘要")
    p0_risks = len(re.findall(r"风险等级[:：]\s*P0|\bP0\b", risk))
    mapped_tc = set(re.findall(r"TC\d{3}", summary + "\n" + trace))
    if p0_risks and not mapped_tc and not re.search(r"P0\s*测试点[:：]\s*\S+", summary):
        errors.append("P0 风险未映射到具体测试点或 TC")

    if xmind_md is not None:
        try:
            outline = validate_markdown_file(xmind_md)
            existing = {node.title for node in outline.tc_nodes}
            missing_tc = sorted(mapped_tc - existing)
            if missing_tc:
                errors.append(f"报告引用了不存在的 TC：{missing_tc}")
        except (OSError, ValidationError) as exc:
            errors.append(f"关联 XMind Markdown 无效：{exc}")

    if re.search(r"纯文档|无业务变更|仅文档|格式化变更", text) and not re.search(
        r"不生成(?:低价值)?业务(?:测试)?用例|不生成业务 TC", text, re.IGNORECASE
    ):
        errors.append("无业务 Diff 必须明确不生成业务用例")

    return list(dict.fromkeys(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按报告模式校验测试分析报告")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument(
        "--mode",
        choices=("auto", MODE_REQUIREMENT, MODE_DIFF, MODE_COMBINED),
        default="auto",
        help="报告模式；默认优先读取报告模式字段，再按章节自动识别",
    )
    parser.add_argument(
        "--require-traceability",
        action="store_true",
        help="兼容旧参数：等价于 --mode combined",
    )
    parser.add_argument("--xmind-md", type=Path)
    args = parser.parse_args(argv)
    failed = 0
    requested_mode = MODE_COMBINED if args.require_traceability else args.mode
    for path in args.files:
        try:
            text = path.read_text(encoding="utf-8-sig")
            resolved_mode = detect_mode(text, requested_mode)
            errors = validate(path, xmind_md=args.xmind_md, mode=requested_mode)
        except (OSError, ValueError) as exc:
            errors = [str(exc)]
            resolved_mode = requested_mode
        if errors:
            failed += 1
            print(f"FAIL {path} mode={resolved_mode}: " + "；".join(errors), file=sys.stderr)
        else:
            print(f"PASS {path} mode={resolved_mode}")
    print(f"SUMMARY passed={len(args.files) - failed} warning=0 failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
