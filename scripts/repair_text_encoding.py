#!/usr/bin/env python3
"""Detect and repair reversible UTF-8/GBK mojibake in Markdown table cells."""

from __future__ import annotations

import argparse
from pathlib import Path

MARKERS = "娴绂銆鈥鍒嗘瀽闇€姹傜敤渚嬭緭鍑"


def marker_score(text: str) -> int:
    return sum(text.count(char) for char in MARKERS)


def repair_segment(text: str) -> str:
    if marker_score(text) < 2:
        return text
    try:
        candidate = text.encode("gb18030").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    return candidate if marker_score(candidate) < marker_score(text) else text


def repair_text(text: str) -> str:
    repaired: list[str] = []
    for line in text.splitlines():
        if "|" in line:
            parts = line.split("|")
            line = "|".join(repair_segment(part) for part in parts)
        else:
            line = repair_segment(line)
        repaired.append(line)
    return "\n".join(repaired) + ("\n" if text.endswith("\n") else "")


def merge_reference_index(text: str, reference: str) -> str:
    reference_lines = reference.splitlines()
    reference_rows = {}
    reference_title = next((line for line in reference_lines if line.startswith("# ")), "")
    reference_header = next(
        (line for line in reference_lines if line.startswith("|") and "生成时间" in line),
        "",
    )
    for line in reference_lines:
        match = __import__("re").match(r"^\|\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\|", line)
        if match:
            reference_rows[match.group(1)] = line

    merged = []
    for line in text.splitlines():
        timestamp = __import__("re").match(r"^\|\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\|", line)
        if timestamp and timestamp.group(1) in reference_rows and marker_score(line) >= 2:
            line = reference_rows[timestamp.group(1)]
        elif line.startswith("# ") and marker_score(line) >= 2 and reference_title:
            line = reference_title
        elif line.startswith("|") and not timestamp and "---" not in line and "生成时间" not in line and reference_header:
            line = reference_header
        merged.append(line)
    return "\n".join(merged) + ("\n" if text.endswith("\n") else "")


def main() -> int:
    parser = argparse.ArgumentParser(description="检查或修复可逆乱码")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--reference", type=Path, help="使用参考索引按时间戳恢复无法直接解码的历史行")
    args = parser.parse_args()
    changed = 0
    for path in args.files:
        original = path.read_text(encoding="utf-8-sig")
        repaired = repair_text(original)
        if args.reference:
            reference = args.reference.read_text(encoding="utf-8-sig")
            repaired = merge_reference_index(repaired, reference)
        if repaired != original:
            changed += 1
            if args.in_place:
                path.write_text(repaired, encoding="utf-8")
                print(f"REPAIRED {path}")
            else:
                print(f"NEEDS_REPAIR {path}")
        else:
            print(f"PASS {path}")
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
