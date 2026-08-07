#!/usr/bin/env python3
"""Find chapter boundaries when the canonical detector reports too few.

Why this exists
---------------
`metadata.json`'s `chapters_detected` comes from `bookrefs.structure`, which
recognises heading dialects — "Chapter 7", "第三章", "บทที่ ๓". That is right for
trade books and translated ebooks and wrong for most converted academic PDFs,
which mark chapters with a publisher DOI suffix, an `Abstract` block, a
dotted-decimal section number, or nothing but a markdown heading level.

Step 3 needs a section list to plan against and Step 7 front-loads from it, so a
source whose structure reads as zero is a source that gets distilled blind.

This runs several candidate strategies over a span, scores each for
chapter-plausibility, and prints what they found. It is a **probe**: check the
top candidates against the book's own table of contents before slicing. A
strategy can score well and still be wrong — a run of prose cross-references
("as we saw in Chapter 7…") is evenly spaced too.

Usage
-----
    python tools/probe_structure.py full_text.txt --source book.pdf
    python tools/probe_structure.py full_text.txt --range 4,2823 --show 40
    python tools/probe_structure.py corpus/book.md --strategy numbered,abstract

`--source` resolves the span from the sibling `metadata.json`, so the caller
never re-derives a fence boundary it can be told.

Exit codes: 0 ok, 1 no strategy found a plausible structure, 2 usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bookrefs.probe import PLAUSIBLE_MIN, STRATEGIES, probe  # noqa: E402


def resolve_span(text_path: Path, source: str | None,
                 line_range: str | None) -> tuple[int, int, str]:
    """Return `(start, end, label)`, 1-indexed inclusive."""
    lines = text_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if line_range:
        try:
            start_s, end_s = line_range.split(",")
            return int(start_s), int(end_s), f"lines {start_s}-{end_s}"
        except ValueError:
            raise SystemExit("x --range wants START,END (e.g. 4,2823)")
    if source:
        meta_path = text_path.parent / "metadata.json"
        if not meta_path.is_file():
            raise SystemExit(f"x --source needs {meta_path}; pass --range instead")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for entry in meta.get("sources", []):
            if source in (entry.get("filename"), entry.get("path")):
                return int(entry["start_line"]), int(entry["end_line"]), entry["filename"]
        known = ", ".join(e.get("filename", "?") for e in meta.get("sources", []))
        raise SystemExit(f"x no source matching '{source}'. Known: {known}")
    return 1, len(lines), text_path.name


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Probe a corpus for chapter boundaries using several strategies.",
        epilog="Strategies: " + ", ".join(STRATEGIES),
    )
    ap.add_argument("text", type=Path, help="full_text.txt or a single corpus file")
    ap.add_argument("--source", help="restrict to one source, resolved via metadata.json")
    ap.add_argument("--range", dest="line_range", metavar="START,END",
                    help="restrict to a 1-indexed inclusive line range")
    ap.add_argument("--strategy", help="comma-separated subset (default: all)")
    ap.add_argument("--show", type=int, default=12, metavar="N",
                    help="candidates to print per strategy (default 12; 0 for all)")
    ap.add_argument("--max-level", type=int, default=2, metavar="N",
                    help="deepest markdown heading level treated as a boundary (default 2)")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    if not args.text.is_file():
        print(f"x no such file: {args.text}", file=sys.stderr)
        return 2

    start, end, label = resolve_span(args.text, args.source, args.line_range)
    all_lines = args.text.read_text(encoding="utf-8", errors="replace").splitlines()
    span = "\n".join(all_lines[start - 1:end])
    offset = start - 1

    names = tuple(s.strip() for s in args.strategy.split(",")) if args.strategy else None
    result = probe(span, strategies=names, max_level=args.max_level)

    if args.as_json:
        print(json.dumps({
            "source": label,
            "span": {"start": start, "end": end, "lines": result.total_lines},
            "best": result.best.name if result.best else None,
            "strategies": [
                {
                    "name": r.name, "count": r.count, "score": r.score, "note": r.note,
                    "candidates": [
                        {"line": c.line + offset, "label": c.label, "number": c.number}
                        for c in (r.candidates if args.show == 0 else r.candidates[:args.show])
                    ],
                }
                for r in result.results
            ],
        }, indent=2))
        return 0 if result.best else 1

    print(f"{label}: lines {start}-{end} ({result.total_lines:,} lines)\n")
    for r in result.results:
        marker = "*" if result.best and r.name == result.best.name else " "
        print(f"{marker} {r.name:<10} {r.count:>4} hit(s)  score {r.score:.3f}   {r.note}")
        shown = r.candidates if args.show == 0 else r.candidates[:args.show]
        for c in shown:
            print(f"      {c.line + offset:>7}  {c.label}")
        if args.show and r.count > args.show:
            print(f"      ... {r.count - args.show} more")
        print()

    if not result.best:
        print("x no strategy found a plausible chapter structure "
              f"(need >= {PLAUSIBLE_MIN} boundaries). Check the source's own "
              "table of contents and slice by hand.", file=sys.stderr)
        return 1

    print(f"best guess: {result.best.name} — verify against the book's table of "
          "contents before slicing.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
