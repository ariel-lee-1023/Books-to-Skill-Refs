# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
