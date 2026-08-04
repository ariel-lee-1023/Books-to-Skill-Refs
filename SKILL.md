---
name: books-to-skill-refs
description: "Distills MULTIPLE books/documents (PDF, EPUB, DOCX, HTML, Markdown, plain text, RTF, MOBI/AZW with Calibre) in one run into a flat knowledge library: one master SKILL.md that indexes and routes across all sources, plus one standalone reference-<book-slug>.md per book. Same extraction discipline as book-to-skill (structure over summary, author's own terminology, density over length, never copy raw text), but a flat multi-book output instead of a single-book nested folder. Use when the user points at several sources at once and wants a shared, cross-referenced knowledge base rather than a per-book folder skill."
---

<!--
Cross-agent notes (informational; ignored by host agents):
  - Compatible skill roots: GitHub Copilot CLI (~/.copilot/skills, ~/.agents/skills,
    .github/skills, .claude/skills, .agents/skills), Amp (.agents/skills,
    ~/.config/agents/skills, ~/.config/amp/skills), Claude Code (~/.claude/skills).
  - `allowed-tools` is intentionally omitted to stay agent-neutral. The skill needs
    shell (to run extract.py) and file read/write; each host prompts on first use.
  - Argument hint: <path-to-document-folder-or-glob>... [library-name-slug]
  - Extraction engine is book-to-skill's by @virgiliojr94 (MIT), reused unchanged (see Step 2).
-->

# Books-to-Skill&Refs (multi-book, flat library)

Distill several books at once into one shared, cross-referenced library — **not** a book report, and **not** one folder per book.

## What this is — and how it differs from book-to-skill

This is the engine from [`book-to-skill`](https://github.com/virgiliojr94/book-to-skill) by
@virgiliojr94 (MIT), re-pointed at a different output shape. The reading
and extraction discipline is identical and load-bearing; only the shape of what we
write to disk changes. So you don't have to reverse-engineer it from a diff:

| | book-to-skill (original) | books-to-skill-refs (this) |
|---|---|---|
| Books per run | one | **N** |
| Output per book | a nested folder: `SKILL.md` + `chapters/` + `glossary.md` + `patterns.md` + `cheatsheet.md` | **one flat file:** `reference-<book-slug>.md` |
| Shared file | that book's `SKILL.md` indexes its own chapters | **one master `SKILL.md`** indexes/routes across all books |
| Directory | per-book folder nesting | **all files siblings in one flat dir** |
| Chapters split into `chapters/*.md` | yes | **no** — folded into the one reference file |
| `glossary` / `patterns` / `cheatsheet` as separate files | yes | **no** — see "What survives the collapse" |

**What carries over unchanged (this is the actually load-bearing part):**
- **Extraction discipline** — extract *structure*, not summaries; preserve the
  author's exact terminology and framework names; **density over length**;
  front-load the most important content; **never copy raw text verbatim** — synthesize.
- **Reading method** — targeted, on-demand extraction from each source (grep/sed/offset
  probes into `full_text.txt`), never a full re-read per section. This is the token-cost
  logic that makes the whole approach worth using (Step 2.6).

**What survives the collapse of the three cross-cutting files (one judgment call):**
The original's `glossary.md` / `patterns.md` / `cheatsheet.md` were *cross-cutting scaffolding for the folder design*. Dropping them as separate files is correct. But their content isn't equally disposable:
- **Glossary** → dissolved inline: define each key term where it first appears in the reference file. No separate alphabetized dump.
- **Patterns** → dissolved into each book's structural sections; techniques were never separable from structure.
- **Cheatsheet's decision rules** → **kept**, as a short `## Decision Rules & Judgment` tail *inside each reference file*. This was the original's "most differentiated layer" (the author's judgment, not just their vocabulary), it is **per-book** so it maps cleanly onto parallel files (your objection was to *cross-cutting* files, and this isn't one), and it's cheap.
  - **Switch to strict mode:** if you want a pure structural distillation with zero cheatsheet residue, delete the `## Decision Rules & Judgment` section from the Step 7 template and skip its bullet in the report. That's the only change needed.

---

## Output contract (the flat shape, explicit)

```
$SKILLS_HOME/<library-name>/
├── SKILL.md                       # master: router + library index + cross-book topic index
├── reference-<book1-slug>.md      # dense standalone distillation of book 1
├── reference-<book2-slug>.md      # dense standalone distillation of book 2
├── reference-<bookN-slug>.md
└── topic-index.md                 # ONLY if the master overflows its budget (Step 8 valve)
```

No `chapters/`. No `glossary.md`, `patterns.md`, `cheatsheet.md`. No per-book subfolders. Every file is a sibling.

---

## Modes of operation

1. **Full build (default)** — user gives several source paths/dirs/globs. Run Steps 0–9.
2. **Analyze only** — user says "analyze"/"just extract"/"review first". Run Steps 0–3 per book, emit an extraction report, stop. Write nothing.
3. **Add a book (fold-in)** — user points at a new source and an existing library dir (or a slug that already exists in `SKILLS_HOME`). Extract the new source, write **one new `reference-<slug>.md`**, and re-index the master `SKILL.md`. See the Fold-in Workflow. (No chapter renumbering exists here — a new book is just a new sibling file, which is why fold-in is simpler than the original's.)

---

## Skill locations

Prefer these roots when finding the extractor or writing the library (probe in order):
`~/.copilot/skills/` → `~/.agents/skills/` → `~/.claude/skills/` → `.github/skills/` → `.claude/skills/` → `.agents/skills/` → `~/.config/agents/skills/` → `~/.config/amp/skills/`.
When more than one valid root exists, ask the user once and remember it for the session — do not silently default.

---

## Step 0 — Out-of-scope check

If no arguments are provided, stop and respond:
> "books-to-skill-refs requires one or more supported document paths, folders, or globs. Usage: `books-to-skill-refs <path>... [library-name-slug]`"

- Parse args into `INPUT_PATHS` and an optional trailing `LIBRARY_NAME` slug (lowercase-hyphen token that is not an existing file/glob).
- If any input path is an existing library dir (a flat dir containing `SKILL.md` and `reference-*.md`), or `LIBRARY_NAME` matches an existing library slug, flag this as **Add a book (Mode 3)**.

---

## Step 1 — Validate input

Verify at least one supported file among `INPUT_PATHS`. Expand directories/globs to supported files
(`.pdf .epub .docx .txt .md .markdown .rst .adoc .html .htm .rtf .mobi .azw .azw3`). If none found, stop with a clear error.

Unlike the original, expect and keep **multiple** sources — each becomes its own reference file.

**Preflight the extractor NOW, before asking the user anything else.** The extractor is a hard dependency
(Step 2 dies without it), so fail here with a fix rather than after the user has answered content-type/purpose:

```bash
# Reuse the Step 2 discovery block to set SCRIPT_PATH, then:
if [ -z "$SCRIPT_PATH" ]; then
  cat >&2 <<'MSG'
✗ books-to-skill-refs needs book-to-skill's extractor and it isn't installed.
  Bootstrap it into an adjacent skill root (pick the one your host uses), e.g.:

    DEST="$HOME/.claude/skills/book-to-skill"      # or ~/.copilot/skills, ~/.agents/skills
    git clone --depth 1 https://github.com/virgiliojr94/book-to-skill "$DEST"

  Or copy book-to-skill's scripts/ and book_to_skill/ next to this skill. Then re-run.
MSG
  exit 1
fi
"$PYTHON_BIN" "$SCRIPT_PATH" --check   # prints which per-format extractors are present/missing
```

If `--check` reports the extractor missing packages for a format you're about to process, surface that now too — don't discover it mid-generation.

---

## Step 1.5 — Identify content type

Ask once (applies to the whole batch):
> "What kind of content is in these sources?
> 1. **Technical** — code, tables, formulas, diagrams
> 2. **Text-heavy** — mostly prose
> 3. **Not sure** — I'll use the fast method and warn if quality seems limited"

Store `BOOK_TYPE`: option 1 → `technical`; options 2/3 → `text`.
If sources are genuinely mixed, you may set `BOOK_TYPE` per source in Step 3; default to the batch answer.

- `technical` → "📐 Technical mode — Docling, structure-aware (tables/code/formulas preserved). ~1.5s/page."
- `text` → "📄 Text mode — fastest suitable extractor per file type."

---

## Step 2 — Extract text (reuse book-to-skill's engine, unchanged)

The extractor is book-to-skill's `extract.py`. It **already** accepts multiple inputs, combines them into one
`full_text.txt` with a hard per-source fence, and writes a per-source `metadata.json`. Do not rewrite it.

```bash
SCRIPT_PATH=""
for candidate in \
  "$HOME/.copilot/skills/books-to-skill-refs/scripts/extract.py" \
  "$HOME/.claude/skills/books-to-skill-refs/scripts/extract.py" \
  "$HOME/.agents/skills/books-to-skill-refs/scripts/extract.py" \
  "$HOME/.copilot/skills/book-to-skill/scripts/extract.py" \
  "$HOME/.agents/skills/book-to-skill/scripts/extract.py" \
  "$HOME/.claude/skills/book-to-skill/scripts/extract.py" \
  ".github/skills/book-to-skill/scripts/extract.py" \
  ".claude/skills/book-to-skill/scripts/extract.py" \
  ".agents/skills/book-to-skill/scripts/extract.py"
do
  [ -f "$candidate" ] && { SCRIPT_PATH="$candidate"; break; }
done
[ -z "$SCRIPT_PATH" ] && { echo "Could not find extract.py (install book-to-skill alongside, or bundle its scripts/ + book_to_skill/ package here)" >&2; exit 1; }

PYTHON_BIN="${PYTHON_BIN:-python3}"; command -v "$PYTHON_BIN" >/dev/null 2>&1 || PYTHON_BIN="python"
"$PYTHON_BIN" "$SCRIPT_PATH" $INPUT_PATHS --mode <BOOK_TYPE> --install-missing ask
```

**Dependency note:** `extract.py` is a thin wrapper that imports the `book_to_skill` package, so it needs that
package on disk. Simplest install: have book-to-skill installed in an adjacent skill root (the discovery block
above finds it), or copy book-to-skill's `scripts/` and `book_to_skill/` into this skill's folder.

This writes:
- `<tempdir>/book_skill_work/full_text.txt` — all sources concatenated, each preceded by a fence:
  ```
  ================================================================================
  SOURCE: <filename> (Path: <path>)
  ================================================================================
  ```
- `<tempdir>/book_skill_work/metadata.json` — `total_sources`, and a `sources[]` list where each entry has
  `filename, format, pages, words, chars, estimated_tokens, chapters_detected, has_toc`.

**This fence is how you slice per book.** `grep -n "^SOURCE: " full_text.txt` gives each book's start line; the
next fence (or EOF) is its end. That is the entire mechanism behind "one reference file per book."

---

## Step 2.5 — Per-book cost estimate (before generating anything)

Read `metadata.json`. Present a per-book table so the user sees where the cost is:

```
📚 Library: <total_sources> book(s)
  <filename> — <format>, ~<pages>p, ~<estimated_tokens/1000>K tok
  ...
📄 Combined tokens: ~<sum>K

💰 Estimated cost (Full build):
   Input  (reading + prompts): ~<sum(estimated_tokens)*1.3>K
   Output (1 reference/book + 1 master): ~<Σ per-book budget + master (400 + 50×N + index)>K
   Total: ~<N>K   (Sonnet ~$X · Haiku ~$X)
   ⏱ ~<N> min

📁 To be generated: <total_sources> reference file(s) + 1 master SKILL.md
➡ Proceed? (or "analyze only")
```

Per-book output budget uses the Step 7 matrix — take the **book range** midpoint scaled by that book's detected
section count, not a flat per-book constant. Prices (2025 ref): Sonnet in $3 / out $15 per MTok; Haiku in $0.80 /
out $4. Wait for confirmation. "analyze only" → Mode 2.

---

## Step 2.6 — Sliced reading (unconditional) — CARRIED OVER, load-bearing

Treat `full_text.txt` as a queryable corpus, never one big `Read`. **No size threshold applies here.** The
original's ">50k tokens" rule assumed one book per file; ours is N books concatenated, so a full read always
pulls in the N−1 books you are not currently writing about. A full `Read` of `full_text.txt` is wrong at every
size. This is the token-cost logic that justifies the whole approach — do not skip it.

```bash
grep -n "^SOURCE: " "$FULL_TEXT_PATH"                      # per-book boundaries — RUN ONCE, in Step 2
grep -n -E "^\s*(Chapter|CHAPTER)\s+[0-9]+" "$FULL_TEXT_PATH" | head -60   # chapter offsets
sed -n '<start>,<end>p' "$FULL_TEXT_PATH"                  # pull only the slice you need
grep -c -i "westrum\|dora" "$FULL_TEXT_PATH"               # verify a framework exists before claiming it
```

**Compute the `SOURCE:` fence boundaries once, in Step 2, and reuse them** in Steps 3 and 7. Do not re-grep the
whole file per section.

**Input budget per book (the anti-waste gate):** cumulative reading from a book's slice should stay **≲ 4× that
book's reference-file output budget** (Step 7). Going over means you are re-reading. The intended shape is one
pass: probe (TOC / chapter offsets / framework keywords) → decide the full section list up front → read each
section slice **exactly once** → write. Never `sed` a range you have already read.

Use targeted `Read(offset,limit)` slices, not unbounded reads. Re-reading a 200-page book once per section costs
millions of input tokens; grep+sed keeps cost proportional to output.

---

## Step 3 — Analyze structure, per book (the loop begins)

For **each** source (bounded by its `SOURCE:` fence), read the first ~8,000 chars of its slice to identify:
title, author(s), chapter/section structure, core themes, approximate chapter count. Read its TOC if present.

**Misclassification tripwire (when `BOOK_TYPE=text`, including the "not sure" path):** a book routed through the
fast extractor that is actually technical will silently lose code/tables/formulas — the exact thing Quality Rule #2
says to preserve. So before generating, probe each book's slice for technical signals:

```bash
# Probe this book's fence range [start,end]. Two CLEAN signals only — indented code
# and pipe-tables. (Keyword matching like "def/class/return" was tested and dropped:
# it false-fires on prose — "a class of problems", "a return to" — and under-fires on
# real code.) -E + POSIX classes so it works on BSD grep (macOS default), not just GNU.
SLICE=$(sed -n "${start},${end}p" "$FULL_TEXT_PATH")
TOTAL=$(printf '%s\n' "$SLICE"  | grep -c '')
INDENT=$(printf '%s\n' "$SLICE" | grep -cE '^[[:space:]]{4,}[^[:space:]]')   # code blocks
TABLES=$(printf '%s\n' "$SLICE" | grep -cE '\|[^|]+\|[^|]+\|')               # pipe-tables
# STRUCT = INDENT + TABLES ; on a tested prose slice STRUCT=0, on a technical slice it was ~half the lines
```

If a "text"-mode book shows a **clear presence** of these structural lines (prose scores ~0; a technical chapter
scores many), **warn and offer to re-extract just that book in technical mode** rather than proceeding silently:
> "⚠️ '<title>' was extracted in text mode but looks technical (~<INDENT> indented code blocks, ~<TABLES> tables).
> The fast extractor may have dropped structure. Re-extract this one with `--mode technical`, or proceed as-is?"
**Honest note on the cutoff:** a good starting trigger is "structural lines are a nonzero, non-trivial fraction of
the slice" — e.g. `STRUCT` more than a handful, or `STRUCT/TOTAL` above ~10%. These signals separate prose from
technical cleanly in testing, but the exact cutoff should be tuned on your own corpus; don't treat a fixed number
as calibrated when it isn't. One indented quote in a prose book is not "technical" — it's the *density* that matters.

**Mode 2 (Analyze only):** emit this per book, then stop (write nothing):
```
## Extraction Report — <Title> (<filename>)
### Core Frameworks — **<Name>**: <what it is / when to apply>
### Key Principles — <principle>: <actionable rule>
### Techniques — <technique>: <how-to>
### Anti-patterns — <what to avoid>: <why>
### Suggested reference slug — reference-<author-lastname>-<concept>.md
### Sections detected — | # | Title | Main frameworks |
```

---

## Step 4 — Ask purpose (Full build only)

> "What should this library help you do? 1) Apply frameworks while working 2) Think with the authors' models 3) Reference specific concepts 4) All of the above"

Derive `DEPTH`: only option 3 → `DEPTH=reference` (lean, lookup-oriented). Anything including 1/2/4 → `DEPTH=study` (worked detail + reasoning). `DEPTH` applies library-wide unless the user asks otherwise. In Mode 2/3, default `DEPTH=study`.

---

## Step 5 — Library name, destination, and per-book slugs

- **`LIBRARY_NAME`**: use the provided slug, else propose two and let the user pick — a theme slug
  (`legal-ai-foundations`) or a concatenation of authors/topics. Must be a valid slug (see Quality Rules).
- **`SKILLS_HOME`**: pick the destination root by the host the user is in (Copilot CLI → `~/.copilot/skills`;
  Amp → `~/.agents/skills`/`~/.config/...`; Claude Code → `~/.claude/skills`). If exactly one candidate root
  exists, use it; if none, ask; if the user asked for project-local, use the project row. If `<library-name>/`
  already exists, offer Add-a-book (Mode 3), Overwrite, or Rename.
- **Per-book slug** (for each source): `<author-lastname>-<core-concept>` if the book has a strong
  methodological identity, else a title slug. File name is `reference-<book-slug>.md`.
  **On collision, disambiguate by meaning, not by a number.** Two books on the same concept →
  prefix each with its author (`reference-cialdini-influence.md` vs `reference-carnegie-influence.md`),
  not `influence` and `influence-2`. Append `-2` only if author+concept *still* collides (same author, same
  concept). Whatever the slug, the router table's "Book (→ file)" column shows the full human-readable title,
  so the slug never has to carry the whole disambiguation load alone.

---

## Step 6 — Create the flat directory

```bash
mkdir -p "$SKILLS_HOME/<library-name>"     # flat — NO chapters/ subfolder
```

---

## Step 7 — Generate one reference file per book (the core loop)

**For each source**, write a single dense `$SKILLS_HOME/<library-name>/reference-<book-slug>.md`. This one file
absorbs what the original spread across `chapters/` + glossary + patterns + cheatsheet — compressed, because it's
now one flat file, not a folder.

### Per-reference-file budget

**Why this differs from book-to-skill's per-chapter matrix.** Upstream's `chapters/ch07.md` is *individually*
loadable, so a thick book costs the same per consultation as a thin one and its budget can scale linearly with
chapter count. Our flat design's load granularity is **the whole book**: whatever this file weighs is what every
consultation of that book pays. So the budget scales with content at the bottom and is **capped by
loadability** at the top.

| | `DEPTH=reference` | `DEPTH=study` |
|---|---|---|
| `BOOK_TYPE=text` | ~200–350 tok/section · book 3,000–6,000 · **cap 9,000** | ~400–700 tok/section · book 6,000–12,000 · **cap 14,000** |
| `BOOK_TYPE=technical` | ~350–500 tok/section · book 4,500–9,000 · **cap 12,000** | ~700–1,200 tok/section · book 9,000–18,000 · **cap 20,000** |

- **Per-section allowance sets the shape** — it is what keeps a 30-section book from being crushed into the same
  budget as a 10-section one. (Calibration: upstream measures its *full* chapter template at 700–900 tok of dense
  prose; the section block below is a subset of it, which lands ~150–250 at the terse end.)
- **The book range is a target, not a floor** — a thin book legitimately lands under it. Density beats length;
  never pad to hit a number.
- **The cap is hard**, because it is the price of a single consultation. A book over cap gets there by
  *selection*, never by truncation — see the cut order below.

**When a book projects over cap, cut in this order:**
1. Drop to `reference` depth for this book — delete the Worked Example.
2. Merge adjacent thin sections into one block. The book's structure is the spine, but not every chapter earns
   its own block.
3. In minor sections, keep Core idea + framework names only; drop their anti-patterns.
4. **Never cut:** a framework's exact name and formulation (Quality Rule #2), or `## Decision Rules & Judgment`.
5. Still over (a 600-page technical reference — rare)? **Stop and ask the user:** split into sibling
   `reference-<slug>-part1.md` / `-part2.md`, or use book-to-skill's folder design for that one book. This is a
   real edge of the flat design; say so rather than silently degrading the distillation.

**Coverage check before moving on (acceptance is coverage, not length).** Step 3 produced a framework / principle
/ technique list for this book. Every item on it must either appear in the reference file, or be **explicitly
recorded as dropped, with a reason** ("minor variant, folded into X"). No silent omissions. Satisfy coverage
first, then compress toward the range.

**Reading:** use Step 2.6 probes against this book's slice (`SOURCE:` fence → next fence), within the 4× input
budget. Do not load other books.

**Study-depth worked example scales to the book, not the section:** reproduce **one** worked example for the whole
reference file (the single most instructive artifact the author walks through) — not one per chapter. Reconstruct it
compactly; never copy long raw passages. Reference-depth omits worked examples entirely.

**Reference file template:**

```markdown
# <Full Title> — <Author(s)>
**Format**: <pdf/epub/…> | **Pages**: ~<N> | **Sections**: <N> | **Depth**: <reference|study>

## Mental Model (read first)
<2–4 sentences: how this author thinks and the one thing to take from the whole book.>

## Frameworks & Structure
<!-- The book's own structure is the spine. One compact block per chapter/major section.
     Preserve exact framework names. Define key terms inline on first use (this replaces
     the glossary). Fold techniques/patterns in here as "How:" steps (this replaces patterns.md). -->
### <Section / Chapter N: Title>
- **Core idea**: <1 sentence>
- **<Framework Name>** — <exact formulation>. When: <situation>. How: <steps/criteria>.
- **<Term>**: <one-sentence definition>   ← inline glossary
- **Anti-pattern** — <what to avoid>: <why it fails>
(repeat per section; front-load the most important sections)

## Worked Example  *(DEPTH=study only — one for the whole book; omit for reference)*
<One concrete example the author works end-to-end, reconstructed compactly. Never raw-copied.>

## Decision Rules & Judgment
<!-- The surviving essence of the original cheatsheet: the author's if/then judgment,
     stated so a reader can act without re-reading. Compact rules and tables only —
     no bare term→definition rows (those are inline above). Every line helps DECIDE.
     STRICT-MODE SWITCH: delete this whole section for a pure structural distillation. -->
- When <X>, do <Y>, because <Z>.
- <threshold / default / tell-and-smell the author commits to>

## Key Takeaways
1. <actionable> 2. <actionable> 3. <actionable>   (3–7 a practitioner must remember)
```

---

## Step 8 — Generate the master SKILL.md (router across all books)

Write `$SKILLS_HOME/<library-name>/SKILL.md` **once, at the end**. It plays the role the original SKILL.md played,
but it indexes N reference files instead of one chapter set. **It is a router, not a knowledge dump** — the knowledge
lives in the reference files (loaded on demand). Keep it small; it is always loaded and grows with the library.

**CRITICAL: keep the body within the scaling budget below and front-load the router table** — compaction truncates
from the end.

**Master budget scales with book count** (it must: the router table is inherently O(N)):

```
budget ≈ 400 (frontmatter + How to use + Scope)
       +  50 × N (one router row per book)
       + topic index (~15/entry, ≤600)
       —— hard stop at 3,500 ——
```

Reference points: N=10 → ~1,500; N=20 → ~1,900; N=40 → ~2,800. **Overflow valve:** past 3,500, move the whole
Cross-book Topic Index into a sibling `topic-index.md` (loaded on demand) and leave a one-line pointer here. The
**router table never spills** — it is the only thing that lets an agent find a file at all. Past ~30 books, also
group the router table by theme (a subheading per theme, one row per book inside) so reading it becomes
"pick a theme, then a book" instead of scanning N rows.

**Router only, never a knowledge dump.** Upstream's SKILL.md carries a ~2,000-token "core frameworks" block; that
works for one book and breaks for N, where any such selection is arbitrary. The knowledge lives in the reference
files.

```markdown
---
name: <library-name>
description: "Knowledge library across <N> sources: <book1 short>, <book2 short>, …. Use to apply or cross-reference their frameworks on <3–6 shared topics>. Each book has its own reference-<slug>.md, loaded on demand."
---

<!-- argument-hint: [topic, framework name, or book] -->

# <Library Title>
**Books**: <N> | **Generated**: <YYYY-MM-DD> | **Depth**: <reference|study>

## How to use
- No args → read this router, pick the right book.
- "about <topic>" → use the Topic Index to open the reference file(s) that cover it.
- "<book name>" → open that `reference-<slug>.md`.

## Which book for which job  (front-loaded router — the most important section)
| Book (→ file) | Reach for it when you need… | Its one big idea |
|---|---|---|
| <Title> → [reference-<slug>.md](reference-<slug>.md) | <the kind of question it answers> | <one line> |
| … | | |

## Cross-book Topic Index
<!-- Alphabetical. Term/framework → which book(s) cover it.
     RULE (bounds the size AND sharpens the purpose): list a term ONLY if it spans
     ≥2 books. This index exists for cross-book routing; a term in just one book is
     already reachable via that book's router row, so it stays in the reference file,
     not here. CEILING ~40 entries / ~600 tokens. If it still overflows, keep the
     terms shared by the MOST books and end with "(more in individual reference files)";
     once the whole master passes the 3,500 hard stop, move this section wholesale into a
     sibling topic-index.md and leave a one-line pointer in its place. -->
- **<Term/Framework>** → <slug>, <slug2>
- **<Term>** → <slug1>, <slug3>

## Scope & limits
Covers these sources only. For a topic no book here addresses, say so rather than inventing it.
```

**The 3,500 hard stop is a ceiling, not a wish** — this body is always loaded, in every session. Near the limit,
cut in this order: (1) trim the Topic Index per the ≥2-book rule above, (2) shorten the "one big idea" column to a
phrase, (3) spill the Topic Index to `topic-index.md`, (4) group the router table by theme. **Never cut the router
table's file links** — those are load-bearing.

---

## Step 9 — Cleanup and report

```bash
PYTHON_BIN="${PYTHON_BIN:-python3}"; command -v "$PYTHON_BIN" >/dev/null 2>&1 || PYTHON_BIN="python"
"$PYTHON_BIN" - <<'PY'
import os, shutil, tempfile
from pathlib import Path
shutil.rmtree(os.environ.get("BOOK_SKILL_WORKDIR", Path(tempfile.gettempdir())/"book_skill_work"), ignore_errors=True)
PY
```

Report:
```
✅ Library created: $SKILLS_HOME/<library-name>/

📚 <N> books distilled:
   reference-<slug1>.md  — <Title1>   (~X tok)
   reference-<slug2>.md  — <Title2>   (~X tok)
   ...
   SKILL.md              — router + topic index (~X tok, always loaded)
   ────────────────────────────────────────────
   Reference files load on demand — only the master is always in context.

Usage:
   Ask for <library-name>              → router
   Ask <library-name> about <topic>    → find the right book(s)
   Ask <library-name> for <book>       → open that reference file
```

---

## Fold-in Workflow (Mode 3 — add a book to an existing library)

Far simpler than the original's chapter-renumbering merge — a new book is just a new sibling file.

1. Run Steps 0–2 for the new source(s) only.
2. Step 5 → derive a unique `reference-<slug>.md` (append `-2` on collision).
3. Step 7 → write the **one new** reference file. Do not touch existing reference files.
4. Re-index the master `SKILL.md`: add one row to "Which book for which job", merge the new book's terms into the
   Cross-book Topic Index (append the new slug to existing terms it also covers — or into `topic-index.md` if the
   library has already spilled it), bump the book count and date. Re-check the master against its Step 8 budget:
   `N` just grew by one, so this is where the overflow valve fires.
5. Step 9 cleanup; report which book was added and which topic-index entries changed.

---

## Quality Rules

1. **Extract structure, not summaries** — named frameworks, exact formulations, anti-patterns; not chapter recaps.
2. **Preserve the author's precision** — "The 5 Whys" ≠ "ask why a few times". Keep exact naming.
3. **Density over length** — a 1,000-token distillation beats a 10,000-token excerpt. Never pad.
4. **Front-load** — most important content first, in both each reference file and the master (compaction cuts the tail).
5. **Reference files are on-demand, but load whole** — they cost nothing until opened, and then they cost *all* of
   themselves. That is why Step 7's cap is hard while its range is only a target. Keep the always-loaded master lean.
6. **Never copy raw text** — always synthesize.
7. **The cross-book Topic Index is the payoff** — it's how the agent routes a question to the right book. Get it right.
8. **Name slug rule** — `name:` must be lowercase letters/digits/hyphens only (no spaces, no `&`, not "claude"/"anthropic"). The pretty title lives in the `#` heading and description, not in `name:`.
