#!/usr/bin/env python3
"""Parse pasted DDL conservatively without connecting to a database."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


CREATE_RE = re.compile(r"(?is)\bcreate\s+table\b")
TABLE_NAME_RE = re.compile(
    r"(?is)\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?"
    r"(?P<name>(?:`[^`]+`|\"[^\"]+\"|[\w.]+))"
)
SENSITIVE_RE = re.compile(
    r"(?i)(?:(?:password|passwd|token|jdbc|private[_ -]?key|secret)\s*[:=]|"
    r"-----BEGIN [^-]*PRIVATE KEY-----)"
)
NAME_RE = re.compile(r"(?:`(?:``|[^`])+`|\"(?:\"\"|[^\"])+\"|[A-Za-z_][\w$]*)")
TYPE_NAME_RE = re.compile(r"[A-Za-z][\w]*")
TABLE_CONSTRAINT_PREFIXES = (
    "PRIMARY KEY", "UNIQUE KEY", "DUPLICATE KEY", "AGGREGATE KEY", "FOREIGN KEY",
    "CHECK", "CONSTRAINT", "UNIQUE INDEX", "INDEX", "KEY",
)
TAIL_STARTERS = (
    "engine", "duplicate key", "aggregate key", "unique key", "partition by",
    "distributed by", "order by", "properties", "comment",
)


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_ddl(text: str) -> str:
    """Normalize formatting only; do not rewrite names, types or dialect syntax."""

    without_comments = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    without_comments = re.sub(r"--[^\n]*", " ", without_comments)
    compact = re.sub(r"\s+", " ", without_comments).strip()
    return re.sub(r"\s*([(),])\s*", r"\1", compact)


def _scan_quoted(text: str, start: int) -> tuple[int | None, str | None]:
    quote = text[start]
    position = start + 1
    value: list[str] = []
    while position < len(text):
        char = text[position]
        if char == quote:
            if position + 1 < len(text) and text[position + 1] == quote:
                value.append(quote)
                position += 2
                continue
            return position + 1, "".join(value)
        if char == "\\" and position + 1 < len(text):
            value.append(text[position + 1])
            position += 2
            continue
        value.append(char)
        position += 1
    return None, None


def _scan_balanced(text: str, start: int, opener: str = "(", closer: str = ")") -> int | None:
    if start >= len(text) or text[start] != opener:
        return None
    depth = 0
    position = start
    while position < len(text):
        char = text[position]
        if char in "'\"`":
            end, _ = _scan_quoted(text, position)
            if end is None:
                return None
            position = end
            continue
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return position + 1
        position += 1
    return None


def _keyword_at(text: str, position: int, keyword: str) -> int | None:
    pattern = keyword.replace(" ", r"\s+")
    match = re.match(rf"(?is){pattern}(?![\w$])", text[position:])
    return position + match.end() if match else None


def _scan_until_keyword(text: str, start: int, keywords: tuple[str, ...]) -> int:
    round_depth = 0
    angle_depth = 0
    position = start
    while position < len(text):
        char = text[position]
        if char in "'\"`":
            end, _ = _scan_quoted(text, position)
            if end is None:
                return len(text)
            position = end
            continue
        if char == "(":
            round_depth += 1
        elif char == ")":
            round_depth = max(0, round_depth - 1)
        elif char == "<":
            angle_depth += 1
        elif char == ">":
            angle_depth = max(0, angle_depth - 1)
        if round_depth == 0 and angle_depth == 0:
            if any(_keyword_at(text, position, keyword) is not None for keyword in keywords):
                return position
        position += 1
    return len(text)


def split_create_tables(text: str) -> list[str]:
    statements: list[str] = []
    matches = list(CREATE_RE.finditer(text))
    for index, match in enumerate(matches):
        limit = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        candidate = text[match.start():limit]
        body_open = candidate.find("(")
        if body_open < 0:
            statements.append(candidate.strip())
            continue
        body_close = _scan_balanced(candidate, body_open)
        if body_close is None:
            statements.append(candidate.strip())
            continue
        semicolon = candidate.find(";", body_close)
        end = semicolon + 1 if semicolon >= 0 else len(candidate)
        statement = candidate[:end].strip()
        if statement:
            statements.append(statement)
    return statements


def _split_top_level(body: str) -> tuple[list[str], bool]:
    items: list[str] = []
    start = 0
    round_depth = 0
    angle_depth = 0
    position = 0
    while position < len(body):
        char = body[position]
        if char in "'\"`":
            end, _ = _scan_quoted(body, position)
            if end is None:
                return [body.strip()] if body.strip() else [], False
            position = end
            continue
        if char == "(":
            round_depth += 1
        elif char == ")":
            round_depth -= 1
            if round_depth < 0:
                return items, False
        elif char == "<" and round_depth == 0:
            angle_depth += 1
        elif char == ">" and round_depth == 0 and angle_depth > 0:
            angle_depth -= 1
        elif char == "," and round_depth == 0 and angle_depth == 0:
            item = body[start:position].strip()
            if item:
                items.append(item)
            start = position + 1
        position += 1
    item = body[start:].strip()
    if item:
        items.append(item)
    return items, round_depth == 0 and angle_depth == 0


def _scan_type(fragment: str, position: int) -> tuple[str | None, int, str | None]:
    match = TYPE_NAME_RE.match(fragment, position)
    if not match:
        return None, position, "missing field type"
    position = match.end()
    round_depth = 0
    angle_depth = 0
    while position < len(fragment):
        char = fragment[position]
        if char in "'\"`":
            return None, position, "quoted text is not valid in a field type"
        if char == "(":
            round_depth += 1
        elif char == ")":
            if round_depth == 0:
                break
            round_depth -= 1
        elif char == "<":
            angle_depth += 1
        elif char == ">":
            if angle_depth == 0:
                return None, position, "unbalanced type angle bracket"
            angle_depth -= 1
        elif char.isspace() and round_depth == 0 and angle_depth == 0:
            break
        position += 1
    if round_depth or angle_depth:
        return None, position, "unclosed field type"
    return fragment[match.start():position].strip(), position, None


def _scan_default(text: str, position: int) -> tuple[int | None, str | None, str | None]:
    while position < len(text) and text[position].isspace():
        position += 1
    if position >= len(text):
        return None, None, "DEFAULT has no expression"
    if text[position] in "'\"":
        end, value = _scan_quoted(text, position)
        return (end, value, None) if end is not None else (None, None, "unclosed DEFAULT string")
    if text[position] == "(":
        end = _scan_balanced(text, position)
        return (end, text[position:end], None) if end is not None else (None, None, "unclosed DEFAULT expression")
    number = re.match(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?![\w.])", text[position:])
    if number:
        end = position + number.end()
        return end, text[position:end], None
    word = re.match(r"(?i)(?:null|true|false|current_timestamp|now)(?![\w$])", text[position:])
    if word:
        end = position + word.end()
        if end < len(text) and text[end] == "(":
            call_end = _scan_balanced(text, end)
            if call_end is None:
                return None, None, "unclosed DEFAULT function call"
            end = call_end
        return end, text[position:end], None
    return None, None, "unsupported DEFAULT expression"


def parse_field_fragment(
    fragment: str,
    ordinal: int,
    *,
    full_name: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Parse one field and prove that its type and constraints were fully consumed."""

    raw = fragment.strip().rstrip(",").strip()
    warnings: list[str] = []
    name_match = NAME_RE.match(raw)
    if not name_match:
        return None, [f"table {full_name}: cannot parse field fragment: {raw[:80]}"]
    name = name_match.group(0).strip("`\"").replace("``", "`").replace('""', '"')
    position = name_match.end()
    while position < len(raw) and raw[position].isspace():
        position += 1
    type_name, position, type_error = _scan_type(raw, position)
    if type_error or not type_name:
        return None, [f"table {full_name} field {name}: {type_error or 'missing field type'}"]

    parsed_tokens = [f"name:{name}", f"type:{type_name}"]
    nullable: bool | None = None
    nullable_seen: list[bool] = []
    default_value: str | None = None
    default_state = "unknown"
    comment: str | None = None
    generated: bool | None = False
    generated_expression: str | None = None
    generated_type: str | None = None
    auto_increment: bool | None = False
    inline_constraints: list[str] = []

    while True:
        while position < len(raw) and raw[position].isspace():
            position += 1
        if position >= len(raw):
            break
        before = position
        end = _keyword_at(raw, position, "not null")
        if end is not None:
            nullable_seen.append(False)
            parsed_tokens.append("not null")
            position = end
        else:
            end = _keyword_at(raw, position, "null")
            if end is not None:
                nullable_seen.append(True)
                parsed_tokens.append("null")
                position = end
            else:
                end = _keyword_at(raw, position, "default")
                if end is not None:
                    value_end, value, error = _scan_default(raw, end)
                    if error or value_end is None:
                        warnings.append(f"table {full_name} field {name}: {error}")
                        break
                    default_state = "known_null" if value is not None and value.casefold() == "null" else "known_value"
                    default_value = None if default_state == "known_null" else value
                    parsed_tokens.append(f"default:{raw[end:value_end].strip()}")
                    position = value_end
                else:
                    end = _keyword_at(raw, position, "comment")
                    if end is not None:
                        while end < len(raw) and raw[end].isspace():
                            end += 1
                        if end >= len(raw) or raw[end] not in "'\"":
                            warnings.append(f"table {full_name} field {name}: COMMENT requires a quoted value")
                            break
                        value_end, value = _scan_quoted(raw, end)
                        if value_end is None:
                            warnings.append(f"table {full_name} field {name}: unclosed COMMENT string")
                            break
                        comment = value
                        parsed_tokens.append(f"comment:{raw[end:value_end]}")
                        position = value_end
                    else:
                        generated_end = _keyword_at(raw, position, "generated")
                        bare_as = False
                        if generated_end is None:
                            generated_end = _keyword_at(raw, position, "as")
                            bare_as = generated_end is not None
                        if generated_end is not None:
                            cursor = generated_end
                            mode = "as"
                            if not bare_as:
                                while cursor < len(raw) and raw[cursor].isspace():
                                    cursor += 1
                                always_end = _keyword_at(raw, cursor, "always")
                                if always_end is not None:
                                    cursor = always_end
                                    mode = "always"
                                while cursor < len(raw) and raw[cursor].isspace():
                                    cursor += 1
                                as_end = _keyword_at(raw, cursor, "as")
                                if as_end is None:
                                    warnings.append(f"table {full_name} field {name}: GENERATED requires AS")
                                    break
                                cursor = as_end
                                if mode != "always":
                                    mode = "generated"
                            while cursor < len(raw) and raw[cursor].isspace():
                                cursor += 1
                            expression_end = _scan_balanced(raw, cursor)
                            if expression_end is None:
                                warnings.append(f"table {full_name} field {name}: generated expression is not closed")
                                generated = None
                                break
                            generated = True
                            generated_expression = raw[cursor + 1:expression_end - 1]
                            generated_type = mode
                            parsed_tokens.append(f"generated:{raw[position:expression_end]}")
                            position = expression_end
                        else:
                            end = _keyword_at(raw, position, "auto_increment")
                            if end is not None:
                                auto_increment = True
                                parsed_tokens.append("auto_increment")
                                position = end
                            else:
                                matched_constraint = None
                                for token in ("primary key", "unique key", "unique", "key"):
                                    end = _keyword_at(raw, position, token)
                                    if end is not None:
                                        matched_constraint = token
                                        break
                                if matched_constraint is not None and end is not None:
                                    inline_constraints.append(matched_constraint)
                                    parsed_tokens.append(matched_constraint)
                                    position = end
                                else:
                                    break
        if position <= before:
            warnings.append(f"table {full_name} field {name}: parser made no progress")
            break

    if nullable_seen:
        nullable = nullable_seen[0]
        if any(value != nullable for value in nullable_seen[1:]):
            warnings.append(f"table {full_name} field {name}: conflicting NULL and NOT NULL constraints")
    evidence_fields = ["name", "type"]
    if nullable_seen:
        evidence_fields.append("nullable")
    if default_state != "unknown":
        evidence_fields.append("default")
    if comment is not None:
        evidence_fields.append("comment")
    if generated is True:
        evidence_fields.append("generated")
    unknown_fields = [item for item in ("nullable", "default", "comment") if item not in evidence_fields]
    remainder = raw[position:].strip() or None
    if remainder:
        warnings.append(f"table {full_name} field {name}: unparsed syntax: {remainder[:80]}")
    field = {
        "name": name,
        "type": type_name,
        "nullable": nullable,
        "default": default_value,
        "default_state": default_state,
        "comment": comment,
        "ordinal": ordinal,
        "evidence_fields": evidence_fields,
        "unknown_fields": unknown_fields,
        "raw_fragment": raw,
        "parsed_tokens": parsed_tokens,
        "unparsed_fragment": remainder,
        "generated": generated,
        "generated_expression": generated_expression,
        "generated_type": generated_type,
        "auto_increment": auto_increment,
        "inline_constraints": inline_constraints,
    }
    return field, warnings


def _parse_properties(raw: str) -> tuple[dict[str, str], bool]:
    items, balanced = _split_top_level(raw)
    if not balanced:
        return {}, False
    result: dict[str, str] = {}
    for item in items:
        match = re.fullmatch(
            r"\s*(?:'((?:''|[^'])*)'|\"((?:\"\"|[^\"])*)\"|([\w.-]+))\s*=\s*"
            r"(?:'((?:''|[^'])*)'|\"((?:\"\"|[^\"])*)\"|([^\s,]+))\s*",
            item,
        )
        if not match:
            return result, False
        groups = match.groups()
        key = next(value for value in groups[:3] if value is not None)
        value = next(value for value in groups[3:] if value is not None)
        result[key.replace("''", "'").replace('""', '"')] = value.replace("''", "'").replace('""', '"')
    return result, True


def parse_table_tail(
    tail: str,
    *,
    full_name: str,
) -> tuple[list[str], list[str], list[str], dict[str, str], list[str], str | None, list[str]]:
    raw_tail = tail.strip()
    if raw_tail.endswith(";"):
        raw_tail = raw_tail[:-1].rstrip()
    keys: list[str] = []
    partitions: list[str] = []
    indexes: list[str] = []
    engine_properties: dict[str, str] = {}
    parsed: list[str] = []
    warnings: list[str] = []
    position = 0
    while True:
        while position < len(raw_tail) and raw_tail[position].isspace():
            position += 1
        if position >= len(raw_tail):
            break
        before = position
        engine_end = _keyword_at(raw_tail, position, "engine")
        if engine_end is not None:
            cursor = engine_end
            while cursor < len(raw_tail) and raw_tail[cursor].isspace():
                cursor += 1
            if cursor >= len(raw_tail) or raw_tail[cursor] != "=":
                warnings.append(f"table {full_name}: Engine is missing '='")
                break
            cursor += 1
            while cursor < len(raw_tail) and raw_tail[cursor].isspace():
                cursor += 1
            value = re.match(r"[A-Za-z_][\w.-]*", raw_tail[cursor:])
            if not value:
                warnings.append(f"table {full_name}: Engine has no value")
                break
            if value.group(0).casefold() in {starter.split()[0] for starter in TAIL_STARTERS}:
                warnings.append(f"table {full_name}: Engine has no value")
                break
            position = cursor + value.end()
            engine_properties["engine"] = value.group(0)
            parsed.append(raw_tail[before:position])
        else:
            key_kind = next((kind for kind in ("duplicate key", "aggregate key", "unique key") if _keyword_at(raw_tail, position, kind) is not None), None)
            if key_kind:
                cursor = _keyword_at(raw_tail, position, key_kind)
                assert cursor is not None
                while cursor < len(raw_tail) and raw_tail[cursor].isspace():
                    cursor += 1
                end = _scan_balanced(raw_tail, cursor)
                if end is None:
                    warnings.append(f"table {full_name}: {key_kind.upper()} is not closed")
                    break
                token = raw_tail[position:end].strip()
                keys.append(token)
                parsed.append(token)
                position = end
            else:
                matched_clause = next((kind for kind in ("partition by", "distributed by", "order by") if _keyword_at(raw_tail, position, kind) is not None), None)
                if matched_clause:
                    end = _scan_until_keyword(raw_tail, _keyword_at(raw_tail, position, matched_clause) or position, TAIL_STARTERS)
                    token = raw_tail[position:end].strip()
                    if not token:
                        warnings.append(f"table {full_name}: empty {matched_clause.upper()} clause")
                        break
                    if matched_clause == "partition by":
                        partitions.append(token[len("partition by"):].strip())
                    else:
                        indexes.append(token)
                    parsed.append(token)
                    position = end
                else:
                    properties_end = _keyword_at(raw_tail, position, "properties")
                    if properties_end is not None:
                        cursor = properties_end
                        while cursor < len(raw_tail) and raw_tail[cursor].isspace():
                            cursor += 1
                        end = _scan_balanced(raw_tail, cursor)
                        if end is None:
                            warnings.append(f"table {full_name}: Properties is not closed")
                            break
                        values, valid = _parse_properties(raw_tail[cursor + 1:end - 1])
                        if not valid:
                            warnings.append(f"table {full_name}: Properties contains an unsupported item")
                            break
                        engine_properties.update(values)
                        parsed.append(raw_tail[position:end].strip())
                        position = end
                    else:
                        comment_end = _keyword_at(raw_tail, position, "comment")
                        if comment_end is not None:
                            cursor = comment_end
                            while cursor < len(raw_tail) and raw_tail[cursor].isspace():
                                cursor += 1
                            if cursor < len(raw_tail) and raw_tail[cursor] == "=":
                                cursor += 1
                                while cursor < len(raw_tail) and raw_tail[cursor].isspace():
                                    cursor += 1
                            if cursor >= len(raw_tail) or raw_tail[cursor] not in "'\"":
                                warnings.append(f"table {full_name}: table COMMENT requires a quoted value")
                                break
                            end, _ = _scan_quoted(raw_tail, cursor)
                            if end is None:
                                warnings.append(f"table {full_name}: table COMMENT is not closed")
                                break
                            parsed.append(raw_tail[position:end].strip())
                            position = end
                        else:
                            break
        if position <= before:
            warnings.append(f"table {full_name}: tail parser made no progress")
            break
    unparsed = raw_tail[position:].strip() or None
    if unparsed:
        warnings.append(f"table {full_name}: unparsed table tail: {unparsed[:80]}")
    return keys, partitions, indexes, engine_properties, parsed, unparsed, warnings


def detect_dialect(ddl: str) -> str:
    lowered = ddl.lower()
    if "engine=" in lowered or "distributed by" in lowered or "duplicate key" in lowered:
        return "doris/starrocks"
    if "stored as" in lowered or "row format" in lowered:
        return "hive"
    return "mysql-compatible"


def _blocked_table(full_name: str, statement: str, warning: str) -> dict[str, Any]:
    parts = full_name.split(".")
    raw = statement.strip()
    normalized = normalize_ddl(raw)
    return {
        "table_id": full_name.replace(".", "_"), "domain": "unknown",
        "database": parts[-2] if len(parts) > 1 else "", "table_name": parts[-1],
        "full_name": full_name, "dialect": detect_dialect(raw), "schema_scope": "blocked",
        "current_ddl_path": None, "raw_ddl": raw, "normalized_ddl": normalized,
        "raw_hash": _sha256(raw), "normalized_hash": _sha256(normalized), "fields": [],
        "keys": [], "partitions": [], "indexes": [], "engine_properties": {},
        "status": "candidate", "source_type": "chat_ddl", "source_requirement_ids": [],
        "last_verified_at": None, "parse_warnings": [warning], "applicability_scope": None,
        "raw_tail": "", "parsed_tail_tokens": [], "unparsed_tail": None,
    }


def parse_statement(statement: str, index: int = 1) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    name_match = TABLE_NAME_RE.search(statement)
    if not name_match:
        return None, [f"CREATE TABLE #{index}: cannot identify table name"]
    full_name = name_match.group("name").replace("`", "").replace('"', "")
    parts = full_name.split(".")
    database = parts[-2] if len(parts) > 1 else ""
    table_name = parts[-1]
    open_paren = statement.find("(", name_match.end())
    if open_paren < 0:
        warning = f"table {full_name}: missing field-definition parentheses"
        return _blocked_table(full_name, statement, warning), [warning]
    close_after = _scan_balanced(statement, open_paren)
    if close_after is None:
        warning = f"table {full_name}: field-definition parentheses are not closed"
        return _blocked_table(full_name, statement, warning), [warning]
    close_paren = close_after - 1
    body = statement[open_paren + 1:close_paren]
    items, body_balanced = _split_top_level(body)
    if not body_balanced:
        warning = f"table {full_name}: field or type delimiters are not closed"
        return _blocked_table(full_name, statement, warning), [warning]

    fields: list[dict[str, Any]] = []
    keys: list[str] = []
    indexes: list[str] = []
    for item in items:
        upper = item.lstrip().upper()
        constraint = next((prefix for prefix in TABLE_CONSTRAINT_PREFIXES if upper == prefix or upper.startswith(prefix + " ") or upper.startswith(prefix + "(")), None)
        if constraint:
            if constraint in {"UNIQUE INDEX", "INDEX", "KEY"}:
                indexes.append(item.strip())
            else:
                keys.append(item.strip())
            continue
        field, item_warnings = parse_field_fragment(item, len(fields) + 1, full_name=full_name)
        warnings.extend(item_warnings)
        if field is not None:
            fields.append(field)

    raw_tail = statement[close_after:].strip()
    tail_keys, partitions, tail_indexes, engine_properties, parsed_tail_tokens, unparsed_tail, tail_warnings = parse_table_tail(
        raw_tail, full_name=full_name
    )
    warnings.extend(tail_warnings)
    keys.extend(tail_keys)
    indexes.extend(tail_indexes)
    raw = statement.strip()
    normalized = normalize_ddl(raw)
    all_fields_consumed = bool(fields) and all(field["unparsed_fragment"] is None for field in fields)
    schema_scope = "complete" if all_fields_consumed and unparsed_tail is None and not warnings else "partial" if fields else "blocked"
    model = {
        "table_id": full_name.replace(".", "_"),
        "domain": "unknown",
        "database": database,
        "table_name": table_name,
        "full_name": full_name,
        "dialect": detect_dialect(raw),
        "schema_scope": schema_scope,
        "current_ddl_path": None,
        "raw_ddl": raw,
        "normalized_ddl": normalized,
        "raw_hash": _sha256(raw),
        "normalized_hash": _sha256(normalized),
        "fields": fields,
        "keys": keys,
        "partitions": partitions,
        "indexes": indexes,
        "engine_properties": engine_properties,
        "status": "candidate",
        "source_type": "chat_ddl",
        "source_requirement_ids": [],
        "last_verified_at": None,
        "parse_warnings": warnings,
        "applicability_scope": None,
        "raw_tail": raw_tail[:-1].rstrip() if raw_tail.endswith(";") else raw_tail,
        "parsed_tail_tokens": parsed_tail_tokens,
        "unparsed_tail": unparsed_tail,
    }
    return model, warnings


def parse_ddl(text: str) -> dict[str, Any]:
    input_raw_hash = _sha256(text)
    input_normalized_hash = _sha256(normalize_ddl(text))
    if SENSITIVE_RE.search(text):
        return {"tables": [], "warnings": ["input contains a possible sensitive credential marker"], "sensitive": True, "input_raw_hash": input_raw_hash, "input_normalized_hash": input_normalized_hash}
    statements = split_create_tables(text)
    if not statements:
        return {"tables": [], "warnings": ["no CREATE TABLE statement was identified"], "sensitive": False, "input_raw_hash": input_raw_hash, "input_normalized_hash": input_normalized_hash}
    tables: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, statement in enumerate(statements, 1):
        model, item_warnings = parse_statement(statement, index)
        warnings.extend(item_warnings)
        if model is not None:
            tables.append(model)
    return {"tables": tables, "warnings": warnings, "sensitive": False, "input_raw_hash": input_raw_hash, "input_normalized_hash": input_normalized_hash}


def parse_partial_fields(text: str, full_name: str, domain: str = "unknown") -> dict[str, Any]:
    """Parse explicitly supplied fields with the shared parser; scope always remains partial."""

    input_raw_hash = _sha256(text)
    input_normalized_hash = _sha256(normalize_ddl(text))
    if SENSITIVE_RE.search(text):
        return {"tables": [], "warnings": ["input contains a possible sensitive credential marker"], "sensitive": True, "input_raw_hash": input_raw_hash, "input_normalized_hash": input_normalized_hash}
    parts = full_name.split(".")
    database = parts[-2] if len(parts) > 1 else ""
    table_name = parts[-1]
    fields: list[dict[str, Any]] = []
    warnings: list[str] = []
    for line in text.splitlines():
        fragments, balanced = _split_top_level(line.strip().rstrip(";"))
        if not balanced:
            warnings.append(f"partial fields contain unclosed delimiters: {line[:80]}")
        for fragment in fragments:
            field, item_warnings = parse_field_fragment(fragment, len(fields) + 1, full_name=full_name)
            warnings.extend(item_warnings)
            if field is not None:
                fields.append(field)
    if not fields:
        warnings.append("no reliable field was identified")
    table = {
        "table_id": full_name.replace(".", "_"), "domain": domain, "database": database,
        "table_name": table_name, "full_name": full_name, "dialect": "unspecified",
        "schema_scope": "partial" if fields else "blocked", "current_ddl_path": None,
        "raw_ddl": None, "normalized_ddl": None, "raw_hash": input_raw_hash,
        "normalized_hash": input_normalized_hash, "fields": fields, "keys": [], "partitions": [],
        "indexes": [], "engine_properties": {}, "status": "candidate", "source_type": "chat_partial_fields",
        "source_requirement_ids": [], "last_verified_at": None, "parse_warnings": warnings,
        "applicability_scope": f"limited to {len(fields)} explicitly supplied fields" if fields else None,
        "raw_tail": "", "parsed_tail_tokens": [], "unparsed_tail": None,
    }
    return {"tables": [table], "warnings": warnings, "sensitive": False, "input_raw_hash": input_raw_hash, "input_normalized_hash": input_normalized_hash}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse CREATE TABLE DDL without database access or execution")
    parser.add_argument("input", nargs="?", help="UTF-8 DDL file; reads stdin when omitted")
    parser.add_argument("--partial", type=Path, help="UTF-8 file containing partial field definitions")
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--table", help="database.table for --partial mode")
    parser.add_argument("--domain", default="unknown")
    args = parser.parse_args(argv)
    if args.partial and args.input:
        parser.error("DDL input and --partial cannot be supplied together")
    if args.partial and not args.table:
        parser.error("--partial requires --table")
    if args.partial:
        text = args.partial.read_text(encoding="utf-8-sig")
        result = parse_partial_fields(text, args.table, args.domain)
    else:
        text = Path(args.input).read_text(encoding="utf-8-sig") if args.input else sys.stdin.read()
        result = parse_ddl(text)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    parse_succeeded = bool(result.get("tables")) and any(table.get("schema_scope") != "blocked" for table in result["tables"])
    return 0 if parse_succeeded and not result.get("sensitive") else 1


if __name__ == "__main__":
    raise SystemExit(main())
