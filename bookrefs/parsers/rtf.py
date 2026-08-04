"""RTF on the standard library.

RTF is a control-word format, not a markup language, so this strips groups and
control words rather than parsing a tree. Unicode escapes (`\\uN?`) are decoded
because RTF written by Word stores all non-Latin text that way — dropping them
would silently empty a Chinese or Japanese document while appearing to succeed.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import ParsedDoc, read_text_file

# Groups whose entire contents are metadata, not body text.
_DISCARD_GROUPS = ("fonttbl", "colortbl", "stylesheet", "info", "pict",
                   "listtable", "listoverridetable", "rsidtbl", "generator")

_UNICODE = re.compile(r"\\u(-?\d+)\s?\??")
_HEXCHAR = re.compile(r"\\'([0-9a-fA-F]{2})")
_PARAGRAPH = re.compile(r"\\(par|line|pard|sect)\b")
_TAB = re.compile(r"\\tab\b")
_CONTROL = re.compile(r"\\\*?[a-zA-Z]+-?\d*\s?")
_ESCAPED = re.compile(r"\\([\\{}])")
_BRACES = re.compile(r"[{}]")
_BLANKS = re.compile(r"\n{3,}")


def _drop_metadata_groups(text: str) -> str:
    for name in _DISCARD_GROUPS:
        while True:
            start = text.find("{\\" + name)
            if start == -1:
                break
            depth, i = 0, start
            while i < len(text):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            text = text[:start] + text[i + 1:]
    return text


def rtf_to_text(raw: str) -> str:
    text = _drop_metadata_groups(raw)
    text = _UNICODE.sub(lambda m: chr(int(m.group(1)) % 65536), text)
    text = _HEXCHAR.sub(lambda m: bytes([int(m.group(1), 16)]).decode("cp1252", "replace"), text)
    text = _TAB.sub("\t", text)
    text = _PARAGRAPH.sub("\n", text)
    text = _ESCAPED.sub(r"\1", text)
    text = _CONTROL.sub("", text)
    text = _BRACES.sub("", text)
    return _BLANKS.sub("\n\n", text).strip()


def parse(path: Path) -> ParsedDoc:
    return ParsedDoc(text=rtf_to_text(read_text_file(path)))
