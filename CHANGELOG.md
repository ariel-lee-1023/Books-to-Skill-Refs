# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed — the output layout is now the Agent Skills convention

Generated libraries were flat: `SKILL.md` and every `reference-*.md` as siblings in one
directory. They now follow the layout hosts actually expect — **`SKILL.md` at the root and
every reference file under `references/`**.

The flat shape was solving the wrong problem. What this design rejects is nesting *within* a
book's material — a folder per book, a `chapters/` split, separate glossary/patterns/cheatsheet
files — and none of that requires putting reference files beside `SKILL.md`. It only cost
compatibility: `references/` is where Claude Code, Copilot CLI and Amp look for supporting
files, and a library that invents its own shape is harder to install, harder to read, and fails
anyone's expectations about what a skill directory looks like.

- **`SKILL.md`** — output contract, Step 5 slugs, Step 6 `mkdir`, Step 7 write paths, the Step 8
  router template and its overflow valve (`references/topic-index.md`), Step 9's report, and the
  fold-in workflow all target `references/`.
- **`tools/validate_library.py`** — the layout check inverts: `references/` is now the one
  permitted subdirectory, and a `reference-*.md` left at the library root is an **error** with
  the `git mv` that fixes it. Router links are matched on the path relative to the library, so
  a link missing the `references/` prefix is reported with a "did you mean" hint rather than as
  two unrelated failures. The topic-index spill valve moves to `references/topic-index.md`.
- **Fixtures and tests** — `good-library` and `bad-library` restructured; `bad-library` gains a
  stray root-level reference file so the migration error stays covered.

**Migrating an existing library**: `mkdir -p references && git mv reference-*.md references/`,
then prefix every router link and topic-index target with `references/`. `validate_library.py`
names both steps if you miss one.

### Added — first-party extraction runtime (Tier 1)

The project no longer depends on another skill to run. `scripts/extract.py` and the
`bookrefs` package replace the external engine entirely.

- **`bookrefs/parsers/`** — text/markdown, HTML, DOCX, EPUB and RTF are parsed with the
  **Python standard library alone** (`zipfile`, `xml.etree`, `html.parser`); PDF uses
  whichever of pymupdf / pdfplumber / pypdf is installed; MOBI/AZW shell out to calibre.
  Five of eight format families therefore need nothing installed, which is also what makes
  the suite runnable in CI without network access.
- **`bookrefs/structure.py`** — chapter and ToC detection across five heading dialects:
  English and European chapter words, standalone Roman numerals, CJK `第N章/回/卷/节/篇/讲`
  with Chinese numerals and full-width digits, CJK markdown headings, and Thai. Prose
  cross-references ("Chapter 6 explores…") are rejected by a heading-plausibility gate.
- **`bookrefs/tokens.py`** — the canonical token estimator; `tools/count_tokens.py` is now
  a CLI over it, so the extractor's metadata, the cost gate, the caps and the validator
  cannot drift apart.
- **`bookrefs/sanitize.py`** — normalisation plus an untrusted-input boundary: invisible and
  bidi-override characters are stripped, and a `SOURCE:` fence forged *inside* a document is
  neutralised so one source cannot impersonate another. The marker is broken rather than
  deleted, keeping the tampering visible.
- **`bookrefs/dependencies.py`** — `--check` reports each format family with a remedy, and
  the preflight only complains about formats the current batch actually contains.
- **Richer `metadata.json`** — now carries `mode`, `token_method`, `path`, per-source
  `start_line` / `end_line` (so callers stop re-deriving fence boundaries), and a
  `failures[]` list. One corrupt or DRM-protected source no longer sinks the run.
- Parsers preserve structure rather than flattening it: DOCX `Heading N` styles and HTML
  `<h1..h6>` become markdown headings, tables become pipe rows, `<pre>` becomes a fenced
  block — the exact signals `structure.py` and the technical/text tripwire read.
- Legacy Chinese encodings (gb18030, Big5-HKSCS) and RTF `\uN?` escapes are decoded, so a
  Chinese document does not silently extract as mojibake or as nothing.

### Added — verification and engineering (Tier 2)

- **`tools/scan_generated_skill.py`** — advisory scan of a generated library for
  instructions aimed at the reading agent: instruction and identity overrides, system-prompt
  references, concealment, credential solicitation, shell/network egress, claimed authority.
  This closes a laundering path — text that is untrusted data inside a PDF becomes trusted
  instruction text once distilled into a file an agent loads. New Step 8.5 runs it.
- **`tools/validate_skill.py`** — audits a `SKILL.md` under a `claude`, `copilot` or `amp`
  lens. The project claimed cross-agent compatibility and never checked it.
- **`SECURITY.md`** — the threat model, the three places the boundary is enforced, and an
  explicit list of what the project does *not* do (no sandboxing, no network, no DRM
  circumvention, no OCR).
- **`docs/ARCHITECTURE.md`**, **`CONTRIBUTING.md`**, **`pyproject.toml`** (no required
  dependencies; `pdf` / `pdf-layout` / `all` extras; `bookrefs-extract` entry point).
- **CI** — a 3-version Python matrix, both validators, both scanner fixtures, and an
  end-to-end extraction smoke test asserting that CJK chapter detection, ToC detection and
  token counting have not regressed.
- Test suite grown to **131 cases**. DOCX and EPUB fixtures are built at test time
  (`tests/builders.py`) rather than committed as binaries, so they stay reviewable in a diff
  and a test can vary them — a shuffled EPUB spine, a `Heading 2` style.

### Changed — Tier 1/2 follow-through

- **`SKILL.md` Steps 1 and 2 now invoke the first-party runtime.** The bootstrap block that
  told users to `git clone` another repository is gone; there is nothing to install.
- **Step 2.5 no longer distrusts `estimated_tokens`.** The runtime's own estimate is
  script-density based, and `metadata.json` records `token_method` so the check is
  falsifiable rather than assumed.
- **Step 2 documents the fence-forgery defence** and the `failures[]` behaviour.
- **NOTICE.md rewritten.** The runtime dependency is gone and no code from the earlier
  upstream is present or called. The one debt removing the dependency does *not* settle is
  now stated plainly rather than left implicit: the numbered Step 0–9 skeleton, the three
  modes, the cost gate, the `BOOK_TYPE`/`DEPTH` questions and the Quality Rules' ordering
  and phrasing are derived from that project's `SKILL.md` prose, and stand until rewritten.
- README requirements, install steps and tool documentation updated to match.

### Added

- **`tools/count_tokens.py`** — token estimation that segments by script density instead
  of by whitespace. The extractor's `estimate_tokens` is `len(text.split()) / 0.75`, which
  counts space-delimited words; Chinese, Japanese and Thai prose has none, so a measured
  1,080-character Chinese passage estimated as **1** token against a realistic ~720. Step
  2.5's cost gate would have shown `~0K` and collected approval for a run costing orders of
  magnitude more. Stdlib only.
- **`tools/validate_library.py`** — validates a *generated* library against the contracts
  in `SKILL.md`: flat directory, every reference file reachable from the router, no dangling
  router links, the topic index's ≥2-book rule, the master's scaling budget and 3,500 hard
  stop, and each reference file against its Step 7 cap for its detected type and declared
  depth. `ERROR` exits non-zero; `WARN` does not.
- **`tests/`** — 38 stdlib `unittest` cases plus conforming and deliberately broken library
  fixtures. Includes a regression test asserting the CJK undercount cannot return.
- **Step 8.5 — Verify the library against the contract.** Runs the validator before
  reporting success; a library that has not been verified must not be reported as done.
- CI now runs the unit tests, requires the good fixture to pass and the bad fixture to
  fail, and prints this skill's own always-loaded token cost.
- README documents both tools and how to run the tests.

### Fixed

- **Step 2.6's chapter probe now matches CJK headings.** It was ASCII-only
  (`Chapter|CHAPTER \d+`) while the extractor detects `第N章 / 第N节 / 第N讲` and reports
  them in `chapters_detected` — so on a Chinese book the extractor parsed correctly, the
  probe found zero offsets and Steps 3 and 7 had no section boundaries to work with.
- **`.gitignore` no longer blanket-ignores `/scripts/`.** It was added to keep a vendored
  copy of the upstream engine out of the repository, but it would also have silently
  swallowed a first-party extractor written here. Only `/book_to_skill/` — a name that can
  only be upstream's — stays ignored.
- CI's relative-link sweep skips `tests/fixtures`, whose broken links are the fixtures.

### Changed

- **Per-reference-file budget now scales with book size** (Step 7). The flat per-book
  constants (2,000–7,000 tok) were unsatisfiable for long books: the section template
  grows with chapter count while the budget did not, so a 30-section book spent its
  entire budget on a skeleton. Replaced with a per-section allowance, a book-level target
  range, and a hard cap per `DEPTH` × `BOOK_TYPE` cell.
- **Master `SKILL.md` budget is now a formula, not a constant** (Step 8):
  `400 + 50 × N + index (≤600)`, hard stop 3,500. The old flat ~2,500 held to roughly 30
  books, then bound; the router table is inherently O(N) and needed to scale with it.
- **Sliced reading is unconditional** (Step 2.6). The inherited ">50k tokens" threshold
  assumed one book per file; with N books concatenated into `full_text.txt`, a full read
  always pulls in the N−1 books not currently being written, at any size.
- Quality Rule #5 now states that reference files load *whole*, which is why Step 7's cap
  is hard while its range is only a target.
- Step 2.5 cost estimate updated to the new master formula and to per-book budgets scaled
  by section count.

### Added

- **Cut order for over-cap books** (Step 7): drop to reference depth → merge thin sections
  → trim minor sections → never cut exact framework formulations or `Decision Rules &
  Judgment` → ask the user before splitting a book across sibling files.
- **Coverage check as the acceptance criterion** (Step 7): every framework/principle/
  technique found in Step 3 must appear in the reference file or be explicitly recorded as
  dropped with a reason. Coverage is satisfied before compressing toward the range.
- **Input budget per book** (Step 2.6): cumulative reading stays ≲ 4× that book's output
  budget, with `SOURCE:` fence boundaries computed once and each slice read exactly once.
- **Topic Index overflow valve** (Step 8): past the 3,500 hard stop, the Cross-book Topic
  Index moves to a sibling `topic-index.md` loaded on demand; the router table never
  spills. Router grouping by theme past ~30 books. Fold-in re-checks the budget since `N`
  grows by one.

## [1.0.0] - 2026-07-22

### Added

- Initial release of the `books-to-skill-refs` agent skill.
- Multi-book batch distillation: one run over N sources produces one flat library.
- Flat output contract — a master `SKILL.md` router plus one `reference-<book-slug>.md`
  per book, all siblings in a single directory (no `chapters/`, no per-book subfolders).
- Cross-book Topic Index in the master `SKILL.md`, with a ≥2-book inclusion rule and a
  ~40-entry / ~600-token ceiling to bound growth.
- Three modes: Full build, Analyze only (report, write nothing), and Add-a-book fold-in.
- Per-book cost estimate presented before any generation, gated on user confirmation.
- Extractor preflight in Step 1 with bootstrap instructions, so a missing dependency
  fails immediately instead of mid-run.
- Misclassification tripwire: probes each text-mode book for indented code blocks and
  pipe-tables, and offers a technical-mode re-extract for that book alone.
- Per-book output budget matrix across `DEPTH` (reference/study) and `BOOK_TYPE`
  (text/technical).
- Strict mode switch — remove `## Decision Rules & Judgment` for a pure structural
  distillation.
- Slug collision policy: disambiguate by author and concept rather than by numeric suffix.

### Notes

- The extraction engine is reused unchanged from
  [`book-to-skill`](https://github.com/ariel-lee-1023/book-to-skill); this project only
  changes the output shape.
- Cost figures in the skill reference 2025 model pricing and should be re-checked over time.

[Unreleased]: https://github.com/ariel-lee-1023/books-to-skill-refs/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ariel-lee-1023/books-to-skill-refs/releases/tag/v1.0.0
