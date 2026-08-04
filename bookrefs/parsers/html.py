"""HTML parsing on the standard library's html.parser.

Also used by the EPUB parser, whose payload is XHTML.

Structure is preserved rather than flattened: headings become markdown-style
`#` lines and tables become pipe rows, because Step 3's technical/text tripwire
and structure.py's markdown heading rules both read those signals. A parser
that emitted bare prose would erase the very evidence the workflow uses.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from .base import ParsedDoc, read_text_file

_SKIP = {"script", "style", "head", "noscript", "svg", "template"}
_BLOCK = {"p", "div", "section", "article", "br", "li", "blockquote",
          "figure", "figcaption", "hr", "tr"}
_HEADINGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####", "h5": "#####", "h6": "######"}
# Punctuation that must never be preceded by an inserted space, in both ASCII
# and the full-width forms CJK typesetting uses.
_NO_SPACE_BEFORE = frozenset(".,;:!?)]}'\"”’、。，；：！？）」』")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._pre_depth = 0
        self._cell_open = False

    # -- helpers
    def _emit(self, text: str) -> None:
        self.parts.append(text)

    def _newline(self, count: int = 1) -> None:
        while self.parts and self.parts[-1] == "\n":
            self.parts.pop()
            count = max(count, 1)
        self.parts.extend("\n" * count)

    # -- HTMLParser interface
    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "pre":
            self._pre_depth += 1
            self._newline(2)
            self._emit("```\n")
        elif tag in _HEADINGS:
            self._newline(2)
            self._emit(_HEADINGS[tag] + " ")
        elif tag in ("td", "th"):
            self._emit("| " if not self._cell_open else " | ")
            self._cell_open = True
        elif tag == "tr":
            self._newline()
            self._cell_open = False
        elif tag in _BLOCK:
            self._newline(2 if tag in ("p", "div", "blockquote") else 1)

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag == "pre":
            self._pre_depth = max(0, self._pre_depth - 1)
            self._newline()
            self._emit("```\n")
        elif tag == "tr":
            if self._cell_open:
                self._emit(" |")
            self._cell_open = False
            self._newline()
        elif tag in _HEADINGS or tag in _BLOCK:
            self._newline()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._pre_depth:
            self._emit(data)
            return
        collapsed = " ".join(data.split())
        if collapsed:
            # Join inline runs with a space, but never in front of punctuation:
            # "<b>world</b>." must not become "world .".
            needs_space = (
                self.parts
                and not self.parts[-1].endswith(("\n", " ", "#"))
                and collapsed[0] not in _NO_SPACE_BEFORE
            )
            if needs_space:
                self._emit(" ")
            self._emit(collapsed)

    def result(self) -> str:
        return "".join(self.parts)


def html_to_text(markup: str) -> str:
    parser = _TextExtractor()
    parser.feed(markup)
    parser.close()
    return parser.result()


def parse(path: Path) -> ParsedDoc:
    return ParsedDoc(text=html_to_text(read_text_file(path)))
