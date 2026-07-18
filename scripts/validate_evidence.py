#!/usr/bin/env python3
"""Validate Evidence Reference structure and repository-backed authenticity."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from file_hash_utils import stable_file_content_hash


EVIDENCE_REQUIRED_FIELDS = (
    "source_type", "storage_type", "source_path", "snapshot_path", "source_record_id",
    "line_start", "line_end", "commit_sha", "content_hash", "excerpt", "captured_at",
    "captured_timezone", "evidence_status",
)
FILE_ONLY_SOURCE_TYPES = {
    "requirement", "openspec", "markdown", "diff", "code_context", "api_document",
    "sql_definition", "complete_ddl", "knowledge_table",
}
SNAPSHOT_ONLY_SOURCE_TYPES = {"user_confirmation", "pasted_text", "chat_snapshot"}
HYBRID_SOURCE_TYPES = {
    "zentao_section_3", "acceptance_criteria", "formal_change_record", "screenshot",
    "historical_defect",
}
SOURCE_TYPES = FILE_ONLY_SOURCE_TYPES | SNAPSHOT_ONLY_SOURCE_TYPES | HYBRID_SOURCE_TYPES
STABLE_RECORD_SOURCE_TYPES = SNAPSHOT_ONLY_SOURCE_TYPES | HYBRID_SOURCE_TYPES
TEXT_SNAPSHOT_SOURCE_TYPES = {"user_confirmation", "pasted_text", "chat_snapshot"}
EVIDENCE_STATUSES = {"current", "stale", "reconfirm_required"}
CAPTURED_AT_PATTERN = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
HASH_PATTERN = r"^sha256:[0-9a-fA-F]{64}$"
COMMIT_SHA_PATTERN = r"^[0-9a-fA-F]{7,40}$"
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".pdf", ".xmind"}
INFERENCE_TOKENS = ("推断", "推测", "可能", "应该", "因此", "证明")
EVIDENCE_IDENTITY_FIELDS = (
    "source_path", "snapshot_path", "source_record_id", "line_start", "line_end", "content_hash", "excerpt",
)


def normalize_evidence_text(value: str) -> str:
    """Normalize line endings and whitespace without changing content order."""

    return re.sub(r"\s+", " ", value.replace("\r\n", "\n").replace("\r", "\n")).strip()


def evidence_reference_identity(evidence: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(evidence.get(field) for field in EVIDENCE_IDENTITY_FIELDS)


def _is_absolute_evidence_path(value: str) -> bool:
    native_path = Path(value)
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    return (
        native_path.is_absolute()
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
    )


def _resolve_evidence_path(value: Any, *, root: Path, label: str) -> tuple[Path | None, list[str]]:
    errors: list[str] = []
    if not isinstance(value, str) or not value.strip():
        return None, [f"{label} 必须是非空仓库相对路径"]
    candidate = Path(value)
    if _is_absolute_evidence_path(value):
        return None, [f"{label} 禁止绝对路径：{value}"]
    if ".." in candidate.parts:
        return None, [f"{label} 禁止包含 ../：{value}"]
    root = root.resolve()
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        return None, [f"{label} resolve 后越出仓库：{value}"]
    if not resolved.exists():
        errors.append(f"{label} 文件不存在：{value}")
    elif not resolved.is_file():
        errors.append(f"{label} 必须指向文件：{value}")
    return resolved if not errors else None, errors


def validate_evidence_reference(
    evidence: dict[str, Any],
    *,
    root: Path,
    confirmed: bool = False,
    changed_files: set[str] | None = None,
    expected_change_file: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(evidence, dict):
        return ["Evidence Reference 必须是 object"]
    missing = [field for field in EVIDENCE_REQUIRED_FIELDS if field not in evidence]
    if missing:
        errors.append(f"Evidence Reference 缺少必填字段：{', '.join(missing)}")

    source_type = evidence.get("source_type")
    storage_type = evidence.get("storage_type")
    status = evidence.get("evidence_status")
    if source_type not in SOURCE_TYPES:
        errors.append(f"source_type 非法：{source_type}")
    if storage_type not in {"file", "snapshot"}:
        errors.append(f"storage_type 非法：{storage_type}")
    if source_type in FILE_ONLY_SOURCE_TYPES and storage_type != "file":
        errors.append(f"{source_type} 只允许 storage_type=file")
    if source_type in SNAPSHOT_ONLY_SOURCE_TYPES and storage_type != "snapshot":
        errors.append(f"{source_type} 必须使用 storage_type=snapshot")
    if status not in EVIDENCE_STATUSES:
        errors.append(f"evidence_status 非法：{status}")
    if not re.fullmatch(CAPTURED_AT_PATTERN, str(evidence.get("captured_at", ""))):
        errors.append("captured_at 必须使用 yyyy-MM-dd HH:mm:ss")
    if evidence.get("captured_timezone") not in {"Asia/Shanghai", "UTC"}:
        errors.append("captured_timezone 必须明确声明")
    if not isinstance(evidence.get("excerpt"), str) or not evidence.get("excerpt", "").strip():
        errors.append("excerpt 必须是非空字符串")

    path_field = "source_path" if storage_type == "file" else "snapshot_path"
    other_path_field = "snapshot_path" if storage_type == "file" else "source_path"
    if evidence.get(other_path_field) is not None:
        errors.append(f"storage_type={storage_type} 时 {other_path_field} 必须为 null")
    resolved, path_errors = _resolve_evidence_path(evidence.get(path_field), root=root, label=path_field)
    errors.extend(path_errors)

    source_record_id = evidence.get("source_record_id")
    if source_type in STABLE_RECORD_SOURCE_TYPES and (
        not isinstance(source_record_id, str) or not source_record_id.strip()
    ):
        errors.append(f"{source_type} 必须提供稳定 source_record_id")
    if source_type == "screenshot" and isinstance(source_record_id, str) and not re.match(
        r"^(?:attachment|screenshot):", source_record_id
    ):
        errors.append("screenshot source_record_id 必须使用 attachment: 或 screenshot: 标识")
    if source_type == "user_confirmation" and isinstance(source_record_id, str) and not re.match(
        r"^(?:chat|snapshot):", source_record_id
    ):
        errors.append("user_confirmation source_record_id 必须使用 chat: 或 snapshot: 标识")

    content_hash = evidence.get("content_hash")
    if not re.fullmatch(HASH_PATTERN, str(content_hash or "")):
        errors.append("content_hash 必须使用 sha256:<64位十六进制>")
    if status in {"stale", "reconfirm_required"} and not evidence.get("stale_reason"):
        errors.append(f"{status} Evidence 必须填写 stale_reason")
    raw: bytes | None = None
    if resolved is not None:
        try:
            raw = resolved.read_bytes()
        except OSError as exc:
            errors.append(f"Evidence 文件无法读取：{exc}")
    if raw is not None and re.fullmatch(HASH_PATTERN, str(content_hash or "")):
        binary = resolved is not None and resolved.suffix.lower() in BINARY_SUFFIXES
        actual_hash = stable_file_content_hash(
            resolved,
            normalize_text_newlines=not binary,
        )
        if status == "current" and actual_hash != content_hash:
            errors.append(f"current Evidence content_hash 与文件不一致：actual={actual_hash}")

    if source_type in {"diff", "code_context"}:
        if storage_type != "file":
            errors.append("Diff/代码 Evidence 必须使用 file")
        working_tree = evidence.get("working_tree_evidence") is True
        commit_sha = evidence.get("commit_sha")
        if not working_tree and not re.fullmatch(COMMIT_SHA_PATTERN, str(commit_sha or "")):
            errors.append("committed Diff Evidence 必须提供 7～40 位十六进制 commit_sha")
        if working_tree and commit_sha is not None and not re.fullmatch(COMMIT_SHA_PATTERN, str(commit_sha)):
            errors.append("working tree Evidence 的 commit_sha 非空时格式必须合法")
        source_path = evidence.get("source_path")
        if expected_change_file is not None and source_path != expected_change_file:
            errors.append(f"Diff Evidence source_path 必须等于 change.file：{expected_change_file}")
        if changed_files is not None and source_path not in changed_files:
            errors.append(f"Diff Evidence source_path 不在 changed_files：{source_path}")

    if raw is not None:
        binary = resolved is not None and resolved.suffix.lower() in BINARY_SUFFIXES
        text: str | None = None
        if not binary:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                if source_type != "screenshot":
                    errors.append("文本 Evidence 必须可解码为 UTF-8")
        start, end = evidence.get("line_start"), evidence.get("line_end")
        if text is not None:
            if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
                errors.append("UTF-8 文本 Evidence 必须同时提供 line_start 和 line_end")
            elif start < 1 or end < start:
                errors.append("Evidence 行号范围非法")
            else:
                lines = text.splitlines()
                if end > len(lines):
                    errors.append(f"Evidence line_end 超出文件范围：{end}/{len(lines)}")
                else:
                    selected = normalize_evidence_text("\n".join(lines[start - 1:end]))
                    excerpt = normalize_evidence_text(str(evidence.get("excerpt", "")))
                    if not excerpt or excerpt not in selected:
                        errors.append("EVIDENCE_EXCERPT_OUTSIDE_RANGE: Evidence excerpt 不在指定行号范围")
        elif start is not None or end is not None:
            if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
                errors.append("二进制 Evidence 行号必须同时为 null 或合法范围")
    if source_type in TEXT_SNAPSHOT_SOURCE_TYPES and resolved is not None and resolved.suffix.lower() in BINARY_SUFFIXES:
        errors.append(f"{source_type} 快照必须是 UTF-8 文本文件")
    if source_type == "screenshot" and any(token in str(evidence.get("excerpt", "")) for token in INFERENCE_TOKENS):
        errors.append("screenshot excerpt 只能描述直接观察内容，不得包含推断")
    if confirmed and status != "current":
        errors.append(f"{status} Evidence 不得单独支撑 confirmed 结论")
    return list(dict.fromkeys(errors))


def validate_evidence_references(
    items: Any,
    *,
    label: str,
    root: Path,
    confirmed: bool = False,
    changed_files: set[str] | None = None,
    expected_change_file: str | None = None,
) -> list[str]:
    if not isinstance(items, list):
        return [f"{label}.evidence_references 必须是 array"]
    errors: list[str] = []
    authentic_current = False
    for index, evidence in enumerate(items):
        item_errors = validate_evidence_reference(
            evidence,
            root=root,
            changed_files=changed_files,
            expected_change_file=expected_change_file,
        )
        errors.extend(f"{label}.evidence_references[{index}] {error}" for error in item_errors)
        if isinstance(evidence, dict) and evidence.get("evidence_status") == "current" and not item_errors:
            authentic_current = True
    if confirmed and not authentic_current:
        code = "CONFIRMED_FACT_WITHOUT_CURRENT_EVIDENCE" if label.startswith("事实 ") else "CONFIRMED_EVIDENCE_REQUIRED"
        errors.append(f"{code}: {label} confirmed 结论至少需要一条真实且 current 的 Evidence")
    return list(dict.fromkeys(errors))


def evidence_precision_warnings(facts: Any, *, root: Path) -> list[str]:
    """Detect the mechanical 'every fact cites the same first line' pattern."""

    confirmed = [item for item in facts if isinstance(item, dict) and item.get("category") == "confirmed"] if isinstance(facts, list) else []
    if len(confirmed) < 3:
        return []
    references = [item.get("evidence_references") for item in confirmed]
    if any(not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict) for items in references):
        return []
    evidence_items = [items[0] for items in references]
    if len({evidence_reference_identity(item) for item in evidence_items}) != 1:
        return []
    evidence = evidence_items[0]
    if evidence.get("line_start") != evidence.get("line_end"):
        return []
    path_value = evidence.get("source_path") or evidence.get("snapshot_path")
    resolved, errors = _resolve_evidence_path(path_value, root=root, label="evidence_path")
    if errors or resolved is None or resolved.suffix.lower() in BINARY_SUFFIXES:
        return []
    try:
        effective_lines = [line for line in resolved.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError):
        return []
    if len(effective_lines) <= 1:
        return []
    return [
        "EVIDENCE_REFERENCE_OVERCONCENTRATED: 三条及以上 confirmed Fact 机械复用同一单行 Evidence，请复核真实行号与 excerpt"
    ]
