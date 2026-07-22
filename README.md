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

This reuses [`book-to-skill`](https://github.com/ariel-lee-1023/book-to-skill)'s extraction engine unchanged and re-points it at a different output shape.

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
- **[`book-to-skill`](https://github.com/ariel-lee-1023/book-to-skill) installed in an adjacent skill root** — this skill calls its `scripts/extract.py`, which imports the `book_to_skill` package. Alternatively, copy that repo's `scripts/` and `book_to_skill/` next to this skill.
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
git clone --depth 1 https://github.com/ariel-lee-1023/book-to-skill ~/.claude/skills/book-to-skill
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

Per reference file (targets, not caps — density beats length):

| | `DEPTH=reference` | `DEPTH=study` |
|---|---|---|
| Text-heavy book | 2,000–3,500 tok | 3,000–5,000 tok |
| Technical book | 3,000–4,500 tok | 4,500–7,000 tok |

Master `SKILL.md`: **hard ceiling ~2,500 tokens**, router table front-loaded (compaction truncates from the end).

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

Issues and pull requests are welcome. Since the whole project is one prompt file, please keep changes focused: state which step you are changing and why, and keep the master-`SKILL.md` token ceiling intact.

## License

[MIT](LICENSE)
