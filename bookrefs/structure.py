"""Chapter and table-of-contents detection across scripts.

Feeds metadata.json's `chapters_detected` / `has_toc`, which SKILL.md Step 3
uses to plan sections and Step 7 uses to size each reference file.

Organisation: one `HeadingRule` per heading dialect, each pairing a pattern
with the numeral system it writes numbers in. Adding a language means adding a
rule and, if it counts differently, a numeral parser — nothing else changes.

CJK support is not a nicety here. This project is used heavily on Chinese
sources, and a detector that only understands "Chapter 7" reports zero
structure for a book it parsed perfectly well.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

# --- numeral systems ------------------------------------------------------

_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

_CN_DIGITS = {"〇": 0, "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}
_CN_CHARS = "".join(_CN_DIGITS) + "".join(_CN_UNITS)

_FULLWIDTH = "０-９"
_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def parse_arabic(token: str) -> int | None:
    token = token.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    return int(token) if token.isdigit() else None


def parse_roman(token: str) -> int | None:
    token = token.upper()
    if not token or any(ch not in _ROMAN_VALUES for ch in token):
        return None
    total, prev = 0, 0
    for ch in reversed(token):
        value = _ROMAN_VALUES[ch]
        total = total - value if value < prev else total + value
        prev = max(prev, value)
    return total or None


def parse_chinese(token: str) -> int | None:
    """Handles 三, 十, 十二, 二十, 二十三, 一百零八, and full-width digits."""
    arabic = parse_arabic(token)
    if arabic is not None:
        return arabic
    if not token or any(ch not in _CN_CHARS for ch in token):
        return None
    total, section, last_digit = 0, 0, None
    for ch in token:
        if ch in _CN_DIGITS:
            last_digit = _CN_DIGITS[ch]
        else:  # a unit: 十 / 百 / 千
            unit = _CN_UNITS[ch]
            section += (last_digit if last_digit is not None else 1) * unit
            last_digit = None
    total = section + (last_digit or 0)
    return total or None


def parse_thai(token: str) -> int | None:
    return parse_arabic(token.translate(_THAI_DIGITS))


# --- heading rules --------------------------------------------------------

# A heading's number is followed by end of line, punctuation, or a capitalised
# title word. A lowercase continuation ("Chapter 6 explores how...") is prose.
_PLAUSIBLE_TAIL = re.compile(r"\A\s*\Z|\A\s*[.:\-—–)]|\A\s+[A-ZÀ-Þ0-9\"“'(]")


@dataclass(frozen=True)
class HeadingRule:
    name: str
    pattern: re.Pattern[str]
    parse: Callable[[str], int | None]
    check_tail: bool = False


HEADING_RULES: tuple[HeadingRule, ...] = (
    # "Chapter 7", "Capítulo 7: Título", "Kapitel VII."
    HeadingRule(
        "latin-chapter",
        re.compile(
            r"^\s*(?:chapter|chapitre|kapitel|cap[ií]tulo|capitolo|hoofdstuk|ch\.?)"
            r"\s*([0-9]{1,3}|[IVXLCDM]{1,7})\b(?P<tail>.*)$",
            re.IGNORECASE,
        ),
        lambda t: parse_arabic(t) or parse_roman(t),
        check_tail=True,
    ),
    # "I: Loomings", "IV. The Carpet-Bag" — a separator and a capitalised title
    # are required so a bare "V." page marker is not mistaken for a chapter.
    HeadingRule(
        "roman-standalone",
        re.compile(r"^\s*([IVXLCDM]{1,7})\s*[.:]\s+(?P<tail>[A-ZÀ-Þ\"“(].*)$"),
        parse_roman,
    ),
    # 第一章 / 第 3 回 / 第十二节 / 第１講
    HeadingRule(
        "cjk-chapter",
        re.compile(rf"^\s*第\s*([0-9{_FULLWIDTH}{_CN_CHARS}]+)\s*[章回卷節节篇講讲部](?P<tail>.*)$"),
        parse_chinese,
    ),
    # "## 一 · 缘起", "### 第三讲" — markdown-converted CJK ebooks
    HeadingRule(
        "cjk-markdown",
        re.compile(rf"^#{{1,6}}\s+第?\s*([{_FULLWIDTH}{_CN_CHARS}]+)\s*[·、.:：章回卷節节篇講讲](?P<tail>.*)$"),
        parse_chinese,
    ),
    # บทที่ ๓ / ตอนที่ 12 / ภาคที่ ๒
    HeadingRule(
        "thai-chapter",
        re.compile(r"^\s*(?:#{1,6}\s+)?(?:บทที่|ตอนที่|ภาคที่|บท|ตอน|ภาค)\s*([0-9๐-๙]+)(?P<tail>.*)$"),
        parse_thai,
    ),
)

# Table-of-contents headers, matched as a whole line so an inline mention of
# "the contents of this chapter" never counts.
TOC_HEADERS = frozenset({
    "table of contents", "contents", "index",
    "índice", "indice", "sumário", "sommaire", "inhalt", "inhaltsverzeichnis",
    "目录", "目錄", "目次", "차례", "목차", "สารบัญ",
})


@dataclass(frozen=True)
class Heading:
    number: int
    title: str
    line: int          # 1-indexed, for grep/sed slicing
    rule: str


@dataclass(frozen=True)
class Structure:
    headings: tuple[Heading, ...]
    has_toc: bool

    @property
    def count(self) -> int:
        return len(self.headings)


def _match_line(line: str) -> tuple[int, str, str] | None:
    for rule in HEADING_RULES:
        m = rule.pattern.match(line)
        if not m:
            continue
        if rule.check_tail and not _PLAUSIBLE_TAIL.match(m.group("tail") or ""):
            continue
        number = rule.parse(m.group(1))
        if number is None or not (1 <= number <= 999):
            continue
        title = (m.group("tail") or "").strip(" .:-—–\t")
        return number, title, rule.name
    return None


def detect_structure(text: str) -> Structure:
    """Find chapter headings and whether the source carries a ToC."""
    headings: list[Heading] = []
    seen: set[tuple[str, int]] = set()
    has_toc = False

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip().strip("#").strip().lower().rstrip(":：")
        if stripped in TOC_HEADERS:
            has_toc = True
            continue

        hit = _match_line(line)
        if hit is None:
            continue
        number, title, rule = hit
        # Dedupe by (dialect, number): a ToC entry and the chapter itself, or a
        # "##" heading repeated as "###", collapse to one chapter.
        key = (rule, number)
        if key in seen:
            continue
        seen.add(key)
        headings.append(Heading(number=number, title=title, line=lineno, rule=rule))

    return Structure(headings=tuple(headings), has_toc=has_toc)
