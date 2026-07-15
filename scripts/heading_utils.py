#!/usr/bin/env python3
"""Shared Markdown heading normalization and section extraction helpers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


_NUMBER = r"(?:[一二三四五六七八九十百零〇]+|\d+)"
_PAREN_NUMBER = re.compile(rf"^\(\s*{_NUMBER}\s*\)\s*")
_PLAIN_NUMBER = re.compile(rf"^{_NUMBER}(?:\s*[、.]\s*|\s+)")
_ORDINAL_NUMBER = re.compile(rf"^第\s*{_NUMBER}\s*(?:部分|章|节)\s*(?:[、.:：]\s*|\s+)?")
_HEADING = re.compile(
    r"(?m)^(?P<marks>#{1,6})[ \t]+(?P<title>.*?)[ \t]*#*[ \t]*(?:\r?\n|$)"
)


@dataclass(frozen=True)
class MarkdownSection:
    """A Markdown heading and the body owned by its heading level."""

    level: int
    raw_title: str
    title: str
    body: str


def normalize_heading(title: str) -> str:
    """Normalize full-width text and remove a leading Chinese/numeric section number."""

    normalized = unicodedata.normalize("NFKC", title).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    previous = None
    while previous != normalized:
        previous = normalized
        normalized = _ORDINAL_NUMBER.sub("", normalized, count=1).strip()
        normalized = _PAREN_NUMBER.sub("", normalized, count=1).strip()
        normalized = _PLAIN_NUMBER.sub("", normalized, count=1).strip()
    return normalized


def heading_key(title: str) -> str:
    """Return a case-insensitive key that ignores heading whitespace."""

    return re.sub(r"\s+", "", normalize_heading(title)).casefold()


def parse_markdown_sections(text: str) -> list[MarkdownSection]:
    """Parse headings once so existence checks and body extraction share one model."""

    matches = list(_HEADING.finditer(text))
    sections: list[MarkdownSection] = []
    for index, match in enumerate(matches):
        level = len(match.group("marks"))
        end = len(text)
        for following in matches[index + 1 :]:
            if len(following.group("marks")) <= level:
                end = following.start()
                break
        raw_title = match.group("title").strip()
        sections.append(
            MarkdownSection(
                level=level,
                raw_title=raw_title,
                title=normalize_heading(raw_title),
                body=text[match.end() : end].strip(),
            )
        )
    return sections
