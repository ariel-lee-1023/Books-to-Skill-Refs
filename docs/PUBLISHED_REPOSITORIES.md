# Published repository profile

This is the user's standing preference for future new deliverables built in this local Books-to-Skill-Refs project, unless a task explicitly requests a draft or no publication. It is based on the layout of [Cognitive Neuroscience Expert](https://github.com/ariel-lee-1023/Cognitive-Neuroscience-Expert), inspected on 2026-09-10. The 2026-09-12 local workflow stages output under `/Users/AI products/Git-deliverables/<repository-name>/`, packages and validates it there, moves it to `/Users/AI products/GIthub/<repository-name>/`, and only then commits and pushes. Read `/Users/AI products/Git-deliverables/WORKFLOW.md` for destination handling. Existing deliverables are not relocated by this setting. The general metatool contract remains available outside this local profile.

## Deliverable layout

```text
<destination>/
├── SKILL.md
├── references/
│   └── reference-<source-slug>.md
├── AGENTS.md
├── README.md
├── LICENSE
├── .gitignore
├── .agents/
│   └── skills/
│       └── <skill-name> -> ../..
└── fidelity-ledger/
    ├── source-and-coverage-ledger.md
    ├── source-manifest.json
    ├── evaluation.md
    └── validation.json
```

`SKILL.md` and `references/` are the canonical runtime content. The relative directory symlink makes the root skill discoverable when the repository is opened as a project; it must resolve to that repository's root. Do not keep divergent root and nested copies. Hosts or checkouts that do not preserve symlinks can load the root skill directly or install the complete root skill/reference tree in their configured skill location.

The exact filenames within `fidelity-ledger/` may vary with the build; its directory name does not. It holds human-facing provenance and quality records, and is never included in the skill's task-triggered reference table. Domain answers load `SKILL.md` and the required reference files explicitly, not every Markdown file in the root. `AGENTS.md` may direct maintainers to the ledger when the task is repository maintenance.

## What to add

- **SKILL:** immediately after the title, state the actual distilled corpus language (or its principal language) as the default output language, unless the user explicitly selects another. Follow [the language writing standard](../SKILL.md#default-language-for-generated-skills), including translated and multilingual sources.
- **README:** open with the particular constructed expert introducing itself in first person, following [the writing standard](../SKILL.md#writing-the-experts-readme-introduction). Show how it approaches real questions, makes domain-specific distinctions, weighs evidence, and revises judgments. Source counts and conceptual-layer summaries belong in later background sections, not the opening identity. Then provide visible layout; full-title/author source tables; installation using the real destination URL and skill slug; usage examples; progressive loading; scope and limitations; extraction provenance; and license scope. Keep these supporting sections as ordinary documentation. Avoid generic expert praise, invented personal credentials, and copying the exemplar's domain content.
- **AGENTS:** read the root skill at the start of a new domain conversation; follow its reasoning and loading triggers without requiring explicit invocation; follow the core's corpus-derived default output language and switch only on an explicit user language request; preserve source/evidence boundaries; let explicit user instructions and maintenance tasks take precedence over the default domain role.
- **LICENSE:** follow an existing destination's terms. For a new repository of the user's original skill instructions and synthetic reference text, follow the exemplar's MIT default and verified owner/year. Clearly distinguish this original work from the underlying sources, whose terms remain their own. Do not relicense third-party files or claim to grant rights the user does not hold.
- **.gitignore:** editor and platform artifacts, temporary extraction/build output, and raw source material. Do not ignore the intended reference Markdown or fidelity ledger.
- **Fidelity ledger:** source editions and quality, recovery of damaged extractions, retained/compressed/dropped concepts, explicit cross-source synthesis, relevant source hashes without private absolute paths, editorial evaluation cases and their limits, and actual validation results.

Do not add a badge for a nonexistent workflow, fabricate evaluation runs, copy secrets or raw books, or invent current facts to fill the README. Use judgment about additional repository features; a website, CI deployment, or release is not required by this profile.

## Validation and publication

1. Run `python3 tools/validate_library.py <destination> --layout published-repo --json` and save the result to `<destination>/fidelity-ledger/validation.json`. This validates root content, required packaging files, the discovery alias, routing, reference layout, and token limits. Nested libraries continue to use the validator without the profile flag.
2. Run `scan_generated_skill.py` on `<destination>/SKILL.md` and `<destination>/references/` separately. A scan over the entire repository would mix authored project instructions and maintainer documents with source-derived runtime material.
3. Resolve repository-relative Markdown links, check the expected source count and reference sections, verify symlink resolution and Git mode `120000`, and inspect tracked files for source or temporary material.
4. Review ordinary, ambiguous/conflicting, and outside-corpus questions. Check the opening language rule against the corpus and any explicit user choice, and reconcile host instructions. A question written in another language retains the default; an explicit output-language request overrides it for the stated scope. Also check the README introduction against the final expert core: it must express this expert's distinctive reasoning in first person, rather than merely announce the source collection. Apply the writing standard's unrelated-expert substitution check. Record editorial review honestly; neither this review nor structural validation is an independent model benchmark.
5. Move the validated staged project to `/Users/AI products/GIthub/<repository-name>/` before commit/push. Use the intended remote repository name unless the user specifies another local name. If the path exists, inspect it and integrate into a matching checkout while preserving its `.git`, history, and local changes; do not overwrite a different directory or repository. Recheck relative links and the skill discovery symlink after moving.
6. From the final local checkout, commit only the intended destination changes, push without overwriting unrelated history, and verify the remote branch SHA and tree. Do not publish first and clone afterward. Preserve the local result if publication fails. Report the remote destination, final local path, and any material limitations.

Packaging is part of the already requested build-and-publish task. Do not ask for confirmation merely to add these files. If an existing destination has a different established architecture, adapt to it while retaining the explicit `fidelity-ledger/` preference where feasible; an explicit new user direction prevails.
