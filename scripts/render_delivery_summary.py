#!/usr/bin/env python3
"""Render a deterministic Chinese chat delivery summary from QA artifacts."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from qa_contracts import (
    load_json,
    summarize_confirmations,
    validate_requirement_model,
    validate_risk_matrix,
    validate_testcase_model,
)
from qa_validation import (
    ValidationError,
    count_tree_nodes,
    markdown_tree,
    validate_markdown_file,
    validate_xmind_archive,
)
from validate_manifest import artifact_workspace_root, validate_manifest_data
from validate_testcase_index import validate_index


class DeliverySummaryError(ValueError):
    """Raised when deterministic source data cannot produce a truthful summary."""


FILE_TYPES: dict[str, tuple[str, str]] = {
    "report_path": ("需求分析报告", "供人工阅读需求理解、证据、待确认点、风险、验收标准和回归范围"),
    "draft_report_path": ("草稿需求分析报告", "供确认完成前审阅当前需求理解、证据、风险和待确认点"),
    "risk_matrix_path": ("风险覆盖矩阵", "保存 Risk 与 Requirement、TC 的双向追踪关系"),
    "draft_risk_matrix_path": ("草稿风险覆盖矩阵", "保存确认完成前的 Risk 与 Requirement、草稿 TC 追踪关系"),
    "testcase_model_path": ("测试用例模型", "保存结构化 TC、入口分支、步骤、预期和条件覆盖"),
    "draft_testcase_model_path": ("草稿测试用例模型", "保存确认完成前的结构化 TC、入口分支、步骤和预期"),
    "xmind_md_path": ("测试用例 Markdown", "可审查、可版本管理、可重新生成 Workbook 的测试用例源文件"),
    "draft_xmind_md_path": ("草稿测试用例 Markdown", "供确认完成前审阅的非正式测试用例源文件"),
    "xmind_path": ("测试用例", "可直接使用 XMind 打开的正式测试用例 Workbook"),
    "manifest": ("产物清单", "保存产物路径、版本、来源 Hash、数量和交付状态"),
    "index": ("全局测试产物索引", "查询正式历史测试产物及新增、补充、替代、废弃关系"),
    "requirement_model": ("需求分析模型", "保存 Fact、Confirmation、Acceptance Criteria 和 Condition Matrix"),
}

SECTION_ORDER = (
    "处理结果", "待确认点", "主要交付文件", "追踪和校验文件", "用例摘要", "校验结果", "未执行事项",
)

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _repo_path(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise DeliverySummaryError(f"{field} 必须是非空仓库相对路径或 null")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", normalized):
        raise DeliverySummaryError(f"{field} 禁止绝对路径或越界路径：{value}")
    return path.as_posix()


def _load_path(manifest: dict[str, Any], manifest_path: Path, field: str) -> tuple[str | None, Path | None]:
    relative = _repo_path(manifest.get(field), field=field)
    if relative is None:
        return None, None
    root = artifact_workspace_root(manifest_path)
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise DeliverySummaryError(f"{field} 路径越界：{relative}")
    if not resolved.is_file():
        raise DeliverySummaryError(f"{field} 路径不存在：{relative}")
    return relative, resolved


def _analysis_models(manifest: dict[str, Any], manifest_path: Path) -> tuple[list[tuple[str, Path, dict[str, Any]]], dict[str, Any] | None]:
    values = manifest.get("analysis_model_paths")
    if not isinstance(values, list):
        raise DeliverySummaryError("analysis_model_paths 必须是数组")
    models: list[tuple[str, Path, dict[str, Any]]] = []
    requirement: dict[str, Any] | None = None
    root = artifact_workspace_root(manifest_path)
    for index, value in enumerate(values):
        relative = _repo_path(value, field=f"analysis_model_paths[{index}]")
        if relative is None:
            raise DeliverySummaryError(f"analysis_model_paths[{index}] 不得为 null")
        resolved = (root / relative).resolve()
        if resolved != root and root not in resolved.parents:
            raise DeliverySummaryError(f"analysis_model_paths[{index}] 路径越界：{relative}")
        if not resolved.is_file():
            raise DeliverySummaryError(f"analysis_model_paths[{index}] 路径不存在：{relative}")
        model = load_json(resolved)
        models.append((relative, resolved, model))
        if "facts" in model:
            requirement = model
    return models, requirement


def _assert_counts(manifest: dict[str, Any], requirement: dict[str, Any] | None, risk: dict[str, Any] | None, testcase: dict[str, Any] | None) -> None:
    if requirement is not None:
        summary = summarize_confirmations(requirement)
        keys = ("pending_count", "blocking_pending_count", "nonblocking_pending_count", "suggested_pending_count")
        mismatches = [f"{key}: Manifest={manifest.get(key)} Model={summary[key]}" for key in keys if manifest.get(key) != summary[key]]
        if mismatches:
            raise DeliverySummaryError("Manifest 与 Requirement Model 的 Confirmation Summary 不一致：" + "; ".join(mismatches))
    if risk is not None:
        risks = risk.get("risk_items", []) if isinstance(risk.get("risk_items"), list) else []
        p0_risks = sum(item.get("test_priority") == "P0" for item in risks if isinstance(item, dict))
        if manifest.get("p0_risk_count") != p0_risks:
            raise DeliverySummaryError(f"p0_risk_count 不一致：Manifest={manifest.get('p0_risk_count')} Risk Matrix={p0_risks}")
    if testcase is not None:
        cases = testcase.get("cases", []) if isinstance(testcase.get("cases"), list) else []
        p0_cases = sum(item.get("test_priority") == "P0" for item in cases if isinstance(item, dict))
        expected = {
            "case_count": len(cases),
            "p0_case_count": p0_cases,
            "branch_count": testcase.get("branch_count", 0),
        }
        for field, value in expected.items():
            if manifest.get(field) != value:
                raise DeliverySummaryError(f"{field} 不一致：Manifest={manifest.get(field)} Testcase Model={value}")


def _confirmation_lines(requirement: dict[str, Any] | None) -> list[str]:
    points = requirement.get("confirmation_points", []) if requirement and isinstance(requirement.get("confirmation_points"), list) else []
    groups = (("blocking", "阻塞确认点"), ("nonblocking", "非阻塞确认点"), ("suggested", "建议确认点"))
    lines: list[str] = []
    for severity, title in groups:
        lines.append(f"### {title}")
        selected = [point for point in points if isinstance(point, dict) and point.get("severity") == severity]
        if not selected:
            lines.extend(["", "- 无", ""])
            continue
        for point in selected:
            status = point.get("status", "unknown")
            status_text = {"pending": "待确认", "resolved": "已解决", "skipped": "已跳过"}.get(str(status), str(status))
            statement = str(point.get("statement") or "未提供问题描述")
            fact_ids = ", ".join(str(item) for item in point.get("fact_ids", [])) or "未关联"
            if status == "resolved":
                handling = str(point.get("resolution") or "已解决，但未提供简要结论")
            elif status == "skipped":
                handling = "跳过原因：" + str(point.get("skip_reason") or "未提供")
            else:
                handling = "等待用户确认；受影响的正式产物保持暂停"
            lines.extend([
                f"- `{point.get('confirmation_id', 'CONF-UNKNOWN')}`：{statement}",
                f"  - 状态：{status_text}",
                f"  - 影响：关联 Fact {fact_ids}",
                f"  - 当前处理：{handling}",
            ])
        lines.append("")
    summary = summarize_confirmations(requirement or {})
    resolved = sum(point.get("status") == "resolved" for point in points if isinstance(point, dict))
    skipped = sum(point.get("status") == "skipped" for point in points if isinstance(point, dict))
    lines.extend([
        "汇总：",
        "",
        f"- 阻塞：{summary['blocking_pending_count']}",
        f"- 非阻塞：{summary['nonblocking_pending_count']}",
        f"- 建议确认：{summary['suggested_pending_count']}",
        f"- 已解决：{resolved}",
        f"- 已跳过：{skipped}",
    ])
    return lines


def _artifact_line(label: str, path: str | None, purpose: str, status: str) -> list[str]:
    display = f"`{path}`" if path else "未生成"
    return [f"- {label}：{display}", f"  - 用途：{purpose}", f"  - 状态：{status}", ""]


def _validation_results(
    manifest: dict[str, Any], manifest_path: Path, requirement: dict[str, Any] | None,
    risk: dict[str, Any] | None, testcase: dict[str, Any] | None,
    resolved_paths: dict[str, Path | None],
) -> dict[str, str]:
    root = artifact_workspace_root(manifest_path)
    results: dict[str, str] = {}
    results["Requirement Model"] = "不适用" if requirement is None else ("通过" if not validate_requirement_model(requirement, evidence_root=root) else "失败")
    results["Risk Matrix"] = "未生成" if risk is None else ("通过" if not validate_risk_matrix(risk, evidence_root=root) else "失败")
    results["Testcase Model"] = "未生成" if testcase is None else ("通过" if not validate_testcase_model(testcase) else "失败")
    markdown_path = resolved_paths.get("xmind_md_path") or resolved_paths.get("draft_xmind_md_path")
    outline = None
    if markdown_path is None:
        results["XMind Markdown"] = "未生成"
    else:
        try:
            outline = validate_markdown_file(markdown_path)
            results["XMind Markdown"] = "通过"
        except (OSError, ValidationError, ValueError):
            results["XMind Markdown"] = "失败"
    workbook = resolved_paths.get("xmind_path")
    if workbook is None:
        results["XMind Workbook 完整树"] = "未生成"
    elif outline is None:
        results["XMind Workbook 完整树"] = "失败"
    else:
        try:
            validate_xmind_archive(workbook, outline.root.title, len(outline.tc_nodes), count_tree_nodes(outline.root), markdown_tree(outline.root))
            results["XMind Workbook 完整树"] = "通过"
        except (OSError, ValidationError, ValueError):
            results["XMind Workbook 完整树"] = "失败"
    results["Manifest"] = "通过" if not validate_manifest_data(manifest, manifest_path) else "失败"
    index = root / "testcases/index.md"
    if manifest.get("validation_status") == "passed" and index.is_file():
        results["Index"] = "通过" if not validate_index(index) else "失败"
    else:
        results["Index"] = "不适用"
    results["正式产物统一扫描"] = "本轮未运行"
    results["全量单元测试"] = "本轮未运行"
    results["git diff --check"] = "本轮未运行"
    return results


def render_delivery_summary(manifest_path: Path) -> str:
    manifest_path = manifest_path.resolve()
    manifest = load_json(manifest_path)
    status = manifest.get("validation_status")
    if status not in {"passed", "pending", "failed"}:
        raise DeliverySummaryError(f"validation_status 非法：{status}")
    models, requirement = _analysis_models(manifest, manifest_path)
    resolved_paths: dict[str, Path | None] = {}
    relative_paths: dict[str, str | None] = {}
    for field in (
        "report_path", "draft_report_path", "risk_matrix_path", "draft_risk_matrix_path",
        "testcase_model_path", "draft_testcase_model_path", "xmind_md_path", "draft_xmind_md_path", "xmind_path",
    ):
        relative_paths[field], resolved_paths[field] = _load_path(manifest, manifest_path, field)
    risk_path = resolved_paths.get("risk_matrix_path") or resolved_paths.get("draft_risk_matrix_path")
    testcase_path = resolved_paths.get("testcase_model_path") or resolved_paths.get("draft_testcase_model_path")
    risk = load_json(risk_path) if risk_path else None
    testcase = load_json(testcase_path) if testcase_path else None
    _assert_counts(manifest, requirement, risk, testcase)

    has_testcases = testcase is not None or any(relative_paths.get(field) for field in ("xmind_md_path", "draft_xmind_md_path", "xmind_path"))
    status_text = {"passed": "已完成", "pending": "待确认", "failed": "失败"}[status]
    lines = [
        "## 处理结果", "",
        f"- 需求分析：{'已完成' if requirement is not None else '不适用'}",
        f"- 风险分析：{'已完成' if risk is not None else '未生成'}",
        f"- 测试用例设计：{status_text if has_testcases else '不适用'}",
        f"- 测试设计状态：{status}",
        f"- validation_status：{status}",
        f"- SQL 校验状态：{manifest.get('sql_status') if manifest.get('sql_status') is not None else '不适用'}",
        f"- sql_status：{manifest.get('sql_status') if manifest.get('sql_status') is not None else '不适用'}",
        f"- 产物关系：{manifest.get('relation') or '不适用'}",
        f"- 版本关系：规则 {manifest.get('rule_version') or '未知'}；supersedes={manifest.get('supersedes') or '无'}",
        f"- 正式 XMind：{'已生成' if relative_paths.get('xmind_path') else '未生成'}",
        "- 真实页面/接口/SQL：未执行",
    ]
    if status == "pending":
        lines.append(f"- pending_reason：{manifest.get('pending_reason') or '未提供'}")
        lines.append("- 下一步：请回答上述 blocking Confirmation；确认后将自动续跑原始任务")
    if status == "failed":
        lines.append(f"- failure_reason：{manifest.get('failure_reason') or '未提供'}")

    lines.extend(["", "## 待确认点", ""] + _confirmation_lines(requirement))
    lines.extend(["", "## 主要交付文件", ""])
    if status == "passed" and relative_paths.get("xmind_path"):
        label, purpose = FILE_TYPES["xmind_path"]
        lines.extend(_artifact_line(label, relative_paths["xmind_path"], purpose, "完整树复验结果见校验章节"))
    if status == "passed":
        order = ("xmind_md_path", "report_path") if has_testcases else ("report_path",)
    elif status == "pending":
        order = ("draft_report_path", "draft_xmind_md_path") if has_testcases else ("draft_report_path",)
    else:
        order = tuple(field for field in ("report_path", "xmind_md_path", "draft_report_path", "draft_xmind_md_path") if relative_paths.get(field))
    for field in order:
        label, purpose = FILE_TYPES[field]
        path = relative_paths.get(field)
        artifact_status = "可用" if path else ("被阻塞" if status == "pending" else "未生成")
        lines.extend(_artifact_line(label, path, purpose, artifact_status))
    if status == "pending" and has_testcases and not relative_paths.get("xmind_path"):
        label, purpose = FILE_TYPES["xmind_path"]
        lines.extend(_artifact_line("正式 XMind", None, purpose, f"被阻塞：{manifest.get('pending_reason') or '存在待确认点'}"))

    lines.extend(["## 追踪和校验文件", ""])
    for relative, _, model in models:
        if "facts" in model:
            label, purpose = FILE_TYPES["requirement_model"]
        else:
            label, purpose = "Diff 影响模型", "保存结构化变更、影响链、风险和疑似缺陷"
        lines.extend(_artifact_line(label, relative, purpose, "可用"))
    for field in (("risk_matrix_path" if status == "passed" else "draft_risk_matrix_path"), ("testcase_model_path" if status == "passed" else "draft_testcase_model_path")):
        label, purpose = FILE_TYPES[field]
        lines.extend(_artifact_line(label, relative_paths.get(field), purpose, "可用" if relative_paths.get(field) else "未生成"))
    manifest_relative = manifest_path.relative_to(artifact_workspace_root(manifest_path)).as_posix()
    label, purpose = FILE_TYPES["manifest"]
    lines.extend(_artifact_line(label, manifest_relative, purpose, "可用"))
    index_relative = "testcases/index.md" if status == "passed" else None
    label, purpose = FILE_TYPES["index"]
    lines.extend(_artifact_line(label, index_relative, purpose, "已登记" if index_relative else ("未登记" if status == "pending" else "不适用")))

    if has_testcases:
        req_matrix = requirement.get("condition_matrix") if requirement and isinstance(requirement.get("condition_matrix"), dict) else {}
        required = req_matrix.get("required_combinations", []) if isinstance(req_matrix.get("required_combinations"), list) else []
        excluded = req_matrix.get("excluded_combinations", []) if isinstance(req_matrix.get("excluded_combinations"), list) else []
        coverage = [item for case in (testcase or {}).get("cases", []) if isinstance(case, dict) for item in case.get("condition_coverage", []) if isinstance(item, dict)]
        behavior_ids = {item.get("combination_id") for item in coverage if item.get("coverage_type") == "behavior"}
        required_ids = {item.get("combination_id") for item in required if isinstance(item, dict)}
        blocked = summarize_confirmations(requirement or {})["blocking_pending_count"]
        lines.extend([
            "## 用例摘要", "",
            f"- TC 数量：{manifest.get('case_count', 0)}",
            f"- P0 TC 数量：{manifest.get('p0_case_count', manifest.get('p0_count', 0))}",
            f"- P0 Risk 数量：{manifest.get('p0_risk_count', 0)}",
            f"- Risk 总数：{len((risk or {}).get('risk_items', []))}",
            f"- 入口分支数量：{manifest.get('branch_count', (testcase or {}).get('branch_count', 0))}",
            f"- 条件组合总数：{len(required) + len(excluded)}",
            f"- 行为覆盖组合数：{len(required_ids & behavior_ids)}",
            f"- 被阻塞组合数：{len(required_ids - behavior_ids) if blocked else 0}",
            f"- 排除组合数：{len(excluded)}",
            f"- 未覆盖组合数：{len(required_ids - behavior_ids)}",
            f"- 版本关系：{manifest.get('relation') or '不适用'}",
            f"- supersedes：{manifest.get('supersedes') or '无'}",
            "",
        ])

    results = _validation_results(manifest, manifest_path, requirement, risk, testcase, resolved_paths)
    lines.extend(["## 校验结果", ""] + [f"- {label}：{value}" for label, value in results.items()])
    if status == "failed":
        lines.append(f"- 失败校验：{manifest.get('failure_reason') or 'Manifest 未提供具体失败原因'}")
    lines.extend([
        "", "## 未执行事项", "",
        "- 未连接真实页面",
        "- 未调用真实接口",
        "- 未执行数据库 SQL",
        f"- SQL 校验状态为 {manifest.get('sql_status') if manifest.get('sql_status') is not None else '不适用'}；该状态与测试设计状态分开表达",
        "- 未生成接口自动化",
        "- 未提交 Git",
    ])
    output = "\n".join(lines).rstrip() + "\n"
    if _ANSI_RE.search(output):
        raise DeliverySummaryError("摘要不得包含 ANSI 控制字符")
    return output


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="从 Manifest 和结构化模型确定性渲染中文对话交付摘要")
    parser.add_argument("--manifest", required=True, type=Path, help="QA Manifest 仓库相对或本地路径")
    parser.add_argument("--output", type=Path, help="可选输出文件；默认仅输出到 stdout")
    parser.add_argument("--check", action="store_true", help="渲染后执行对话交付摘要契约校验")
    args = parser.parse_args(argv)
    try:
        summary = render_delivery_summary(args.manifest)
        if args.check:
            from validate_delivery_summary import validate_summary
            errors = validate_summary(summary, args.manifest)
            if errors:
                for error in errors:
                    print(f"FAIL {error}", file=sys.stderr)
                return 1
        if args.output:
            args.output.write_text(summary, encoding="utf-8", newline="\n")
        print(summary, end="")
        return 0
    except (DeliverySummaryError, OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
