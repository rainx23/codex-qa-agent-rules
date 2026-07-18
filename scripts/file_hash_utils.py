#!/usr/bin/env python3
"""Cross-platform file content hashing utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath, PureWindowsPath


BINARY_ARTIFACT_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".pdf", ".xmind", ".zip",
}
UTF8_BOM = b"\xef\xbb\xbf"


def is_binary_artifact(path: Path) -> bool:
    return path.suffix.lower() in BINARY_ARTIFACT_SUFFIXES


def stable_file_content_bytes(path: Path, *, normalize_text_newlines: bool | None = None) -> bytes:
    """Return cross-platform bytes for text and byte-exact content for binaries."""

    content = path.read_bytes()
    normalize = not is_binary_artifact(path) if normalize_text_newlines is None else normalize_text_newlines
    if normalize:
        if content.startswith(UTF8_BOM):
            content = content[len(UTF8_BOM):]
        content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return content


def stable_file_content_hash(
    path: Path,
    *,
    normalize_text_newlines: bool | None = None,
) -> str:
    return "sha256:" + hashlib.sha256(stable_file_content_bytes(
        path, normalize_text_newlines=normalize_text_newlines,
    )).hexdigest()


def normalize_repository_relative_path(value: str) -> str:
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value.replace("\\", "/"))
    if windows.is_absolute() or windows.drive or posix.is_absolute() or ".." in posix.parts:
        raise ValueError(f"来源路径必须是仓库内相对路径：{value}")
    normalized = posix.as_posix()
    if normalized in {"", "."}:
        raise ValueError("来源路径不能为空")
    return normalized


def stable_multi_file_hash(root: Path, paths: list[str]) -> str:
    """Hash normalized relative paths plus normalized text or byte-exact binary content."""

    root_resolved = root.resolve()
    normalized_paths = sorted({normalize_repository_relative_path(value) for value in paths})
    digest = hashlib.sha256()
    for normalized in normalized_paths:
        path = (root_resolved / Path(*PurePosixPath(normalized).parts)).resolve()
        if path != root_resolved and root_resolved not in path.parents:
            raise ValueError(f"来源路径越界：{normalized}")
        if not path.is_file():
            raise ValueError(f"来源文件不存在：{normalized}")
        digest.update(normalized.encode("utf-8"))
        digest.update(b"\0")
        digest.update(stable_file_content_bytes(path))
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()
