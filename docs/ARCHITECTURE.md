# Architecture

Three layers, deliberately separable: a **prompt** that an agent follows, a
**runtime** that turns documents into a queryable corpus, and **tools** that
check what the prompt produced.

```
SKILL.md ............ the prompt. Steps 0-9, budgets, output contract.
scripts/extract.py .. entry point (runs without installation)
bookrefs/ ........... the extraction runtime
tools/ .............. measurement, validation, security scanning
tests/ .............. 131 stdlib unittest cases + fixtures
```

## Why the layers are split this way

The prompt states contracts; the tools enforce them. Keeping them apart is what
makes "the master must stay under 3,500 tokens" a checkable claim rather than a
hope. When a budget changes in `SKILL.md`, the matching constant in
`tools/validate_library.py` changes with it, and a test fails if they drift.

## The runtime

```
bookrefs/
├── config.py ........ the output contract: fence format, supported extensions,
│                      token constants. One file, because Steps 2.5-7 all read it.
├── tokens.py ........ token estimation by script density (canonical)
├── structure.py ..... chapter + ToC detection across scripts
├── sanitize.py ...... normalisation and the untrusted-input boundary
├── dependencies.py .. what is installed, what is missing, what to do
├── extract.py ....... orchestrator: N documents -> full_text.txt + metadata.json
├── cli.py ........... argument parsing and reporting
└── parsers/
    ├── base.py ...... ParsedDoc, encoding detection
    ├── text.py ...... .txt .md .markdown .rst .adoc     stdlib
    ├── html.py ...... .html .htm                        stdlib
    ├── docx.py ...... .docx (zip + XML)                 stdlib
    ├── epub.py ...... .epub (zip + OPF spine)           stdlib
    ├── rtf.py ....... .rtf (control-word stripping)     stdlib
    ├── pdf.py ....... .pdf                              pymupdf / pdfplumber / pypdf
    └── calibre.py ... .mobi .azw .azw3                  calibre's ebook-convert
```

Five of eight format families need nothing beyond the standard library. That is
not an accident of scope — it is what makes the project installable, testable in
CI without network access, and honest about its one real dependency (PDF).

## Three decisions worth knowing

### Token estimation segments by script, not by whitespace

The conventional estimate is `len(text.split()) / 0.75`. Chinese, Japanese and
Thai prose has no spaces, so a whole paragraph counts as one word: a measured
1,080-character Chinese passage estimates as **1** token against a realistic
~720. Every budget in `SKILL.md` and the pre-generation cost gate read this
number, so a ~700x undercount would not be a cosmetic error — it would collect
the user's approval for a run costing orders of magnitude more.

`bookrefs/tokens.py` therefore counts dense scripts at ~1 token per 1.5
characters and everything else at ~1 per 4. It is an estimate (±15% against a
real BPE tokenizer), which is well inside what round budgets like 3,500 need.

### The fence is a contract, and it is defended

`full_text.txt` concatenates every source behind a separator:

```
================================================================================
SOURCE: <filename> (Path: <path>)
================================================================================
```

This is the entire mechanism behind "one reference file per book": grep the
fences, slice between them, and each book is addressable without reading the
others. `metadata.json` also carries `start_line` / `end_line` per source, so a
caller never re-derives what it can be told.

Because a source document could contain that pattern itself — deliberately or
by accident — `sanitize.py` neutralises any `SOURCE:` line found *inside* a
document. The marker is broken, not deleted, so tampering stays visible to a
reader.

### Budgets scale with the book, and cap at loadability

A reference file loads **whole** on every consultation. That is different from a
per-chapter folder design, where a thick book costs the same per lookup as a
thin one and its budget can scale linearly. Here the budget scales with content
at the bottom (a per-section allowance, so a 30-section book is not crushed into
a 10-section budget) and is capped at the top by what is worth loading in one
go. A book over cap gets there by *selection* — `SKILL.md` Step 7 states the cut
order — never by truncation.

## Data flow

```
documents ──► parsers ──► sanitize ──► structure detection ──► tokens
                                              │                  │
                                              ▼                  ▼
                                        full_text.txt      metadata.json
                                              │                  │
                                              └────── agent ─────┘
                                                        │
                                          reference-*.md + master SKILL.md
                                                        │
                                     validate_library.py + scan_generated_skill.py
```

## Testing

`python -m unittest discover -s tests` — no third-party packages, no network.

DOCX and EPUB fixtures are **built at test time** (`tests/builders.py`) rather
than committed as binaries: the fixtures stay reviewable in a diff, and a test
can vary them — a shuffled EPUB spine, a `Heading 2` style — without anyone
regenerating a blob.

The suite covers the things that would fail silently: CJK token counts, chapter
detection across five heading dialects, fence-forgery isolation, spine ordering,
legacy Chinese encodings, and every budget constant in `SKILL.md`.
