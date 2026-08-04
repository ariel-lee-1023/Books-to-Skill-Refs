"""Plain-text family: .txt .md .markdown .rst .adoc.

Already text, so the work is decoding rather than parsing. Markup is left
intact on purpose: markdown headings feed structure.py's heading rules, and
fenced code feeds Step 3's technical/text tripwire.
"""

from __future__ import annotations

from pathlib import Path

from .base import ParsedDoc, read_text_file


def parse(path: Path) -> ParsedDoc:
    return ParsedDoc(text=read_text_file(path))
