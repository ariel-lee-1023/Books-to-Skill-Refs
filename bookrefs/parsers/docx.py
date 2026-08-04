"""DOCX on the standard library: a .docx is a zip of XML.

No third-party package. Paragraph styles named Heading N are re-emitted as
markdown `#` headings so structure.py can see them, and tables are re-emitted
as pipe rows so the technical/text tripwire can.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from ..exceptions import ParseFailure
from .base import ParsedDoc

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DOCUMENT = "word/document.xml"
_HEADING_STYLE = re.compile(r"heading\s*([1-6])", re.IGNORECASE)


def _style_of(paragraph: ElementTree.Element) -> str:
    props = paragraph.find(f"{W}pPr")
    if props is None:
        return ""
    style = props.find(f"{W}pStyle")
    return style.get(f"{W}val", "") if style is not None else ""


def _text_of(paragraph: ElementTree.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{W}t":
            parts.append(node.text or "")
        elif node.tag in (f"{W}tab",):
            parts.append("\t")
        elif node.tag in (f"{W}br", f"{W}cr"):
            parts.append("\n")
    return "".join(parts).strip()


def _render_paragraph(paragraph: ElementTree.Element) -> str:
    text = _text_of(paragraph)
    if not text:
        return ""
    level = _HEADING_STYLE.search(_style_of(paragraph))
    if level:
        return "#" * int(level.group(1)) + " " + text
    return text


def _render_table(table: ElementTree.Element) -> str:
    rows: list[str] = []
    for row in table.findall(f"{W}tr"):
        cells = [" ".join(_text_of(p) for p in cell.findall(f"{W}p")).strip()
                 for cell in row.findall(f"{W}tc")]
        if any(cells):
            rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def parse(path: Path) -> ParsedDoc:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read(DOCUMENT)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ParseFailure(f"{path.name} is not a readable .docx ({exc})") from exc

    root = ElementTree.fromstring(xml)
    body = root.find(f"{W}body")
    if body is None:
        raise ParseFailure(f"{path.name} has no document body")

    blocks: list[str] = []
    for child in body:
        if child.tag == f"{W}p":
            rendered = _render_paragraph(child)
            if rendered:
                blocks.append(rendered)
        elif child.tag == f"{W}tbl":
            rendered = _render_table(child)
            if rendered:
                blocks.append(rendered)

    return ParsedDoc(text="\n\n".join(blocks))
