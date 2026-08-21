# books-to-skill-refs

> Distill **many books at once** into one cross-referenced knowledge library: a single master `SKILL.md` router plus one standalone `references/reference-<book-slug>.md` per book.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/type-agent%20skill-blue.svg)](#)

An [agent skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills) for Claude Code, GitHub Copilot CLI, Amp, and other skill-aware agents.

---

## What it does

Point it at several documents (PDF, EPUB, DOCX, HTML, Markdown, plain text, RTF, MOBI/AZW) and it produces a knowledge base your agent can route across — not book reports.

```
$SKILLS_HOME/<library-name>/
├── SKILL.md                           # master: router + library index + cross-book topic index
└── references/
    ├── reference-<book1-slug>.md      # dense standalone distillation of book 1
    ├── reference-<book2-slug>.md      # dense standalone distillation of book 2
    └── reference-<bookN-slug>.md
```

That is the standard [Agent Skills](https://docs.claude.com/en/docs/agents-and-tools/agent-skills) layout: `SKILL.md` at the root — the only file a host loads automatically — with supporting files under `references/`, loaded on demand.

**One file per book, and they are all siblings.** No `chapters/`, no per-book subfolders inside `references/`, no separate glossary/patterns/cheatsheet files.

The master `SKILL.md` is kept small because it is *always loaded*; the reference files cost nothing until a question actually needs one.

## How it differs from a per-book folder skill

| | per-book folder skill | books-to-skill-refs |
|---|---|---|
| Books per run | one | **N** |
| Output per book | nested folder (`SKILL.md` + `chapters/` + `glossary.md` + `patterns.md` + `cheatsheet.md`) | **one `references/reference-<slug>.md`** |
| Shared file | that book's own `SKILL.md` | **one master `SKILL.md`** routing across all books |
| Layout | one folder per book, nested inside | **`SKILL.md` + `references/`** — every book a sibling in one directory |

The load-bearing disciplines: extract *structure* rather than summaries, preserve the author's exact framework names, density over length, never copy raw text, and read on demand (`grep`/`sed`/offset probes) instead of re-reading whole books.

## Folding into an existing, differently-shaped repo

When the destination already has its own skill architecture — its own core-voice file, its own module
template, its own supporting-file conventions — apply this tool's *discipline* (structure over summary,
exact terminology, density, no verbatim copying, the coverage check) rather than forcing its *output
shape* (router `SKILL.md` + one `reference-<slug>.md` per book). Follow the destination repo's own module
template and its own extension protocol instead. See `SKILL.md` → "Folding into a pre-existing,
differently-shaped skill repo" for the full rule.

## Host-facing modules vs. human-facing documentation

A library can grow two different kinds of file: modules a host agent trigger-loads into its own voice
(`references/reference-<slug>.md`), and documentation written for the human maintaining the repo —
sourcing, fidelity notes, a staleness ledger, known gaps, the extension protocol. The two must never share
a directory. If a library needs the second kind, it lives in a sibling directory to the modules directory
(for example `fidelity-ledger/` beside `references/`), never inside it — a host must never be able to load
maintainer documentation as if it were skill content. See `SKILL.md` → "Host-facing modules vs.
human-facing documentation" for the full rule and the one-question test.

## Requirements

- A skill-aware agent (Claude Code, Copilot CLI, Amp, …)
- **Python 3.10+** on `PATH`

That is the whole list. **No third-party packages are required and no companion skill needs installing** — the extraction runtime ships with this repository, and text, HTML, DOCX, EPUB and RTF are handled with the Python standard library alone.

Two format families need something extra, and only if you use them:

| Format | Needs | Install |
|---|---|---|
| `.pdf` | a PDF backend | `pip install pypdf` (or `pymupdf` / `pdfplumber` for layout-aware extraction) |
| `.mobi` `.azw` `.azw3` | calibre's `ebook-convert` | `brew install --cask calibre`, or [calibre-ebook.com](https://calibre-ebook.com/download) |

Check what your machine can handle:

```bash
python scripts/extract.py --check
```

The skill runs this as a preflight and fails early with a remedy rather than dying mid-run — and it only complains about formats your batch actually contains.

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

Nothing else to install.

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

A reference file loads *whole* on every consultation, so what it weighs is what every future question about
that book costs. The budget is **computed, not looked up** — `tools/reference_budget.py` is the single
definition, and `validate_library.py` and CI measure against the same function.

```
scaffold = 2,250 study | 1,700 reference        # reference drops the Worked Example
body     = (1,050 + 1,500 × √n_sections) × depth_factor × type_factor
             depth: study 1.00 · reference 0.55    type: text 1.00 · technical 1.45
budget   = scaffold + body                      # a target, ±10% — never a floor
cap      = budget at 50 sections, rounded up to the next 500
```

| | `DEPTH=reference` | `DEPTH=study` |
|---|---|---|
| Text-heavy book | cap **8,500** | cap **14,000** |
| Technical book | cap **11,000** | cap **19,500** |

**Why this form.** Deciding what to measure came first, and everything else follows from it. `n_sections` is
the book's own top-level structure, read off the table of contents before a line of the file exists — not the
number of blocks the writer ends up producing, because the remedy for a book projecting over budget is to merge
thin sections until it fits, so a budget priced on blocks written is one its own remedy dissolves, and a
quantity that moves when you apply the control cannot be the input that sets it. The measurement agrees: across
a five-book library, blocks written spanned 7.3× while the finished files spanned 1.36×, and the book's own
section count predicts file size at r = +0.85 against +0.53 for blocks written.

The functional form is a claim about the material rather than a matter of taste. Cost per section *falls* as a
book thickens — 462 tokens per section at eleven sections, 287 at twenty-five — because a thick book gets
merged and compressed instead of paid for chapter by chapter, so the response has to be concave, and a linear
allowance over-budgets a thick book by roughly 60% in the one direction that produces bloat and collides with
the cap. A square root is the plainest concavity consistent with that measurement and adds nothing to tune. The
rest of the model is deliberately thin: `Frameworks & Structure` is 72–77% of a finished file and carries
nearly all of its variance while everything else measured near-constant, so the formula is a constant plus a
single term — a coefficient with nothing varying underneath it is a knob that can only be turned wrong.

The cap answers a different question from the budget — not what this book supports, but what a reader will
afford in one load — so it is applied to the estimate afterwards instead of folded into it, and a book over it
comes back down by selection, never truncation (`SKILL.md` Step 7 states the cut order). What gets checked
after writing is density rather than length, 50–70 tokens per retained named item, so a thin book that lands
under budget with full coverage passes and a padded one that hit its number does not.

Fitted against five hand-written reference files from a single library, all `study`/`text`: mean 4.9%, max
8.7%. The `reference` and `technical` multipliers are back-solved from the midpoints of the table this replaces
rather than fitted, since no data exists for those three cells — treat the structure as settled and the
constants as provisional.

Master `SKILL.md` is always loaded, so its budget scales with the library: `300 + 75 × N books + 350 × C
capability blocks + 900 protocol + index (≤600)`, with a **hard stop at 4,500**. Past that the cross-book topic
index spills to a sibling `topic-index.md`; the router table never spills, and it is front-loaded because
compaction truncates from the end.

## Tools

Seven first-party tools, stdlib only — nothing to install.

```bash
# preparing sources
python tools/build_corpus.py https://github.com/org/book --out corpus/book.md  # site/repo -> one file
python tools/probe_structure.py full_text.txt --source book.pdf               # where are the chapters?
python tools/clean_slice.py full_text.txt --range 4,2823 --stats-only         # what is this slice costing?

# checking output
python tools/reference_budget.py --sections 22               # what should this book cost?
python tools/reference_budget.py ~/.claude/skills/my-library/ # is the library inside its budgets?
python tools/validate_library.py ~/.claude/skills/my-library/ # contract satisfied?
python tools/scan_generated_skill.py my-library --strict      # injected instructions?
python tools/validate_skill.py SKILL.md --lens all            # valid on every host?
python -m unittest discover -s tests -v                       # 205 tests, no network
```

**`build_corpus.py`** exists because `extract.py` emits one `SOURCE:` fence per *file*, so a book that arrives as
a 51-page documentation site would otherwise become 51 "books". It consolidates one source into one file in the
order the project declares — `_toc.yml`, or `index.rst` toctrees **followed recursively**, since they nest and a
flat read of the root reached 19% of a real 287-page source against the recursive walk's 92%. Always `--dry-run`
first and check the part list against the book's table of contents.

**`probe_structure.py`** finds chapters that heading-dialect detection cannot see. Converted academic PDFs mark
chapters with a publisher DOI suffix, an `Abstract` block, or `11.2 SECTION TITLE` rather than "Chapter 7";
across ten mixed sources the canonical count was right once. Six strategies run and are scored — but it is a
probe, not a detector: a run of prose cross-references scores well too, so verify before slicing.

**`clean_slice.py`** removes what a slice costs without teaching anything — page markers, `Link:` runs, rST
directives, site navigation, quiz blocks that repeat every option once per answer (~250 of 460 lines on one
measured chapter). Run it on a copy of a span, never on `full_text.txt`: parsers preserve `#` headings and pipe
rows because `structure.py` and the Step 3 tripwire read them.

**`count_tokens.py`** estimates tokens by script density rather than by whitespace. This matters more than it
sounds: the conventional word-split estimate (`len(text.split()) / 0.75`) undercounts space-free scripts by orders
of magnitude — a 1,080-character Chinese passage estimates as **1** token against a realistic ~720 — which would
silently defeat the pre-generation cost gate on any Chinese, Japanese, or Thai source.

**`validate_library.py`** turns the "should" statements in `SKILL.md` into executable assertions against a
generated library: `SKILL.md` sits at the root with every reference file inside `references/`, every reference file
is reachable from the router, no router link dangles, the topic index honours the ≥2-book rule, the master is under
its hard stop, and each reference file is inside its cap for its detected type and declared depth. Step 8.5 runs it
before reporting success.

**`scan_generated_skill.py`** scans a generated library for instructions aimed at the reading agent. This skill
reads documents it did not author and writes files a host agent later loads *as instructions* — a laundering path
that nothing else in the pipeline closes. See [SECURITY.md](SECURITY.md).

**`validate_skill.py`** audits a `SKILL.md` under a `--lens` of `claude`, `copilot` or `amp`, so this project's
cross-agent compatibility claim is checked rather than asserted.

Architecture and design rationale: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

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

See [CONTRIBUTING.md](CONTRIBUTING.md). The short version: the prompt states contracts and the tools enforce them
— if you change a budget in `SKILL.md`, change the matching constant in `tools/reference_budget.py` (the single
definition, which `validate_library.py` and CI both import) and add a test. Run the suite before opening a PR.

## License

MIT © 2026 Ariel Lee. [See LICENSE](LICENSE).
