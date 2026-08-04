# books-to-skill-refs

> Distill **many books at once** into one flat, cross-referenced knowledge library: a single master `SKILL.md` router plus one standalone `reference-<book-slug>.md` per book.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/type-agent%20skill-blue.svg)](#)

An [agent skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills) for Claude Code, GitHub Copilot CLI, Amp, and other skill-aware agents.

---

## What it does

Point it at several documents (PDF, EPUB, DOCX, HTML, Markdown, plain text, RTF, MOBI/AZW) and it produces a knowledge base your agent can route across — not book reports.

```
$SKILLS_HOME/<library-name>/
├── SKILL.md                    # master: router + library index + cross-book topic index
├── reference-<book1-slug>.md   # dense standalone distillation of book 1
├── reference-<book2-slug>.md   # dense standalone distillation of book 2
└── reference-<bookN-slug>.md
```

Every file is a sibling. No `chapters/`, no per-book subfolders, no separate glossary/patterns/cheatsheet files.

The master `SKILL.md` stays under ~2,500 tokens because it is *always loaded*; the reference files cost nothing until a question actually needs one.

## How it differs from `book-to-skill`

This reuses the extraction engine from [`book-to-skill`](https://github.com/virgiliojr94/book-to-skill) by @virgiliojr94 (MIT), unchanged, and re-points it at a different output shape.

| | book-to-skill | books-to-skill-refs |
|---|---|---|
| Books per run | one | **N** |
| Output per book | nested folder (`SKILL.md` + `chapters/` + `glossary.md` + `patterns.md` + `cheatsheet.md`) | **one flat `reference-<slug>.md`** |
| Shared file | that book's own `SKILL.md` | **one master `SKILL.md`** routing across all books |
| Layout | per-book folder nesting | **flat — all files siblings** |

What carries over unchanged is the load-bearing part: extract *structure* rather than summaries, preserve the author's exact framework names, density over length, never copy raw text, and read on demand (`grep`/`sed`/offset probes) instead of re-reading whole books.

## Requirements

- A skill-aware agent (Claude Code, Copilot CLI, Amp, …)
- **Python 3** on `PATH`
- **[`book-to-skill`](https://github.com/virgiliojr94/book-to-skill) by @virgiliojr94 installed in an adjacent skill root** — this skill calls its `scripts/extract.py`, which imports the `book_to_skill` package. Alternatively, copy that repo's `scripts/` and `book_to_skill/` next to this skill.
- Optional: [Calibre](https://calibre-ebook.com/) for MOBI/AZW input

The skill preflights the extractor and fails early with a fix rather than dying mid-run.

## Install

Clone into whichever skill root your host uses:

```bash
# Claude Code
git clone https://github.com/ariel-lee-1023/books-to-skill-refs ~/.claude/skills/books-to-skill-refs

# GitHub Copilot CLI
git clone https://github.com/ariel-lee-1023/books-to-skill-refs ~/.copilot/skills/books-to-skill-refs

# Amp / agent-neutral
git clone https://github.com/ariel-lee-1023/books-to-skill-refs ~/.agents/skills/books-to-skill-refs
```

Project-local roots also work: `.github/skills/`, `.claude/skills/`, `.agents/skills/`.

Then install the extractor dependency:

```bash
git clone --depth 1 https://github.com/virgiliojr94/book-to-skill ~/.claude/skills/book-to-skill
```

## Usage

```
books-to-skill-refs <path-to-document-folder-or-glob>... [library-name-slug]
```

```bash
# Full build from a folder
books-to-skill-refs ~/books/legal-ai/ legal-ai-foundations

# Several explicit files
books-to-skill-refs ~/books/influence.pdf ~/books/thinking-fast.epub persuasion-lib

# Inspect first, write nothing
books-to-skill-refs ~/books/*.pdf   # then: "analyze only"

# Fold a new book into an existing library
books-to-skill-refs ~/books/new-title.epub legal-ai-foundations
```

### Modes

| Mode | Trigger | Behavior |
|---|---|---|
| **Full build** (default) | several source paths | Runs Steps 0–9, writes the whole library |
| **Analyze only** | "analyze" / "just extract" / "review first" | Emits a per-book extraction report, writes nothing |
| **Add a book** | a source + an existing library dir or slug | Writes one new reference file, re-indexes the master |

Before generating anything, the skill shows a per-book token and cost estimate and waits for confirmation.

## Output sizing

Budgets scale with the book, because the section template does. A reference file loads *whole* on every
consultation, so the range is a target while the cap is hard:

| | `DEPTH=reference` | `DEPTH=study` |
|---|---|---|
| Text-heavy book | ~200–350/section · 3,000–6,000 · cap 9,000 | ~400–700/section · 6,000–12,000 · cap 14,000 |
| Technical book | ~350–500/section · 4,500–9,000 · cap 12,000 | ~700–1,200/section · 9,000–18,000 · cap 20,000 |

A book over cap gets there by selection, never truncation — `SKILL.md` Step 7 states the cut order.

Master `SKILL.md` is always loaded, so its budget scales with the library: `400 + 50 × N + index (≤600)`, with a
**hard stop at 3,500**. Past that the cross-book topic index spills to a sibling `topic-index.md`; the router
table never spills. The router table is front-loaded because compaction truncates from the end.

## Tools

Two first-party tools, stdlib only — no third-party packages, nothing to install.

```bash
# What does this cost / is it inside budget?
python tools/count_tokens.py path/to/reference-*.md --budget 14000

# Does a generated library actually satisfy the contract?
python tools/validate_library.py ~/.claude/skills/my-library/
```

**`tools/count_tokens.py`** estimates tokens by script density rather than by whitespace. This matters more than
it sounds: the conventional word-split estimate (`len(text.split()) / 0.75`) undercounts space-free scripts by
orders of magnitude — a 1,080-character Chinese passage estimates as **1** token against a realistic ~720 — which
would silently defeat the pre-generation cost gate on any Chinese, Japanese, or Thai source.

**`tools/validate_library.py`** turns the "should" statements in `SKILL.md` into executable assertions against a
generated library: the directory is flat, every reference file is reachable from the router, no router link
dangles, the topic index honours the ≥2-book rule, the master is under its hard stop, and each reference file is
inside its cap for its detected type and declared depth. `ERROR` exits non-zero; `WARN` does not. Step 8.5 runs it
before reporting success.

```bash
python -m unittest discover -s tests -v
```

## Quality rules

1. Extract structure, not summaries
2. Preserve the author's exact terminology
3. Density over length — never pad
4. Front-load the most important content
5. Keep the always-loaded master lean; reference files load on demand
6. Never copy raw text — synthesize
7. The cross-book topic index is the payoff — get it right
8. `name:` slugs are lowercase letters, digits, and hyphens only

## Strict mode

For a pure structural distillation with zero cheatsheet residue, delete the `## Decision Rules & Judgment` section from the Step 7 template in `SKILL.md` and skip its bullet in the report. That is the only change needed.

## Contributing

Issues and pull requests are welcome. Most of the project is one prompt file, so please keep changes focused:
state which step you are changing and why. If you change a budget or a shape rule in `SKILL.md`, change the
matching constant in `tools/validate_library.py` and add a test — the contract and its enforcement are meant to
stay in sync. Run `python -m unittest discover -s tests` before opening a PR.

## License

MIT © 2026 Ariel Lee. [See LICENSE](LICENSE).
