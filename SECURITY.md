# Security

## The threat this project actually has

This skill reads documents it did not author and writes files that a host agent
later loads **as instructions**.

That is a laundering path. Text inside a PDF is untrusted data. The same text,
once distilled into a `reference-*.md` and loaded by an agent, is read as
instruction. Nothing about the extraction re-establishes the boundary, so the
project has to do it deliberately, in three places:

| Stage | Control | Where |
|---|---|---|
| Extraction | Invisible and bidi-override characters stripped; forged `SOURCE:` fences neutralised so one document cannot impersonate another | `bookrefs/sanitize.py` |
| Generation | The distillation carries the author's ideas, never directives aimed at the reading agent | `SKILL.md` Quality Rules |
| Before use | Advisory scan of the generated library for injected instructions | `tools/scan_generated_skill.py`, run by Step 8.5 |

Run the scan before loading a library built from a source you do not control:

```bash
python tools/scan_generated_skill.py path/to/library --strict
```

It flags instruction overrides, identity overrides, system-prompt references,
concealment directives, credential solicitation, shell and network egress, and
claimed authority. **It is advisory: it cannot prove absence.** A clean report
means no known pattern matched, not that the library is safe.

## What this project does not do

- **No sandboxing.** Parsers run in your interpreter. Only the MOBI/AZW path
  shells out, to calibre's `ebook-convert`, and it is reported when used.
- **No network access.** Nothing here fetches anything. Extraction is local, and
  the only optional install is a PDF backend via pip, which is opt-in
  (`--install-missing`, default `never`).
- **No DRM circumvention.** A DRM-protected file fails with a clear message.
- **No OCR.** A scanned PDF with no text layer is detected and reported rather
  than silently distilled into nothing.

## Handling sources you do not trust

1. Extract and scan before generating anything you intend to keep.
2. Read the extraction report — a source that failed to parse, or that tripped
   the fence-forgery neutraliser, is worth a look.
3. Treat any HIGH scan finding as a reason to inspect the source, not just to
   delete the line. A document that tried this is worth knowing about.

## Reporting a vulnerability

Open a private security advisory on the repository, or an issue if the problem
is not sensitive. Please include the input that triggers it where you can — a
minimal fixture is more useful than a description, and it becomes a regression
test.

Useful reports include: a document shape that escapes `sanitize.py`, an
injection pattern the scanner misses, a parser that can be made to read outside
its archive, or a path where extracted text reaches a generated file unfiltered.
