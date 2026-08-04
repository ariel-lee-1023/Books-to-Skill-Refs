"""Shared parser types and byte decoding."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Tried in order. gb18030 before the latin fallback so Simplified Chinese text
# saved in a legacy encoding decodes as Chinese rather than as mojibake — a
# silent corruption that would otherwise reach the distillation intact.
ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "big5hkscs", "shift_jis", "cp1252", "latin-1")


@dataclass(frozen=True)
class ParsedDoc:
    """One source document's extracted text.

    `pages` is None when the format has no intrinsic pagination; the caller
    estimates a page-equivalent from character count instead.
    """
    text: str
    pages: int | None = None


def decode(data: bytes) -> str:
    for encoding in ENCODINGS:
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def read_text_file(path: Path) -> str:
    return decode(path.read_bytes())
