"""MOBI / AZW / AZW3 via calibre's `ebook-convert`.

These are DRM-era Amazon formats with no practical standard-library path.
Rather than reimplement PalmDB and Amazon's compression, this shells out to
calibre if it is installed, converting to a temporary .txt.

Deliberately not silent about it: the run reports that an external tool was
used, because unlike every other parser here the result depends on software
this project does not control or version.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ..exceptions import MissingDependency, ParseFailure
from .base import ParsedDoc, read_text_file

TOOL = "ebook-convert"
INSTALL_HINT = (
    "install calibre and put ebook-convert on PATH — macOS: `brew install --cask calibre`; "
    "Linux: see https://calibre-ebook.com/download"
)
TIMEOUT_SECONDS = 300


def is_available() -> bool:
    return shutil.which(TOOL) is not None


def parse(path: Path) -> ParsedDoc:
    if not is_available():
        raise MissingDependency(
            f"{path.suffix} needs calibre's {TOOL}, which is not on PATH",
            remedy=INSTALL_HINT,
        )
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / (path.stem + ".txt")
        try:
            result = subprocess.run(
                [TOOL, str(path), str(out)],
                capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ParseFailure(f"{path.name}: {TOOL} timed out after {TIMEOUT_SECONDS}s") from exc
        if result.returncode != 0 or not out.exists():
            detail = (result.stderr or result.stdout or "").strip().splitlines()
            raise ParseFailure(
                f"{path.name}: {TOOL} failed"
                + (f" — {detail[-1]}" if detail else "")
                + ". A DRM-protected file cannot be converted."
            )
        return ParsedDoc(text=read_text_file(out))
