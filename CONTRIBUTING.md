# Contributing

Issues and pull requests are welcome.

## Before opening a PR

```bash
python -m unittest discover -s tests -v
python tools/validate_skill.py SKILL.md --lens all
python tools/validate_library.py tests/fixtures/good-library
```

All three must pass. CI runs the same commands.

## The one rule that matters

**The prompt states contracts; the tools enforce them. Do not let them drift.**

If you change a budget or a shape rule in `SKILL.md`, change the matching
constant in `tools/validate_library.py` and add a test. A budget nobody can
measure is not a budget, and a contract nothing checks is a contract waiting to
be wrong. `tests/test_validate_library.py::TestHelpers::test_caps_match_skill_md`
exists precisely to catch this.

## Changing `SKILL.md`

Most of the behaviour lives in one prompt file, so keep changes focused: say
which step you are changing and why. State the reasoning inline where a future
reader would otherwise re-derive it — several steps carry a short note on why a
threshold is what it is, and those notes are load-bearing.

## Adding a format

1. Add a parser under `bookrefs/parsers/` returning `ParsedDoc`.
2. Register the extension in `bookrefs/config.py`.
3. Add dispatch in `bookrefs/parsers/__init__.py`.
4. If it needs a third-party package, add a capability in
   `bookrefs/dependencies.py` so `--check` reports it with a remedy — never let
   a missing dependency surface as a traceback mid-run.
5. Add tests. Build the fixture programmatically if you can (see
   `tests/builders.py`); commit a binary only if the format makes that
   impossible.

**Preserve structure.** Headings should come out as `#` lines and tables as pipe
rows: `structure.py` reads the first and the technical/text tripwire reads the
second. A parser that flattens everything to prose erases the evidence the
workflow runs on.

## Dependencies

The runtime has **no required third-party dependencies** and should keep none.
Text, HTML, DOCX, EPUB and RTF are handled with the standard library; that is
what makes the project testable in CI without network access. New optional
dependencies need a reason that cannot be met with `zipfile`, `xml.etree` or
`html.parser`.

## Security-relevant changes

Read [SECURITY.md](SECURITY.md) first. Anything touching `sanitize.py` or
`tools/scan_generated_skill.py` sits on the boundary between untrusted document
text and text an agent will treat as instructions. Changes there need a test
with the input that motivated them.

New scanner rules must not fire on `tests/fixtures/good-library` — a scanner
that flags ordinary distillations is noise, and noise gets ignored.
