#!/usr/bin/env python3
"""Strip boilerplate from a span before reading it, and report what that saved.

Why this exists
---------------
Step 2.6 controls *how much* gets read by slicing instead of reading whole
files. It says nothing about what is in the slice, and converted sources carry
a great deal that costs tokens and teaches nothing: PDF page markers and `Link:`
runs, reStructuredText directives, per-page site navigation, and end-of-chapter
quiz blocks that repeat every multiple-choice option once per answer. On one
measured chapter the quiz block was ~250 of 460 lines — more than half the read.

Those tokens come out of the Step 2.6 input budget (<= 4x a book's output
budget), so cleaning a slice is not tidiness; it is what keeps the budget real.

Where this must not run
-----------------------
On `full_text.txt` itself. Parsers deliberately preserve `#` headings and pipe
table rows because `structure.py` reads the first and Step 3's technical/text
tripwire counts the second. This cleans a *copy of a span on its way to being
read*, leaving the extracted corpus intact.

Usage
-----
    python tools/clean_slice.py full_text.txt --range 48348,48803
    python tools/clean_slice.py full_text.txt --source book.pdf --filters pdf,repeats
    python tools/clean_slice.py chapter.md --stats-only

Filters (auto-detected unless --filters is given):
    pdf       page markers, Link: runs, image refs, mangled table scaffolding
    rst       .. directives, :option: lines, ==== underlines
    nav       navigation chrome from HTML exports
    quiz      truncate at an end-of-chapter quiz block
    repeats   lines repeated 4+ times (running headers, page furniture)
    blanks    collapse blank-line runs

Exit codes: 0 ok, 2 usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bookrefs.denoise import DEFAULT_ORDER, clean  # noqa: E402
from bookrefs.tokens import estimate_tokens  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_structure import resolve_span  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Remove boilerplate from a span before reading it.",
        epilog="Filters: " + ", ".join(DEFAULT_ORDER) + ". Writes to stdout; stats to stderr.",
    )
    ap.add_argument("text", type=Path, help="full_text.txt or a single file")
    ap.add_argument("--source", help="restrict to one source, resolved via metadata.json")
    ap.add_argument("--range", dest="line_range", metavar="START,END",
                    help="restrict to a 1-indexed inclusive line range")
    ap.add_argument("--filters", help="comma-separated subset (default: auto-detect)")
    ap.add_argument("--out", type=Path, help="write here instead of stdout")
    ap.add_argument("--stats-only", action="store_true", help="report savings, emit nothing")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    if not args.text.is_file():
        print(f"x no such file: {args.text}", file=sys.stderr)
        return 2

    start, end, label = resolve_span(args.text, args.source, args.line_range)
    all_lines = args.text.read_text(encoding="utf-8", errors="replace").splitlines()
    span = "\n".join(all_lines[start - 1:end])

    chosen = tuple(f.strip() for f in args.filters.split(",")) if args.filters else None
    result = clean(span, filters=chosen)

    before_tokens = estimate_tokens(span)
    after_tokens = estimate_tokens(result.text)
    saved = before_tokens - after_tokens
    saved_pct = round(100.0 * saved / before_tokens, 1) if before_tokens else 0.0

    if args.as_json:
        print(json.dumps({
            "source": label,
            "span": {"start": start, "end": end},
            "applied": list(result.applied),
            "lines": {"before": result.lines_before, "after": result.lines_after,
                      "removed": result.lines_removed, "percent": result.percent_removed},
            "tokens": {"before": before_tokens, "after": after_tokens,
                       "saved": saved, "percent": saved_pct},
        }, indent=2))
        return 0

    print(f"{label}: lines {start}-{end}  filters={','.join(result.applied) or 'none'}",
          file=sys.stderr)
    print(f"  lines  {result.lines_before:>7,} -> {result.lines_after:>7,}"
          f"  (-{result.lines_removed:,}, -{result.percent_removed}%)", file=sys.stderr)
    print(f"  tokens {before_tokens:>7,} -> {after_tokens:>7,}"
          f"  (-{saved:,}, -{saved_pct}%)", file=sys.stderr)

    if args.stats_only:
        return 0
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(result.text, encoding="utf-8")
        print(f"  wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(result.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
