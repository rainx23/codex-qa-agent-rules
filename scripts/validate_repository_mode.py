#!/usr/bin/env python3
"""Validate explicit standalone or integrated repository behavior."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


MIRRORED_ENTRIES = (
    "AGENTS.md", "README.md", "RULE_VERSION", ".github", "docs", "rules", "skills", "scripts", "tests",
    "testcases/manifest.example.json",
)


def repository_root(config: Path) -> Path:
    return config.resolve().parent


def _files(root: Path, entry: str) -> list[Path]:
    path = root / entry
    if not path.exists():
        return []
    if path.is_file():
        return [path]
    return [
        item for item in path.rglob("*")
        if item.is_file() and "__pycache__" not in item.parts and item.suffix != ".pyc"
    ]


def validate_mode(config_path: Path) -> tuple[str, list[str]]:
    try:
        data = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return "unknown", [f"仓库模式配置无法读取：{exc}"]
    mode = data.get("repository_mode")
    if mode not in {"standalone", "integrated"}:
        return str(mode), ["repository_mode 只允许 standalone 或 integrated"]
    if mode == "standalone":
        if data.get("template_path"):
            return mode, ["standalone 模式不得配置 template_path"]
        return mode, []

    template_path = data.get("template_path")
    if not isinstance(template_path, str) or not template_path:
        return mode, ["integrated 模式必须配置 template_path"]
    root = repository_root(config_path)
    template = (root / template_path).resolve()
    if root.resolve() not in template.parents or not template.is_dir():
        return mode, [f"integrated 模式模板目录不存在或越界：{template_path}"]
    errors: list[str] = []
    for entry in MIRRORED_ENTRIES:
        for source in _files(root, entry):
            relative = source.relative_to(root)
            target = template / relative
            if not target.is_file():
                errors.append(f"模板缺少文件：{relative.as_posix()}")
                continue
            if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
                errors.append(f"双目录内容不一致：{relative.as_posix()}")
    return mode, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验规则仓库运行模式")
    parser.add_argument("--config", type=Path, default=Path("rules-repository.json"))
    args = parser.parse_args(argv)
    mode, errors = validate_mode(args.config)
    if errors:
        for error in errors:
            print(f"FAIL {args.config}: {error}", file=sys.stderr)
    else:
        print(f"PASS {args.config}: repository_mode={mode}")
    print(f"SUMMARY passed={0 if errors else 1} warning=0 failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
