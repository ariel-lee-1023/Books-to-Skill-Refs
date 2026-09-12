# books-to-skill-refs

> Distill **many books at once** into one working domain expert: an expert reasoning core in `SKILL.md` plus one standalone `references/reference-<book-slug>.md` per book.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/type-agent%20skill-blue.svg)](#)

An [agent skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills) for Claude Code, GitHub Copilot CLI, Amp, and other skill-aware agents.

---

## What it does

Point it at several documents (PDF, EPUB, DOCX, HTML, Markdown, plain text, RTF, MOBI/AZW) and it produces an expert skill that reasons from the sources and loads their detailed methods when needed.

```
<output-root>/<library-name>/
└── .agents/
    └── skills/
        └── <library-name>/            # matches SKILL.md frontmatter `name`
            ├── SKILL.md               # expert reasoning core + loading triggers
            └── references/
                ├── reference-<book1-slug>.md
                ├── reference-<book2-slug>.md
                └── reference-<bookN-slug>.md
```

The outer directory is a complete project that can be opened directly by a compatible agent host. The runtime skill is already in `.agents/skills/<library-name>/`, so no copying or symlink setup is required; its supporting files remain under `references/` and load on demand.

**One file per book, and they are all siblings.** No `chapters/`, no per-book subfolders inside `references/`, no separate glossary/patterns/cheatsheet files.

The master `SKILL.md` is kept small because it is *always loaded*; the reference files cost nothing until a question actually needs one.

## What the generated master reads like

The master opens as an expert, in connected first-person prose: what problems it helps solve, what it
notices first, how it decides between competing explanations or actions, what changes its judgment,
and how it works with the user. These commitments come from the books and the user's purpose.
The result should remain useful before a reference is opened, without claiming that the core contains
all the evidence needed for a detailed answer.

The shape is **expert voice first, loading instructions last**:

```markdown
# <Expert role>
<I help with ...; my starting lens is ...>

## How I read a question
<Domain-specific distinctions and reasoning in prose.>

## What changes my judgment
<Evidence, competing models, decision rules, and boundaries.>

## How I work with you
<How analysis becomes a useful response.>

---

## Loading depth (host-agent note)
| Trigger in the current task | Reference and the depth it supplies |
|---|---|
| <Concrete need> | [<Book title>](references/reference-<slug>.md) — <contribution> |
```

The core headings adapt to the domain; the `Loading depth` heading marks the host-facing boundary.
References remain one file per book and supply structure, procedures, and evidence in an expository
register. A cross-book Topic Index is optional. A supplied exemplar informs the architecture; its subject
matter and instructions are not automatically inherited. Full writing criteria and the template are in
[SKILL.md, Step 8](SKILL.md#step-8--generate-the-expert-core-then-its-loading-triggers).

## How it differs from a per-book folder skill

| | per-book folder skill | books-to-skill-refs |
|---|---|---|
| Books per run | one | **N** |
| Output per book | nested folder (`SKILL.md` + `chapters/` + `glossary.md` + `patterns.md` + `cheatsheet.md`) | **one `references/reference-<slug>.md`** |
| Shared file | that book's own `SKILL.md` | **one expert `SKILL.md`** with a shared reasoning stance and task-based loading triggers |
| Layout | one folder per book, nested inside | **project wrapper + `.agents/skills/<library-name>/`** — every book remains a sibling under `references/` |

The load-bearing disciplines: extract *structure* rather than summaries, preserve the author's exact framework names, density over length, never copy raw text, and read on demand (`grep`/`sed`/offset probes) instead of re-reading whole books.

## Folding into an existing, differently-shaped repo

When the destination already has its own skill architecture — its own core-voice file, its own module
template, its own supporting-file conventions — apply this tool's *discipline* (structure over summary,
exact terminology, density, no verbatim copying, the coverage check) rather than forcing its *output
shape* (expert `SKILL.md` + one `reference-<slug>.md` per book). Follow the destination repo's own module
template and its own extension protocol instead. See `SKILL.md` → "Folding into a pre-existing,
differently-shaped skill repo" for the full rule.

## Host-facing modules vs. human-facing documentation

A library can grow two different kinds of file: modules a host agent trigger-loads into its own voice
(`references/reference-<slug>.md`), and documentation written for the human maintaining the repo —
sourcing, fidelity notes, a staleness ledger, known gaps, the extension protocol. The two must never share
a directory. If a library needs the second kind, it lives at the project root outside `.agents/`
(for example `<library-name>/fidelity-ledger/`), never inside the runtime skill — a host must never be able to load
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
| **Add a book** | a source + an existing library dir or slug | Adds a reference and loading triggers; revises core judgments when warranted |

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
core reasoning sections + 900 shared voice/interaction + optional index (≤600)`, with a **hard stop at 4,500**. Past that the cross-book topic
index can spill to `references/topic-index.md`. The expert core comes first; the loading table stays in
the master after the core, with direct links to every source. Both tools count nonempty level-two sections
before `Loading depth` for the core allowance; legacy Capability headings still work. The coefficients are
provisional for this prose format, and the ceiling is unchanged.

## Tools

Seven first-party tools, stdlib only — nothing to install.

```bash
# preparing sources
python tools/build_corpus.py https://github.com/org/book --out corpus/book.md  # site/repo -> one file
python tools/probe_structure.py full_text.txt --source book.pdf               # where are the chapters?
python tools/clean_slice.py full_text.txt --range 4,2823 --stats-only         # what is this slice costing?

# checking output
python tools/reference_budget.py --sections 22               # what should this book cost?
python tools/reference_budget.py my-library/ # is the wrapped project inside its budgets?
python tools/validate_library.py my-library/ # .agents layout and content contract satisfied?
python tools/scan_generated_skill.py my-library/.agents/skills/my-library --strict # injected instructions?
python tools/validate_skill.py SKILL.md --lens all            # valid on every host?
python -m unittest discover -s tests -v                       # no network
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
generated project: exactly one `.agents/skills/<name>/SKILL.md` exists, its directory matches frontmatter `name`, every reference file sits inside that skill's `references/`, every reference file
is reachable from the loading table, no loading link dangles, the topic index honours the ≥2-book rule, the master is under
its hard stop, and each reference file is inside its cap for its detected type and declared depth. It accepts the new `Loading depth` table and warns on legacy book-router masters. It checks structure,
not whether the expert makes good judgments; Step 8 requires an editorial review against realistic requests
before Step 8.5 runs the tools.

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
7. Synthesize an expert’s reasoning and judgment; route to source depth by task
8. `name:` slugs are lowercase letters, digits, and hyphens only

## Strict mode

For a pure structural distillation with zero cheatsheet residue, delete the `## Decision Rules & Judgment` section from the Step 7 template in `SKILL.md` and skip its bullet in the report. That is the only change needed.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The short version: the prompt states contracts and the tools enforce them
— if you change a budget in `SKILL.md`, change the matching constant in `tools/reference_budget.py` (the single
definition, which `validate_library.py` and CI both import) and add a test. Run the suite before opening a PR.

## License

MIT © 2026 Ariel Lee. [See LICENSE](LICENSE).

## Behavioral acceptance and reading audits

Full builds now freeze representative tasks before extracting methods and compare recorded
answers from the same model under a minimal role prompt, the generated core, and core plus
references. The suite covers application, inapplicability, disagreement and unsupported questions.
`tools/acceptance_suite.py` verifies records, retrieval traces and freshness, and reports per-task
scores and added value. Add-a-book runs preserve earlier tasks as regressions.

Reading beyond four times the output budget triggers an expenditure review. The new
`tools/reading_audit.py` separates unique source coverage from repeated reading and permits
question-driven verification. Each reference also audits source material outside the initial
framework list. Formats and commands: [Behavioral acceptance](docs/BEHAVIORAL_ACCEPTANCE.md).

The optional [evaluation runner](docs/EVALUATION_RUNNER.md) now executes isolated prediction
and blind grading, records actual retrieval and token usage, and seals run records that subsequent runs do not overwrite. Version 2 suites separate development from final scenario groups; final groups
are claimed once. A fourth, targeted-retrieval condition tests addressable canonical sections
against whole-book loading, with missed qualifications reported explicitly.
