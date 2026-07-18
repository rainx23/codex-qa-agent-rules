#!/usr/bin/env python3
"""Verify that an XMind workbook losslessly matches its Markdown source."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qa_validation import ValidationError, count_tree_nodes, validate_markdown_file, validate_xmind_archive


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 XMind Markdown 与工作簿节点完整性")
    parser.add_argument("xmind", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    markdown = args.markdown or args.xmind.with_suffix(".xmind.md")
    try:
        outline = validate_markdown_file(markdown)
        node_count = count_tree_nodes(outline.root)
        validate_xmind_archive(
            args.xmind,
            expected_root=outline.root.title,
            expected_tc_count=len(outline.tc_nodes),
            expected_node_count=node_count,
        )
    except (OSError, ValidationError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        print("SUMMARY passed=0 warning=0 failed=1")
        return 1
    for warning in outline.warnings:
        print(f"WARNING {warning}")
    print(f"PASS {args.xmind}: tc={len(outline.tc_nodes)} nodes={node_count}")
    print(f"SUMMARY passed=1 warning={len(outline.warnings)} failed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
