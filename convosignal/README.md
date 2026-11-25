# ConvoSignal

ConvoSignal is a local Python CLI that classifies and safely filters agent
questions, then evaluates retained user goals and conversations as **Satisfied**,
**Dissatisfied**, or **Neutral** with source-turn evidence. It supports offline
snapshots and MLflow traces, plus a Databricks model-serving chat endpoint.

The software and comparison tools are implemented. Real-world accuracy remains
unvalidated: no independently labeled real-conversation dataset was supplied.
The bundled fixtures/fake model demonstrate behavior, not judge accuracy.

## Install and run offline

Requires Python 3.11 or 3.12 and uv. From `convosignal/` in this checkout:

```bash
uv sync --locked
uv run python -m convosignal demo --output-dir demo-results
uv run pytest
```

The demo needs no credentials or network. It loads bundled synthetic traces and
explicit fixture evidence, rather than guessing labels from keywords. It includes
10 conversations: 1 Satisfied, 1 Dissatisfied, 4 Neutral, 3 skipped, 1 intentional
model-error case. Six evaluated conversations form the outcome denominator.
`demo` exits zero when it successfully demonstrates these cases; ordinary
`evaluate` exits 1 if any conversation has an operational error.

The demo explicitly accepts only its bundled synthetic example policy. Normal
`propose` never accepts anything automatically, and existing outputs require
`--overwrite`. Offline success does not establish live connectivity.

## Portable replay, reports and checkpointed evaluation

The installed `convosignal` command supports a portable workflow with no private
script imports or developer-specific paths:

```bash
uv run convosignal demo --output-dir runs/example
uv run convosignal report --run-dir runs/example \
  --metadata report.example.json --output-dir runs/example-report
```

This produces offline HTML and editable Word summaries/explorers, plus CSV/JSON
and a source-bound manifest. Edit the explicit report metadata for your agent.
`replay --run-dir ... --output-dir ...` reproduces saved labels without model
calls. `acquire` freezes MLflow snapshots; `batch-evaluate` adds atomic checkpoints
and guarded `--resume`. The batch command defaults to rules 3; existing `evaluate`
still defaults to rules 2. Fresh LLM extraction may produce different evidence.

See [Running and reproducing ConvoSignal](docs/Reproducibility.md) for exact
commands, configuration, missing-data behavior, retry rules, error exit codes,
private-data handoff and clean-install checks. Human accuracy validation remains
pending. A portable application is not a validated measurement of user feelings.

## CLI workflow

All commands support `--help`. From a fresh checkout, exercise manual review with
fixture-backed proposal generation:

```bash
uv run python -m convosignal propose \
  --trace-json src/convosignal/fixtures/demo_traces.json \
  --fake-responses src/convosignal/fixtures/demo_responses.json \
  --output proposal.json
# Review/edit proposal.json: categories, excluded IDs and standalone examples.
uv run python -m convosignal accept --input proposal.json --output taxonomy.json
uv run python -m convosignal classify \
  --input-jsonl demo-results/conversations.jsonl \
  --taxonomy taxonomy.json --filter-policy filter_policy.json --output-dir classified
uv run python -m convosignal evaluate \
  --input-jsonl demo-results/conversations.jsonl \
  --taxonomy taxonomy.json --filter-policy filter_policy.json \
  --fake-responses src/convosignal/fixtures/demo_responses.json --output-dir results
```

The last command returns 1 for the intentional invalid-response fixture and still
writes all records. Inspect `summary.json` and `evaluations.jsonl`. `classify`
requires no model. `evaluate` runs classification/routing automatically and consumes
that same fixed input. `--routing-snapshot PATH` validates cached routing against
authoritative input, taxonomy, policy, versions and rows; mismatches fail.

For question-only snapshots, use `classify --input-jsonl questions.jsonl
--input-kind questions ...`. Records must be grouped contiguously by conversation,
as in this tool's output; interleaved groups are rejected rather than reordered.
Question-only input is explicitly rejected for satisfaction evaluation. Supply
conversation snapshots with assistant/tool context instead.

## Connect MLflow and Databricks

Copy `config.example.toml` to a private local path, replace placeholders, and use:

```bash
databricks auth login --profile YOUR_PROFILE
uv run python -m convosignal --config private/config.toml doctor --llm
uv run python -m convosignal --config private/config.toml propose --output proposal.json
# Review proposal.json and explicitly accept it as above.
uv run python -m convosignal --config private/config.toml evaluate \
  --taxonomy taxonomy.json --filter-policy filter_policy.json --output-dir results
```

Alternatively copy `.env.example` to `.env`, edit it, then run with
`uv run --env-file .env python -m convosignal ...`. MLflow tracking URI and experiment
ID, serving endpoint, extraction shape/paths, bounds and output directory are
configuration, not hard-coded resource identifiers. TOML settings are overridden
by the documented environment variables. `--config` goes before the subcommand.

Authentication uses standard Databricks SDK/MLflow configuration: CLI profile,
host/token, or the SDK's other supported standard methods. No application-specific
credential format is required. MLflow and serving are separately configured even
when they share a profile. Permissions needed: experiment trace read, access to
trace artifacts, and query permission on the selected chat endpoint.

`doctor` checks configuration and, when configured, searches/downloads at most one
MLflow trace. `--llm` adds a small synthetic chat probe containing no trace data.
It reports each integration separately and exact installed versions, without
printing credentials. An endpoint that specifically rejects temperature gets one
disclosed retry without it; unrelated errors do not trigger that fallback.

Tested integration versions: **mlflow-skinny 3.18.0**, **databricks-sdk 0.170.0**,
**Pydantic 2.14.4**; exact dependencies are in uv.lock. SDK signatures were inspected.
MLflow reading and serving were verified separately in the configured workspace,
and one synthetic conversation passed through live evidence extraction and rules.
This does not validate real-user satisfaction accuracy or every endpoint/shape.

## Supported source shapes and ordering

Offline `--trace-json` defaults to chat shape:

```json
[{"trace_id":"synthetic-1","timestamp_ms":1000,"messages":[
  {"role":"user","content":"Compare weeks"},
  {"role":"assistant","content":"Synthetic comparison"}
]}]
```

Set `--shape interaction` for normalized exports with a `spans` list containing
one `interaction` root. The adapter reads `inputs.query` and `outputs.answer`
relative to that root, configurable via `question_path`/`answer_path`. Tool spans
named `tool:*` preserve output/result and status as tool evidence between query
and answer in supplied span-list order. Raw tool arguments/root configuration are
not exported. Missing final output/source ERROR marks incomplete context.

Live SDK objects are normalized into these shapes. For live chat input,
`messages_path` is relative to root-span inputs; offline chat paths are relative
to the record. Supported paths use dotted keys and numeric list indices such as
`data.0.messages`, without wildcards or literal dotted keys. Message content must
be text and roles user/assistant/tool; unsupported shapes/roles/structured content
produce actionable failures rather than guessed questions. Only user messages
feed taxonomy/classification; all nonblank requests count, without requiring `?`.

Traces sort by `(timestamp_ms, trace_id)` before stable grouping. Conversation
groups use first-trace order with message order retained within each. Explicit
snapshots preserve file order. Default boundary is one trace per conversation.
A configured `session_path="session_id"` merges only explicit session IDs; no
proximity joins occur. Live context is bounded by limit/time window, with merged
sessions marked incomplete because outside-window history is not fetched.
Timestamp ties at a bounded server page boundary follow the server's selection.

Identical native turn-ID captures are deduplicated only when role/text agree;
conflicts fail. Repeated text with distinct IDs remains real traffic. Generated
IDs are based on source trace and position. Export overlapping histories with
stable native IDs, or select non-overlapping snapshots; no text-based deduplication
is used to guess conversation history. Counts expose blanks, duplicates, source
failures and extracted messages. Download/extraction failures remain visible
operational errors, with any unaffected conversations still evaluated.

The trace limit applies before explicit `excluded_users` filtering. No test-user
or shared-A2A identity is silently excluded by default. Configure test exclusions
explicitly and inspect provenance counts; an email identity does not prove real
human traffic. Increase the limit if exclusions leave no eligible source data.

## Taxonomy and safe filtering

Proposal sampling collapses whitespace, truncates to 300 characters, deduplicates
case-insensitively after truncation, and selects up to 120 distinct questions in
order. The response is validated/normalized; missing set_aside warns and defaults
to false. Actual coverage, unmatched markers and unused types are reported.
Taxonomy generation can vary; temperature zero does not guarantee determinism.

Classification uses longest **literal substring** markers, keeping first-declared
type/marker order on equal-length ties. It has no per-question model call.
Unmatched questions remain unclassified and eligible. Category assignment is
separate from filtering: any exact accepted category ID can be included/excluded
via proposal.filter_policy.excluded_type_ids, then explicitly accepted again.

Exclusion additionally requires a normalized whole-turn match to an accepted
standalone example. Partial/ambiguous or mixed included/excluded requests remain
eligible. Excluded turns in retained conversations become context_only, preserving
thanks, rejection and corrections without opening excluded goals. Excluded-only
conversations bypass the satisfaction model. Review seeded examples carefully;
matching a category is not evidence that a compound request is safe to discard.

Canonical SHA-256 hashes use UTF-8 JSON, sorted object keys, compact separators,
preserved arrays, no NaN, unescaped Unicode. Taxonomy hashes cover ordered types,
names, markers, asks_for and flags, excluding descriptive prose. Policy hashes
include overrides and normalized examples. Input hashes cover full ordered source
turns/tool evidence, source references, completeness and diagnostics.

## Evidence, rules and output

The LLM returns only scoped goals/events with real source citations; the application
attaches immutable turns and derives labels in Python. It keeps task outcome,
requirements, user response, factual correctness and recovery separate. Citation
validity alone cannot prove that an interpretation is semantically justified.

- Acceptance/use supports Satisfied absent material contradiction; correctness
  can remain unverified. Bare thanks, permission, silence or a new task alone do not.
- Attributed unresolved rejection supports direct Dissatisfied; independently
  supported unresolved material failure supports inferred Dissatisfied.
- A concrete same-issue repair without confirmation yields Neutral /
  recovery_unconfirmed; accepted/useful repair confirms recovery. Earlier failures
  remain in the saved evidence.
- Acceptance conflicting with independently proven failure yields Neutral /
  conflicting_evidence. Missing context, silence and mixed goals have separate
  reasons; unrelated later success cannot repair an earlier goal.
- Excluded/no-eligible conversations are skipped, and operational failures are
  errors. Both have null labels. Source-agent errors are task evidence, distinct
  from evaluator failures. Partial evaluation errors preserve completed goals
  without aggregating only the successful subset.

Schema/citation failures get one repair attempt with diagnostics. Temperature
fallback is specific and remembered, limiting application-level serving queries
to at most three per evidence request including one schema repair. SDK transport
behavior is SDK-managed. Oversized inputs fail visibly rather than dropping turns.

Each evaluation run writes:

| File | Contents |
| --- | --- |
| conversations.jsonl | Ordered authoritative source/context snapshot |
| questions.jsonl | User questions with source IDs and positions |
| routing.jsonl | Per-question category, decision/reason and policy/taxonomy hashes |
| routing_snapshot.json | Cached routing bound to all relevant inputs |
| evaluations.jsonl | Status/label, goal results, evidence, raw responses and errors |
| summary.json | Separate question/goal/conversation counts, outcome shares and coverage |
| manifest.json | Source bounds, versions, hashes, model and fallback diagnostics |

Each saved result includes `evaluation_status` (and consistent internal `status`).
See `schemas/evaluation_record.schema.json` for persisted JSONL and the other
schemas for source, policy and evidence contracts. Regenerate with:

```bash
uv run python -m convosignal.schemas --output-dir schemas
```

`input = evaluated + skipped + error`; `evaluated = Satisfied + Dissatisfied +
Neutral`. Outcome shares use all evaluated conversations, including Neutral.
Skipped/error shares use input conversations. Zero evaluated means null shares.
Goal metrics have their own denominator, explicitly including completed goal
results in error conversations. Multi-category conversations use a separate
bucket rather than additive double-counting. These inferred labels are not survey
response rates.

Taxonomy generation sends sampled **user text only** to the configured endpoint.
Evaluation separately sends retained user/assistant turns and available tool text.
Raw responses/artifacts may contain sensitive data. Use private local directories;
results/, demo-results/, classified/, runs/ and private/ are Git-ignored here.
Only sanitized/synthetic fixtures belong in Git. Remove private outputs according
to your retention policy; the tool does not upload them or schedule retention.
Terminal output contains aggregates/status, not account details or credentials.

## Independent review

Create a template without predicted labels, then have a reviewer read the matching
source conversations independently and fill in label/reviewer/reason:

```bash
uv run python -m convosignal review-template \
  --predictions results/evaluations.jsonl --output private/reviews.jsonl
uv run python -m convosignal compare \
  --predictions results/evaluations.jsonl --reviews private/reviews.jsonl \
  --output private/comparison.json
```

Labels are exactly Satisfied, Dissatisfied or Neutral. Records include conversation_id,
input_checksum, reviewer, annotation_source="human" and optional goal_id for
`compare --unit goal`. Optional existing_judge_label enables a separate baseline
comparison. Snapshot mismatches and duplicate IDs fail. Technical failures/skips
stay outside three-class metrics and remain in coverage; undefined precision/recall
is null. Reports include all three classes, confusion matrix, sample sizes,
Neutral/unknown shares and coverage. Templates are intentionally invalid until
completed; no human labels are bundled or fabricated. Freeze a holdout and agree
quality thresholds before examining it. Comparison labels never enter prompts.

## Troubleshooting and development

- No extracted questions: inspect shape/paths, extraction diagnostics and traffic
  exclusions. Unsupported records are errors, not clean skipped inputs.
- Checksum mismatch: review/edit the proposal and explicitly accept again; do not
  patch hashes or silently reuse stale routing.
- Authentication/model failures: run doctor and doctor --llm separately; confirm
  experiment/artifact and endpoint permissions. No generic fallback judge exists.
- Existing files: choose a new output directory or explicitly request --overwrite.
- Invalid evidence: inspect local raw responses/citations and schema errors; do not
  turn model failures into Neutral or lower the rule gate to make a run pass.

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```

Tests block network connections and use fake adapters; live probes are explicit.
To add a provider, implement `llm.ChatClient.complete(system, user)` and supply a
model_identifier; reuse the evidence validation/rule pipeline. No provider registry
or orchestration framework is needed. See [product spec](docs/Prod-Spec.md),
[architecture](docs/Architecture.md), [milestones](docs/Milestones.md), and the
preserved [original brief](docs/original-brief.md).

## Revised criteria and comparison

The revised policy is available with `evaluate --rules-version 3`; version 2
remains the default for existing callers and saved records replay under their
declared policy. Version 3 can infer satisfaction from supported completion
without manufacturing user feedback. Essential factual claims need corroboration;
complete grounded drafts can qualify from the delivered content. Cited honest
inability stays Neutral unless an actual failure or rejection also applies.
Rejection recovery, known contradictions and mixed-goal rules remain explicit.

Saved evidence uses schema 1/rules 2 or schema 2/rules 3, with separately versioned
prompts and validation. The published revision schemas describe cited limitations,
deliverable scope and relevant-context evidence. Structural citations are not
proof of semantic accuracy.

```bash
uv run python -m convosignal compare-runs \
  --baseline original/evaluations.jsonl --baseline-source original/conversations.jsonl \
  --predictions revised/evaluations.jsonl --source revised/conversations.jsonl \
  --output comparison.json
uv run python -m convosignal review-packet \
  --predictions revised/evaluations.jsonl --source revised/conversations.jsonl \
  --output-dir independent-review
uv run python -m convosignal compare \
  --predictions revised/evaluations.jsonl --reviews independent-review/reviews.jsonl \
  --review-sampling unknown --review-context independent-review/review_context.json \
  --output reviewer-comparison.json
```

Keep the review packet apart from predictions until independent human annotations
are frozen. The conversation-level review gate requires 90% precision and at least
30 reviewed predictions for each non-Neutral class. Reports include Wilson 95%
intervals, coverage and sampling limitations. Review context must bind the source
checksums and establish a blind, frozen holdout prepared before tuning. The packet
starts with unknown context and false provenance declarations; record only facts
that can actually be established. Exploratory or missing review context cannot
pass the gate even with high precision. Missing reviews keep the gate pending;
goal-level comparison cannot pass this conversation-level gate. The original
100-session comparison is exploratory and has no Satisfied percentage target.

## Historical real-data pilots

The opt-in version 3 comparison on the same frozen 100 sessions produced
**12 Satisfied, 15 Dissatisfied and 66 Neutral**, plus 7 skips and no processing
errors. All positive conversation judgments are inferred. Twelve former Neutral
conversations became Satisfied, 26 former Dissatisfied became Neutral, and one
former Neutral became Dissatisfied. All 93 original and 93 revised evaluated
records passed source/replay checks under their respective policies.

The comparison used fresh model evidence extraction, so changed counts combine
new rules and interpretation variation. They do not establish improved accuracy
or changed user feelings. The original predictions are preserved. The private
report and 93 blank independent-review forms are in `private/criteria-v3-20261124/`;
independent validation is pending. All 181 tests pass on Python 3.11 and 3.12.

The 2026-11-24 operational pilot processed 12 frozen attributed sessions and
40 user messages. After separately documented error retries, 11 conversations
were evaluated and one capability-only conversation was skipped: 0 Satisfied,
8 Dissatisfied and 3 Neutral. All eight Dissatisfied judgments infer unmet tasks;
they do not establish explicit user dissatisfaction or measured label accuracy.
Independent human review is still pending, including conditional requests and
honest unavailable-data responses. Sensitive sources, original baseline, retry
provenance, report and blank review packet remain in the Git-ignored
`private/real-pilot-20261124/` directory.

Validator 1.1 permits fulfillment and correctness verification on the same answer
while preserving conflict checks. Prompt v2.2 clarifies required correctness
references. Business verdict rules are unchanged. See the
[pilot milestone notes](docs/Milestones.md#real-data-operational-pilot--2026-11-24).

The subsequent 100-session expansion contains 173 user messages: 93 conversations
were evaluated (0 Satisfied, 40 Dissatisfied, 53 Neutral), 7 skipped and none
failed processing. The sample includes the original 12 sessions and 88 additional
ones, with unchanged rules, prompt and accepted taxonomy. Of 40 Dissatisfied
conversations, 39 rest entirely on inferred unmet tasks. A partial productive-use
signal remains Neutral under the implementation's all-requirement scope gate;
review that strictness before interpreting zero Satisfied as user sentiment.
The taxonomy leaves 83 messages unclassified, all retained for evaluation.
The private report, evidence audit and blank independent reviews are under
`private/real-pilot-100-20261124/`. Human accuracy validation is still pending.
