"""Build valid DOCX / EPUB fixtures at test time.

Both formats are zip archives of XML, so a real one can be assembled in a few
lines. Doing that beats committing binaries: the fixtures stay reviewable in a
diff, and a test can vary them (a shuffled EPUB spine, a Heading 2 style)
without anyone regenerating a blob.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _docx_paragraph(text: str, style: str | None = None) -> str:
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{props}<w:r><w:t>{text}</w:t></w:r></w:p>"


def _docx_table(rows: list[list[str]]) -> str:
    cells = "".join(
        "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in row) + "</w:tr>"
        for row in rows
    )
    return f"<w:tbl>{cells}</w:tbl>"


def write_docx(path: Path, blocks: list[tuple[str, str | None]],
               table: list[list[str]] | None = None) -> Path:
    """blocks is [(text, style_or_None)]; style "Heading1" becomes `# text`."""
    body = "".join(_docx_paragraph(t, s) for t, s in blocks)
    if table:
        body += _docx_table(table)
    document = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/content-types"/>')
        z.writestr("word/document.xml", document)
    return path


def write_epub(path: Path, chapters: list[tuple[str, str]], *, shuffle_zip: bool = False) -> Path:
    """chapters is [(filename, xhtml_body)], written in spine order.

    `shuffle_zip` stores the entries in reverse so a test can prove the parser
    follows the spine rather than the archive's own ordering.
    """
    container = (
        '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:'
        'opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    manifest = "".join(
        f'<item id="c{i}" href="{name}" media-type="application/xhtml+xml"/>'
        for i, (name, _) in enumerate(chapters)
    )
    spine = "".join(f'<itemref idref="c{i}"/>' for i in range(len(chapters)))
    opf = (
        f'<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        f'<manifest>{manifest}</manifest><spine>{spine}</spine></package>'
    )

    entries = [("OEBPS/" + name,
                f'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml">'
                f'<body>{body}</body></html>')
               for name, body in chapters]
    if shuffle_zip:
        entries.reverse()

    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        for name, xhtml in entries:
            z.writestr(name, xhtml)
    return path


def write_rtf(path: Path, body: str) -> Path:
    path.write_text(
        r"{\rtf1\ansi\deff0{\fonttbl{\f0 Times;}}{\info{\title Ignored}}" + body + "}",
        encoding="utf-8",
    )
    return path
