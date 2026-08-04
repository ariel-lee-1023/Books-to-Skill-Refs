"""Token estimation by script density. The canonical implementation.

`tools/count_tokens.py` is a CLI over this module, and the extractor writes its
output into metadata.json, so the cost gate, the budget caps and the validator
all agree on one definition.

Why not a word-split estimate
-----------------------------
The conventional `len(text.split()) / 0.75` counts space-delimited words.
Chinese, Japanese and Thai prose has no spaces, so a whole paragraph counts as
one "word". Measured: a 1,080-character Chinese passage estimates as 1 token
against a realistic ~720 — a ~700x undercount, which silently defeats the
pre-generation cost gate on any CJK source.

Method: segment by script density.

  * "dense" scripts (Han, Kana, Hangul, CJK/full-width punctuation, Thai) pack
    far more meaning per character and tokenize at ~1 token / 1.5 characters.
  * everything else tokenizes at ~1 token / 4 characters.

An estimate, not a tokenizer: expect +/-15% against a real BPE tokenizer, which
is well inside the precision round budgets like 3,500 and 14,000 need. It is
deterministic, needs no third-party package, and never fails by orders of
magnitude on the languages this project is actually used with.
"""

from __future__ import annotations

import re

from .config import DENSE_CHARS_PER_TOKEN, OTHER_CHARS_PER_TOKEN

# Codepoint ranges that tokenize densely. Han covers Chinese and the Chinese
# characters in Japanese; Kana and Hangul are listed separately because they
# behave the same way for our purposes.
DENSE_RANGES = (
    (0x2E80, 0x2EFF),    # CJK radicals supplement
    (0x3000, 0x303F),    # CJK symbols and punctuation
    (0x3040, 0x309F),    # Hiragana
    (0x30A0, 0x30FF),    # Katakana
    (0x3400, 0x4DBF),    # CJK Unified Ideographs Extension A
    (0x4E00, 0x9FFF),    # CJK Unified Ideographs
    (0xF900, 0xFAFF),    # CJK compatibility ideographs
    (0xFF00, 0xFFEF),    # Halfwidth and fullwidth forms
    (0xAC00, 0xD7AF),    # Hangul syllables
    (0x0E00, 0x0E7F),    # Thai
    (0x20000, 0x2A6DF),  # CJK Extension B
)

_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def is_dense(ch: str) -> bool:
    """True if `ch` belongs to a script that packs ~1 token per 1.5 chars."""
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in DENSE_RANGES)


def count_dense(text: str) -> int:
    return sum(1 for ch in text if is_dense(ch))


def estimate_tokens(text: str) -> int:
    """Estimate the token count of `text`. See the module docstring."""
    if not text:
        return 0
    dense = count_dense(text)
    other = len(text) - dense
    return int(dense / DENSE_CHARS_PER_TOKEN + other / OTHER_CHARS_PER_TOKEN)


def strip_frontmatter(text: str) -> str:
    """Drop a leading YAML frontmatter block.

    SKILL.md budgets are stated for the *body*; frontmatter is not part of it.
    """
    return _FRONTMATTER.sub("", text, count=1)


def count_words(text: str) -> int:
    """Word count that does not pretend CJK has spaces.

    Latin words are whitespace-delimited; dense-script characters each count as
    a word, which is the closest honest analogue. Reported in metadata for
    human orientation only — budgets use estimate_tokens.
    """
    dense = count_dense(text)
    latin = len([w for w in re.split(r"\s+", text) if w and not all(is_dense(c) for c in w)])
    return dense + latin
