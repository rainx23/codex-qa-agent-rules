#!/usr/bin/env python3
"""Validate repository README navigation and version-history governance."""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

from qa_contracts import read_rule_version


REQUIRED_README_DIRECTORIES = (
    "skills", "rules", "rules/core", "rules/profiles", "rules/schemas",
    "scripts", "tests", "testcases", "docs/codex", "qa-knowledge",
)
README_HEADINGS = ("## 目录定位", "## 维护约束")
CHANGELOG_ENTRY = re.compile(r"^## \[(?P<version>\d+\.\d+\.\d+)\] - (?P<date>.+)$")
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
RULE_MARKERS = ("小内容修改豁免", "不得根据当前文件状态编造历史版本", "历史信息不足")


def version_key(version: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


def validate_changelog(root: Path, version: str) -> list[str]:
    path = root / "CHANGELOG.md"
    if not path.is_file():
        return ["缺少 CHANGELOG.md"]
    text = path.read_text(encoding="utf-8-sig")
    if "RULE_VERSION" not in text:
        return ["CHANGELOG.md 未引用 RULE_VERSION"]
    entries: list[str] = []
    errors: list[str] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.startswith("## [") or line == "## [Unreleased]":
            continue
        match = CHANGELOG_ENTRY.fullmatch(line)
        if not match:
            errors.append(f"CHANGELOG.md 第 {line_no} 行版本标题或日期格式错误")
            continue
        entry_version, entry_date = match.group("version", "date")
        try:
            datetime.strptime(entry_date, "%Y-%m-%d")
        except ValueError:
            if entry_date != "日期待确认":
                errors.append(f"CHANGELOG.md 第 {line_no} 行日期不是 yyyy-mm-dd")
        entries.append(entry_version)
    if version not in entries:
        errors.append(f"CHANGELOG.md 缺少当前 RULE_VERSION={version} 的版本章节")
    if len(entries) != len(set(entries)):
        errors.append("CHANGELOG.md 存在重复版本章节")
    if entries != sorted(entries, key=version_key, reverse=True):
        errors.append("CHANGELOG.md 正式版本未按从新到旧排序")
    return errors


def validate_readmes(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_README_DIRECTORIES:
        directory = root / relative
        if not directory.is_dir():
            continue
        path = directory / "README.md"
        if not path.is_file():
            errors.append(f"{relative} 缺少 README.md")
            continue
        text = path.read_text(encoding="utf-8-sig")
        if not text.strip():
            errors.append(f"{relative}/README.md 为空")
            continue
        for heading in README_HEADINGS:
            if heading not in text:
                errors.append(f"{relative}/README.md 缺少 {heading}")
        if relative == "rules/schemas" and "自动生成" not in text:
            errors.append("rules/schemas/README.md 未说明 Schema 是否自动生成")
        if re.search(r"^## \[\d+\.\d+\.\d+\]", text, flags=re.MULTILINE):
            errors.append(f"{relative}/README.md 不得维护独立完整版本历史")
        for target in MARKDOWN_LINK.findall(text):
            target = target.split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if not (path.parent / target).resolve().exists():
                errors.append(f"{relative}/README.md 引用路径不存在：{target}")
    return errors


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        version = read_rule_version(root)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    errors.extend(validate_changelog(root, version))
    errors.extend(validate_readmes(root))
    rule_path = root / "rules/core/repository-documentation-rules.md"
    if not rule_path.is_file():
        errors.append("缺少正式规则 rules/core/repository-documentation-rules.md")
    else:
        rule_text = rule_path.read_text(encoding="utf-8-sig")
        for marker in RULE_MARKERS:
            if marker not in rule_text:
                errors.append(f"repository-documentation-rules.md 缺少规则：{marker}")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = validate_repository(root)
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
    else:
        print("PASS repository documentation and version history are valid")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
