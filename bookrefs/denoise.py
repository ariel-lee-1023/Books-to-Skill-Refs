"""Strip boilerplate from a span before an agent spends tokens reading it.

Why this exists
---------------
Step 2.6 says to read by slicing rather than by whole-file `Read`. That controls
*how much* is read; it says nothing about what is in the slice. Converted
sources carry a lot that costs tokens and teaches nothing:

  PDF -> markdown   `<!-- page 41 -->` markers, `Link: [...]` runs (one per
                    hyperlink, often a dozen consecutive), running headers
                    repeating the chapter title on every page, and pipe-table
                    scaffolding left over from a failed table extraction.
  Sphinx / rST      `.. figure::` and `.. toctree::` directives, `:align:`
                    option lines, `====` title underlines.
  HTML textbooks    per-page navigation, "Skip to Main Content", donation
                    banners repeated on all 51 chapters.
  Course sites      end-of-chapter quiz blocks, where each question repeats
                    all its options once per answer. Measured on one chapter:
                    ~250 of 460 lines were the quiz block — more than half the
                    read spent on permutations of four multiple-choice options.

Where this runs, and where it must not
--------------------------------------
**After extraction, on the agent's reading slice — never before extraction.**

CONTRIBUTING is explicit that parsers must preserve `#` headings and pipe-table
rows, because `structure.py` reads the first and Step 3's technical/text
tripwire counts the second. Denoising the corpus itself would erase the evidence
those run on. `full_text.txt` stays as extracted; this cleans a copy of a span
on its way to being read.

For the same reason the table filter is conservative: it drops rows that are
mostly empty cells or bare `---` separators — the residue of a table a PDF
parser could not reconstruct — and keeps rows carrying real content.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Callable

# --- individual line predicates -------------------------------------------

# MULTILINE so the same pattern serves per-line `.match()` and whole-text
# `.search()` in detect_filters(); without it `$` only matched end-of-string.
_PAGE_MARKER = re.compile(r"^\s*<!--\s*page\s+\d+\s*-->\s*$",
                          re.IGNORECASE | re.MULTILINE)
_LINK_LINE = re.compile(r"^\s*Link:\s*\[")
_IMAGE_LINE = re.compile(r"^\s*!\[")
_ASSET_LINE = re.compile(r"^\s*!?\[?[^]]*\]?\(asset:sha256:[0-9a-f]+\)\s*$")
_RST_DIRECTIVE = re.compile(r"^\s*\.\.\s+[a-zA-Z_][\w-]*::")
_RST_COMMENT = re.compile(r"^\s*\.\.\s+_?[\w.-]+:?\s*$")
_RST_OPTION = re.compile(r"^\s*:(align|width|height|scale|alt|maxdepth|caption|name|"
                         r"linenos|class|target|figclass|hidden|titlesonly):")
_RST_UNDERLINE = re.compile(r"^\s*[-=~^\"#*+`']{3,}\s*$")
_PIPE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_SEPARATOR_CELL = re.compile(r"^[\s:-]*$")

# Whole-line navigation chrome seen across HTML textbook exports.
_NAV_PHRASES = frozenset({
    "skip to main content", "skip to navigation", "home", "table of contents",
    "further reading", "contact us", "index", "next", "previous", "back to top",
    "×", "-",
})

# Markers after which a chapter body becomes end-matter an agent should not read.
QUIZ_MARKERS = (
    "test your knowledge",
    "check your understanding",
    "self-test",
    "review questions",
)


def _is_mangled_table_row(line: str) -> bool:
    """A pipe row that is mostly empty or separator cells.

    A genuine table row has content in most of its cells. PDF table extraction
    that loses cell boundaries emits long rows of `|  |  | --- |  |`, which are
    pure noise and can dominate a slice.
    """
    if not _PIPE_ROW.match(line):
        return False
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if not cells:
        return True
    empty = sum(1 for c in cells if not c or _SEPARATOR_CELL.match(c))
    return empty / len(cells) >= 0.6


# --- filters --------------------------------------------------------------
# Each maps a list of lines to a list of lines. Registered by name so a caller
# can pick, and so `auto` can compose a subset.

def filter_pdf(lines: list[str]) -> list[str]:
    return [ln for ln in lines
            if not (_PAGE_MARKER.match(ln) or _LINK_LINE.match(ln)
                    or _IMAGE_LINE.match(ln) or _ASSET_LINE.match(ln)
                    or _is_mangled_table_row(ln))]


def filter_rst(lines: list[str]) -> list[str]:
    return [ln for ln in lines
            if not (_RST_DIRECTIVE.match(ln) or _RST_OPTION.match(ln)
                    or _RST_UNDERLINE.match(ln) or _RST_COMMENT.match(ln))]


def filter_nav(lines: list[str]) -> list[str]:
    out = []
    for ln in lines:
        bare = ln.strip().lstrip("-*# ").strip().lower()
        if bare in _NAV_PHRASES:
            continue
        out.append(ln)
    return out


def filter_quiz(lines: list[str]) -> list[str]:
    """Truncate at the first end-of-chapter quiz marker.

    Truncation rather than removal: these blocks run to the end of a chapter,
    and anything after them is end-matter too.
    """
    for i, ln in enumerate(lines):
        if ln.strip().lower().lstrip("#* ").rstrip("* ") in QUIZ_MARKERS:
            return lines[:i]
    return lines


def filter_repeats(lines: list[str], threshold: int = 4, min_len: int = 12) -> list[str]:
    """Drop lines repeated many times — running headers and page furniture.

    A chapter title reprinted on every page is the common case. The length
    floor keeps short structural lines (`---`, list bullets) out of it, and the
    threshold is high enough that a repeated sentence in prose survives.

    Pipe rows are exempt. Running headers are prose; a repeated table row is
    table content, and `filter_pdf` has already removed the mangled kind.
    Without this exemption the two filters compose into something that deletes
    real tables, which is exactly what the module promises not to do.
    """
    counts = Counter(ln.strip() for ln in lines
                     if len(ln.strip()) >= min_len and not _PIPE_ROW.match(ln))
    noisy = {text for text, n in counts.items() if n >= threshold}
    return [ln for ln in lines if _PIPE_ROW.match(ln) or ln.strip() not in noisy]


def filter_blanks(lines: list[str]) -> list[str]:
    """Collapse runs of blank lines to one."""
    out: list[str] = []
    blank = False
    for ln in lines:
        if ln.strip():
            out.append(ln)
            blank = False
        elif not blank:
            out.append("")
            blank = True
    return out


FILTERS: dict[str, Callable[[list[str]], list[str]]] = {
    "pdf": filter_pdf,
    "rst": filter_rst,
    "nav": filter_nav,
    "quiz": filter_quiz,
    "repeats": filter_repeats,
    "blanks": filter_blanks,
}

# Order matters: structural removals first, then repeats (which counts what is
# left), then blank collapsing (which tidies the gaps the others opened).
DEFAULT_ORDER: tuple[str, ...] = ("pdf", "rst", "nav", "quiz", "repeats", "blanks")


def detect_filters(text: str) -> tuple[str, ...]:
    """Choose filters by sniffing the span, so `auto` does something sensible."""
    chosen = ["blanks"]
    if _PAGE_MARKER.search(text) or "Link: [" in text:
        chosen.append("pdf")
    if ".. figure::" in text or ".. toctree::" in text or ".. note::" in text:
        chosen.append("rst")
    lowered = text.lower()
    if any(marker in lowered for marker in QUIZ_MARKERS):
        chosen.append("quiz")
    if "skip to main content" in lowered or "table of contents" in lowered:
        chosen.append("nav")
    chosen.append("repeats")
    return tuple(name for name in DEFAULT_ORDER if name in chosen)


@dataclass
class Cleaned:
    text: str
    lines_before: int
    lines_after: int
    applied: tuple[str, ...]

    @property
    def lines_removed(self) -> int:
        return self.lines_before - self.lines_after

    @property
    def percent_removed(self) -> float:
        if not self.lines_before:
            return 0.0
        return round(100.0 * self.lines_removed / self.lines_before, 1)


def clean(text: str, filters: tuple[str, ...] | None = None) -> Cleaned:
    """Apply the named filters (or auto-detected ones) to a span."""
    names = detect_filters(text) if filters is None else tuple(
        name for name in DEFAULT_ORDER if name in filters)
    lines = text.splitlines()
    before = len(lines)
    for name in names:
        fn = FILTERS.get(name)
        if fn is not None:
            lines = fn(lines)
    return Cleaned(text="\n".join(lines).strip() + "\n",
                   lines_before=before, lines_after=len(lines), applied=names)
