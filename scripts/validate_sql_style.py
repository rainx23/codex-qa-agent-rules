#!/usr/bin/env python3
"""Static validation for read-only verification SQL; never parses or executes it remotely."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


HEADER_RE = re.compile(r"^/\*{4,}\n(?P<body>.*?)\n\*{4,}/", re.S)
UPPER_KEYWORDS = re.compile(r"\b(?:SELECT|FROM|WHERE|WITH|AS|JOIN|LEFT|RIGHT|FULL|INNER|OUTER|GROUP|BY|ORDER|HAVING|CASE|WHEN|THEN|ELSE|END|UNION|ALL|AND|OR|ON|IS|NULL|NOT|DISTINCT|COUNT|SUM|AVG|MIN|MAX)\b")
DANGEROUS = re.compile(r"(?i)\b(?:insert|update|delete|merge|alter|drop|truncate|create|grant|revoke|replace|call|execute)\b")


def find_config(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        path = candidate / "rules-repository.json"
        if path.is_file():
            return path
    return None


def load_sql_defaults(config: Path | None) -> tuple[dict[str, str], list[str]]:
    if config is None or not config.is_file():
        return {}, ["缺少 rules-repository.json，无法读取 SQL 默认配置"]
    try:
        defaults = json.loads(config.read_text(encoding="utf-8-sig")).get("sql_defaults", {})
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"SQL 配置无法读取：{exc}"]
    errors = [f"sql_defaults.{key} 缺失或为空" for key in ("author", "timezone", "dialect") if not isinstance(defaults.get(key), str) or not defaults.get(key).strip()]
    return defaults, errors


def validate_sql(text: str, strict: bool = False, config: Path | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    defaults, config_errors = load_sql_defaults(config or find_config(Path.cwd()))
    errors.extend(config_errors)
    header = HEADER_RE.match(text.lstrip("\ufeff"))
    if not header:
        errors.append("SQL 顶部必须使用固定星号注释块")
    else:
        body = header.group("body")
        if not re.search(r"(?m)^\*\* sql\s*$", body):
            errors.append("顶部注释缺少 ** sql")
        author = re.search(r"(?m)^\*\* author:\s*(\S.*?)\s*$", body)
        if not author or author.group(1).strip() != defaults.get("author"):
            errors.append(f"顶部注释 author 必须等于 sql_defaults.author={defaults.get('author')}")
        time_match = re.search(r"(?m)^\*\* create time:\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*$", body)
        if not time_match:
            errors.append("顶部注释 create time 必须精确到秒")
        else:
            try:
                datetime.strptime(time_match.group(1), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                errors.append(f"create time 不是有效 {defaults.get('timezone')} 时间格式")
        if not re.search(r"(?m)^\*\* description:\s*\S+", body):
            errors.append("顶部注释 description 不能为空")
        if not re.search(r"(?m)^\*\* comment:\s*\S+", body):
            errors.append("顶部注释 comment 不能为空")
    sql = text[header.end():] if header else text
    sql_for_checks = re.sub(r"(?s)^\s*(?:/\*.*?\*/\s*)+", "", sql)
    if DANGEROUS.search(sql_for_checks):
        errors.append("验证 SQL 只允许 select 或 with ... select，禁止 DML/危险 DDL")
    if not re.match(r"(?is)^\s*(?:select\b|with\b)", sql_for_checks):
        errors.append("验证 SQL 必须以 select 或 with 开始")
    if re.search(r"(?is)\bselect\s+\*|,\s*\*\s*(?:from|,)", sql_for_checks):
        errors.append("默认禁止 select *")
    if re.search(r"(?i)\blimit\b", sql_for_checks):
        errors.append("验证 SQL 默认禁止 limit")
    if "--" in sql_for_checks:
        errors.append("SQL 正文禁止使用横线注释模板")
    uppercase = UPPER_KEYWORDS.findall(sql_for_checks)
    if uppercase:
        errors.append(f"SQL 关键字必须小写：{sorted(set(uppercase))}")
    if re.search(r",\S", sql_for_checks):
        errors.append("逗号后必须保留一个空格")
    cte_matches = re.findall(r"(?is)(?:\bwith|,)\s*([A-Za-z_]\w*)\s+as\s*\(", sql_for_checks)
    if cte_matches and any(not name.startswith("v_") for name in cte_matches):
        errors.append("CTE 必须使用 v_ 前缀")
    if re.search(r"(?is)(?:\bwith|,)\s*/\*", sql_for_checks):
        errors.append("CTE 注释必须位于 with 或逗号前一行，不得写在同一行")
    if cte_matches and not re.search(r"(?s)/\*.*?\*/\s*\n\s*with\s+v_", sql):
        errors.append("首个 CTE 注释必须位于 with 前一行")
    if len(cte_matches) > 1 and not re.search(r"(?s)/\*.*?\*/\s*\n\s*,\s*v_", sql):
        errors.append("后续 CTE 注释必须位于逗号前一行")
    if re.search(r"(?is)\blateral\s+(?!json_each\s*\()", sql_for_checks):
        errors.append("仅允许 StarRocks lateral json_each(...) 形式")
    if re.search(r"(?i)\b(?:password|passwd|token|jdbc|private[_ -]?key|secret)\b", text):
        errors.append("SQL 文件不得包含账号、密码、Token 或连接配置")
    if re.search(r"(?m)^\s*(?:select|from|where)\b", sql_for_checks) and "," not in sql_for_checks:
        warnings.append("SQL 未出现逗号前置列清单，建议复核格式")
    projection = False
    projection_seen = False
    for line in sql_for_checks.splitlines():
        stripped = line.strip()
        lower = stripped.casefold()
        if lower.startswith("select"):
            projection = True
            projection_seen = False
            continue
        if projection and lower.startswith(("from", "where", "group by", "order by", "having", ")")):
            projection = False
            continue
        if projection and stripped:
            if projection_seen and not stripped.startswith(","):
                errors.append("查询列清单必须使用逗号前置")
            projection_seen = True
    if strict and warnings:
        errors.extend(f"strict 模式拒绝 warning：{warning}" for warning in warnings)
    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="静态校验只读验证 SQL，不执行 SQL")
    parser.add_argument("sql", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)
    try:
        config = args.config or find_config(args.sql.parent)
        errors, warnings = validate_sql(args.sql.read_text(encoding="utf-8-sig"), args.strict, config)
    except OSError as exc:
        errors, warnings = [str(exc)], []
    for warning in warnings:
        print(f"WARNING {warning}")
    for error in errors:
        print(f"FAIL {error}", file=sys.stderr)
    if not errors:
        print(f"PASS {args.sql}: SQL style valid")
    print(f"SUMMARY passed={0 if errors else 1} warning={len(warnings)} failed={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
