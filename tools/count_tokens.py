#!/usr/bin/env python3
"""Estimate token counts, with CJK-correct segmentation.

Why this exists
---------------
SKILL.md sets hard token budgets (Step 7's per-reference caps, Step 8's master
hard stop, Step 2.6's 4x input gate). A budget nobody can measure is not a
budget, so this is the instrument those rules are checked with.

Why not reuse the extractor's estimator: `book_to_skill.utils.estimate_tokens`
is `len(text.split()) / 0.75` — it counts space-delimited words. Chinese,
Japanese and Thai prose has no spaces, so a whole paragraph counts as one
"word". Measured: a 1,080-character Chinese passage estimates as 1 token
against a realistic ~720. That is a ~700x undercount, which would silently
defeat Step 2.5's cost gate on any CJK source.

Method
------
Segment by script density rather than by whitespace:

  * "dense" scripts (Han, Kana, Hangul, CJK/full-width punctuation, Thai)
    pack far more meaning per character and tokenize at roughly
    1 token per 1.5 characters.
  * everything else tokenizes at roughly 1 token per 4 characters, the
    conventional English approximation.

  tokens ~= dense_chars / 1.5 + other_chars / 4

This is an estimate, not a tokenizer. Expect +/-15% against a real BPE
tokenizer, which is well inside the precision the budgets need (they are
round numbers like 3,500 and 14,000). It is deterministic, needs no
third-party package, and — unlike a word-split estimator — never fails by
orders of magnitude on the languages this project is actually used with.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Characters per token, by script density. See the module docstring.
DENSE_CHARS_PER_TOKEN = 1.5
OTHER_CHARS_PER_TOKEN = 4.0

# Codepoint ranges that tokenize densely. Han covers Chinese and the Chinese
# characters in Japanese; Kana and Hangul are listed separately because they
# behave the same way for our purposes.
DENSE_RANGES = (
    (0x2E80, 0x2EFF),   # CJK radicals supplement
    (0x3000, 0x303F),   # CJK symbols and punctuation (、。「」etc.)
    (0x3040, 0x309F),   # Hiragana
    (0x30A0, 0x30FF),   # Katakana
    (0x3400, 0x4DBF),   # CJK Unified Ideographs Extension A
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0xF900, 0xFAFF),   # CJK compatibility ideographs
    (0xFF00, 0xFFEF),   # Halfwidth and fullwidth forms
    (0xAC00, 0xD7AF),   # Hangul syllables
    (0x0E00, 0x0E7F),   # Thai
    (0x20000, 0x2A6DF),  # CJK Extension B
)

_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def is_dense(ch: str) -> bool:
    """True if `ch` belongs to a script that packs ~1 token per 1.5 chars."""
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in DENSE_RANGES)


def estimate_tokens(text: str) -> int:
    """Estimate the token count of `text`. See the module docstring for method."""
    if not text:
        return 0
    dense = sum(1 for ch in text if is_dense(ch))
    other = len(text) - dense
    return int(dense / DENSE_CHARS_PER_TOKEN + other / OTHER_CHARS_PER_TOKEN)


def strip_frontmatter(text: str) -> str:
    """Drop a leading YAML frontmatter block.

    SKILL.md budgets are stated for the *body*; frontmatter is not part of it.
    """
    return _FRONTMATTER.sub("", text, count=1)


def count_file(path: Path, body_only: bool = False) -> int:
    text = path.read_text(encoding="utf-8")
    if body_only:
        text = strip_frontmatter(text)
    return estimate_tokens(text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Estimate token counts (CJK-correct).",
        epilog="Exit code is 1 if --budget is given and any file exceeds it.",
    )
    ap.add_argument("paths", nargs="*", type=Path, help="files to measure; omit to read stdin")
    ap.add_argument("--body-only", action="store_true",
                    help="ignore a leading YAML frontmatter block")
    ap.add_argument("--budget", type=int, metavar="N",
                    help="fail if a file exceeds N tokens")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="emit machine-readable output")
    args = ap.parse_args(argv)

    results: list[dict[str, object]] = []

    if not args.paths:
        text = sys.stdin.read()
        if args.body_only:
            text = strip_frontmatter(text)
        results.append({"path": "-", "tokens": estimate_tokens(text)})
    else:
        for path in args.paths:
            if not path.exists():
                print(f"x no such file: {path}", file=sys.stderr)
                return 2
            results.append({"path": str(path), "tokens": count_file(path, args.body_only)})

    over = []
    for r in results:
        if args.budget is not None and int(r["tokens"]) > args.budget:
            r["over_budget"] = True
            over.append(r)

    if args.as_json:
        print(json.dumps({"budget": args.budget, "files": results}, indent=2))
    else:
        width = max((len(str(r["path"])) for r in results), default=1)
        for r in results:
            flag = "  OVER" if r.get("over_budget") else ""
            print(f"{str(r['path']):<{width}}  {r['tokens']:>7,} tok{flag}")
        if len(results) > 1:
            total = sum(int(r["tokens"]) for r in results)
            print(f"{'TOTAL':<{width}}  {total:>7,} tok")

    if over:
        print(f"\nx {len(over)} file(s) over the {args.budget:,}-token budget", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
