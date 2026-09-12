# Executable evaluation workflow

The optional `evaluation_runner.py` performs model calls through a user-selected
chat-completions-compatible HTTP endpoint. Set `EVALUATION_API_KEY` if the endpoint
needs bearer authentication. The runner does not install a provider SDK or choose
a model. Run it only with material authorized for the selected endpoint.

Prediction and grading are separate commands and contexts. Prediction has only
the task, its condition's prompt and permitted runtime files. It cannot execute
shell commands, open arbitrary paths, read the grading key or use a previous task's
conversation. A model requests a reference through `{"action":"read","path":"..."}`
and answers through `{"action":"answer","text":"..."}`. The HTTP adapter sends
`model`, `messages`, `temperature`, `stream:false` and reads
`choices[0].message.content` plus provider `usage` when available. An incompatible
provider needs an adapter implementing that response convention.

## Task suite and holdout registry

Use version 2 suites with `defined_before_extraction: true`, a `baseline_prompt`,
and a `tasks` list. Every task has `id`, `prompt`, `partition` (`development` or
`final`), and a `group` shared by related scenario variants. A group cannot cross
partitions. Every task also has `kind` and named boolean success `criteria`, which
are sent only to the grader. Put target passages and expected answers in a separate
rubric JSON mapping task IDs to grading evidence; its path is never passed to the
prediction command. Freeze tasks before construction and reserve final cases.

For Books, each partition covers `apply`, `inapplicable`, `disagreement`, and
`unsupported`, with at least one `references_required: true`. To compare targeted
loading, name the criteria detecting lost qualifications in `qualification_criteria`.

For Persona, task kinds are `projection`, `reasoning`, `commitment`, `scope`, and
`identity`. Projection IDs must match the existing source split's development/test
IDs exactly. Additional behavioral tasks belong to the same partition discipline.
Use metadata described in Persona’s `references/behavioral-evaluation.md` when preparing those tasks.
Identity tasks use only the `identity` criterion; candidate names and the anonymous answer are
the grader’s evidence, and the expected actor is never sent.
Add `subject`, `identity_candidates` (target plus at least two plausible neighbors),
and `neighbors: [{"id":"neighbor1","name":"...","prompt":"Think like ..."}]`.
Neighbor conditions receive the same task and facts but their own minimal role
prompt. The baseline is a minimal prompt for the target; it is reported separately.

Keep one persistent `--runs-root` per project. The runner claims each final scenario
group before any prediction call, including failed attempts, and rejects reuse even
if the suite is edited or extended. Development runs can repeat. If a final run
informs revision, retire its groups to development and obtain new final cases.
Changing group IDs or moving to a fresh registry does not create independence.
This local check cannot detect unrecorded prior reading, pretraining exposure or
an operator deleting the registry; record those limitations honestly.

## Commands

Run from the tool repository; `RUNNER` is `tools/evaluation_runner.py` for Books or
`scripts/evaluation_runner.py` for Persona. These examples use an explicit endpoint
and model chosen by the operator:

```bash
python3 "$RUNNER" predict /path/to/runtime-skill --suite suite.json \
  --runs-root /path/to/fidelity-ledger/runs --endpoint "$EVALUATION_ENDPOINT" \
  --model "$EVALUATION_MODEL" --kind books --phase development --targeted
python3 "$RUNNER" grade /path/to/predict-RUN --suite suite.json --rubric rubric.json \
  --runs-root /path/to/fidelity-ledger/runs --endpoint "$EVALUATION_ENDPOINT" \
  --model "$GRADING_MODEL" --reviewer reviewer-1
python3 "$RUNNER" verify /path/to/predict-RUN
```

Use `--kind persona` without `--targeted` for Persona. Once development is complete,
use `--phase final` to open the reserved partition. Each task/condition starts a
new message list; retrieval continues within that task only. All response records
are saved before any grading. Grade requests omit condition names and runtime
content, and use randomized presentation order. Identity requests present candidate
names but hide the expected actor. Blinding cannot conceal identifying prose itself.

The prediction run saves the runtime snapshot, prompts, full request/response
events, retrieved source hashes and line ranges, provider usage, status and a hash
manifest. Grade runs refer to the prediction manifest and save their own full
request/response events. No bearer credentials are written to records. Files use
exclusive creation and read-only permissions; reruns get new directories. The
manifest detects edits, missing files and additions. This is write-once,
tamper-evident recording, not a defense against the machine owner's ability to
change files and recompute hashes. Do not call it cryptographic proof of honesty.

## Human review and exports

A grader marks ambiguous judgments `disputed: true`. Export blocks unresolved
judgments. To correct a result, supply a JSON object keyed by `task-id/condition`;
each correction has `criteria`, integer `score` (0/1/2), `reviewer`, and `rationale`.
Identity corrections can also supply `choice`. The review command creates a new
sealed child record; it does not alter the original grade:

```bash
python3 "$RUNNER" review /path/to/grade-RUN --corrections corrections.json \
  --runs-root /path/to/fidelity-ledger/runs
python3 "$RUNNER" export-books /path/to/predict-RUN /path/to/grade-OR-review-RUN \
  --out acceptance-results.json
python3 "$RUNNER" export-persona /path/to/predict-RUN --suite suite.json \
  --grades /path/to/grade-reviewer1 /path/to/grade-reviewer2 --out fidelity-fragment.json
```

Persona export produces projection and behavioral fragments. Place the projection
under `projection.gate` for development or `projection.final` for final; use final
behavioral results under `behavioral`. Preserve the run manifest identifiers in
the human ledger. Different reviewer grades on non-identity criteria require
explicit review before export. Identity keeps separate blind choices, including
disagreements, because recognition accuracy is the measurement.

For verified Books final acceptance, use the sealed records directly:

```bash
python3 tools/acceptance_suite.py /path/to/runtime-skill --suite suite.json \
  --prediction-run /path/to/predict-RUN --grade-run /path/to/grade-OR-review-RUN
```

Operator-supplied version 1 results remain development records. They cannot claim
independent final acceptance. The runner does not prove that the final responses
are good; that depends on valid tasks, meaningful rubrics and review. Unit tests
use a simulated endpoint and demonstrate transport/isolation mechanics only.
