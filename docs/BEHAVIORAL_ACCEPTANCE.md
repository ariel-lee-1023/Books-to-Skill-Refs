# Behavioral acceptance and evidence-directed reading

## Freeze representative tasks before extraction

Turn the user's purpose into at least four concrete tasks before semantic
extraction or reference writing. Metadata inspection and file conversion may
precede this step. If purpose is already clear, derive the tasks without another
permission gate. Include applying a method, recognizing when it does not apply,
preserving a real disagreement, and an unsupported question. Define observable
success criteria, not framework-name recall. Use user scenarios and source
metadata to choose tasks; resolve answers against evidence later.

Use version 2 suites for independent final acceptance: separate development and final
scenario groups before extraction. Revisions use development only; final cases are opened
once after the candidate is fixed. Version 1 records remain development-only. The optional
[executable runner](EVALUATION_RUNNER.md) enforces partition separation, captures real model
requests/retrievals, and separates prediction from blind grading and append-only human review.

Store `acceptance-suite.json` in the generated project's `fidelity-ledger/`:

```json
{
  "version": 2,
  "defined_before_extraction": true,
  "tasks": [{
    "id": "apply-01",
    "kind": "apply",
    "partition": "development",
    "group": "application-scenario-01",
    "prompt": "<concrete situation and requested decision>",
    "criteria": {
      "method": "<observable steps a successful application demonstrates>",
      "condition": "<the prerequisite the answer must check>"
    },
    "references_required": true,
    "qualification_criteria": ["condition"]
  }]
}
```

At least one task must set `references_required: true`; a suite with no reference-dependent
task is rejected even if an incidental retrieval occurred. Its full-configuration run must
record an actual retrieved reference, so acceptance exercises the loading mechanism.

This is a task-entry example; each development/final partition also includes `inapplicable`,
`disagreement`, and `unsupported` tasks, with different scenario groups in the two partitions. Include a case needing detail beyond the
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

## Targeted retrieval and compression experiment

Keep one canonical Markdown reference per book. Organize method sections so the prerequisites,
steps, answer-changing exceptions and source locator travel together. Do not write a second
summary that can drift from the canonical reference. `evaluation_runner.py index` creates a
small addressable index of headings and source line ranges; rebuild it after source edits.
Its entries reference canonical text and carry source hashes. Add a compact task-to-section
map in the core's loading note when the task trials establish useful routes.

The runner's optional `--targeted` condition uses the same tasks and model as whole-book
loading. Each section read automatically includes that book's Mental Model and Decision Rules
sections. These guards reduce accidental loss of global qualifications but do not prove every
relevant condition was captured; put local prerequisites and exceptions next to the method.
Cross-author comparisons can read one relevant section from each author.

The acceptance report shows whole-reference versus targeted criterion scores, missed
`qualification_criteria`, provider-reported total tokens and retrieved characters. Missing
provider usage is null, not zero. Count prompt/catalog overhead and repeated context, not only
the retrieved excerpt. The targeted condition is an experiment: its failure is reported and
must prevent adoption of that retrieval/compression choice, while an otherwise passing
whole-reference candidate can still pass ordinary acceptance.

Use development ablations to allocate space: when removing a condition changes a correct answer,
restore it and shorten lower-value material instead. Spend more of the canonical reference's
budget on prerequisites, exceptions and distinctions that change decisions, even if they occupy
little of the source. Shorten sections whose removal does not impair representative tasks.
Chapter-count formulas remain provisional planning targets; they do not establish usefulness.
Preserve hard load caps for normal whole-book delivery. If the task evidence cannot fit those
caps, report the architectural constraint and evaluate a targeted-loading variant explicitly
before changing the delivery contract. Run the untouched final suite once after selecting the
candidate; repeated success on development tasks is not broader validation.
