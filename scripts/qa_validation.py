#!/usr/bin/env python3
"""Shared deterministic validators for QA Markdown and XMind artifacts."""

from __future__ import annotations

import json
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

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
TC_RE = re.compile(r"^TC(?P<number>\d{3,})$")
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


def descendant_paths(node: Node) -> list[list[Node]]:
    if not node.children:
        return [[node]]
    return [[node, *tail] for child in node.children for tail in descendant_paths(child)]


def walk_nodes(node: Node) -> list[Node]:
    return [node, *(item for child in node.children for item in walk_nodes(child))]


def _canonical_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).lower()
    value = re.sub(r"[\s，。；、:：()（）【】\[\]'“”]+", "", value)
    value = re.sub(r"正式|模拟", "", value)
    value = re.sub(
        r"[\u4e00-\u9fffA-Za-z0-9_]+(?=(?:字段|必填|留空|为空|未填写|格式|长度|范围|校验|弹窗|页面))",
        "<对象>",
        value,
    )
    return value


def _case_signature(tc: Node) -> str:
    return "|".join(_canonical_text(node.title) for node in walk_nodes(tc)[1:])


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

            signature = _case_signature(tc)
            if signature in case_signatures:
                previous = case_signatures[signature]
                errors.append(f"{source}:{tc.line}: {tc.title} 与 {previous.title} 属于同规则重复用例")
            case_signatures[signature] = tc

    numbers = [int(TC_RE.fullmatch(node.title).group("number")) for node in tc_nodes]
    if numbers != list(range(1, len(numbers) + 1)):
        errors.append(f"{source}: TC 编号必须从 TC001 全局连续，实际 {numbers}")
    if len(numbers) != len(set(numbers)):
        errors.append(f"{source}: TC 编号重复")
    if not tc_nodes:
        errors.append(f"{source}: 未找到 TC 节点")

    for expected in expected_nodes:
        matched = [token for token in FUZZY_ASSERTIONS if token in expected.title]
        if matched:
            errors.append(f"{source}:{expected.line}: 预期包含模糊断言 {matched}，必须改为可观察结果")

    if errors:
        raise ValidationError("\n".join(dict.fromkeys(errors)))
    return Outline(root, nodes, tc_nodes, expected_nodes)


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
    with zipfile.ZipFile(path) as archive:
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

