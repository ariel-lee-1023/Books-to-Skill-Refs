"""Consolidate a multi-file source tree into one corpus file, in reading order.

Why this exists
---------------
`extract.py` emits one `SOURCE:` fence per *file*. That is the whole mechanism
behind "one reference file per book" (see docs/ARCHITECTURE.md). So a book that
arrives as a documentation site — 51 HTML chapters, 287 reStructuredText pages,
67 Jupyter Book files — must become **one file** before extraction, or Step 7
will treat every page as a separate book and the library shape collapses.

Consolidating is easy. Consolidating *in the right order* is not, and getting it
wrong is silent: chapter order is the spine Step 3 plans against and Step 7
front-loads from. This module reads the order the project itself declares.

Two declared-order dialects are supported, plus a fallback:

  jupyter-book   `_toc.yml`      — `- file: <path>` entries, `caption:` parts
  sphinx         `index.rst`     — `.. toctree::` blocks, **followed recursively**
  natural        directory walk  — natural sort, digits compared numerically

The recursion in the Sphinx walker is the part that matters. Sphinx toctrees
nest: the root `index.rst` lists section overviews, and each overview lists its
own pages. A flat read of the root reaches only the first level — measured on a
real 287-page book, 56 files (19%). The recursive walk reaches 265 (92%). A
consolidation that quietly drops four fifths of a source is worse than one that
fails, because nothing downstream can tell.

YAML is parsed line-wise rather than with a library: the runtime has no
third-party dependencies and `_toc.yml` files in the wild are flat enough that
`- file:` / `caption:` scanning is sufficient. Anything more exotic should use
`--order natural` with an explicit include list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Extensions tried when a *declared* entry omits one ("intro" -> "intro.md").
# Ordered by how commonly a docs project uses them as the page source.
ENTRY_EXTENSIONS: tuple[str, ...] = (".rst", ".md", ".markdown", ".Rmd", ".txt", ".ipynb")


def corpus_extensions() -> tuple[str, ...]:
    """Extensions a natural walk will pick up.

    Wider than ENTRY_EXTENSIONS: a crawled documentation site arrives as
    `.html`, which no toctree declares but which the runtime parses perfectly
    well. Anything `bookrefs.parsers` handles is fair game, plus the notebook
    and R Markdown sources that Jupyter Book projects use and the runtime reads
    as plain text.
    """
    from .config import SUPPORTED_FORMATS
    return tuple(dict.fromkeys(ENTRY_EXTENSIONS + tuple(SUPPORTED_FORMATS)))

# Provenance marker written above each part. Deliberately an HTML/markdown
# comment: it survives every parser in bookrefs/parsers, is invisible in
# rendered output, and gives the agent a grep target for locating a part inside
# the consolidated file.
PART_MARKER = "<!-- FILE: {rel} -->"

_TOCTREE_START = re.compile(r"^(\s*)\.\.\s+toctree::")
_DIRECTIVE_OPTION = re.compile(r"^\s*:[a-zA-Z_-]+:")
_CAPTION = re.compile(r"^\s*:caption:\s*(.+?)\s*$")
_YAML_FILE = re.compile(r"^\s*-\s*file:\s*(\S+)")
_YAML_ROOT = re.compile(r"^\s*root:\s*(\S+)")
_YAML_CAPTION = re.compile(r"^\s*-?\s*caption:\s*(.+?)\s*$")
# A toctree entry may be a bare path or "Title <path>".
_ENTRY = re.compile(r"^\s*(?:[^<>]*<\s*(?P<angle>[^<>]+?)\s*>|(?P<bare>[A-Za-z0-9_][\w/.\-]*))\s*$")

_NATURAL = re.compile(r"(\d+)")


@dataclass
class Part:
    """One file destined for the consolidated corpus."""
    path: Path
    rel: str
    caption: str | None = None


@dataclass
class Plan:
    """What consolidation would write, before it writes it."""
    parts: list[Part] = field(default_factory=list)
    order: str = "natural"
    unreached: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.parts)


def natural_key(text: str) -> list[object]:
    """Sort key where embedded digits compare numerically (ch2 < ch10)."""
    return [int(part) if part.isdigit() else part.lower()
            for part in _NATURAL.split(text)]


def _resolve(entry: str, base: Path, root: Path) -> Path | None:
    """Resolve a declared entry to a file.

    Sphinx entries are relative to the containing document's directory; a
    leading slash means relative to the source root. Jupyter Book entries are
    relative to the root. Try both, and try each known extension, because a
    declared entry normally omits it.
    """
    entry = entry.strip().lstrip("/")
    if not entry:
        return None
    for anchor in (base, root):
        candidate = anchor / entry
        if candidate.is_file():
            return candidate.resolve()
        for ext in ENTRY_EXTENSIONS:
            with_ext = candidate.with_suffix(ext) if candidate.suffix else Path(str(candidate) + ext)
            if with_ext.is_file():
                return with_ext.resolve()
    return None


def parse_toctrees(text: str) -> list[tuple[str | None, list[str]]]:
    """Return `(caption, entries)` for every `.. toctree::` block in a document.

    Entries are the indented non-option lines under the directive. The block
    ends at the first line indented no further than the directive itself.
    """
    blocks: list[tuple[str | None, list[str]]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        start = _TOCTREE_START.match(lines[i])
        if not start:
            i += 1
            continue
        base_indent = len(start.group(1))
        caption: str | None = None
        entries: list[str] = []
        i += 1
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= base_indent:
                break
            cap = _CAPTION.match(line)
            if cap:
                caption = cap.group(1)
            elif not _DIRECTIVE_OPTION.match(line):
                m = _ENTRY.match(line)
                if m:
                    entries.append(m.group("angle") or m.group("bare"))
            i += 1
        blocks.append((caption, entries))
    return blocks


def plan_sphinx(root_doc: Path, source_root: Path, max_depth: int = 8) -> Plan:
    """Walk `index.rst` toctrees **recursively**, in declaration order.

    Depth-first: a section overview is emitted before the pages it lists, which
    is the order a reader would meet them. `max_depth` guards against a cyclic
    toctree, which is legal reStructuredText and does occur.
    """
    plan = Plan(order="sphinx")
    source_root = source_root.resolve()
    visited: set[Path] = set()

    def walk(doc: Path, caption: str | None, depth: int) -> None:
        if depth > max_depth or doc in visited or not doc.is_file():
            return
        visited.add(doc)
        plan.parts.append(Part(path=doc, rel=_rel(doc, source_root), caption=caption))
        for block_caption, entries in parse_toctrees(doc.read_text(encoding="utf-8", errors="replace")):
            for entry in entries:
                child = _resolve(entry, doc.parent, source_root)
                if child:
                    walk(child, block_caption or caption, depth + 1)

    root_doc = root_doc.resolve()
    visited.add(root_doc)   # the root is a container, not a part
    for block_caption, entries in parse_toctrees(root_doc.read_text(encoding="utf-8", errors="replace")):
        for entry in entries:
            child = _resolve(entry, root_doc.parent, source_root)
            if child:
                walk(child, block_caption, 1)

    plan.unreached = _unreached(source_root, {p.path for p in plan.parts} | {root_doc},
                                corpus_extensions())
    return plan


def plan_jupyter_book(toc: Path, source_root: Path) -> Plan:
    """Read `_toc.yml` line-wise: `root:`, `- file:` entries, `caption:` parts."""
    plan = Plan(order="jupyter-book")
    seen: set[Path] = set()
    caption: str | None = None

    for line in toc.read_text(encoding="utf-8", errors="replace").splitlines():
        root_m = _YAML_ROOT.match(line)
        if root_m:
            resolved = _resolve(root_m.group(1), source_root, source_root)
            if resolved and resolved not in seen:
                seen.add(resolved)
                plan.parts.append(Part(path=resolved,
                                       rel=_rel(resolved, source_root), caption=None))
            continue
        cap = _YAML_CAPTION.match(line)
        if cap and "file:" not in line:
            caption = cap.group(1)
            continue
        file_m = _YAML_FILE.match(line)
        if file_m:
            resolved = _resolve(file_m.group(1), source_root, source_root)
            if resolved and resolved not in seen:
                seen.add(resolved)
                plan.parts.append(Part(path=resolved,
                                       rel=_rel(resolved, source_root), caption=caption))

    plan.unreached = _unreached(source_root, seen, corpus_extensions())
    return plan


def plan_natural(source_root: Path, include: tuple[str, ...] = ("**/*",),
                 exclude: tuple[str, ...] = ()) -> Plan:
    """Fallback: every matching file, natural-sorted by relative path."""
    plan = Plan(order="natural")
    wanted = {e.lower() for e in corpus_extensions()}
    found: set[Path] = set()
    for pattern in include:
        for path in source_root.glob(pattern):
            if path.is_file() and path.suffix.lower() in wanted:
                found.add(path.resolve())
    for pattern in exclude:
        for path in source_root.glob(pattern):
            found.discard(path.resolve())
    for path in sorted(found, key=lambda p: natural_key(_rel(p, source_root))):
        plan.parts.append(Part(path=path, rel=_rel(path, source_root)))
    return plan


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _unreached(root: Path, reached: set[Path], extensions: tuple[str, ...]) -> list[str]:
    """Files present on disk that the declared order never mentions.

    Reported rather than silently included: an orphan is usually boilerplate
    (`contributing.rst`) but is sometimes a real chapter the toctree forgot,
    and only the caller can tell which.
    """
    out: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda p: natural_key(str(p))):
        if path.is_file() and path.suffix.lower() in {e.lower() for e in extensions} \
                and path.resolve() not in reached:
            out.append(_rel(path, root))
    return out


def detect_order(source_root: Path) -> str:
    """Pick the ordering dialect a source tree declares, if any."""
    if (source_root / "_toc.yml").is_file():
        return "jupyter-book"
    for candidate in (source_root / "index.rst", source_root / "docs" / "index.rst"):
        if candidate.is_file() and "toctree::" in candidate.read_text(
                encoding="utf-8", errors="replace"):
            return "sphinx"
    return "natural"


def build_plan(source_root: Path, order: str = "auto",
               include: tuple[str, ...] = ("**/*",),
               exclude: tuple[str, ...] = ()) -> Plan:
    """Resolve `order`, then produce the ordered list of parts."""
    resolved = detect_order(source_root) if order == "auto" else order
    if resolved == "jupyter-book":
        toc = source_root / "_toc.yml"
        if toc.is_file():
            return plan_jupyter_book(toc, source_root)
    elif resolved == "sphinx":
        for candidate in (source_root / "index.rst", source_root / "docs" / "index.rst"):
            if candidate.is_file():
                return plan_sphinx(candidate, candidate.parent)
    return plan_natural(source_root, include, exclude)


def read_part(path: Path) -> str:
    """Text of one part, through the format's parser where one exists.

    HTML is the case that matters: a documentation site consolidated raw would
    put markup into a `.md` corpus, and every downstream token estimate and
    structure probe would then be measuring tags. Extensions the runtime has no
    parser for (`.Rmd`, `.ipynb`) fall back to a plain decode, which is what
    they need anyway.
    """
    from .exceptions import UnsupportedFormat
    from .parsers import parse

    try:
        return parse(path).text
    except (UnsupportedFormat, Exception):  # noqa: BLE001 - a bad part must not sink the build
        return path.read_text(encoding="utf-8", errors="replace")


def render(plan: Plan, title: str | None = None) -> str:
    """Concatenate the planned parts, each behind a provenance marker.

    Captions become `# Part: <caption>` headings so the structure the project
    declared survives into the corpus — `bookrefs.structure` and the Step 3
    section plan both read `#` lines.
    """
    chunks: list[str] = []
    if title:
        chunks.append(f"# {title}\n")
    last_caption: str | None = None
    for part in plan.parts:
        if part.caption and part.caption != last_caption:
            chunks.append(f"\n\n# Part: {part.caption}\n")
            last_caption = part.caption
        chunks.append(f"\n\n{PART_MARKER.format(rel=part.rel)}\n\n{read_part(part.path)}")
    return "\n".join(chunks).strip() + "\n"
