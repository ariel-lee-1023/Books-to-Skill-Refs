#!/usr/bin/env python3
"""Compute the Step 7 reference-file budget and the Step 8 master budget.

Why this exists
---------------
Step 7 used to be a 2x2 lookup table: a per-section allowance, a 2x-wide "book
range", and a cap. Three things were wrong with it, and all three are visible in
a real library.

1. It priced the number of blocks you *write*. The cut order tells you to merge
   thin sections precisely so you land inside the budget, so a budget computed
   from the merged count can never bind. Measured across a five-book library,
   blocks written spanned 7.3x while the files spanned 1.36x; the book's own
   section count predicts file size at r=+0.85, the blocks written at +0.53.

2. Per-section cost is not constant. It *falls* as sections rise -- 462 tok/section
   at 11 sections down to 287 at 25 -- because you merge and compress. A linear
   allowance over-budgets a thick book by ~60%, which is the direction that
   produces bloat and collides with the cap.

3. The table contradicted itself. At study/technical, per-section minimum times
   26 sections already exceeded the stated book range, and past 29 sections it
   exceeded the hard cap -- with no rule saying which constraint wins. Any
   26-chapter technical book had an unsatisfiable spec.

So the budget is computed:

    scaffold = 2250 (study) | 1700 (reference, which drops the Worked Example)
    body     = (1050 + 1500*sqrt(n_sections)) * depth_factor * type_factor
    budget   = scaffold + body                      +/-10% tolerance
    cap      = budget(n_sections=50) rounded to 500

`n_sections` is the BOOK's own top-level structure, read off the TOC in Step 3 --
never the blocks you decide to write.

Only one section of a reference file varies: `Frameworks & Structure` is 72-77%
of the file and carries all of it. Everything else measured near-constant, which
is why the formula is a constant plus a single term.

Calibration
-----------
Five reference files, one library, all study/text, measured with this repo's own
count_tokens.py: mean 4.9% / max 8.7%. The `reference` and `technical`
multipliers are NOT fitted -- no data exists for those three cells. They are
back-solved from the midpoints of the table this replaces, so they preserve the
original intent rather than inventing one. Structure settled, constants
provisional.

Usage
-----
    python3 tools/reference_budget.py --sections 22 --depth study --type text
    python3 tools/reference_budget.py --master --books 5 --capabilities 4 --index-entries 14
    python3 tools/reference_budget.py path/to/<library-name>/          # measure a library
    python3 tools/reference_budget.py path/to/<library-name>/ --strict # and fail CI on over-budget

Exit codes: 0 clean; 1 a file is over its hard cap, or over budget under --strict.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from count_tokens import estimate_tokens, strip_frontmatter  # noqa: E402

# --- Step 7: per-reference-file -------------------------------------------

SCAFFOLD = {"study": 2_250, "reference": 1_700}   # reference drops the Worked Example (~510)
BODY_BASE = 1_050
BODY_PER_SQRT_SECTION = 1_500
DEPTH_FACTOR = {"study": 1.00, "reference": 0.55}
TYPE_FACTOR = {"text": 1.00, "technical": 1.45}
CAP_AT_SECTIONS = 50          # a book past this is the split/ask edge, not a budget case
TOLERANCE = 0.10              # measurement band around the computed budget

# --- Step 8: master --------------------------------------------------------

MASTER_BASE = 300             # frontmatter + Scope & limits
MASTER_PER_BOOK = 75          # one router row per book (measured 76)
MASTER_PER_CAPABILITY = 350   # one Capability block each (measured 347)
MASTER_PROTOCOL = 900         # Voice + opening protocol + Standing rules (measured 912)
MASTER_PER_INDEX_ENTRY = 25   # cross-book topic index (measured 23)
MASTER_INDEX_ALLOWANCE = 600
MASTER_HARD_STOP = 4_500

DEPTHS = tuple(SCAFFOLD)
TYPES = tuple(TYPE_FACTOR)


def reference_budget(n_sections: int, depth: str = "study", book_type: str = "text") -> int:
    """Computed target size for one reference file, in tokens."""
    if depth not in DEPTH_FACTOR:
        raise ValueError("depth must be one of %s" % (DEPTHS,))
    if book_type not in TYPE_FACTOR:
        raise ValueError("type must be one of %s" % (TYPES,))
    if n_sections < 1:
        raise ValueError("n_sections must be >= 1")
    body = (BODY_BASE + BODY_PER_SQRT_SECTION * math.sqrt(n_sections))
    body *= DEPTH_FACTOR[depth] * TYPE_FACTOR[book_type]
    return round(SCAFFOLD[depth] + body)


def reference_cap(depth: str = "study", book_type: str = "text") -> int:
    """Hard cap for a cell: the budget at CAP_AT_SECTIONS, rounded UP to the next 500.

    Up, not to nearest: rounding down would let the computed budget exceed its own
    cap at the boundary, which is the same class of self-contradiction the old 2x2
    table had. A budget you are told to hit and forbidden to reach is not a budget.
    """
    raw = reference_budget(CAP_AT_SECTIONS, depth, book_type)
    return int(math.ceil(raw / 500.0) * 500)


def master_budget(n_books: int, n_capabilities: int = 0, index_entries: int = 0) -> int:
    """Computed target size for the master SKILL.md body, in tokens."""
    index = min(MASTER_PER_INDEX_ENTRY * max(index_entries, 0), MASTER_INDEX_ALLOWANCE)
    return (MASTER_BASE
            + MASTER_PER_BOOK * max(n_books, 0)
            + MASTER_PER_CAPABILITY * max(n_capabilities, 0)
            + MASTER_PROTOCOL
            + index)


# --- library measurement ---------------------------------------------------

SECTIONS_RE = re.compile(r"\*\*Sections\*\*:\s*~?([0-9]+)")
DEPTH_RE = re.compile(r"\*\*Depth\*\*:\s*(study|reference)", re.I)
CAPABILITY_RE = re.compile(r"^##\s+Capability\b", re.M)
INDEX_ENTRY_RE = re.compile(r"^\s*[-|]\s*\*\*(.+?)\*\*", re.M)
FRAMEWORKS_RE = re.compile(r"^##\s+Frameworks\b.*?(?=^##\s|\Z)", re.M | re.S)
# Mirrors validate_library.py: a technical book is detected from fenced code.
TECHNICAL_RE = re.compile(r"^```(?!markdown\b)[a-z0-9+#.-]*\s*$", re.M)


def detect_type(text: str) -> str:
    return "technical" if len(TECHNICAL_RE.findall(text)) >= 6 else "text"


def measure_library(root: Path):
    """Return (rows, master_row). Rows are dicts; nothing is printed here."""
    refs = sorted((root / "references").glob("reference-*.md"))
    rows = []
    for path in refs:
        text = path.read_text(encoding="utf-8")
        m = SECTIONS_RE.search(text)
        d = DEPTH_RE.search(text)
        depth = d.group(1).lower() if d else "study"
        btype = detect_type(text)
        tokens = estimate_tokens(text)
        sections = int(m.group(1)) if m else None
        budget = reference_budget(sections, depth, btype) if sections else None
        cap = reference_cap(depth, btype)
        fw = FRAMEWORKS_RE.search(text)
        rows.append({
            "name": path.name, "sections": sections, "depth": depth, "type": btype,
            "tokens": tokens, "budget": budget, "cap": cap,
            "frameworks_tokens": estimate_tokens(fw.group(0)) if fw else 0,
        })

    master_path = root / "SKILL.md"
    master = None
    if master_path.exists():
        body = strip_frontmatter(master_path.read_text(encoding="utf-8"))
        n_cap = len(CAPABILITY_RE.findall(body))
        idx_part = re.split(r"^##\s+Cross-book", body, flags=re.M)
        entries = len(INDEX_ENTRY_RE.findall(idx_part[1])) if len(idx_part) > 1 else 0
        master = {
            "tokens": estimate_tokens(body), "books": len(refs),
            "capabilities": n_cap, "index_entries": entries,
            "budget": master_budget(len(refs), n_cap, entries),
            "hard_stop": MASTER_HARD_STOP,
        }
    return rows, master


def _report(root: Path, strict: bool) -> int:
    rows, master = measure_library(root)
    if not rows:
        print("no references/reference-*.md found under %s" % root, file=sys.stderr)
        return 1

    failures, warnings = [], []
    width = max(len(r["name"]) for r in rows)
    print("%-*s %5s %-9s %-6s %8s %8s %8s %7s"
          % (width, "reference file", "sec", "depth", "type", "tokens", "budget", "cap", "delta"))
    for r in rows:
        if r["budget"] is None:
            print("%-*s %5s %-9s %-6s %8d %8s %8d %7s"
                  % (width, r["name"], "?", r["depth"], r["type"], r["tokens"], "n/a", r["cap"], "n/a"))
            warnings.append("%s: no '**Sections**: N' header, so no budget could be computed"
                            % r["name"])
            continue
        delta = (r["tokens"] - r["budget"]) / r["budget"]
        print("%-*s %5d %-9s %-6s %8d %8d %8d %+6.1f%%"
              % (width, r["name"], r["sections"], r["depth"], r["type"],
                 r["tokens"], r["budget"], r["cap"], delta * 100))
        if r["tokens"] > r["cap"]:
            failures.append("%s: ~%d tok is over the %d cap for %s/%s. Use the Step 7 cut order — "
                            "selection, never truncation."
                            % (r["name"], r["tokens"], r["cap"], r["type"], r["depth"]))
        elif delta > TOLERANCE:
            msg = ("%s: ~%d tok is %.0f%% over its %d budget (tolerance %.0f%%)."
                   % (r["name"], r["tokens"], delta * 100, r["budget"], TOLERANCE * 100))
            (failures if strict else warnings).append(msg)
        elif delta < -TOLERANCE:
            warnings.append("%s: ~%d tok is %.0f%% under its %d budget. The budget is a target, "
                            "not a floor — fine if coverage is complete, but check that every "
                            "Step 3 item is present or explicitly recorded as dropped."
                            % (r["name"], r["tokens"], -delta * 100, r["budget"]))

    if master:
        d = (master["tokens"] - master["budget"]) / master["budget"]
        print("\n%-*s %5s %-9s %-6s %8d %8d %8d %+6.1f%%"
              % (width, "SKILL.md (master)", "", "N=%d" % master["books"],
                 "C=%d" % master["capabilities"], master["tokens"], master["budget"],
                 master["hard_stop"], d * 100))
        if master["tokens"] > master["hard_stop"]:
            failures.append("SKILL.md body ~%d tok is over the %d hard stop. Apply the Step 8 "
                            "valves in order: spill the topic index, consolidate Capability "
                            "blocks to <=4, then group the router table by theme."
                            % (master["tokens"], master["hard_stop"]))
        elif d > TOLERANCE:
            msg = ("SKILL.md body ~%d tok is %.0f%% over its %d budget."
                   % (master["tokens"], d * 100, master["budget"]))
            (failures if strict else warnings).append(msg)

    dense = [r for r in rows if r["frameworks_tokens"] and r["budget"]]
    if dense:
        print("\nDensity check — Frameworks & Structure share (measured band 72–77%):")
        for r in dense:
            share = r["frameworks_tokens"] / r["tokens"] * 100
            flag = "" if 65 <= share <= 85 else "   <- outside the measured band"
            print("  %-*s %5.1f%%%s" % (width, r["name"], share, flag))

    for w in warnings:
        print("\nWARN   %s" % w)
    for f in failures:
        print("\nERROR  %s" % f)
    print("\n%d file(s) checked — %d error(s), %d warning(s)"
          % (len(rows) + (1 if master else 0), len(failures), len(warnings)))
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Step 7 / Step 8 budgets. Formula and calibration status: SKILL.md.")
    ap.add_argument("library", nargs="?", help="path to a generated <library-name>/ to measure")
    ap.add_argument("--sections", type=int, help="compute one reference-file budget")
    ap.add_argument("--depth", choices=DEPTHS, default="study")
    ap.add_argument("--type", dest="book_type", choices=TYPES, default="text")
    ap.add_argument("--master", action="store_true", help="compute the master budget")
    ap.add_argument("--books", type=int, default=0)
    ap.add_argument("--capabilities", type=int, default=0)
    ap.add_argument("--index-entries", type=int, default=0)
    ap.add_argument("--strict", action="store_true",
                    help="treat over-budget (not just over-cap) as an error — for CI")
    ap.add_argument("--table", action="store_true", help="print the cap for every cell and exit")
    args = ap.parse_args()

    if args.table:
        print("%-12s %10s %10s" % ("depth", "text", "technical"))
        for d in DEPTHS:
            print("%-12s %10d %10d" % (d, reference_cap(d, "text"), reference_cap(d, "technical")))
        return 0

    if args.sections:
        b = reference_budget(args.sections, args.depth, args.book_type)
        c = reference_cap(args.depth, args.book_type)
        print("%d sections · %s · %s" % (args.sections, args.depth, args.book_type))
        print("  budget %d tok  (tolerance %d–%d)  ·  cap %d"
              % (b, round(b * (1 - TOLERANCE)), round(b * (1 + TOLERANCE)), c))
        return 0

    if args.master:
        b = master_budget(args.books, args.capabilities, args.index_entries)
        print("N=%d books · C=%d capabilities · %d index entries"
              % (args.books, args.capabilities, args.index_entries))
        print("  budget %d tok  ·  hard stop %d" % (b, MASTER_HARD_STOP))
        return 0

    if args.library:
        return _report(Path(args.library), args.strict)

    ap.error("give a library path, or --sections N, or --master, or --table")
    return 2


if __name__ == "__main__":
    sys.exit(main())
