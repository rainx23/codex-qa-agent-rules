#!/usr/bin/env python3
"""Validate deterministic delivery-summary Markdown against its Manifest."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from qa_contracts import load_json, summarize_confirmations


REQUIRED_SECTIONS = (
    "处理结果", "待确认点", "主要交付文件", "追踪和校验文件", "测试维度覆盖", "校验结果", "未执行事项",
)
FORBIDDEN_VAGUE_ONLY = ("相关文件", "产物见目录", "已生成若干文件", "查看对应文件")
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _section_positions(text: str) -> tuple[dict[str, int], list[str]]:
    positions: dict[str, int] = {}
    errors: list[str] = []
    for name in REQUIRED_SECTIONS:
        matches = list(re.finditer(rf"(?m)^## {re.escape(name)}\s*$", text))
        if len(matches) != 1:
            errors.append(f"章节 {name} 必须且只能出现一次")
        elif matches:
            positions[name] = matches[0].start()
    ordered = [positions[name] for name in REQUIRED_SECTIONS if name in positions]
    if ordered != sorted(ordered):
        errors.append("固定章节顺序不正确")
    return positions, errors


def validate_summary(text: str, manifest_path: Path) -> list[str]:
    """Validate summary content without rendering the same summary a second time."""

    errors: list[str] = []
    _, section_errors = _section_positions(text)
    errors.extend(section_errors)
    manifest = load_json(manifest_path.resolve())
    testcase_task = any(
        manifest.get(field)
        for field in (
            "testcase_model_path", "draft_testcase_model_path", "xmind_md_path",
            "draft_xmind_md_path", "xmind_path",
        )
    )
    if testcase_task and not re.search(r"(?m)^## 用例摘要\s*$", text):
        errors.append("完整用例任务必须包含用例摘要")
    if testcase_task:
        dimension_body = (
            text.split("## 测试维度覆盖", 1)[1].split("\n## ", 1)[0]
            if "## 测试维度覆盖" in text else ""
        )
        for dimension in (
            "功能测试", "数据测试", "异常测试", "权限测试",
            "导出测试", "兼容性测试", "回归测试", "SQL验证",
        ):
            if dimension not in dimension_body:
                errors.append(f"测试维度覆盖遗漏：{dimension}")
    if ANSI_RE.search(text):
        errors.append("输出包含 ANSI 控制字符")
    if "validation_status" not in text or "sql_status" not in text:
        errors.append("validation_status 与 sql_status 必须分开显示")
    for phrase in FORBIDDEN_VAGUE_ONLY:
        if phrase in text:
            errors.append(f"禁止模糊文件说明：{phrase}")
    status = manifest.get("validation_status")
    if status == "passed" and re.search(r"`[^`]*(?:^|/)drafts?/[^`]*`", text, re.I):
        errors.append("passed 摘要不得引用 draft 路径")
    if status == "pending":
        formal_xmind = manifest.get("xmind_path")
        if formal_xmind and formal_xmind.replace("\\", "/") in text:
            errors.append("pending 摘要不得引用正式 XMind 路径")
        if "正式交付完成" in text or "完整交付" in text:
            errors.append("pending 摘要不得宣称正式完整交付")
    if status == "failed" and "校验通过" in text:
        errors.append("failed 摘要不得宣称校验通过")

    analysis_paths = manifest.get("analysis_model_paths", [])
    requirement = None
    root = manifest_path.resolve().parent
    for candidate in (root, *root.parents):
        if (candidate / "RULE_VERSION").is_file() and (candidate / "AGENTS.md").is_file():
            root = candidate
            break
    for value in analysis_paths if isinstance(analysis_paths, list) else []:
        model = load_json(root / str(value).replace("\\", "/"))
        if "facts" in model:
            requirement = model
            break
    if requirement is not None:
        summary = summarize_confirmations(requirement)
        expected_counts = {
            "阻塞": summary["blocking_pending_count"],
            "非阻塞": summary["nonblocking_pending_count"],
            "建议确认": summary["suggested_pending_count"],
        }
        for label, value in expected_counts.items():
            if f"- {label}：{value}" not in text:
                errors.append(f"Confirmation Summary 与 Requirement Model 不一致：{label}")
    if not any(token in text for token in ("- 无", "`CONF-")):
        errors.append("待确认点为空时必须明确输出无，有记录时必须输出 CONF ID")
    count_lines = {
        "case_count": "TC 数量",
        "p0_case_count": "P0 TC 数量",
        "branch_count": "入口分支数量",
    }
    for field, label in count_lines.items():
        value = manifest.get(field)
        if testcase_task and isinstance(value, int) and f"- {label}：{value}" not in text:
            errors.append(f"摘要数量与 Manifest 不一致：{field}")
    return list(dict.fromkeys(errors))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="校验对话交付摘要与 Manifest/模型的一致性")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        errors = validate_summary(args.summary.read_text(encoding="utf-8-sig"), args.manifest)
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        print(f"SUMMARY passed=0 warning=0 failed={len(errors)}")
        return 1
    print("PASS delivery summary matches manifest and structured models")
    print("SUMMARY passed=1 warning=0 failed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
