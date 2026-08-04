"""PDF: the one format with no honest standard-library answer.

Backends are tried in order of extraction quality and reported by name, so the
run is never ambiguous about which one produced the text. `--mode technical`
prefers a layout-aware backend, since column and table structure is exactly
what that mode exists to keep.

A scanned PDF has no text layer. This module does not OCR; it detects the case
and says so, which is more useful than returning a few hundred bytes of page
furniture and letting the distillation proceed on nothing.
"""

from __future__ import annotations

from pathlib import Path

from ..exceptions import MissingDependency, ParseFailure
from .base import ParsedDoc

INSTALL_HINT = "pip install pypdf   # or: pip install pymupdf / pdfplumber"

# (import name, human name, layout-aware?)
BACKENDS = (
    ("fitz", "pymupdf", True),
    ("pdfplumber", "pdfplumber", True),
    ("pypdf", "pypdf", False),
)

# Below this many characters per page, assume no usable text layer.
MIN_CHARS_PER_PAGE = 24


def available_backends() -> list[str]:
    import importlib.util
    return [name for module, name, _ in BACKENDS if importlib.util.find_spec(module)]


def _pick(mode: str) -> tuple[str, str, bool]:
    import importlib.util
    candidates = list(BACKENDS)
    if mode == "technical":
        candidates.sort(key=lambda b: not b[2])  # layout-aware first
    for module, name, layout in candidates:
        if importlib.util.find_spec(module):
            return module, name, layout
    raise MissingDependency(
        "no PDF backend is installed (tried pymupdf, pdfplumber, pypdf)",
        remedy=INSTALL_HINT,
    )


def _extract_fitz(path: Path) -> tuple[list[str], int]:
    import fitz
    with fitz.open(path) as doc:
        return [page.get_text("text") for page in doc], doc.page_count


def _extract_pdfplumber(path: Path) -> tuple[list[str], int]:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return [page.extract_text() or "" for page in pdf.pages], len(pdf.pages)


def _extract_pypdf(path: Path) -> tuple[list[str], int]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return [page.extract_text() or "" for page in reader.pages], len(reader.pages)


_EXTRACTORS = {"fitz": _extract_fitz, "pdfplumber": _extract_pdfplumber, "pypdf": _extract_pypdf}


def parse(path: Path, mode: str = "text") -> ParsedDoc:
    module, name, _layout = _pick(mode)
    try:
        pages, count = _EXTRACTORS[module](path)
    except MissingDependency:
        raise
    except Exception as exc:  # backend-specific failures are not worth enumerating
        raise ParseFailure(f"{path.name}: {name} could not read this PDF ({exc})") from exc

    text = "\n\n".join(p.strip() for p in pages if p and p.strip())
    if count and len(text) / count < MIN_CHARS_PER_PAGE:
        raise ParseFailure(
            f"{path.name} yielded {len(text)} characters across {count} pages — it is "
            f"almost certainly a scan with no text layer. OCR it first "
            f"(e.g. `ocrmypdf in.pdf out.pdf`) and re-run."
        )
    return ParsedDoc(text=text, pages=count)
