#!/usr/bin/env python3
"""Estimate token counts, with CJK-correct segmentation.

A CLI over `bookrefs.tokens`, which holds the canonical implementation and the
explanation of why this is not a word-split estimate. Keeping one definition
means the extractor's metadata, the cost gate, the budget caps and the library
validator cannot drift apart.

SKILL.md sets hard token budgets (Step 7's per-reference caps, Step 8's master
hard stop, Step 2.6's 4x input gate). A budget nobody can measure is not a
budget; this is the instrument those rules are checked with.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bookrefs.tokens import (  # noqa: E402,F401  (re-exported for callers and tests)
    DENSE_RANGES,
    estimate_tokens,
    is_dense,
    strip_frontmatter,
)
from bookrefs.config import (  # noqa: E402,F401
    DENSE_CHARS_PER_TOKEN,
    OTHER_CHARS_PER_TOKEN,
)


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
