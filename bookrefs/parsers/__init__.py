"""Parser dispatch by file extension."""

from __future__ import annotations

from pathlib import Path

from ..config import SUPPORTED_FORMATS
from ..exceptions import UnsupportedFormat
from .base import ParsedDoc

__all__ = ["ParsedDoc", "parse", "parser_for"]


def parser_for(path: Path) -> str:
    """Return the parser family name for `path`, or raise UnsupportedFormat."""
    family = SUPPORTED_FORMATS.get(path.suffix.lower())
    if family is None:
        raise UnsupportedFormat(
            f"{path.name}: unsupported extension '{path.suffix}'. Supported: "
            + " ".join(sorted(SUPPORTED_FORMATS))
        )
    return family


def parse(path: Path, mode: str = "text") -> ParsedDoc:
    """Extract text from `path`, choosing a parser by extension."""
    family = parser_for(path)

    if family == "text":
        from . import text as backend
        return backend.parse(path)
    if family == "html":
        from . import html as backend
        return backend.parse(path)
    if family == "docx":
        from . import docx as backend
        return backend.parse(path)
    if family == "epub":
        from . import epub as backend
        return backend.parse(path)
    if family == "rtf":
        from . import rtf as backend
        return backend.parse(path)
    if family == "pdf":
        from . import pdf as backend
        return backend.parse(path, mode=mode)
    if family == "calibre":
        from . import calibre as backend
        return backend.parse(path)

    raise UnsupportedFormat(f"no parser registered for family '{family}'")
