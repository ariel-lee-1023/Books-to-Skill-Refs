# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
