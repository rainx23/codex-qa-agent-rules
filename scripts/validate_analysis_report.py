#!/usr/bin/env python3
"""Validate mode-specific QA analysis-report contracts."""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

from heading_utils import MarkdownSection, heading_key, parse_markdown_sections
from qa_contracts import build_model_id_index, load_json
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


STRICT_ID_PATTERNS = {
    "fact_ids": ("FACT", r"\bFACT-\d{3,}\b"),
    "confirmation_ids": ("CONF", r"\bCONF-\d{3,}\b"),
    "change_ids": ("CHG", r"\bCHG-\d{3,}\b"),
    "risk_ids": ("RISK", r"\bRISK-\d{3,}\b"),
    "testcase_ids": ("TC", r"\bTC-?\d{3,}\b"),
    "branch_ids": ("BRANCH", r"\bBRANCH-\d{3,}\b"),
}


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


def _validate_line_evidence(bodies: dict[str, list[str]], resolved_mode: str) -> list[str]:
    errors: list[str] = []
    requirements = {
        "规则拆解": (r"\bFACT[A-Z0-9-]*\d+\b", "Fact ID"),
        "风险点": (r"\bRISK[A-Z0-9-]*\d+\b.*\b(?:FACT|CHG|DEF)[A-Z0-9-]*\d+\b", "Risk ID 与来源 ID"),
        "疑似风险点": (r"\bRISK[A-Z0-9-]*\d+\b.*\b(?:FACT|CHG|DEF)[A-Z0-9-]*\d+\b", "Risk ID 与来源 ID"),
        "待确认点": (r"\bCONF[A-Z0-9-]*\d+\b.*\bFACT[A-Z0-9-]*\d+\b", "Confirmation ID 与 Fact ID"),
        "测试点摘要": (r"\bRISK[A-Z0-9-]*\d+\b", "Risk ID"),
    }
    if resolved_mode == MODE_REQUIREMENT:
        requirements.pop("疑似风险点", None)
    for section, (pattern, label) in requirements.items():
        for line in _body(bodies, section).splitlines():
            item = re.match(r"\s*-\s+(.+)", line)
            if not item or item.group(1).strip() in {"无", "无。", "暂无", "暂无。"}:
                continue
            if not re.search(pattern, item.group(1), re.I):
                errors.append(f"{section} 行缺少 {label}：{item.group(1)[:60]}")
    defect = _body(bodies, "疑似缺陷")
    if defect and not _no_defect_conclusion(defect):
        for line in defect.splitlines():
            item = re.match(r"\s*-\s+(.+)", line)
            if item and not all(re.search(rf"\b{kind}[A-Z0-9-]*\d+\b", item.group(1), re.I) for kind in ("DEF", "FACT", "CHG")):
                errors.append("疑似缺陷行必须同时引用 DEF、FACT 和 CHG ID")
    return errors


def _validate_strict_ids(
    text: str,
    bodies: dict[str, list[str]],
    known_ids: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    for key, (label, pattern) in STRICT_ID_PATTERNS.items():
        known = set(known_ids.get(key, set()))
        for value in sorted(set(re.findall(pattern, text, re.I)) - known):
            errors.append(f"报告引用不存在的 {label} ID: {value}")
    malformed_patterns = {
        "FACT": r"\bFACT(?:\d{3,}|_\d+|-[A-Za-z][\w-]*)\b",
        "CONF": r"\bCONF(?:\d{3,}|_\d+|-[A-Za-z][\w-]*)\b",
        "CHG": r"\bCHG(?:\d{3,}|_\d+|-[A-Za-z][\w-]*)\b",
        "RISK": r"\bRISK(?:\d{3,}|_\d+|-[A-Za-z][\w-]*)\b",
    }
    for label, pattern in malformed_patterns.items():
        for value in sorted(set(re.findall(pattern, text, re.I))):
            errors.append(f"报告包含格式非法的 {label} ID: {value}")
    for fact_id in sorted(set(known_ids.get("core_fact_ids", set()))):
        if fact_id not in text:
            errors.append(f"报告遗漏核心 Fact: {fact_id}")
    pending_body = _body(bodies, "待确认点")
    for confirmation_id in sorted(set(known_ids.get("blocking_confirmation_ids", set()))):
        if confirmation_id not in pending_body:
            errors.append(f"报告待确认章节遗漏 blocking Confirmation: {confirmation_id}")
    risk_body = _body(bodies, "风险点", "疑似风险点")
    for risk_id in sorted(set(known_ids.get("high_risk_ids", set()))):
        if risk_id not in risk_body:
            errors.append(f"报告风险章节遗漏高风险项: {risk_id}")
    return errors


def validate(
    path: Path,
    require_traceability: bool | None = None,
    xmind_md: Path | None = None,
    mode: str = "auto",
    legacy: bool = False,
    known_ids: dict[str, Any] | None = None,
    strict: bool = True,
    validation_status: str | None = None,
) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    _, bodies = _section_map(text)
    errors: list[str] = []

    if legacy and strict:
        strict = False
    if strict:
        if not re.search(r"(?im)^\s*(?:schema[_ ]version)\s*[:=]\s*2\.0\.0\s*$", text):
            errors.append("strict 报告必须声明 Schema Version: 2.0.0")
        if not re.search(r"(?im)^\s*(?:rule[_ ]version)\s*[:=]\s*\d+\.\d+\.\d+\s*$", text):
            errors.append("strict 报告必须声明 Rule Version")
        if known_ids is None:
            errors.append("strict 报告必须由调用方提供真实模型 ID 索引")

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
    # Schema 2 reports are model-driven and must carry row-level IDs. Legacy is opt-in.
    if strict:
        errors.extend(_validate_line_evidence(bodies, resolved_mode))
        if False and known_ids:  # retained only to preserve the legacy error wording below
            for kind, pattern in (("FACT", r"\bFACT[A-Z0-9-]*\d+\b"), ("CHG", r"\bCHG[A-Z0-9-]*\d+\b"), ("RISK", r"\bRISK[A-Z0-9-]*\d+\b"), ("DEF", r"\bDEF[A-Z0-9-]*\d+\b"), ("CONF", r"\bCONF[A-Z0-9-]*\d+\b"), ("TC", r"\bTC\d{3}\b")):
                for value in sorted(set(re.findall(pattern, text, re.I)) - known_ids.get(kind, set())):
                    errors.append(f"报告引用不存在的 {kind} ID: {value}")
        if known_ids is not None:
            errors.extend(_validate_strict_ids(text, bodies, known_ids))
    elif re.search(r"\bFACT[A-Z0-9-]*\d+\b", text, re.I):
        errors.extend(_validate_line_evidence(bodies, resolved_mode))

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
    parser.add_argument("--legacy", action="store_true", help="显式使用旧报告兼容模式")
    parser.add_argument("--strict", action="store_true", help="显式启用严格模型驱动校验（默认行为）")
    parser.add_argument("--requirement", "--requirement-model", dest="requirement_model", type=Path)
    parser.add_argument("--diff", "--diff-model", dest="diff_model", type=Path)
    parser.add_argument("--risk", "--risk-matrix", dest="risk_matrix", type=Path)
    parser.add_argument("--testcase", "--testcase-model", dest="testcase_model", type=Path)
    args = parser.parse_args(argv)
    failed = 0
    requested_mode = MODE_COMBINED if args.require_traceability else args.mode
    strict = not args.legacy
    model_paths = (args.requirement_model, args.diff_model, args.risk_matrix, args.testcase_model)
    if strict and any(path is None for path in model_paths):
        parser.error("strict 模式必须同时提供 --requirement、--diff、--risk 和 --testcase")
    requirement_model = load_json(args.requirement_model) if args.requirement_model else None
    diff_model = load_json(args.diff_model) if args.diff_model else None
    risk_model = load_json(args.risk_matrix) if args.risk_matrix else None
    testcase_model = load_json(args.testcase_model) if args.testcase_model else None
    known_ids = build_model_id_index(
        requirement_model=requirement_model,
        diff_model=diff_model,
        risk_model=risk_model,
        testcase_model=testcase_model,
    )
    for path in args.files:
        try:
            text = path.read_text(encoding="utf-8-sig")
            resolved_mode = detect_mode(text, requested_mode)
            errors = validate(path, xmind_md=args.xmind_md, mode=requested_mode, legacy=args.legacy, strict=strict, known_ids=known_ids if strict else None)
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
