#!/usr/bin/env python3
"""Conservative static extraction of SQL identifiers; never executes SQL."""

from __future__ import annotations

import re
from typing import Any

KEYWORDS = {"select", "from", "where", "join", "left", "right", "inner", "outer", "full", "on", "as", "and", "or", "not", "null", "is", "in", "with", "group", "by", "order", "having", "limit", "case", "when", "then", "else", "end", "distinct", "union", "all", "asc", "desc"}


def _clean(sql: str) -> tuple[str, list[str], list[str]]:
    text = re.sub(r"/\*.*?\*/|--[^\r\n]*", " ", sql, flags=re.S)
    parameters = re.findall(r"\$\{([A-Za-z_]\w*)\}|:([A-Za-z_]\w*)", text)
    parameter_names = [left or right for left, right in parameters]
    strings = re.findall(r"'(?:''|[^'])*'", text)
    text = re.sub(r"'(?:''|[^'])*'", "''", text)
    text = re.sub(r"\$\{[A-Za-z_]\w*\}|:[A-Za-z_]\w*", "?", text)
    return text, parameter_names, strings


def extract_sql_identifiers(sql_text: str, *, dialect: str = "") -> dict[str, Any]:
    text, parameters, strings = _clean(sql_text)
    uncommented = re.sub(r"/\*.*?\*/|--[^\r\n]*", " ", sql_text, flags=re.S)
    ctes = set(re.findall(r"(?i)(?:\bwith|,)\s*([A-Za-z_]\w*)\s+as\s*\(", text))
    table_pairs = re.findall(r"(?i)\b(?:from|join)\s+([A-Za-z_][\w.]*)(?:\s+(?:as\s+)?([A-Za-z_]\w*))?", text)
    tables: set[str] = set()
    aliases: dict[str, str] = {}
    for table, alias in table_pairs:
        if table not in ctes:
            tables.add(table)
            if alias and alias.casefold() not in KEYWORDS:
                aliases[alias] = table
    functions = {name.casefold() for name in re.findall(r"\b([A-Za-z_]\w*)\s*\(", text) if name.casefold() not in KEYWORDS and name not in ctes}
    qualified: set[str] = set()
    for owner, column in re.findall(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b", text):
        table = aliases.get(owner, owner)
        if table in tables:
            qualified.add(f"{table}.{column}")
    columns: set[str] = set(qualified)
    if len(tables) == 1:
        table = next(iter(tables))
        select_parts = re.findall(r"(?is)\bselect\s+(.*?)\bfrom\b", text)
        for part in select_parts:
            aliases_in_select = set(re.findall(r"(?i)\bas\s+([A-Za-z_]\w*)", part))
            part = re.sub(r"\b[A-Za-z_]\w*\s*\([^)]*\)", " ", part)
            for token in re.findall(r"\b[A-Za-z_]\w*\b", part):
                if token.casefold() not in KEYWORDS | functions and token not in aliases and token not in ctes and token not in aliases_in_select:
                    columns.add(f"{table}.{token}")
    filter_values = []
    for owner, column, value in re.findall(r"(?i)(?:(\w+)\.)?(\w+)\s*=\s*'([^'$][^']*)'", uncommented):
        table = aliases.get(owner, owner) if owner else (next(iter(tables)) if len(tables) == 1 else "")
        filter_values.append({"scope_table": table, "column": column, "value": value, "qualified_identifier": f"{column}={value}"})
    return {"physical_tables": sorted(tables), "cte_names": sorted(ctes), "table_aliases": aliases,
            "columns": sorted(columns), "functions": sorted(functions), "parameters": sorted(set(parameters)),
            "string_literals": strings, "filter_values": filter_values, "has_star": bool(re.search(r"(?i)\bselect\s+\*|\.\*", text))}
