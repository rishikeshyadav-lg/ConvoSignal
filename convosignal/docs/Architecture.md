# Architecture — ConvoSignal

## Standalone repository — 2026-11-24

The canonical repository is `rishikeshyadav-lg/ConvoSignal`. Retain the tested
`convosignal/` package layout and its locked environment; root documentation
routes contributors to that directory. The package has no campaign-agent runtime
dependency. Historical campaign/Account360 references below describe the original
development workspace, not requirements or deployments of this repository.

## Portable workflow design — 2026-11-24

Use existing validated conversation/evidence contracts and deterministic rules.
A run-artifact module owns UTF-8 JSONL reads, checksum/source/policy validation
and replay. A batch module checkpoints whole conversations atomically and binds
resume to source, policy, model, budgets and code. A report model separates
trusted source-derived counts from owner-declared agent/stage metadata; packaged
offline templates and a dependency-free Word writer consume that validated model.
Report generation performs no model calls. Snapshots use the existing bounded
MLflow reader and expose its incomplete-session semantics and failures.
Package all templates and synthetic examples, with no private pilot imports.
Use only existing dependencies; PDF remains browser printing of the summary
instead of requiring a locally installed browser or office application.

Batch cases include a contract hash and hashes of their complete artifact files;
resume verifies these before reuse, including completed error cases. Per-worker
model adapters reuse one authenticated workspace client and retain their own
parameter-fallback state. The final `completed/` directory is the canonical saved
run. Reports and replay publish new directories atomically. Report manifests bind
owner metadata, optional captured headers, source/policy and packaged templates;
Word ZIP timestamps are fixed so identical rendering inputs reproduce output
bytes in the same environment. Identity metadata is used only for source-derived
aggregate counts and is excluded from report payloads. Unknown source dates/users
and unknown archived prompt text remain explicitly unavailable.

## Production report expansion — 2026-11-24

Select up to 1,000 latest eligible interaction traces before evaluation; fetch
their session history through a fixed acquisition cutoff. Evaluate each distinct
session once with unchanged rules 3, schema 2 and evidence prompt v3.0. Preserve
private source/evidence/checkpoints and replay saved verdicts before reporting.
The explorer has one row per selected interaction and labels its associated
conversation decision explicitly; it does not invent independent prompt ratings.
One-page counts distinguish selected prompts, trace-associated decisions and
distinct conversation verdicts. Production stage is owner-supplied and supported
by the MLflow experiment name; user counts reflect normalized attribution IDs,
not verified unique humans. New reports remain local private HTML and printable
one-page output; source identities and credentials are excluded from exports.

The full 2,899-header scan found 993 eligible traces, spanning 375 conversations
and 68 normalized attributed IDs. Report that shortfall explicitly; do not add
known tests or unattributed traffic to reach 1,000. Each session's immutable
download checkpoint precedes its evaluation call, allowing remaining downloads
to overlap evaluation. Model calls began with four workers and continued with
eight; completed results were retained and four unfinished attempts preserved
before operational restart. The established repair allowance is unchanged;
there are no verdict-driven retries. Source acquisition resolves OAuth once in
memory to avoid concurrent CLI keyring refreshes; credentials are never exported.

Five baseline operational failures receive one separate recovery run: transport
failures or an explicit input-capacity guard, selected before seeing any recovery
label. Recovery keeps rules 3, prompt v3.0 and 16,000 output tokens, with a
1,000,000-character input ceiling and 600-second HTTP timeout. Four recovery
workers share one authenticated workspace client. Original cases remain intact;
the consolidated report records each final row's origin. Invalid evidence after
the existing repair opportunity is not retried or converted to Neutral.

The report also has editable DOCX exports built from its frozen data using
standard-library WordprocessingML/ZIP generation. Selected prompts and answers
appear once per sample; internal bookmarks link each sample to its conversation
decision, requirements, evidence basis and chronology. Goal details are stored
once per conversation to avoid repeating long histories. Companion JSON retains
full machine-readable events and evaluator prompt. Verification checks exact
source-text round trips, bookmarks, citation links and package structure.

Last updated: 2026-11-24
Status: Functional implementation complete, including offline CLI, live adapters
and comparison tools. Independent real-conversation validation is pending.

## Package boundaries

Isolated Python 3.11 project, own pyproject.toml and uv.lock. This matches the
campaign runtime without importing its local-only dependencies. Proposed runtime
dependencies: MLflow, databricks-sdk, Pydantic. Proposed development dependencies:
pytest, Ruff, mypy. Use standard-library argparse, json, hashlib, pathlib, tomllib.
Approve exact bounds before adding them. MLflow 3.12.0 was used in exploration;
it is not yet a tested ConvoSignal dependency.

Intended modules under convosignal/src/convosignal/:

| Module | Ownership |
| --- | --- |
| cli.py / __main__.py | Commands and readable errors |
| config.py / models.py | Configuration and versioned data contracts |
| traces.py | MLflow listing, downloads, pagination and diagnostics |
| conversations.py | Extraction, turn IDs, order, boundaries and provenance |
| llm.py | Databricks adapter and fake adapter contract |
| taxonomy.py | Proposal, coverage, validation, acceptance and hashes |
| routing.py | Literal classification and conservative policy routing |
| evidence.py | Prompt construction and evidence validation |
| verdicts.py | Pure goal/conversation rules; no I/O or LLM calls |
| pipeline.py | One snapshot through both stages and artifact persistence |
| reporting.py | Counts, denominators and independent-review comparison |

Keep cohesive modules; split only when complexity warrants. Existing campaign
code supplies trace-shape evidence, not a runtime dependency or purported full port.

## Extraction and boundaries

Configuration supplies tracking URI, experiment, time window, limits, root span,
question/answer paths and optional session key. Campaign records use
interaction.inputs.query and interaction.outputs.answer. Internal model calls
and assistant prompts must not become user traffic.

List headers, then explicitly fetch selected artifacts so download failures cannot
silently disappear. Paginate with verified SDK signatures. Order traces by timestamp
and trace ID; retain message order within traces and supplied offline snapshot
order. Record server tie-order assumptions at bounded page boundaries.

Stable IDs derive from trace ID, source position and role; retain native turn IDs.
Deduplicate duplicate capture by source identity, never genuine repeated text.
Merge only using configured session keys and reliable ordering. Additional context
fetches have explicit limits and record exhausted/truncated/unavailable history.
Sessions contain multiple goals. Tool evidence remains referenced; do not export
raw configuration. Unsupported schemas produce actionable diagnostics.

Explicit traffic filtering is separate from category policy. Campaign configuration
can exclude the known agent-evals-fix identity, but generic defaults cannot hard-code
it. Shared A2A provenance remains unknown unless verified; email identity alone is
not proof of human traffic. Report provenance cohorts separately.

## Pipeline and persistence

Read/load one conversation snapshot -> classify and route -> freeze checksums ->
extract structured evidence for retained conversations -> validate -> derive
verdicts in Python -> aggregate and persist.

Required outputs: questions.jsonl, routing.jsonl, evaluations.jsonl, summary.json.
Also save normalized conversations.jsonl to resolve citations/replay, and a run
manifest with cutoff, bounds, completeness, hashes and versions. Local output
directories are private and ignored by Git; only synthetic/sanitized fixtures are
committed. Excluded-only conversations bypass satisfaction extraction.

Canonical hashes: SHA-256 over UTF-8 JSON, sorted object keys, compact separators,
array order preserved. Select classification-relevant taxonomy fields exactly as
specified in the brief. Input hash covers ordered turns/tool evidence; policy
hash covers overrides and normalized standalone examples. Cache keys also include
extraction/routing versions. A changed input, taxonomy or policy invalidates routing.
Record prompt/model/rules/schema versions independently. Identical validated
evidence replayed through identical rules must reproduce verdicts.

## Model boundary and failures

Models propose taxonomies and extract evidence; Python owns labels and counts.
Trace content is untrusted data. Parse string/structured output, exclude reasoning
blocks, detect truncation, validate citations, roles, chronology and contradictions.
Assertions of acceptance/recovery must reference user turns and specific results.

Proposed limits: one evidence-schema repair retry and one temperature-free retry
only for explicit temperature rejection, with at most three transport attempts
per logical request. Authentication/unrelated service errors fail visibly.
Oversized inputs are rejected with diagnostics rather than silently truncated.
Never convert invalid evidence or missing artifacts into Neutral. API failure
coverage and incomplete historical-context cases remain distinguishable.

## CLI

Planned prefix: python -m convosignal.

| Command | Behavior |
| --- | --- |
| doctor | Config checks; independent MLflow read and optional synthetic model probe; disclose calls |
| propose | Reviewable taxonomy and policy candidates; no automatic acceptance |
| accept | Validate/save separate accepted artifacts; explicit overwrite flag |
| classify | Offline-capable classification/routing from accepted artifacts |
| evaluate | Both stages automatically on one conversation snapshot |
| demo | Credential-free synthetic workflow with fake evidence |
| compare | Saved predictions versus independent labels; no label leakage into prompts |

Document schemas and examples for question snapshots (classify) and conversation
snapshots (evaluate); reject question-only satisfaction input.

## Verification and live dependencies

Meaningful rule/validation tests plus an end-to-end offline test with network
disabled. Live reader/model probes are separate opt-in checks. Verify installed
SDK signatures and record exact tested versions before implementing calls.

Planned checks from convosignal/ after dependency approval/scaffolding:
uv run pytest; uv run ruff check .; uv run ruff format --check .;
uv run mypy src; uv run python -m convosignal demo --output-dir demo-results.
Root-required Account360 checks are separate. ConvoSignal needs no deployment.

## C0 implementation decision — 2026-11-24

Start the deterministic core with standard-library dataclasses/enums and unittest,
without adding dependencies. Run it with PYTHONPATH=convosignal/src and the existing
Python environment. Schema parsing and model evidence extraction remain pending;
these typed primitives do not certify semantic truth or real-world accuracy.

## C0 completion decisions — 2026-11-24

Use Pydantic dataclasses to preserve immutable positional Python contracts while
adding strict JSON parsing and TypeAdapter schema export. The only runtime
dependency is Pydantic >=2.12.5,<3 (tested/locked 2.14.4). MLflow/Databricks SDK
dependencies are deferred to C3. Rules remain independent of model/network I/O.

The package supports Python >=3.11,<3.13, verified on 3.11.16 and 3.12.14. C0
exports schema JSON with python -m convosignal.schemas --output-dir schemas; it
does not expose the future evaluation CLI. Installed development dependencies
are pytest, Ruff and mypy with exact versions in uv.lock.

## C1 decisions — 2026-11-24

- Offline input is an explicit normalized chat or interaction export shape.
  Unsupported structures fail visibly; the future SDK reader normalizes its own
  trace objects into that documented shape.
- Interaction tool spans named tool:* preserve their output/result and status as
  referenced tool turns between the root query and final answer, in supplied
  span-list order. Do not export raw tool arguments or root configuration.
- Sources sort by timestamp_ms then trace_id before stable session grouping.
  Conversation groups use first-trace order, with ordered messages inside each.
  Explicit conversation snapshots retain their supplied order. No proximity joins.
- Native IDs deduplicate identical captures only, not repeated question text.
  Conflicting captures fail atomically and mark the affected session incomplete.
- Accepted taxonomy.json and filter_policy.json are separate checksum-bound files.
  Proposals retain original model/sample metadata; acceptance recalculates hashes
  for reviewed edits. Loading changed accepted artifacts requires renewed acceptance.
- RoutingSnapshot binds complete normalized input (including tools/diagnostics),
  taxonomy, policy and versions. Validation recomputes deterministic routing and
  rejects any mismatch, including changed rows, rather than trusting cached metadata.
- C1 artifact saves preflight names and are exclusive by default. Filesystem
  failures are reported; a partial write is not a completed/accepted artifact set.

## C2–C5 implementation decisions — 2026-11-24

- ModelEvidence contains only goals and scoped overall feedback. Python attaches
  authoritative turns/versions; model-provided labels or replacement sources are
  rejected. Each requirement must originate in an evaluate-routed user turn.
- One schema repair retry includes mechanical diagnostics and the prior response.
  Provider/auth/truncation errors do not become Neutral or schema retries.
  A remembered temperature fallback yields at most three application queries
  across a schema repair. SDK transport retries remain SDK-managed.
- Use mlflow-skinny for client-side reads, rather than full MLflow server/scientific
  dependencies. SDK signatures and live probes were checked at installed versions
  3.18.0 / databricks-sdk 0.170.0. No real identifiers are package defaults.
- Live reads select bounded headers before local explicit user exclusions, then
  download each selected artifact explicitly. Failures become error records, not
  skipped traffic. Session histories outside the selected bounds are not fetched
  and merged sessions are marked incomplete. Trace and snapshot order are explicit.
- Evidence/response details remain in local JSONL. Persisted EvaluationRecord has
  evaluation_status plus the consistent internal status for compatibility. Its
  schema is separate from the pure Evaluation contract.
- Comparison consumes saved predictions and independent human-label files only,
  never model prompts. Review templates omit predictions. C4 needs external human
  annotations; no accuracy threshold is invented or silently bypassed.
- Runtime results/private/configuration directories are ignored by Git. The
  packaged fake responses and sources are explicitly synthetic fixtures.

## Pilot decisions — 2026-11-24

- Validator 1.1 permits distinct fulfillment and correctness_verified events on
  the same requirement/turn because they describe separate axes of one answer.
  Duplicate kinds and incompatible transitions remain errors. Correctness events
  still require result_turn_id, chronological citations and appropriate proof.
- Prompt v2.2 makes those result references explicit. Business verdict rules stay
  at version 2. Manifests record validation_version independently of schema/rules.
- Operational pilot retries reuse frozen conversations and retain original valid
  results. Per-record origins preserve actual input hashes, prompts and raw attempts;
  a mixed-run rollup must never be described as a single uniform evaluation.
- A long-source capacity diagnostic uses explicit higher limits without truncation.
  It does not change packaged defaults or repair missing source history.
- Initialize live SDK clients sequentially during pilot retries: concurrent CLI
  token-cache refresh failed before a request; the standard sequential retry passed.

## 100-session expansion — 2026-11-24

The expanded operational sample freezes the latest 100 attributed sessions before
evaluation, retaining the accepted taxonomy/policy and prompt/rule versions.
Trace acquisition is sequential to avoid CLI authentication-cache conflicts.
Evaluation uses four threads sharing one authenticated workspace, with separate
chat adapters and per-conversation artifacts. This changes throughput only.
Every case uses 400,000 input characters, 16,000 output tokens and the existing
single evidence-repair allowance; oversized/malformed cases stay visible errors.
Per-case snapshot hashes are preserved, alongside the full-cohort frozen hash.
No case is selected or retried because of its label. Original pilot overlap is
reported; independent accuracy validation still requires human annotations.

The first acquisition snapshot is preserved. Three transient source-read failures
were retried once against the same selected sessions and cutoff before evaluation;
`analysis_source.jsonl` and `analysis_protocol.json` freeze the final model input
and its checksum. There are no outcome-based retries. All 93 evaluated records
replay identically; fresh extraction changed one prior overlap label, demonstrating
that deterministic replay does not establish model interpretation stability.

An interpretation audit records partial productive use that remains Neutral:
the implementation requires scoped acceptance/use for every active material
requirement. This strict scope gate warrants independent semantic review against
the product wording. The pilot records that concern without changing verdict rules.

## Accepted criteria revision plan

All 18 decisions are consolidated in the [revision plan](criteria-revision-plan.md)
and the [ready-for-agent spec](../../.scratch/convosignal-criteria-revision/spec.md).
Implementation adds an opt-in version 3 rule path independently versioned
from its evidence prompt and contracts, retaining genuine version 2 replay.
Model observations must distinguish supported delivery, honest inability,
essential scope and relevant missing history; Python continues to derive labels.
Inferred satisfaction must not manufacture acceptance or read/session-end signals.

Evidence of completion depends on the task: relevant source support for essential
factual claims, and delivered content as evidence of requested drafting/format
completion. Structural citations alone cannot establish semantic support;
independent review checks interpretations.

The first comparison reuses the final frozen 100-session source with unchanged
accepted taxonomy/filter policy. New extraction and rules have new versions and
separate artifacts. Disclose fresh-extraction variation separately from deterministic
replay where compatible evidence permits it. Preserve historical predictions;
there is no positive-label percentage target.

Independent review is separate from functional delivery: conversation precision
at least 90% for each predicted non-Neutral class, with at least 30 reviews per
class and uncertainty/coverage reported. Reviewer judgments do not measure the
original user's feelings unless that user's feedback exists.

## Private decision audit artifact

The report exports user/assistant messages and decision evidence from frozen
records. User text is rendered as text, never executable HTML; session identity
metadata, raw tool payloads and connection configuration are excluded. The
self-contained HTML and companion exports remain in the ignored private area.
Sites creation is disabled for this workspace, so artifact delivery is local.

## Revision implementation

The original goal contract remains the version 2 input. A separate revision
contract extends goals with deliverable requirement IDs, cited external
limitations and goal-relevant context references. Factual requirements default
to needing independent correctness support; only observable content/format
requirements qualify by delivered content alone. Citation checks establish
structure, not semantic truth; independent review remains necessary.

Version 3 shares chronological requirement replay but uses a separate verdict
gate. It tracks rejection history separately from inferred failure and resets
verification when a different answer replaces a result. Correctness and concrete
repair can share a turn only under version 3 validation. Version 2 dispatch and
its original same-turn restrictions remain intact.

Evaluation defaults to version 2 and explicitly selects version 3 with its own
prompt, schema and validation identifiers. Saved evidence dispatches by its
declared rules. Sources, goals and report axes retain their original identities.
New compare-runs and review-packet commands use saved source-bound artifacts;
review packets contain blank reviews, source and label-free criteria guidance.
The comparison reports both rule replays and flags extraction variability.

Independent review reports the agreed class-specific gate and Wilson 95%
intervals on the reviewed sample, with sampling limitations disclosed. Goal-level
comparison cannot satisfy the conversation-level validation gate.

Review-context provenance is source-bound and separately serialized. The gate
requires a declared holdout, blind reviewers, frozen annotations and a holdout
frozen before tuning. Unknown/exploratory sets remain pending even if numeric
precision/sample thresholds pass. These are explicit operator declarations, not
automatically verified facts about reviewer independence.
