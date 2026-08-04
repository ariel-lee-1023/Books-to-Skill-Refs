"""Orchestrator: N source documents -> full_text.txt + metadata.json.

This is the contract SKILL.md Steps 2 through 7 read. Two outputs:

  full_text.txt   every source concatenated, each behind a `SOURCE:` fence.
                  The fence is how Step 2.6 slices one book out of a library
                  run without reading the others.

  metadata.json   per-source facts: format, pages, words, chars,
                  estimated_tokens, chapters_detected, has_toc — plus the
                  fence's start/end line numbers, so a caller never has to
                  re-grep for boundaries it can be told.

`estimated_tokens` comes from bookrefs.tokens, which segments by script
density. A word-split estimate would report ~0 for Chinese sources and make
the pre-generation cost gate meaningless.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import (
    CHARS_PER_PAGE,
    FULL_TEXT_NAME,
    METADATA_NAME,
    SUPPORTED_FORMATS,
    WORKDIR_NAME,
    fence,
)
from .exceptions import BookrefsError
from .parsers import parse, parser_for
from .sanitize import sanitize
from .structure import detect_structure
from .tokens import count_words, estimate_tokens


@dataclass
class SourceRecord:
    filename: str
    path: str
    format: str
    pages: int
    words: int
    chars: int
    estimated_tokens: int
    chapters_detected: int
    has_toc: bool
    start_line: int
    end_line: int
    ok: bool = True
    error: str = ""


@dataclass
class ExtractionResult:
    workdir: Path
    full_text_path: Path
    metadata_path: Path
    sources: list[SourceRecord] = field(default_factory=list)
    failures: list[SourceRecord] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return sum(s.estimated_tokens for s in self.sources)


def default_workdir() -> Path:
    return Path(tempfile.gettempdir()) / WORKDIR_NAME


def collect_inputs(paths: list[Path]) -> list[Path]:
    """Expand directories and globs into a sorted list of supported files."""
    found: list[Path] = []
    for raw in paths:
        if raw.is_dir():
            found.extend(p for p in sorted(raw.rglob("*"))
                         if p.is_file() and p.suffix.lower() in SUPPORTED_FORMATS)
        elif raw.is_file():
            found.append(raw)
        else:  # treat as a glob relative to cwd
            found.extend(sorted(p for p in Path().glob(str(raw))
                                if p.is_file() and p.suffix.lower() in SUPPORTED_FORMATS))
    # De-duplicate while preserving order.
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in found:
        resolved = p.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(p)
    return unique


def extract_one(path: Path, mode: str) -> tuple[str, SourceRecord]:
    """Parse one document. Returns (sanitized text, record without line spans)."""
    family = parser_for(path)
    doc = parse(path, mode=mode)
    text = sanitize(doc.text)
    structure = detect_structure(text)
    chars = len(text)

    record = SourceRecord(
        filename=path.name,
        path=str(path),
        format=path.suffix.lower().lstrip("."),
        pages=doc.pages if doc.pages is not None else max(1, round(chars / CHARS_PER_PAGE)),
        words=count_words(text),
        chars=chars,
        estimated_tokens=estimate_tokens(text),
        chapters_detected=structure.count,
        has_toc=structure.has_toc,
        start_line=0,
        end_line=0,
    )
    return text, record


def run(paths: list[Path], mode: str = "text", workdir: Path | None = None) -> ExtractionResult:
    """Extract every supported file under `paths` into one corpus."""
    if mode not in ("text", "technical"):
        raise BookrefsError(f"unknown mode '{mode}' (expected text or technical)")

    inputs = collect_inputs(paths)
    if not inputs:
        raise BookrefsError(
            "no supported documents found. Supported extensions: "
            + " ".join(sorted(SUPPORTED_FORMATS))
        )

    workdir = workdir or default_workdir()
    workdir.mkdir(parents=True, exist_ok=True)
    full_text_path = workdir / FULL_TEXT_NAME
    metadata_path = workdir / METADATA_NAME

    result = ExtractionResult(workdir=workdir,
                              full_text_path=full_text_path,
                              metadata_path=metadata_path)

    chunks: list[str] = []
    line_cursor = 1
    for path in inputs:
        try:
            text, record = extract_one(path, mode)
        except BookrefsError as exc:
            result.failures.append(SourceRecord(
                filename=path.name, path=str(path), format=path.suffix.lower().lstrip("."),
                pages=0, words=0, chars=0, estimated_tokens=0, chapters_detected=0,
                has_toc=False, start_line=0, end_line=0, ok=False, error=str(exc),
            ))
            continue

        header = fence(record.filename, str(path))
        block = header + text
        if not block.endswith("\n"):
            block += "\n"

        header_lines = header.count("\n")
        record.start_line = line_cursor + header_lines   # first line of body
        record.end_line = line_cursor + block.count("\n") - 1
        line_cursor = record.end_line + 1

        chunks.append(block)
        result.sources.append(record)

    full_text_path.write_text("".join(chunks), encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "total_sources": len(result.sources),
                "mode": mode,
                "token_method": "script-density (bookrefs.tokens); not word-split",
                "full_text": str(full_text_path),
                "sources": [asdict(s) for s in result.sources],
                "failures": [asdict(s) for s in result.failures],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return result
