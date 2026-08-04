"""bookrefs — the extraction runtime for the books-to-skill-refs skill.

First-party and self-contained: five of the eight supported format families
(text, html, docx, epub, rtf) need nothing beyond the Python standard library.
PDF needs one of pymupdf / pdfplumber / pypdf; MOBI/AZW need calibre.
"""

from __future__ import annotations

__version__ = "1.1.0"

from .exceptions import BookrefsError, MissingDependency, ParseFailure, UnsupportedFormat
from .extract import ExtractionResult, SourceRecord, run
from .tokens import estimate_tokens

__all__ = [
    "__version__",
    "BookrefsError",
    "MissingDependency",
    "ParseFailure",
    "UnsupportedFormat",
    "ExtractionResult",
    "SourceRecord",
    "run",
    "estimate_tokens",
]
