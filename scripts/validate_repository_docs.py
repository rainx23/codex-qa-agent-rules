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
    ".codebuddy",
)
README_HEADINGS = ("## 目录定位", "## 维护约束")
CHANGELOG_ENTRY = re.compile(r"^## \[(?P<version>\d+\.\d+\.\d+)\] - (?P<date>.+)$")
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
RULE_MARKERS = ("小内容修改豁免", "不得根据当前文件状态编造历史版本", "历史信息不足")
README_SKILL_LINK = re.compile(r"skills/([a-z0-9][a-z0-9-]*)/SKILL\.md")


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


def validate_skill_catalog(root: Path) -> list[str]:
    """Derive the Skill catalog from disk and compare it with the root README."""

    skills_root = root / "skills"
    actual = {
        path.parent.name for path in skills_root.glob("*/SKILL.md") if path.is_file()
    } if skills_root.is_dir() else set()
    if not actual:
        return []
    readme = root / "README.md"
    if not readme.is_file():
        return ["缺少根 README.md，无法校验 Skill 清单"]
    text = readme.read_text(encoding="utf-8-sig")
    listed = set(README_SKILL_LINK.findall(text))
    errors: list[str] = []
    if listed != actual:
        errors.append(
            "根 README Skill 清单与实际 skills/*/SKILL.md 不一致："
            f"missing={sorted(actual - listed)} extra={sorted(listed - actual)}"
        )
    expected_count_phrase = f"{len(actual)} 个 QA Skills"
    if expected_count_phrase not in text:
        errors.append(f"根 README.md 未使用派生总数表述：{expected_count_phrase}")
    return errors


def read_skill_metadata(path: Path) -> tuple[str | None, str | None]:
    """Read name and description from a SKILL.md YAML frontmatter block."""
    if not path.is_file():
        return None, None

    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()

    if not lines or lines[0].strip() != "---":
        return None, None

    name: str | None = None
    description: str | None = None

    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip()

    return name, description


def validate_codebuddy_adapter(root: Path) -> list[str]:
    """Validate CodeBuddy entry files and thin Skill wrappers."""
    errors: list[str] = []

    entry_path = root / "CODEBUDDY.md"
    if not entry_path.is_file():
        errors.append("缺少 CodeBuddy 总入口 CODEBUDDY.md")
    else:
        entry_text = entry_path.read_text(encoding="utf-8-sig")
        if not re.search(r"(?m)^@AGENTS\.md\s*$", entry_text):
            errors.append("CODEBUDDY.md 未通过 @AGENTS.md 导入唯一权威入口")
        if ".codebuddy/skills/" not in entry_text:
            errors.append("CODEBUDDY.md 未说明 .codebuddy/skills/ 包装入口")
        if "scripts/validate_release.py" not in entry_text:
            errors.append("CODEBUDDY.md 未说明规则发布校验入口 validate_release.py")

    official_root = root / "skills"
    wrapper_root = root / ".codebuddy" / "skills"

    official_skills = {
        path.parent.name: path
        for path in official_root.glob("*/SKILL.md")
        if path.is_file()
    }

    wrapper_skills = {
        path.parent.name: path
        for path in wrapper_root.glob("*/SKILL.md")
        if path.is_file()
    } if wrapper_root.is_dir() else {}

    if not wrapper_root.is_dir():
        errors.append("缺少 CodeBuddy Skill 包装目录 .codebuddy/skills")
        return errors

    official_names = set(official_skills)
    wrapper_names = set(wrapper_skills)

    if wrapper_names != official_names:
        errors.append(
            "CodeBuddy Skill 包装清单与正式 Skill 不一致："
            f"missing={sorted(official_names - wrapper_names)} "
            f"extra={sorted(wrapper_names - official_names)}"
        )

    for skill_name in sorted(official_names & wrapper_names):
        official_path = official_skills[skill_name]
        wrapper_path = wrapper_skills[skill_name]

        official_name, official_description = read_skill_metadata(official_path)
        wrapper_name, wrapper_description = read_skill_metadata(wrapper_path)

        if official_name != skill_name:
            errors.append(
                f"正式 Skill 目录名与 frontmatter name 不一致："
                f"{official_path.relative_to(root)} name={official_name!r}"
            )

        if wrapper_name != skill_name:
            errors.append(
                f"CodeBuddy Skill 目录名与 frontmatter name 不一致："
                f"{wrapper_path.relative_to(root)} name={wrapper_name!r}"
            )

        if not official_description:
            errors.append(
                f"正式 Skill 缺少 description：{official_path.relative_to(root)}"
            )
        elif wrapper_description != official_description:
            errors.append(
                f"CodeBuddy Skill description 与正式 Skill 不一致：{skill_name}"
            )

        wrapper_text = wrapper_path.read_text(encoding="utf-8-sig")
        expected_reference = (
            f"@${{CODEBUDDY_SKILL_DIR}}/../../../skills/{skill_name}/SKILL.md"
        )

        if expected_reference not in wrapper_text:
            errors.append(
                f"CodeBuddy Skill 未引用正式 Skill："
                f"{wrapper_path.relative_to(root)} -> {expected_reference}"
            )

        if "唯一权威" not in wrapper_text:
            errors.append(
                f"CodeBuddy Skill 未声明正式 Skill 为唯一权威正文："
                f"{wrapper_path.relative_to(root)}"
            )

    return errors


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        version = read_rule_version(root)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    errors.extend(validate_changelog(root, version))
    errors.extend(validate_readmes(root))
    errors.extend(validate_skill_catalog(root))
    errors.extend(validate_codebuddy_adapter(root))
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
