#!/usr/bin/env python3
"""Convert XMind-style Markdown outlines to .xmind files.

The expected Markdown format is the repository's testcase outline format:

- Root topic
    - Dimension
        - TC001
            - Scenario

Only dash-list items are converted. Indentation is interpreted as 4 spaces
per level, which matches docs/codex/xmind-case-rules.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class Node:
    title: str
    children: list["Node"] = field(default_factory=list)


LIST_ITEM_RE = re.compile(r"^(?P<indent> *)(?:-)\s+(?P<title>.+?)\s*$")


def parse_markdown_outline(markdown: str, source: Path) -> Node:
    stack: list[tuple[int, Node]] = []
    roots: list[Node] = []

    for line_no, raw_line in enumerate(markdown.splitlines(), start=1):
        if not raw_line.strip():
            continue

        if "\t" in raw_line:
            raise ValueError(f"{source}:{line_no}: tab indentation is not supported")

        match = LIST_ITEM_RE.match(raw_line)
        if not match:
            raise ValueError(f"{source}:{line_no}: expected a Markdown '- ' list item")

        indent = len(match.group("indent"))
        if indent % 4 != 0:
            raise ValueError(f"{source}:{line_no}: indentation must be a multiple of 4 spaces")

        level = indent // 4
        node = Node(match.group("title"))

        if level == 0:
            roots.append(node)
            stack = [(level, node)]
            continue

        while stack and stack[-1][0] >= level:
            stack.pop()

        if not stack:
            raise ValueError(f"{source}:{line_no}: found child item without a parent")

        stack[-1][1].children.append(node)
        stack.append((level, node))

    if len(roots) != 1:
        raise ValueError(f"{source}: expected exactly one root topic, found {len(roots)}")

    return roots[0]


def topic_id() -> str:
    return uuid.uuid4().hex


def node_to_topic(node: Node) -> dict:
    topic = {
        "id": topic_id(),
        "class": "topic",
        "title": node.title,
    }

    if node.children:
        topic["children"] = {"attached": [node_to_topic(child) for child in node.children]}

    return topic


def build_content(root: Node) -> list[dict]:
    return [
        {
            "id": topic_id(),
            "class": "sheet",
            "title": root.title,
            "rootTopic": node_to_topic(root),
            "topicPositioning": "fixed",
        }
    ]


def build_metadata() -> dict:
    created = int(time.time() * 1000)
    return {
        "creator": {
            "name": "Codex Markdown to XMind",
            "version": "1.0",
        },
        "activeSheetId": None,
        "created": created,
        "modified": created,
    }


def build_manifest() -> dict:
    return {
        "file-entries": {
            "content.json": {},
            "metadata.json": {},
            "manifest.json": {},
        }
    }


def write_xmind(root: Node, output_path: Path) -> None:
    content = build_content(root)
    metadata = build_metadata()
    metadata["activeSheetId"] = content[0]["id"]
    manifest = build_manifest()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "content.json",
            json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        archive.writestr(
            "metadata.json",
            json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )


def default_output_path(input_path: Path) -> Path:
    stem = input_path.stem
    if "_xmind_" in stem:
        stem = stem.replace("_xmind_", "_workbook_", 1)
    elif not stem.endswith("_workbook"):
        stem = f"{stem}_workbook"
    return input_path.with_name(f"{stem}.xmind")


def convert_file(input_path: Path, output_path: Path | None = None) -> Path:
    input_path = input_path.resolve()
    if output_path is None:
        output_path = default_output_path(input_path)
    else:
        output_path = output_path.resolve()

    markdown = input_path.read_text(encoding="utf-8-sig")
    root = parse_markdown_outline(markdown, input_path)
    write_xmind(root, output_path)
    return output_path


def iter_markdown_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(path.rglob("*.md"))
        else:
            yield path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Convert testcase Markdown outlines to .xmind files")
    parser.add_argument("inputs", nargs="+", type=Path, help="Markdown file(s) or directories")
    parser.add_argument("-o", "--output", type=Path, help="Output .xmind path; only valid for one input file")
    args = parser.parse_args(argv)

    input_files = list(iter_markdown_files(args.inputs))
    if not input_files:
        parser.error("no Markdown files found")

    if args.output and len(input_files) != 1:
        parser.error("--output can only be used with one input file")

    for input_file in input_files:
        output_path = convert_file(input_file, args.output)
        print(f"{input_file} -> {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
