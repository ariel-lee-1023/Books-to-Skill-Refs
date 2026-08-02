# NOTICE

## External dependency — `book-to-skill`

This project depends at runtime on **[`book-to-skill`](https://github.com/virgiliojr94/book-to-skill)
by [@virgiliojr94](https://github.com/virgiliojr94)**, used under the MIT License.

This skill calls that project's `scripts/extract.py`, which imports its `book_to_skill`
package. The extraction engine is reused **unchanged**; it is not vendored into this
repository, and no part of it is claimed here.

Its copyright notice, reproduced from its `LICENSE.md`:

```
MIT License

Copyright (c) 2025 virgiliojr94
```

The full license text is available in that repository.

### What is mine, and what is not

**Not mine — @virgiliojr94's:**

- The extraction engine: `scripts/extract.py`, the `book_to_skill` package, and the
  per-format parsers (PDF, EPUB, DOCX, HTML, RTF, MOBI/AZW) with their OCR and
  text-layer fallback behaviour.
- The extraction discipline this project inherits and applies unchanged — structure over
  summary, the author's own terminology, density over length, never copying raw source
  text. This project's "Quality Rules" list is adapted from that project's own Quality
  Rules and follows its ordering and phrasing closely.

**Mine — [@ariel-lee-1023](https://github.com/ariel-lee-1023):**

- The output architecture: a flat multi-book library (one `reference-<book-slug>.md` per
  source, all files siblings) in place of the original's per-book nested folder with
  `chapters/`, `glossary.md`, `patterns.md`, and `cheatsheet.md`.
- The master-router design: a single always-loaded `SKILL.md` that indexes and routes
  across every source in the library, including the cross-book topic index.
- The token ceiling: the hard ~2,500-token cap on that always-loaded master, with the
  router table front-loaded so compaction truncates only the tail, and per-book
  references costing nothing until a question needs one.
- The judgment about what survives the collapse of the three cross-cutting files, and the
  multi-source fold-in workflow.

## Originality

Text authored in this repository is original.
It reproduces no substantial portion of any copyrighted source work.

## Nature of Reference Material

Source works are named for two purposes only: attribution and verification.
What is distilled here is **structure** — frameworks, decision rules, and
named terminology — not expression. No prose, sentences, or expressive
language from source works has been reproduced.

Framework names and named terminology are preserved exactly as they appear
in the originals. Paraphrasing them would break traceability to the source
and defeat the purpose of attribution.

## Rights

Source works referenced in this repository remain the exclusive property
of their respective rights holders. No license or right in those works is
granted or implied by their citation here.

## Contributor

Contributed by [@ariel-lee-1023](https://github.com/ariel-lee-1023).
