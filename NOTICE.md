# NOTICE

## Dependencies

**This project has no required third-party runtime dependencies and no external
skill dependency.**

The extraction runtime (`scripts/extract.py` and the `bookrefs` package) is
first-party. Text, HTML, DOCX, EPUB and RTF are handled with the Python standard
library alone. Two format families use software this project does not ship:

| Format | Uses | Nature |
|---|---|---|
| `.pdf` | one of `pymupdf`, `pdfplumber`, `pypdf` | optional pip package, chosen at runtime, none vendored |
| `.mobi` `.azw` `.azw3` | calibre's `ebook-convert` | optional external application, invoked as a subprocess |

Neither is bundled or redistributed here, and both are optional — `--check`
reports which are present and names the remedy for whichever is not.

## Prior work

Releases through 1.0.0 called the extraction engine from
[`book-to-skill`](https://github.com/virgiliojr94/book-to-skill) by
[@virgiliojr94](https://github.com/virgiliojr94) (MIT) as a runtime dependency.
**That dependency is gone as of 1.1.0**, replaced by the first-party runtime
described above. No code from that project is present in this repository, and
none is called at runtime.

One debt from that period is not settled by removing the dependency, so it is
recorded here rather than left implicit: **this skill's workflow skeleton is
derived from that project's `SKILL.md`**, which is covered by the same MIT
licence as its code. Specifically, the numbered Step 0–9 structure, the three
operating modes, the pre-generation cost gate, the `BOOK_TYPE` / `DEPTH`
questions, and the ordering and phrasing of the Quality Rules follow it closely.
That derivation is textual, not functional — swapping the extractor does not
undo it — and it stands until that prose is rewritten.

## What is original here

- **The extraction runtime** — parsers, structure detection across scripts,
  sanitisation, the fence and metadata contracts, dependency reporting.
- **Token estimation by script density** (`bookrefs/tokens.py`), which does not
  collapse on Chinese, Japanese or Thai the way a word-split estimate does.
- **The output architecture** — a flat multi-book library, one
  `reference-<book-slug>.md` per source, all siblings, with a single
  always-loaded master router and its cross-book topic index.
- **The budget model** — per-section allowances with hard per-file caps derived
  from whole-file load granularity, the master's `400 + 50 × N + index` scaling
  budget and 3,500 hard stop, the topic-index overflow valve, the cut order for
  over-cap books, and coverage rather than length as the acceptance criterion.
- **The verification toolchain** — `tools/count_tokens.py`,
  `tools/validate_library.py`, `tools/validate_skill.py`,
  `tools/scan_generated_skill.py`, and the test suite.
- **The judgment about what survives** the collapse of the three cross-cutting
  files, and the multi-source fold-in workflow.

## Originality of text

Text authored in this repository is original. It reproduces no substantial
portion of any copyrighted source work.

## Nature of reference material

Source works are named for two purposes only: attribution and verification.
What is distilled is **structure** — frameworks, decision rules, and named
terminology — not expression. No prose, sentences, or expressive language from
source works is reproduced.

Framework names and named terminology are preserved exactly as they appear in
the originals. Paraphrasing them would break traceability to the source and
defeat the purpose of attribution.

## Rights

Source works referenced in this repository remain the exclusive property of
their respective rights holders. No licence or right in those works is granted
or implied by their citation here.

## Contributor

Contributed by [@ariel-lee-1023](https://github.com/ariel-lee-1023).
