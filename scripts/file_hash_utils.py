#!/usr/bin/env python3
"""Cross-platform file content hashing utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path


def stable_file_content_hash(
    path: Path,
    *,
    normalize_text_newlines: bool,
) -> str:
    content = path.read_bytes()
    if normalize_text_newlines:
        content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return "sha256:" + hashlib.sha256(content).hexdigest()
