#!/usr/bin/env python3
"""Validate repository-local Codex Skills with standard-library parsing."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def validate_skill(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return ["缺少 SKILL.md"]
    try:
        text = skill_file.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return ["SKILL.md 必须使用 UTF-8 编码"]
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return ["缺少合法 YAML frontmatter"]
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            errors.append(f"frontmatter 行非法：{line}")
            continue
        values[key.strip()] = value.strip().strip(chr(34) + "'")
    if set(values) != {"name", "description"}:
        errors.append("frontmatter 只能且必须包含 name、description")
    name = values.get("name", "")
    if name != skill_dir.name or not re.fullmatch(r"[a-z0-9-]{1,64}", name):
        errors.append("name 必须与目录一致并使用 hyphen-case")
    description = values.get("description", "")
    if not description:
        errors.append("description 不能为空")
    elif not re.search(r"[\u4e00-\u9fff]", description):
        errors.append("description 必须以中文场景说明为主")
    elif not re.search(r"[A-Za-z]", description):
        errors.append("description 必须保留必要的英文触发关键词")

    references = set(re.findall(r"(?:\.\./){2}(?:rules|scripts)/[A-Za-z0-9_./-]+", text))
    for reference in sorted(references):
        target = (skill_dir / reference.rstrip(".,;，。；")).resolve()
        if not target.exists():
            errors.append(f"引用不存在：{reference}")

    agent_file = skill_dir / "agents" / "openai.yaml"
    if not agent_file.is_file():
        errors.append("缺少 agents/openai.yaml")
    else:
        try:
            agent = agent_file.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            errors.append("openai.yaml 必须使用 UTF-8 编码")
            agent = ""
        for field in ("display_name:", "short_description:", "default_prompt:"):
            if field not in agent:
                errors.append(f"openai.yaml 缺少 {field}")
        if "interface:" not in agent:
            errors.append("openai.yaml 缺少 interface:")
        if "$" + name not in agent:
            errors.append("default_prompt 必须显式引用 Skill 名称")
        for field in ("display_name:", "short_description:", "default_prompt:"):
            if not re.search(rf"(?m)^\s*{re.escape(field)}\s*\S", agent):
                errors.append(f"openai.yaml 的 {field[:-1]} 不能为空")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验仓库 QA Skills")
    parser.add_argument("skills_root", type=Path, nargs="?", default=Path("skills"))
    args = parser.parse_args(argv)
    failed = 0
    for skill_dir in sorted(path for path in args.skills_root.iterdir() if path.is_dir()):
        errors = validate_skill(skill_dir)
        if errors:
            failed += 1
            print(f"FAIL {skill_dir}: " + "；".join(errors), file=sys.stderr)
        else:
            print(f"PASS {skill_dir}")
    total = sum(1 for path in args.skills_root.iterdir() if path.is_dir())
    print(f"SUMMARY passed={total - failed} warning=0 failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
