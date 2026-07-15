#!/usr/bin/env python3
"""Shared deterministic validators for QA Markdown and XMind artifacts."""

from __future__ import annotations

import json
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

VALID_DIMENSIONS = {
    "功能测试", "数据测试", "异常测试", "权限测试",
    "导出测试", "兼容性测试", "回归测试", "SQL验证",
}
FUZZY_ASSERTIONS = (
    "正常", "正确", "合理", "符合预期", "功能可用", "页面无异常",
    "查询成功", "展示正常", "运行正常", "交互正常", "数据正常",
)
LABEL_PREFIXES = (
    "模块：", "模块:", "测试点：", "测试点:",
    "操作步骤：", "操作步骤:", "预期结果：", "预期结果:",
)
UNKNOWN_MARKERS = ("待确认", "未知", "未明确", "口径为准", "尚未确认")
FORBIDDEN_UNKNOWN_RESULTS = ("不展示", "展示为空", "默认过滤", "默认值", "必然", "一定")
PLACEHOLDER_RE = re.compile(r"(?:xxx|某|假设)(?:表|字段|接口|页面|参数)", re.IGNORECASE)
TC_RE = re.compile(r"^TC(?P<number>\d{3})$")
TC_LIKE_RE = re.compile(r"^TC", re.IGNORECASE)
LIST_RE = re.compile(r"^(?P<indent> *)-\s+(?P<title>.*?)\s*$")


class ValidationError(ValueError):
    pass


@dataclass
class Node:
    title: str
    line: int
    level: int
    children: list["Node"] = field(default_factory=list)


@dataclass
class Outline:
    root: Node
    nodes: list[Node]
    tc_nodes: list[Node]
    expected_nodes: list[Node]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TraceRecord:
    line: int
    requirement_id: str
    requirement_evidence: str
    change_id: str
    code_evidence: str
    coverage_status: str
    risk_ids: tuple[str, ...]
    testcase_ids: tuple[str, ...]


def descendant_paths(node: Node) -> list[list[Node]]:
    if not node.children:
        return [[node]]
    return [[node, *tail] for child in node.children for tail in descendant_paths(child)]


def walk_nodes(node: Node) -> list[Node]:
    return [node, *(item for child in node.children for item in walk_nodes(child))]


def _canonical_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).lower()
    value = re.sub(r"[\s，。；、:：()（）【】\[\]'“”]+", "", value)
    value = re.sub(
        r"[\u4e00-\u9fffA-Za-z0-9_]+(?=(?:字段|必填|留空|为空|未填写|格式|长度|范围|校验|弹窗|页面))",
        "<对象>",
        value,
    )
    return value


def _case_signature(tc: Node) -> str:
    return "|".join(_canonical_text(node.title) for node in walk_nodes(tc)[1:])


def _exact_case_signature(tc: Node) -> str:
    return "|".join(
        re.sub(r"\s+", "", unicodedata.normalize("NFKC", node.title).casefold())
        for node in walk_nodes(tc)[1:]
    )


def _case_context(tc: Node) -> tuple[str, ...]:
    text = "|".join(node.title for node in walk_nodes(tc)[1:])
    context: list[str] = []
    for token in ("正式", "模拟", "权限", "越权", "无权限", "金额", "价格", "数量", "日期", "时间"):
        if token in text:
            context.append(token)
    context.extend(sorted(set(re.findall(r"数据源[\w\u4e00-\u9fff-]+", text))))
    return tuple(context)


def _normal_is_observable(title: str) -> bool:
    return bool(
        re.search(r"(?:状态|状态码|字段值|设备状态|任务状态).*(?:由.+变更为|变更为|显示|值为|等于|为)[“\"]?正常[”\"]?", title)
        or re.search(r"由\S+变更为正常", title)
    )


def _fuzzy_tokens(title: str) -> list[str]:
    matched: list[str] = []
    for token in FUZZY_ASSERTIONS:
        if token not in title:
            continue
        if token == "正常" and _normal_is_observable(title):
            continue
        matched.append(token)
    return matched


def _parse_markdown(markdown: str, source: Path) -> tuple[list[Node], list[Node]]:
    roots: list[Node] = []
    nodes: list[Node] = []
    stack: list[Node] = []
    errors: list[str] = []

    for line_no, raw in enumerate(markdown.splitlines(), 1):
        if not raw.strip():
            continue
        if "\t" in raw:
            errors.append(f"{source}:{line_no}: 禁止 Tab")
            continue
        stripped = raw.strip()
        if (
            stripped.startswith("~~~")
            or stripped.startswith(chr(96))
            or stripped.startswith("|")
            or stripped.startswith("{")
            or stripped.startswith("[")
            or re.match(r"^#{1,6}\s", stripped)
        ):
            errors.append(f"{source}:{line_no}: 本地用例禁止代码块、表格、JSON、标题或说明")
            continue
        match = LIST_RE.fullmatch(raw)
        if not match:
            errors.append(f"{source}:{line_no}: 只允许 '- ' 列表节点")
            continue
        indent = len(match.group("indent"))
        title = match.group("title").strip()
        if indent % 4:
            errors.append(f"{source}:{line_no}: 缩进必须为 4 空格的整数倍")
            continue
        if not title:
            errors.append(f"{source}:{line_no}: 禁止空节点")
            continue
        level = indent // 4
        if nodes and level > nodes[-1].level + 1:
            errors.append(f"{source}:{line_no}: 层级一次最多增加一级")
            continue
        node = Node(title, line_no, level)
        while stack and stack[-1].level >= level:
            stack.pop()
        if level == 0:
            roots.append(node)
        elif not stack:
            errors.append(f"{source}:{line_no}: 子节点缺少父节点")
            continue
        else:
            stack[-1].children.append(node)
        stack.append(node)
        nodes.append(node)

        if TC_LIKE_RE.match(title) and not TC_RE.fullmatch(title):
            errors.append(f"{source}:{line_no}: TC 编号必须严格为 TC 加三位数字，例如 TC001")

        if title.startswith(LABEL_PREFIXES):
            errors.append(f"{source}:{line_no}: 禁止标签式节点 '{title}'")
        if PLACEHOLDER_RE.search(title):
            errors.append(f"{source}:{line_no}: 禁止虚构 SQL、字段、接口或页面占位名称")

    if len(roots) != 1:
        errors.append(f"{source}: 根节点必须唯一，实际 {len(roots)} 个")
    if errors:
        raise ValidationError("\n".join(errors))
    return roots, nodes


def validate_markdown_text(markdown: str, source: Path | str = "<memory>") -> Outline:
    source = Path(source)
    roots, nodes = _parse_markdown(markdown, source)
    root = roots[0]
    errors: list[str] = []
    expected_nodes: list[Node] = []
    case_signatures: dict[str, Node] = {}
    exact_signatures: dict[str, Node] = {}
    semantic_cases: list[tuple[Node, str, tuple[str, ...]]] = []
    warnings: list[str] = []

    if root.title in {"测试用例", "用例", "Test Cases"}:
        errors.append(f"{source}:{root.line}: 根节点必须具有业务语义")
    if not root.children:
        errors.append(f"{source}:{root.line}: 根节点缺少测试维度")

    tc_nodes = [node for node in nodes if TC_RE.fullmatch(node.title)]
    for dimension in root.children:
        if dimension.title not in VALID_DIMENSIONS:
            errors.append(f"{source}:{dimension.line}: 非法测试维度 '{dimension.title}'")
            continue
        if not dimension.children:
            errors.append(f"{source}:{dimension.line}: 测试维度不能为空")
            continue

        direct_flags = [bool(TC_RE.fullmatch(child.title)) for child in dimension.children]
        if any(direct_flags) and not all(direct_flags):
            errors.append(f"{source}:{dimension.line}: 同一维度不得混用公共入口和直接 TC")

        grouped = not all(direct_flags)
        candidates: list[Node] = []
        if grouped:
            for entry in dimension.children:
                if not entry.children or any(not TC_RE.fullmatch(child.title) for child in entry.children):
                    errors.append(f"{source}:{entry.line}: 公共入口下只能包含 TC 节点")
                    continue
                candidates.extend(entry.children)
        else:
            candidates.extend(dimension.children)

        for tc in candidates:
            required_path_length = 4 if grouped else 5
            paths = descendant_paths(tc)
            if len(tc.children) != 1:
                errors.append(f"{source}:{tc.line}: {tc.title} 必须只有一个核心测试点分支")
            if not paths or any(len(path) != required_path_length for path in paths):
                schema = "TC-测试点-步骤-预期" if grouped else "TC-一级模块-二级功能点-步骤-预期"
                errors.append(f"{source}:{tc.line}: {tc.title} 层级必须严格为 {schema}")
            else:
                expected_nodes.extend(path[-1] for path in paths)

            subtree_titles = [item.title for item in walk_nodes(tc)]
            if any(marker in title for marker in UNKNOWN_MARKERS for title in subtree_titles):
                for expected in (path[-1] for path in paths):
                    if any(token in expected.title for token in FORBIDDEN_UNKNOWN_RESULTS):
                        errors.append(f"{source}:{expected.line}: 未确认口径不得写成确定业务结果")

            exact_signature = _exact_case_signature(tc)
            signature = _case_signature(tc)
            context = _case_context(tc)
            if exact_signature in exact_signatures:
                previous = exact_signatures[exact_signature]
                errors.append(f"{source}:{tc.line}: {tc.title} 与 {previous.title} 完全重复；重复依据=测试点、步骤和预期一致")
            elif signature in case_signatures:
                previous = case_signatures[signature]
                if _case_context(previous) == context:
                    errors.append(f"{source}:{tc.line}: {tc.title} 与 {previous.title} 属于同规则重复用例；差异字段仅为业务对象名称")
            else:
                for previous, previous_signature, previous_context in semantic_cases:
                    ratio = SequenceMatcher(None, signature, previous_signature).ratio()
                    if ratio >= 0.84 and previous_context == context:
                        warnings.append(
                            f"{source}:{tc.line}: {tc.title} 与 {previous.title} 疑似重复；"
                            f"重复依据=语义相似度 {ratio:.2f}；差异字段=保留业务上下文；建议人工确认是否合并"
                        )
                        break
            exact_signatures[exact_signature] = tc
            case_signatures[signature] = tc
            semantic_cases.append((tc, signature, context))

    numbers = [int(TC_RE.fullmatch(node.title).group("number")) for node in tc_nodes]
    if numbers != list(range(1, len(numbers) + 1)):
        errors.append(f"{source}: TC 编号必须从 TC001 全局连续，实际 {numbers}")
    if len(numbers) != len(set(numbers)):
        errors.append(f"{source}: TC 编号重复")
    if not tc_nodes:
        errors.append(f"{source}: 未找到 TC 节点")

    for expected in expected_nodes:
        matched = _fuzzy_tokens(expected.title)
        if matched:
            errors.append(f"{source}:{expected.line}: 预期包含模糊断言 {matched}，必须改为可观察结果")

    if errors:
        raise ValidationError("\n".join(dict.fromkeys(errors)))
    return Outline(root, nodes, tc_nodes, expected_nodes, list(dict.fromkeys(warnings)))


def testcase_details(outline: Outline) -> dict[str, dict[str, Any]]:
    """Extract rendered testcase semantics without changing the fixed hierarchy."""

    result: dict[str, dict[str, Any]] = {}
    for tc in outline.tc_nodes:
        ancestors_dimension = next((node for node in outline.root.children if tc in walk_nodes(node)), None)
        paths = descendant_paths(tc)
        grouped = bool(paths and len(paths[0]) == 4)
        if grouped:
            test_point = tc.children[0].title if tc.children else ""
            steps = [path[-2].title for path in paths]
        else:
            test_point = tc.children[0].children[0].title if tc.children and tc.children[0].children else ""
            steps = [path[-2].title for path in paths]
        result[tc.title] = {
            "dimension": ancestors_dimension.title if ancestors_dimension else "",
            "test_point": test_point,
            "steps": steps,
            "expected_results": [path[-1].title for path in paths],
        }
    return result


_TRACE_ALIASES = {
    "需求点ID": ("需求点id", "需求点"),
    "需求证据": ("需求证据",),
    "Diff变更ID": ("diff变更id", "diff实现", "diff变更"),
    "代码证据": ("代码证据",),
    "覆盖状态": ("覆盖状态", "覆盖情况", "覆盖"),
    "风险ID": ("风险id", "风险"),
    "测试点或TC": ("测试点或tc", "测试点", "tc"),
}


def _trace_header(value: str) -> str:
    key = re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()
    for canonical, aliases in _TRACE_ALIASES.items():
        if key in aliases:
            return canonical
    return value.strip()


def parse_traceability_records(text: str, mode: str) -> tuple[list[TraceRecord], list[str]]:
    """Parse traceability only from explicit Markdown table rows, never free text."""

    required_by_mode = {
        "requirement": {"需求点ID", "需求证据", "风险ID", "测试点或TC"},
        "diff": {"Diff变更ID", "代码证据", "风险ID", "测试点或TC"},
        "combined": {"需求点ID", "需求证据", "Diff变更ID", "覆盖状态", "风险ID", "测试点或TC"},
    }
    lines = text.splitlines()
    records: list[TraceRecord] = []
    errors: list[str] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip().startswith("|"):
            index += 1
            continue
        block_start = index
        block: list[tuple[int, str]] = []
        while index < len(lines) and lines[index].strip().startswith("|"):
            block.append((index + 1, lines[index].strip()))
            index += 1
        if len(block) < 3:
            continue
        raw_header = [cell.strip() for cell in block[0][1].strip("|").split("|")]
        header = [_trace_header(cell) for cell in raw_header]
        required_headers = required_by_mode[mode]
        if not required_headers.issubset(set(header)):
            recognized = set(header) & set(_TRACE_ALIASES)
            if recognized:
                missing = sorted(required_headers - set(header))
                errors.append(f"追踪矩阵缺少字段：{missing}")
            continue
        for line_no, row in block[2:]:
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            if len(cells) != len(header):
                errors.append(f"第 {line_no} 行追踪矩阵列数与表头不一致")
                continue
            data = dict(zip(header, cells))
            tc_cell = data.get("测试点或TC", "")
            if re.search(r"TC\d+\s*(?:-|~|至)\s*TC\d+", tc_cell, re.IGNORECASE):
                errors.append(f"第 {line_no} 行禁止使用模糊 TC 范围：{tc_cell}")
            testcase_ids = tuple(re.findall(r"TC\d+", tc_cell, re.IGNORECASE))
            if not testcase_ids:
                errors.append(f"第 {line_no} 行未逐条列出 TC")
            for tc_id in testcase_ids:
                if not TC_RE.fullmatch(tc_id):
                    errors.append(f"第 {line_no} 行 TC 编号非法：{tc_id}")
            risk_cell = data.get("风险ID", "")
            risk_ids = tuple(token for token in re.split(r"[,，、;/\s]+", risk_cell) if token and token not in {"无", "-"})
            if not risk_ids:
                errors.append(f"第 {line_no} 行缺少风险 ID")
            if mode == "combined":
                if not data.get("需求证据"):
                    errors.append(f"第 {line_no} 行缺少需求证据")
                if not data.get("Diff变更ID"):
                    errors.append(f"第 {line_no} 行缺少 Diff 变更 ID")
                if data.get("覆盖状态") not in {"已覆盖", "疑似遗漏", "实现不一致", "需求外变更", "无法判断"}:
                    errors.append(f"第 {line_no} 行覆盖状态非法：{data.get('覆盖状态')}")
            if data.get("覆盖状态") in {"疑似遗漏", "实现不一致"} and not risk_ids:
                errors.append(f"第 {line_no} 行 {data.get('覆盖状态')} 必须关联风险")
            records.append(
                TraceRecord(
                    line_no,
                    data.get("需求点ID", ""),
                    data.get("需求证据", ""),
                    data.get("Diff变更ID", ""),
                    data.get("代码证据", ""),
                    data.get("覆盖状态", ""),
                    risk_ids,
                    testcase_ids,
                )
            )
        if block_start == index:
            index += 1
    if not records:
        errors.append("未找到符合当前报告模式的结构化追踪矩阵行")
    return records, list(dict.fromkeys(errors))


def validate_traceability_mapping(
    report_text: str,
    mode: str,
    outline: Outline | None = None,
    risk_matrix: dict[str, Any] | None = None,
    testcase_model: dict[str, Any] | None = None,
) -> tuple[list[str], list[str], list[TraceRecord]]:
    records, errors = parse_traceability_records(report_text, mode)
    warnings: list[str] = []
    tracked_tcs = {tc_id for record in records for tc_id in record.testcase_ids}
    report_tcs = set(re.findall(r"TC\d+", report_text))
    invalid_report_tcs = sorted(tc for tc in report_tcs if not TC_RE.fullmatch(tc))
    if invalid_report_tcs:
        errors.append(f"报告引用非法 TC：{invalid_report_tcs}")
    untracked_report_tcs = sorted(tc for tc in report_tcs if TC_RE.fullmatch(tc) and tc not in tracked_tcs)
    if untracked_report_tcs:
        errors.append(f"TC 只出现在普通正文、未进入追踪矩阵：{untracked_report_tcs}")
    if outline is not None:
        xmind_tcs = {node.title for node in outline.tc_nodes}
        missing = sorted(tracked_tcs - xmind_tcs)
        untracked = sorted(xmind_tcs - tracked_tcs)
        if missing:
            errors.append(f"追踪矩阵引用不存在的 TC：{missing}")
        if untracked:
            errors.append(f"XMind TC 未被追踪矩阵覆盖：{untracked}")
    if risk_matrix is not None:
        matrix_risks = {risk.get("risk_id"): risk for risk in risk_matrix.get("risk_items", [])}
        traced_risks = {risk_id for record in records for risk_id in record.risk_ids}
        unknown_risks = sorted(traced_risks - matrix_risks.keys())
        if unknown_risks:
            errors.append(f"追踪矩阵引用不存在的风险：{unknown_risks}")
        for risk in risk_matrix.get("risk_items", []):
            if risk.get("test_priority") == "P0":
                ids = set(risk.get("testcase_ids", []))
                if not ids:
                    errors.append(f"P0 风险 {risk.get('risk_id')} 未映射 TC")
                if not ids.issubset(tracked_tcs):
                    errors.append(f"P0 风险 {risk.get('risk_id')} 的 TC 未全部进入追踪矩阵")
        for record in records:
            for risk_id in set(record.risk_ids) & matrix_risks.keys():
                risk = matrix_risks[risk_id]
                mapped = set(risk.get("testcase_ids", []))
                if not set(record.testcase_ids).issubset(mapped):
                    errors.append(f"第 {record.line} 行 TC 与风险 {risk_id} 的风险矩阵映射不一致")
                if record.requirement_id and record.requirement_id not in risk.get("requirement_ids", []):
                    errors.append(f"第 {record.line} 行需求点与风险 {risk_id} 的风险矩阵映射不一致")
                if record.change_id and record.change_id not in risk.get("change_ids", []):
                    errors.append(f"第 {record.line} 行 Diff 变更与风险 {risk_id} 的风险矩阵映射不一致")
    if testcase_model is not None and outline is not None:
        model_tcs = {case.get("tc_id") for case in testcase_model.get("cases", [])}
        xmind_tcs = {node.title for node in outline.tc_nodes}
        if model_tcs != xmind_tcs:
            errors.append(f"Testcase Model 与 XMind TC 集合不一致：model={sorted(model_tcs)} xmind={sorted(xmind_tcs)}")
        rendered = testcase_details(outline)
        for case in testcase_model.get("cases", []):
            tc_id = case.get("tc_id")
            if tc_id not in rendered:
                continue
            actual = rendered[tc_id]
            if case.get("test_point") != actual["test_point"]:
                errors.append(f"{tc_id} 测试点与 XMind 不一致")
            if case.get("expected_results") != actual["expected_results"]:
                errors.append(f"{tc_id} 预期结果与 XMind 不一致")
        cases = {case.get("tc_id"): case for case in testcase_model.get("cases", [])}
        for record in records:
            for tc_id in record.testcase_ids:
                case = cases.get(tc_id)
                if not case:
                    continue
                if record.requirement_id and record.requirement_id not in case.get("requirement_ids", []):
                    errors.append(f"第 {record.line} 行需求点与 {tc_id} Testcase Model 不一致")
                if record.change_id and record.change_id not in case.get("change_ids", []):
                    errors.append(f"第 {record.line} 行 Diff 变更与 {tc_id} Testcase Model 不一致")
                if not set(record.risk_ids).issubset(set(case.get("risk_ids", []))):
                    errors.append(f"第 {record.line} 行风险与 {tc_id} Testcase Model 不一致")
    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings)), records


def validate_markdown_file(path: Path) -> Outline:
    return validate_markdown_text(path.read_text(encoding="utf-8-sig"), path)


def count_tree_nodes(node: Node) -> int:
    return 1 + sum(count_tree_nodes(child) for child in node.children)


def validate_xmind_archive(
    path: Path,
    expected_root: str | None = None,
    expected_tc_count: int | None = None,
    expected_node_count: int | None = None,
) -> dict:
    required = {"content.json", "metadata.json", "manifest.json"}
    try:
        archive_context = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValidationError(f"{path}: XMind 工作簿无法读取: {exc}") from exc
    with archive_context as archive:
        missing = required - set(archive.namelist())
        if missing:
            raise ValidationError(f"{path}: XMind 缺少 {sorted(missing)}")
        try:
            content = json.loads(archive.read("content.json").decode("utf-8"))
            json.loads(archive.read("metadata.json").decode("utf-8"))
            json.loads(archive.read("manifest.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError(f"{path}: XMind JSON 无法读取: {exc}") from exc

    if not isinstance(content, list) or len(content) != 1 or "rootTopic" not in content[0]:
        raise ValidationError(f"{path}: XMind 必须包含唯一根主题")
    root = content[0]["rootTopic"]
    titles: list[str] = []

    def walk(topic: dict) -> None:
        title = topic.get("title")
        if not isinstance(title, str) or not title:
            raise ValidationError(f"{path}: XMind 存在空标题节点")
        titles.append(title)
        children = topic.get("children", {}).get("attached", [])
        if not isinstance(children, list):
            raise ValidationError(f"{path}: XMind 子节点结构非法")
        for child in children:
            walk(child)

    walk(root)
    if expected_root is not None and root.get("title") != expected_root:
        raise ValidationError(f"{path}: 根主题名称不一致")
    actual_tc = sum(bool(TC_RE.fullmatch(title)) for title in titles)
    if expected_tc_count is not None and actual_tc != expected_tc_count:
        raise ValidationError(f"{path}: TC 数量 {actual_tc} 与 Markdown {expected_tc_count} 不一致")
    if expected_node_count is not None and len(titles) != expected_node_count:
        raise ValidationError(f"{path}: 节点数量 {len(titles)} 与 Markdown {expected_node_count} 不一致")
    return {"root": root.get("title"), "tc_count": actual_tc, "node_count": len(titles)}
