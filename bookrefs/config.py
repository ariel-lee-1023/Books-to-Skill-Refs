"""Constants and the output contract this project defines for itself.

Tier 1 note: the fence and metadata shapes below used to be inherited from
another project's internals. They are now *this* project's contract, which is
why they live in one file and are covered by tests: SKILL.md Steps 2.5, 2.6, 3
and 7 all read them.
"""

from __future__ import annotations

# --- output contract ------------------------------------------------------

FENCE_RULE = "=" * 80

def fence(filename: str, path: str) -> str:
    """The per-source separator written into full_text.txt.

    Deliberately byte-identical to the format earlier libraries were built
    against, so SKILL.md's `grep -n "^SOURCE: "` slicing keeps working.
    """
    return f"{FENCE_RULE}\nSOURCE: {filename} (Path: {path})\n{FENCE_RULE}\n"


FENCE_MARKER = "SOURCE: "          # what Step 2.6 greps for
FULL_TEXT_NAME = "full_text.txt"
METADATA_NAME = "metadata.json"
WORKDIR_NAME = "book_skill_work"

# --- formats --------------------------------------------------------------

# Extensions handled with the standard library alone. Independence claim: five
# of the eight advertised format families need no third-party package at all.
STDLIB_FORMATS = {
    ".txt": "text", ".md": "text", ".markdown": "text",
    ".rst": "text", ".adoc": "text",
    ".html": "html", ".htm": "html",
    ".docx": "docx",
    ".epub": "epub",
    ".rtf": "rtf",
}

# Extensions that need something extra installed.
OPTIONAL_FORMATS = {
    ".pdf": "pdf",          # needs a PDF library (see dependencies.py)
    ".mobi": "calibre",     # needs calibre's ebook-convert on PATH
    ".azw": "calibre",
    ".azw3": "calibre",
}

SUPPORTED_FORMATS = {**STDLIB_FORMATS, **OPTIONAL_FORMATS}

MODES = ("text", "technical")

# --- token estimation -----------------------------------------------------

# Characters per token, by script density. See bookrefs/tokens.py for why this
# is not a word-split estimate.
DENSE_CHARS_PER_TOKEN = 1.5
OTHER_CHARS_PER_TOKEN = 4.0

# Rough page equivalence for formats with no intrinsic pagination, so
# metadata's `pages` field stays comparable across a mixed library.
CHARS_PER_PAGE = 1_800
