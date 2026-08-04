#!/usr/bin/env python3
"""Validate a generated library against the contracts in this skill's SKILL.md.

Why this exists
---------------
The repository's CI validates *its own* SKILL.md. Nothing validated the thing
the skill actually promises to produce: a flat library of one master router
plus one reference file per book, inside stated token budgets. This turns the
"should" statements in SKILL.md into executable assertions.

Usage
-----
    python tools/validate_library.py path/to/<library-name>/

Severity
--------
    ERROR  breaks the contract SKILL.md states; exits 1
    WARN   a soft guideline or an allowed variant; does not exit 1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from count_tokens import estimate_tokens, strip_frontmatter  # noqa: E402

# --- contract constants, mirroring SKILL.md -------------------------------

MASTER_HARD_STOP = 3_500           # Step 8
MASTER_BASE = 400                  # frontmatter + How to use + Scope
MASTER_PER_BOOK = 50               # one router row per book
MASTER_INDEX_ALLOWANCE = 600       # topic index share of the budget

TOPIC_INDEX_MAX_ENTRIES = 40       # Step 8
TOPIC_INDEX_MIN_BOOKS = 2          # the >=2-book inclusion rule

# Step 7 caps: (BOOK_TYPE, DEPTH) -> hard cap
REFERENCE_CAPS = {
    ("text", "reference"): 9_000,
    ("text", "study"): 14_000,
    ("technical", "reference"): 12_000,
    ("technical", "study"): 20_000,
}

ALLOWED_FILENAMES = re.compile(r"\A(SKILL\.md|topic-index\.md|reference-[a-z0-9]+(-[a-z0-9]+)*\.md)\Z")
SLUG = re.compile(r"\A[a-z0-9]+(-[a-z0-9]+)*\Z")
RESERVED_SLUG_WORDS = ("claude", "anthropic")

REQUIRED_REFERENCE_SECTIONS = ("Mental Model", "Frameworks & Structure", "Key Takeaways")

MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
SECTION = re.compile(r"^##\s+(.*)$", re.MULTILINE)
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
FENCED_CODE = re.compile(r"^```", re.MULTILINE)
PIPE_TABLE_ROW = re.compile(r"^\s*\|.*\|.*\|", re.MULTILINE)
DEPTH_DECL = re.compile(r"\*\*Depth\*\*:\s*(reference|study)", re.IGNORECASE)
INDEX_ENTRY = re.compile(r"^[-*]\s+(.*?)(?:→|->)(.*)$", re.MULTILINE)


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    facts: dict = field(default_factory=dict)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def sections_of(text: str) -> dict[str, str]:
    """Split a markdown document into {section title: body} by `## ` headings."""
    out: dict[str, str] = {}
    matches = list(SECTION.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[m.group(1).strip()] = text[m.end():end]
    return out


def find_section(sections: dict[str, str], needle: str) -> tuple[str, str] | None:
    for title, body in sections.items():
        if needle.lower() in title.lower():
            return title, body
    return None


def detect_book_type(text: str) -> str:
    """Classify a reference file as technical or text.

    Mirrors Step 3's tripwire signals. Fenced code is decisive; pipe tables are
    not, because Step 7 explicitly asks Decision Rules to use compact tables.
    """
    if len(FENCED_CODE.findall(text)) >= 2:  # an opening and a closing fence
        return "technical"
    if len(PIPE_TABLE_ROW.findall(text)) >= 12:
        return "technical"
    return "text"


def declared_depth(text: str, fallback: str) -> str:
    m = DEPTH_DECL.search(text)
    return m.group(1).lower() if m else fallback


# --- checks ---------------------------------------------------------------

def check_layout(lib: Path, rep: Report) -> list[Path]:
    """Flat directory contract: SKILL.md + reference-*.md siblings, no nesting."""
    for child in sorted(lib.iterdir()):
        if child.is_dir():
            rep.error(f"{child.name}/ — the library must be flat; no subdirectories "
                      f"(no chapters/, no per-book folders)")

    files = sorted(p for p in lib.iterdir() if p.is_file())
    for f in files:
        if not ALLOWED_FILENAMES.match(f.name):
            rep.warn(f"{f.name} — unexpected file; the contract is SKILL.md, "
                     f"reference-<slug>.md, and optionally topic-index.md")

    refs = sorted(p for p in files if p.name.startswith("reference-") and p.suffix == ".md")
    if not (lib / "SKILL.md").exists():
        rep.error("SKILL.md is missing — the library has no master router")
    if not refs:
        rep.error("no reference-*.md files — a library needs at least one book")

    for r in refs:
        slug = r.stem[len("reference-"):]
        if not SLUG.match(slug):
            rep.error(f"{r.name} — slug '{slug}' must be lowercase letters, digits and hyphens")

    return refs


def check_master_frontmatter(master_text: str, rep: Report) -> None:
    m = FRONTMATTER.match(master_text)
    if not m:
        rep.error("SKILL.md must open with a YAML frontmatter block delimited by ---")
        return
    fm = m.group(1)

    name = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
    if not name:
        rep.error("SKILL.md frontmatter is missing `name:`")
    else:
        slug = name.group(1).strip().strip("\"'")
        if not SLUG.match(slug):
            rep.error(f"`name: {slug}` must be lowercase letters, digits and hyphens only")
        if any(w in slug for w in RESERVED_SLUG_WORDS):
            rep.error(f"`name: {slug}` must not contain {' or '.join(RESERVED_SLUG_WORDS)}")

    desc = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE | re.DOTALL)
    if not desc:
        rep.error("SKILL.md frontmatter is missing `description:`")
    elif len(desc.group(1).strip()) < 40:
        rep.error("`description:` is too short to trigger reliably")


def check_master_budget(master_text: str, n_books: int, index_tokens: int, rep: Report) -> None:
    body = estimate_tokens(strip_frontmatter(master_text))
    budget = MASTER_BASE + MASTER_PER_BOOK * n_books + min(index_tokens, MASTER_INDEX_ALLOWANCE)
    rep.facts["master_body_tokens"] = body
    rep.facts["master_budget"] = budget

    if body > MASTER_HARD_STOP:
        rep.error(f"SKILL.md body is ~{body:,} tokens, over the {MASTER_HARD_STOP:,} hard stop. "
                  f"It is always loaded — spill the Topic Index to topic-index.md, or group "
                  f"the router table by theme.")
    elif body > budget:
        rep.warn(f"SKILL.md body is ~{body:,} tokens, over its ~{budget:,} scaling budget "
                 f"(400 + 50x{n_books} + index). Still under the {MASTER_HARD_STOP:,} hard stop.")


def check_router(master_text: str, lib: Path, refs: list[Path], rep: Report) -> None:
    sections = sections_of(master_text)
    found = find_section(sections, "which book")
    if not found:
        rep.error("SKILL.md has no router section ('Which book for which job') — "
                  "without it nothing can find the reference files")
        return
    _, router = found

    linked: set[str] = set()
    for _label, target in MD_LINK.findall(router):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        if any(c in target for c in "<>{}"):  # unfilled template placeholder
            rep.error(f"router table contains an unfilled placeholder link: ({target})")
            continue
        clean = target.split("#")[0]
        linked.add(clean)
        if not (lib / clean).exists():
            rep.error(f"router links to {clean}, which does not exist")

    for r in refs:
        if r.name not in linked:
            rep.error(f"{r.name} is not linked from the router table — it is unreachable")


def check_topic_index(master_text: str, lib: Path, refs: list[Path], rep: Report) -> int:
    """Returns the topic index's token count (0 if absent)."""
    spilled = lib / "topic-index.md"
    sections = sections_of(master_text)
    found = find_section(sections, "topic index")

    if spilled.exists():
        index_text = spilled.read_text(encoding="utf-8")
        if found and len(INDEX_ENTRY.findall(found[1])) > 1:
            rep.error("topic-index.md exists, but SKILL.md still carries a populated "
                      "Topic Index. The spill valve replaces it with a one-line pointer.")
        if "topic-index.md" not in master_text:
            rep.error("topic-index.md exists but SKILL.md never points at it — it is unreachable")
        tokens = 0  # spilled: loaded on demand, so it no longer taxes the master
    elif found:
        index_text = found[1]
        tokens = estimate_tokens(index_text)
    else:
        return 0

    entries = INDEX_ENTRY.findall(index_text)
    rep.facts["topic_index_entries"] = len(entries)

    known = {r.stem[len("reference-"):] for r in refs}
    for term, targets in entries:
        slugs = [s.strip().strip("`*_[]()") for s in targets.split(",") if s.strip()]
        slugs = [s[len("reference-"):] if s.startswith("reference-") else s for s in slugs]
        slugs = [s[:-3] if s.endswith(".md") else s for s in slugs]
        label = term.strip().strip("*` ")
        if len(slugs) < TOPIC_INDEX_MIN_BOOKS:
            rep.error(f"topic index entry '{label}' lists {len(slugs)} book(s); the index is "
                      f"for cross-book routing, so entries must span >={TOPIC_INDEX_MIN_BOOKS} books")
        for s in slugs:
            if s and s not in known:
                rep.warn(f"topic index entry '{label}' points at unknown book '{s}'")

    if len(entries) > TOPIC_INDEX_MAX_ENTRIES:
        rep.warn(f"topic index has {len(entries)} entries, over the ~{TOPIC_INDEX_MAX_ENTRIES} ceiling")

    return tokens


def check_reference(path: Path, master_depth: str, rep: Report) -> None:
    text = path.read_text(encoding="utf-8")
    depth = declared_depth(text, master_depth)
    book_type = detect_book_type(text)
    cap = REFERENCE_CAPS[(book_type, depth)]
    tokens = estimate_tokens(text)
    rep.facts.setdefault("references", {})[path.name] = {
        "tokens": tokens, "cap": cap, "depth": depth, "type": book_type,
    }

    if tokens > cap:
        rep.error(f"{path.name} is ~{tokens:,} tokens, over the {cap:,} cap for "
                  f"{book_type}/{depth}. This file loads whole on every consultation — "
                  f"apply Step 7's cut order rather than truncating.")

    if not re.match(r"^#\s+\S", text, re.MULTILINE):
        rep.error(f"{path.name} has no `# <Title>` heading")

    titles = list(sections_of(text))
    for required in REQUIRED_REFERENCE_SECTIONS:
        if not any(required.lower() in t.lower() for t in titles):
            rep.error(f"{path.name} is missing the `## {required}` section")

    if not any("decision rules" in t.lower() for t in titles):
        rep.warn(f"{path.name} has no `## Decision Rules & Judgment` — expected unless "
                 f"the library was built in strict mode")

    worked = [t for t in titles if "worked example" in t.lower()]
    if depth == "reference" and worked:
        rep.error(f"{path.name} declares DEPTH=reference but contains a Worked Example")
    if len(worked) > 1:
        rep.error(f"{path.name} has {len(worked)} Worked Example sections; the budget allows "
                  f"one for the whole book, not one per chapter")
    if depth == "study" and not worked:
        rep.warn(f"{path.name} declares DEPTH=study but has no Worked Example — the single "
                 f"biggest reason a study-depth file earns its budget")


def validate(lib: Path) -> Report:
    rep = Report()
    if not lib.is_dir():
        rep.error(f"{lib} is not a directory")
        return rep

    refs = check_layout(lib, rep)
    master = lib / "SKILL.md"
    if not master.exists():
        return rep

    master_text = master.read_text(encoding="utf-8")
    check_master_frontmatter(master_text, rep)
    check_router(master_text, lib, refs, rep)
    index_tokens = check_topic_index(master_text, lib, refs, rep)
    check_master_budget(master_text, len(refs), index_tokens, rep)

    master_depth = declared_depth(master_text, "study")
    for r in refs:
        check_reference(r, master_depth, rep)

    rep.facts["books"] = len(refs)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate a generated books-to-skill-refs library.")
    ap.add_argument("library", type=Path, help="path to the flat library directory")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    rep = validate(args.library)

    if args.as_json:
        print(json.dumps({"errors": rep.errors, "warnings": rep.warnings, "facts": rep.facts},
                         indent=2, ensure_ascii=False))
    else:
        refs = rep.facts.get("references", {})
        if refs:
            width = max(len(n) for n in refs)
            print(f"Library: {args.library}  ({rep.facts.get('books', 0)} book(s))")
            for name, f in sorted(refs.items()):
                mark = "!" if f["tokens"] > f["cap"] else " "
                print(f"  {mark} {name:<{width}}  {f['tokens']:>7,} / {f['cap']:>6,} tok"
                      f"  [{f['type']}/{f['depth']}]")
            if "master_body_tokens" in rep.facts:
                print(f"    {'SKILL.md (always loaded)':<{width}}  "
                      f"{rep.facts['master_body_tokens']:>7,} / {rep.facts['master_budget']:>6,} tok")
            print()
        for w in rep.warnings:
            print(f"! {w}")
        for e in rep.errors:
            print(f"x {e}")
        if not rep.errors and not rep.warnings:
            print("ok — library satisfies the SKILL.md contract")
        elif not rep.errors:
            print(f"\nok with {len(rep.warnings)} warning(s)")
        else:
            print(f"\nfailed: {len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")

    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
