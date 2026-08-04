"""Normalisation applied to every parser's output.

Two jobs. The first is cosmetic: parsers disagree about line endings, hard
wrapping and how much blank space a page break leaves behind, and downstream
`grep`/`sed` slicing works better on predictable lines.

The second is a safety boundary. Extracted text is written to full_text.txt,
read by an agent, and distilled into files that a host agent later loads as
instructions. A source document can therefore try to smuggle a fence of its
own into the corpus and make its content look like a different book, or hide
directives in characters a human reviewer will not see. Neither is exotic:
both are a `sed` away in any EPUB.
"""

from __future__ import annotations

import re
import unicodedata

from .config import FENCE_MARKER, FENCE_RULE

# Zero-width and bidirectional-override characters. Legitimate in a handful of
# scripts, but in extracted prose they overwhelmingly mean hidden text.
_INVISIBLE = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TRAILING_WS = re.compile(r"[ \t]+$", re.MULTILINE)
_MANY_BLANKS = re.compile(r"\n{4,}")
_MANY_SPACES = re.compile(r"[ \t]{3,}")


def neutralise_fences(text: str) -> str:
    """Stop source content from forging a per-source separator.

    A document containing a line of 80 '=' followed by "SOURCE: other-book.pdf"
    would otherwise split one book into two in every downstream slice. The
    marker is broken, not deleted, so the tampering stays visible to a reader.
    """
    out = []
    for line in text.splitlines():
        if line.startswith(FENCE_MARKER):
            line = "[quoted] " + line
        elif line.strip() == FENCE_RULE:
            line = line.replace("=", "-")
        out.append(line)
    return "\n".join(out)


def sanitize(text: str) -> str:
    """Normalise extracted text and strip invisible characters."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _INVISIBLE.sub("", text)
    text = _CONTROL.sub("", text)
    text = _MANY_SPACES.sub("  ", text)
    text = _TRAILING_WS.sub("", text)
    text = _MANY_BLANKS.sub("\n\n\n", text)
    text = neutralise_fences(text)
    return text.strip() + "\n"
