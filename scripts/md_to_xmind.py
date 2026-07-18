#!/usr/bin/env python3
"""Validate XMind Markdown and convert it to an XMind 2020+ archive."""

from __future__ import annotations
import argparse
import json
import sys
import time
import uuid
import zipfile
from pathlib import Path
from typing import Iterable
from qa_validation import Node, ValidationError, count_tree_nodes, markdown_tree, validate_markdown_file, validate_xmind_archive

def topic_id() -> str:
    return uuid.uuid4().hex

def node_to_topic(node: Node) -> dict:
    topic = {"id": topic_id(), "class": "topic", "title": node.title}
    if node.children:
        topic["children"] = {"attached": [node_to_topic(child) for child in node.children]}
    return topic

def write_xmind(root: Node, output: Path) -> None:
    sheet_id = topic_id()
    content = [{"id": sheet_id, "class": "sheet", "title": root.title, "rootTopic": node_to_topic(root), "topicPositioning": "fixed"}]
    now = int(time.time() * 1000)
    metadata = {"creator": {"name": "Codex QA Markdown to XMind", "version": "2.0.0"}, "activeSheetId": sheet_id, "created": now, "modified": now}
    manifest = {"file-entries": {"content.json": {}, "metadata.json": {}, "manifest.json": {}}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in (("content.json", content), ("metadata.json", metadata), ("manifest.json", manifest)):
            archive.writestr(name, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))

def default_output_path(path: Path) -> Path:
    stem = path.stem
    if "_xmind_" in stem:
        stem = stem.replace("_xmind_", "_workbook_", 1)
    elif stem.endswith("_xmind"):
        stem = stem[:-6] + "_workbook"
    elif not stem.endswith("_workbook"):
        stem += "_workbook"
    return path.with_name(stem + ".xmind")

def is_case_markdown(path: Path) -> bool:
    name = path.name.lower()
    return name != "index.md" and ("_xmind_" in name or name.endswith("_xmind.md"))

def iter_inputs(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            yield from (item for item in sorted(path.rglob("*.md")) if is_case_markdown(item))
        else:
            yield path

def convert_file(
    input_path: Path,
    output: Path | None = None,
    overwrite: bool = False,
    strict: bool = False,
) -> Path:
    input_path = input_path.resolve()
    output = (output or default_output_path(input_path)).resolve()
    if output.exists() and not overwrite:
        raise FileExistsError(f"{output}: 输出已存在；使用 --overwrite 明确覆盖")
    outline = validate_markdown_file(input_path)
    if strict and outline.warnings:
        raise ValidationError(f"{input_path}: strict 模式拒绝 {len(outline.warnings)} 个 warning")
    write_xmind(outline.root, output)
    try:
        validate_xmind_archive(
            output, outline.root.title, len(outline.tc_nodes), count_tree_nodes(outline.root),
            markdown_tree(outline.root),
        )
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return output

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验并转换 XMind Markdown")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--strict", action="store_true", help="warning 也导致当前文件转换失败")
    args = parser.parse_args(argv)
    files = list(iter_inputs(args.inputs))
    if not files:
        parser.error("未找到符合 *_xmind_*.md 或 *_xmind.md 命名的用例文件")
    if args.output and len(files) != 1:
        parser.error("--output 仅适用于单文件")
    passed: list[str] = []
    failed: list[str] = []
    for path in files:
        try:
            outline = validate_markdown_file(path)
            for warning in outline.warnings:
                print(f"WARNING {warning}")
            output = convert_file(path, args.output, args.overwrite, args.strict)
            passed.append(f"{path} -> {output}")
        except (OSError, ValidationError, ValueError, zipfile.BadZipFile) as exc:
            failed.append(f"{path}: {exc}")
    for item in passed:
        print(f"PASS {item}")
    for item in failed:
        print(f"FAIL {item}", file=sys.stderr)
    print(f"SUMMARY success={len(passed)} failed={len(failed)}")
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
