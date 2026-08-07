"""Multi-strategy boundary probing for sources the canonical detector misses.

Why this exists
---------------
`bookrefs.structure` recognises heading *dialects* — "Chapter 7", "第三章",
"บทที่ ๓". That is the right primitive for trade books and translated ebooks,
and it is what `metadata.json`'s `chapters_detected` reports.

Academic PDFs converted to text usually contain none of those. An edited
Springer volume marks chapters with a per-chapter DOI suffix and an `Abstract`
block; a monograph uses `11.2 MATRIX THRESHOLDING`; a lecture-notes PDF uses
markdown heading levels with no chapter word anywhere. Measured across ten
mixed sources, the canonical detector matched the true chapter count in one.

Worse, the documented fallback probe (grep for `^Chapter\\s+\\d`) can return
hits that are all prose cross-references — "as we saw in Chapter 7, the
intuition here is…" — which looks like success and is not.

So this module does not replace `structure.py`; it runs several *candidate*
strategies over a span and reports what each finds, with a plausibility score,
so a caller can pick. It is a probe, not a detector: the output is meant to be
eyeballed against a table of contents before anything is sliced.

Scoring, briefly: a strategy scores well when it finds a chapter-plausible
number of boundaries, spaced evenly enough to look like chapters rather than
like every heading in the book, spanning most of the span, and — where the
strategy recovers numbers — numbered monotonically. No score is a substitute
for looking at the list.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from .structure import detect_structure

# A span with fewer than this many boundaries is a suspiciously coarse read of
# a book; more than this and the strategy is finding sub-sections, not chapters.
PLAUSIBLE_MIN = 3
PLAUSIBLE_MAX = 120


@dataclass(frozen=True)
class Candidate:
    line: int          # 1-indexed within the probed text
    label: str
    number: float | None = None


@dataclass
class StrategyResult:
    name: str
    candidates: tuple[Candidate, ...] = ()
    note: str = ""
    score: float = 0.0

    @property
    def count(self) -> int:
        return len(self.candidates)


# --- strategies -----------------------------------------------------------
# Each takes the split lines and returns Candidates. Line numbers are 1-indexed
# and relative to the text handed in, so a caller probing a slice adds its own
# offset once.

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# "11.2 MATRIX THRESHOLDING" / "2.4.1 Bayesian Models" — dotted decimal, then a
# title that starts with a capital. Trailing page numbers are tolerated.
_NUMBERED = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){1,3})\s+([A-Z][^\n]{3,90}?)\s*$")
# Springer stamps each chapter's opening page with the book DOI plus `_N`.
_DOI_CHAPTER = re.compile(r"(?:10\.\d{4,9}/[-._;()/:\w]*?)[_\s]+(\d{1,3})\b")
# An abstract block opens a chapter in most edited academic volumes.
_ABSTRACT = re.compile(r"^\s*#*\s*\**Abstract\**\s*$|^\s*\**Abstract\**\s+\S")
_ALLCAPS = re.compile(r"^\s*([A-Z][A-Z0-9 ,\-&':()]{7,70})\s*$")


def _by_markdown(lines: list[str], max_level: int = 2) -> tuple[list[Candidate], str]:
    out = []
    for i, line in enumerate(lines, start=1):
        m = _MD_HEADING.match(line)
        if m and len(m.group(1)) <= max_level:
            out.append(Candidate(line=i, label=m.group(2)[:90]))
    return out, f"markdown headings at level <= {max_level}"


def _by_numbered(lines: list[str]) -> tuple[list[Candidate], str]:
    """Top-level numbered sections only: 11.2 counts, 11.2.3 does not.

    Keeping one level means a monograph's chapter-section scheme reads as a
    chapter list rather than as a full outline.
    """
    out = []
    for i, line in enumerate(lines, start=1):
        m = _NUMBERED.match(line)
        if not m:
            continue
        parts = m.group(1).split(".")
        if len(parts) != 2:
            continue
        try:
            number = float(f"{parts[0]}.{parts[1]}")
        except ValueError:
            number = None
        out.append(Candidate(line=i, label=f"{m.group(1)} {m.group(2)}"[:90], number=number))
    return out, "dotted-decimal section numbers (N.M Title)"


def _by_doi(lines: list[str]) -> tuple[list[Candidate], str]:
    """Publisher per-chapter DOI suffixes; keep the first hit per number."""
    out, seen = [], set()
    for i, line in enumerate(lines, start=1):
        m = _DOI_CHAPTER.search(line)
        if not m:
            continue
        number = int(m.group(1))
        if not (1 <= number <= 99) or number in seen:
            continue
        seen.add(number)
        out.append(Candidate(line=i, label=f"chapter {number} (DOI marker)", number=float(number)))
    out.sort(key=lambda c: c.line)
    return out, "per-chapter DOI suffix (Springer and similar)"


def _title_above(lines: list[str], index: int, lookback: int) -> str:
    """Best guess at the title heading a block at `index` (0-based).

    Prefer an explicit markdown heading within the lookback — in an edited
    volume the chapter title is usually one — and fall back to the nearest line
    that is not a URL, page marker, or bare number. Without the heading
    preference this lands on the author byline, which sits between the title
    and the abstract in most publishers' layouts.
    """
    fallback = ""
    for j in range(index, max(0, index - lookback), -1):
        raw = lines[j].strip()
        if raw.startswith("#"):
            heading = raw.lstrip("#").strip()
            if len(heading) > 3:
                return heading
        if fallback:
            continue
        if (raw and not raw.startswith(("Link:", "http", "![", "<!--", "|"))
                and not raw.replace(".", "").isdigit() and len(raw) > 3):
            fallback = raw
    return fallback


def _by_abstract(lines: list[str], lookback: int = 20) -> tuple[list[Candidate], str]:
    """`Abstract` blocks, titled from the heading above them."""
    out = []
    for i, line in enumerate(lines, start=1):
        if not _ABSTRACT.match(line):
            continue
        title = _title_above(lines, i - 2, lookback)
        out.append(Candidate(line=i, label=(title or "(untitled abstract)")[:90]))
    return out, "Abstract blocks with the title backtracked above"


def _by_allcaps(lines: list[str]) -> tuple[list[Candidate], str]:
    out = []
    for i, line in enumerate(lines, start=1):
        m = _ALLCAPS.match(line)
        if m and not m.group(1).strip().isdigit():
            out.append(Candidate(line=i, label=m.group(1)))
    return out, "standalone ALL-CAPS lines (scanned or typeset PDFs)"


def _by_canonical(lines: list[str]) -> tuple[list[Candidate], str]:
    structure = detect_structure("\n".join(lines))
    return ([Candidate(line=h.line, label=f"{h.number} {h.title}"[:90], number=float(h.number))
             for h in structure.headings],
            "bookrefs.structure — the canonical heading-dialect detector")


STRATEGIES = {
    "canonical": _by_canonical,
    "markdown": _by_markdown,
    "numbered": _by_numbered,
    "doi": _by_doi,
    "abstract": _by_abstract,
    "allcaps": _by_allcaps,
}


# --- scoring --------------------------------------------------------------

def score_candidates(candidates: list[Candidate], total_lines: int) -> float:
    """Rough plausibility, 0..1. Higher means "more chapter-shaped".

    Four factors, each a penalty away from 1.0:
      count      inside PLAUSIBLE_MIN..PLAUSIBLE_MAX
      spread     first hit early, last hit late — chapters span a book
      evenness   gaps of similar size — an outline has one huge gap then many tiny
      monotonic  recovered numbers ascend, when the strategy recovers any
    """
    n = len(candidates)
    if n < PLAUSIBLE_MIN or total_lines <= 0:
        return 0.0

    count_penalty = 0.0 if n <= PLAUSIBLE_MAX else min(1.0, (n - PLAUSIBLE_MAX) / PLAUSIBLE_MAX)

    lines = [c.line for c in candidates]
    spread = (max(lines) - min(lines)) / total_lines
    spread_score = min(1.0, spread / 0.7)   # covering 70%+ of the span is full credit

    gaps = [b - a for a, b in zip(lines, lines[1:])]
    mean_gap = statistics.fmean(gaps) if gaps else 0.0
    if mean_gap > 0 and len(gaps) > 1:
        cv = statistics.pstdev(gaps) / mean_gap
        evenness = max(0.0, 1.0 - cv / 2.0)   # cv of 2+ is shapeless
    else:
        evenness = 0.5

    numbers = [c.number for c in candidates if c.number is not None]
    if len(numbers) >= 2:
        ascending = sum(1 for a, b in zip(numbers, numbers[1:]) if b > a)
        monotonic = ascending / (len(numbers) - 1)
    else:
        monotonic = 0.6   # neutral: the strategy recovers no numbers to check

    return round(max(0.0, (0.35 * spread_score + 0.35 * evenness + 0.30 * monotonic)
                     * (1.0 - count_penalty)), 3)


@dataclass
class Probe:
    total_lines: int
    results: list[StrategyResult] = field(default_factory=list)

    @property
    def best(self) -> StrategyResult | None:
        ranked = [r for r in self.results if r.count >= PLAUSIBLE_MIN]
        return max(ranked, key=lambda r: r.score) if ranked else None


def probe(text: str, strategies: tuple[str, ...] | None = None,
          max_level: int = 2) -> Probe:
    """Run every requested strategy over `text` and score each."""
    lines = text.splitlines()
    names = strategies or tuple(STRATEGIES)
    out = Probe(total_lines=len(lines))
    for name in names:
        fn = STRATEGIES.get(name)
        if fn is None:
            continue
        candidates, note = (_by_markdown(lines, max_level) if name == "markdown"
                            else fn(lines))
        out.results.append(StrategyResult(
            name=name,
            candidates=tuple(candidates),
            note=note,
            score=score_candidates(candidates, len(lines)),
        ))
    out.results.sort(key=lambda r: (-r.score, r.name))
    return out
