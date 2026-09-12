# Behavioral acceptance and evidence-directed reading

## Freeze representative tasks before extraction

Turn the user's purpose into at least four concrete tasks before semantic
extraction or reference writing. Metadata inspection and file conversion may
precede this step. If purpose is already clear, derive the tasks without another
permission gate. Include applying a method, recognizing when it does not apply,
preserving a real disagreement, and an unsupported question. Define observable
success criteria, not framework-name recall. Use user scenarios and source
metadata to choose tasks; resolve answers against evidence later.

Store `acceptance-suite.json` in the generated project's `fidelity-ledger/`:

```json
{
  "version": 1,
  "defined_before_extraction": true,
  "tasks": [{
    "id": "apply-01",
    "kind": "apply",
    "prompt": "<concrete situation and requested decision>",
    "criteria": {
      "method": "<observable steps a successful application demonstrates>",
      "condition": "<the prerequisite the answer must check>"
    },
    "references_required": true
  }]
}
```

At least one task must set `references_required: true`; a suite with no reference-dependent
task is rejected even if an incidental retrieval occurred. Its full-configuration run must
record an actual retrieved reference, so acceptance exercises the loading mechanism.

This is a task-entry example; a valid suite also includes `inapplicable`,
`disagreement`, and `unsupported` tasks. Include a case needing detail beyond the
core, plus conditions that would change a recommendation. For an unsupported
question, success means recognizing the evidence boundary and distinguishing
retrieval or extrapolation from an attested answer.

## Run and record three conditions

Use the same model, generation settings, task prompts, and external tool policy.
Use fresh contexts per task and condition; keep expected answers and grades out
of prediction contexts. Freeze a minimal domain-role prompt for the baseline.

1. `baseline`: only the minimal role prompt and task.
2. `core`: generated `SKILL.md` and task, without references.
3. `core_references`: core and task, with references available through the normal
   loading rules. Record files actually retrieved, not merely offered.

Save actual answers, observed retrieval paths, criterion judgments and grading
rationales in `acceptance-results.json`. Grade after predictions are saved,
preferably with condition labels hidden from the reviewer. The script validates
records and calculates comparisons; it does not call a model or grade prose.
Never populate passing answers or grades just to satisfy it.

The result object has `suite_hash`, `content_hash`, `model`, `settings`,
`baseline_prompt`, and `runs`. The latter maps each condition above to a list:

```json
{
  "id": "apply-01",
  "fresh_context": true,
  "answer": "<actual saved response>",
  "criteria": {"method": true, "condition": false},
  "rationale": "<evidence for each grade>",
  "references_loaded": ["references/reference-author-method.md"]
}
```

Hashes have a `sha256:` prefix. `suite_hash` hashes the raw suite file bytes.
Get `content_hash` using the command below; it hashes a compact UTF-8 JSON list of
relative paths and raw file SHA-256 values, with `SKILL.md` first and all reference
files sorted by path. The ledger is excluded. Record hashes at evaluation time,
never refresh them without rerunning the affected evaluation.

```bash
python3 tools/acceptance_suite.py /path/to/runtime-skill --print-hash
python3 tools/acceptance_suite.py /path/to/runtime-skill \
  --suite /path/to/fidelity-ledger/acceptance-suite.json \
  --results /path/to/fidelity-ledger/acceptance-results.json \
  --json /path/to/fidelity-ledger/acceptance-report.json
```

The full configuration must pass every criterion and retrieve references where
required. Report baseline, core and full totals, per-task differences, core gain
and reference gain. A tie is not evidence of added value. Investigate regressions,
missed loading, or material with no demonstrated use; revise and rerun rather
than claiming that structure proves reasoning quality. Preserve failed runs.
If model execution is unavailable, report behavioral acceptance as unrun, even
when structural checks pass.

On add-a-book runs, keep the existing tasks/criteria and compare with the last
version's recorded per-task scores as well as the same-model baseline. Add tasks
for new methods, exceptions or disagreements. A previous passing criterion that
now fails is a regression. Record model/settings changes because cross-model
scores are not a controlled before/after comparison. Save earlier suites/results
under versioned ledger directories; do not overwrite the evidence.

## Allocate reading to unresolved evidence

Record each read in `reading-ledger.json` with original source-local line bounds,
cleaned tokens actually read, and a reason. For rereading or targeted verification,
record the unresolved claim, exception or disagreement and its resolution. Example:

```json
{
  "sources": {"book-a": {"lines": 10000, "output_budget": 6000}},
  "reads": [
    {"source": "book-a", "start": 100, "end": 180, "tokens": 900,
     "reason": "initial"},
    {"source": "book-a", "start": 160, "end": 200, "tokens": 400,
     "reason": "verification", "question": "Does the exception cover case X?",
     "resolution": "Only when prerequisite Y holds; retained in Decision Rules."}
  ]
}
```

Run `python3 tools/reading_audit.py reading-ledger.json --out reading-report.json`.
It reports unique source lines, repeated lines and cumulative input tokens
separately. Source-span coverage is an approximation of inspection, not a claim
that every original line survived cleaning. Crossing 4 times the output budget
is an alert to review expenditure; it is neither proof of rereading nor a ban on
verification. Stop a targeted read when the question is resolved, or record the
remaining gap and its effect on acceptance.

Before finishing each reference, audit a small sample outside the initial
framework list. Choose at least two source spans from different sections, including
an exception, limitation or counterexample when available. Log source locations,
selection reasons, newly found qualifications and whether each was retained or
excluded with a reason in `coverage-audit.md`. If there is only one eligible span,
state that limitation. Expand the sample if it reveals an answer-changing omission.
This is an audit of what extraction missed, not a claim of exhaustive coverage.
