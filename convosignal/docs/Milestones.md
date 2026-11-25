# Milestones — ConvoSignal

## Standalone repository publication — 2026-11-24

- [x] Close the unmerged campaign-agent PR #53 after owner scope correction.
- [x] Prepare the standalone repository with the package, specs, tests, and CI.
- [x] Verify the standalone package for publication to ConvoSignal main.
- [x] Publish to ConvoSignal main and fast-forward the existing Desktop checkout.

Both Python 3.11 and 3.12 pass all 200 offline tests. Ruff lint/format, strict
mypy, source/wheel builds, and the installed-wheel demo/replay/report check pass.
The installed package exports HTML, DOCX, CSV, and JSON outside the checkout.
CI repeats these checks on pushes to the standalone repository.

Publication commit: `1182219`. The first standalone Actions run could not start
either job: GitHub reported failed recent account payments or a spending limit
that needs increasing. This is an account-level block; remote checks have not run
in this repository. Local checks above passed. Restore Actions availability and
rerun the workflow to complete remote verification.

Private snapshots and generated reports are excluded. Existing independent human
accuracy validation remains pending.

## Portable workflow hardening — completed, 2026-11-24

- [x] Promote source-bound replay and safe Unicode JSONL reads.
- [x] Add explicit snapshot acquisition and resumable evaluation checkpoints.
- [x] Package portable HTML, Word and CSV/JSON report exports.
- [x] Add synthetic failure/resume/security/round-trip tests and CI.
- [x] Verify a clean installed wheel and offline historical report regeneration.
- [x] Document configuration, reproduction, recovery and remaining accuracy gate.

Verification: 200 tests pass on Python 3.11 and 3.12 with network connections
forbidden. Ruff lint/format and strict mypy pass; supplemental Pylint error checks
pass for the new package modules. Source/wheel builds contain all report assets
and no private/runtime files. The clean installed wheel runs demo, replay and
HTML/DOCX/CSV/JSON exports outside the checkout. CI records the same two-version
matrix and installed-wheel smoke test. The initial campaign-agent PR passed its
remote checks but was closed unmerged after the owner corrected the destination.

The portable code independently replays all 347 classified historical records
and regenerates all 993 trace rows with identical counts (56/59/232 conversation
labels; 15 skipped; 13 errors). Browser verification covers all filters, exact
prompt/answer inspection, CSV/JSON, pagination, final-sample search, mobile
layout, a one-page printable PDF and zero JavaScript exceptions. Historical
source, old reports, criteria/prompts and CLI defaults remain unchanged. No model
or source calls were needed for historical regeneration. Existing Account360
checks and dev bundle validation pass. Human accuracy validation remains open.

## Production report expansion — completed, 2026-11-24

Owner requested 1,000 interaction traces with session history retained. The full
2,899-header experiment scan found 993 eligible interactions, covering 375
conversations and 68 normalized attributed user IDs. UTC prompt dates are
2026-06-12 through 2026-11-24. Production stage is owner-declared and supported by
the experiment name. Source contains 970 answers; 23 answers were not recorded.

Applied unchanged opt-in version 3 rules/prompt. Initial results and interrupted
attempts are preserved. Five operational failures received one separate recovery
run; invalid evidence was not retried beyond the established repair allowance.
Final conversation results: 56 Satisfied, 59 Dissatisfied, 232 Neutral, 15 skipped,
13 processing errors. Associated interaction-row counts: 85 Satisfied, 95
Dissatisfied, 664 Neutral, 16 skipped, 133 Error. These are conversation decisions
associated with trace rows, not independent prompt ratings or actual user votes.

All 993 prompts and captured answers are exported exactly; every evaluated
conversation (347) replays identically with source and policy hashes checked.
The private report includes a printable one-page summary with three research
references, an interactive explorer with inspect views, CSV/JSON exports, and
verification records. Browser checks pass for filters, last-sample search,
pagination, exact prompt/answer inspection, matching CSV/JSON exports, mobile
layout and a one-page PDF; no JavaScript exceptions occurred. Existing 181
ConvoSignal tests, lint/format and strict types pass; Account360's three tests,
lint/format, types and dev bundle validation pass. Private helpers pass Ruff
checks apart from intentionally unwrapped HTML literal line lengths.

Private source/report: `private/final-1000-v3-20261124/`. Desktop delivery uses
`Campaign-Production-Report-v2/`. No hosted publication or source-system writes.
Independent human validation and the 13 unclassified conversations remain open.

Editable Word exports were subsequently requested and delivered as
`One-Page-Summary.docx` and `Explore-Every-Sample.docx` in the same Desktop
folder. The sample document has 993 sample sections and 375 linked conversation
sections; all 993 prompts and 970 captured answers round-trip exactly, including
line breaks, tabs and Unicode. All internal bookmark links resolve and the
summary retains three clickable research citations. Both packages pass XML/ZIP
validation and the native macOS Word importer; the summary's rendered preview
was visually checked. No source refetch, model call, dependency or rule change.

Last updated: 2026-11-24
Current state: C0–C3 and functional C5 delivery are complete. C4 comparison
tooling and the operational real-data pilot are complete; independent
accuracy validation still awaits human labels.

The separate 100-conversation operational expansion is complete, using unchanged
accepted taxonomy/policy, prompt v2.2 and rule version 2. Independent human
validation remains open; details follow below.

Current planning work: all 18 grill-with-docs decisions are agreed in the
[consolidated plan](criteria-revision-plan.md) and published as a
[ready-for-agent spec](../../.scratch/convosignal-criteria-revision/spec.md).
The revised rules are implemented behind explicit version 3 selection; version 2
remains the default and its replay path is preserved. The first comparison reuses
the frozen 100 sessions; independent review requires 90% precision for each
predicted non-Neutral class and at least 30 reviews per class. There is no positive
label quota. Functional delivery and independent validation remain separate.

All nine tickets were published when the user requested implementation, with
their [blocking edges](../../.scratch/convosignal-criteria-revision/issues/README.md).
All nine tickets are implemented and available for review. The revised run has
completed; independent human validation remains pending.

Planning verification: git diff --check passes. The unchanged ConvoSignal core
passes 148 tests, lint/format and strict types; Account360 passes 3 tests,
lint/format, types and dev bundle validation. No revised rules or new pilot run
were implemented during the interview.

## Revised criteria delivered and compared

All nine published tickets are complete. Version 3 is opt-in; version 2 remains
the default and genuine historical replay is preserved. Standards and spec reviews
ran independently; their findings were fixed and follow-up reviews found no
remaining issues. See the [review record](../../.scratch/convosignal-criteria-revision/implementation-review.md).

On the same frozen 100 sessions / 173 user messages, with unchanged taxonomy and
filter policy, the revised run has 93 evaluated, 7 skipped and 0 processing errors:
12 Satisfied, 15 Dissatisfied and 66 Neutral. All 12 positive conversations rely
on inferred evidence. At goal level the fresh extraction has 148 evaluated goals:
32 Satisfied, 38 Dissatisfied and 78 Neutral. This segmentation differs from the
original model extraction; it is not an isolated rule-effect experiment.

Transitions: 12 Neutral to Satisfied; 26 Dissatisfied to Neutral; 1 Neutral to
Dissatisfied; 14 unchanged Dissatisfied; 40 unchanged Neutral; 7 unchanged skips.
All 93 evaluated baseline records and all 93 revised records replay identically
under their declared policies and retain authoritative source turns. Private
artifacts and 93 blank independent reviews are in `private/criteria-v3-20261124/`.

Verification: 181 tests pass on Python 3.11 and 3.12; lint/format, strict types,
schema freshness and source/wheel builds pass. Account360's 3 tests, lint/format,
types and dev bundle validation pass. Distribution inspection excludes private
pilot material. Review context now requires source-bound blind/frozen holdout
declarations; the original 100 sessions remain explicitly exploratory. No actual
independent annotations exist and the C4 validation gate has not passed.

Private audit artifact v1 is available locally at
`private/criteria-v3-20261124/artifact-v1/index.html`, with ZIP, CSV, JSON and
Markdown companions. It covers all 100 conversations, all 173 original user
prompts, agent replies, revised/original decisions, reasons and goal evidence.
Source matching, archived evaluator instructions, filters, search, pagination,
exports and responsive light/dark rendering were verified. Sites publishing is
disabled for this workspace, so no hosted page was created. Real campaign text
stays in the ignored private area; session identity metadata, raw tool outputs
and credentials are excluded from the report.

| Milestone | Deliverable | Exit condition |
| --- | --- | --- |
| C0 — Contracts and rules | Dependency proposal, schemas, pure verdict functions, paired fixtures | Full rule matrix passes, including recovery and conflicting evidence, without a model |
| C1 — Extraction and filtering | Offline adapters, proposal validation/acceptance, classification, safe routing, hashes | Counts reconcile; mixed/unclassified tasks survive; stale routing rejected |
| C2 — Offline workflow | Fake evidence adapter, validation, CLI, artifacts, schemas, README | Fresh-install demo covers all labels plus skipped/errors without credentials/network; every citation resolves |
| C3 — Live integrations | Verified SDK calls, bounded trace reader, provenance, context, model adapter, doctor | MLflow and model connectivity proven separately; failed downloads/invalid output remain visible |
| C4 — Independent evaluation | Private review format, frozen reviewed conversations, comparison command | Reproducible per-class precision/recall/confusion matrix with sample sizes and coverage; no label leakage |
| C5 — Delivery checks | Full brief checklist, docs, lockfile, .env.example, clean checks | Usable package; functional completion and empirical validation reported separately |

## Completed core

- [x] C0: Approve exact dependency additions before any manifest change/install.
- [x] C0: Implement versioned requirements/evidence contracts and goal chronology.
- [x] C0: Implement ordered verdict rules, aggregation and reason codes.
- [x] C0: Test paired cases and evidence consistency, not only final labels.

## Completed filtering

- [x] C1: Include extraction blanks, duplicates, malformed shapes, source ordering,
  proposal sampling/coverage, conservative policy overrides and cache rejection.
## Next

- [x] C2: Run one snapshot through both stages; report partial failures explicitly;
  emit required artifacts and store source turns for citation review.
- [x] C3: Obtain model endpoint configuration, verify SDK signatures and pin tested
  versions; inspect live trace and model results independently.
- [ ] C4: Obtain independently reviewed complete conversations, including genuine
  acceptance and recovery, separate provenance groups, freeze a holdout before
  tuning, and agree quality thresholds before inspecting holdout results.
- [x] C5: Run package tests, lint, format, types and offline demo; complete the
  root-required regression checks and Databricks bundle validation. Report
  pre-existing failures separately; do not weaken checks or change unrelated code.

No accuracy threshold or live satisfaction-rate claim is invented. C4 requires
human review input; a working CLI does not establish empirical validity.

## Done

- [x] User selected isolated convosignal/ location.
- [x] Saved original brief, revised semantics, architecture and staged plan.

Issue index: [ConvoSignal specification](../../.scratch/convosignal/spec.md).

## Planning verification — 2026-11-24

All local document links resolve; the preserved original brief matches the supplied
file byte-for-byte; git diff --check passes. Root-required checks were run in
account360/ using its existing environment (uv run --no-sync): pytest passed all
3 tests, Ruff lint/format passed, and mypy passed for 5 source files. Databricks
bundle validate -t dev returned Validation OK. These establish existing Account360
checks only; no ConvoSignal application or empirical validation exists yet.

## C0 implementation progress — 2026-11-24

Standard-library dataclasses and enums implement scoped chronological evidence,
structural citation validation, goal verdicts, mixed-goal aggregation and partial
error records. Eight behavioral tests pass. No dependency or manifest was added.
Remaining C0 work: full serialized schemas, complete evidence/outcome contracts,
overall-feedback attribution, scope-change/recovery edge cases and the remaining
acceptance matrix. Do not advance to C1 yet.

## C0 completion — 2026-11-24

The user authorized dependency changes for this session. Added an isolated
pyproject.toml and uv.lock, Pydantic-validated immutable evidence/output contracts,
published JSON schemas, source/result/role/scope validation, scoped requirement
replay, separate outcome/feedback/correctness, recovery and overall user feedback.
Structural errors preserve completed goals and produce a null overall label.

Verification: 50 synthetic contract/rule tests on Python 3.11 and 3.12; Ruff
lint/format and strict mypy pass; wheel/source builds pass. Account360's 3 tests,
lint/format, types and dev bundle validation pass. See README for core commands.
These tests cover C0 behavior, not C1 routing, C2 model-output handling or empirical
accuracy. The C0 acceptance matrix's extraction/filtering rows remain C1 work.

## C1 completion — 2026-11-24

Implemented explicit offline chat/interaction shapes and dotted paths, ordered
source turns including tool outputs, stable source IDs and extraction diagnostics.
Added sampling, proposal parsing/coverage, explicit accepted taxonomy/policy files,
canonical hashes, longest-literal assignment, conservative whole-turn routing,
context retention, cache rejection and reconciled traffic/conversation reports.

C1 writes source/questions/routing snapshots and summary artifacts through the
library API. It does not call a model or claim live MLflow connectivity. C2 owns
the combined CLI and satisfaction pipeline; C3 owns live integrations.

Verification: 112 tests on Python 3.11 and 3.12 with network connections forbidden;
lint/format, strict mypy, source/wheel builds and schema freshness checks pass.
A temporary synthetic smoke run round-tripped proposal acceptance and routing
artifacts and reconciled 3 conversations into 2 eligible and 1 excluded-only.
Root-required Account360 tests/lint/format/types and dev bundle validation pass.
No runtime dependency was added.

## C2 completion — 2026-11-24

Implemented the one-command pipeline, versioned evidence prompt, explicit fake
responses, schema repair, immutable source attachment, source/category guards,
all required artifacts and aggregate reports. The bundled demo covers all three
labels plus excluded-only/no-eligible skips and an intentional model error.
CLI commands include propose, accept, classify, evaluate, demo and schema export.
Question-only snapshots classify but are rejected for satisfaction evaluation.

## C3 completion — 2026-11-24

Implemented settings/env/TOML, SDK chat, explicit header/artifact reads, bounds,
source errors, provenance and independent doctor probes. Inspected installed
signatures: mlflow-skinny 3.18.0, databricks-sdk 0.170.0, Pydantic 2.14.4.
Live MLflow and serving probes succeeded separately. The endpoint rejected the
temperature parameter; the disclosed parameter-specific retry succeeded. One
synthetic conversation also passed live evidence extraction and rule replay.
No real-data taxonomy was automatically accepted and no real accuracy is claimed.
Live session merging remains explicitly bounded/incomplete; no outside-window
history is fetched. Runtime workspace/model identifiers are private configuration.

## C4 tooling delivered; empirical validation pending — 2026-11-24

Implemented human review contracts, label-free review templates, snapshot-bound
comparison, goal/conversation units, precision/recall, confusion matrix, coverage,
Neutral/unknown shares and optional existing-judge comparison. No review labels
enter evaluation prompts. Synthetic tests establish the comparison calculations,
not human labeling quality or evaluator accuracy. No independently reviewed real
dataset/reviewers were supplied; this acceptance gate remains unchecked.

## C5 functional delivery — 2026-11-24

145 synthetic tests pass on Python 3.11 and 3.12 with network blocked, including
CLI/pipeline/provider failures and source protection. Ruff lint/format, strict
mypy, schema freshness, source/wheel builds and installed-wheel offline demo pass.
Existing Account360 tests/lint/format/types and dev bundle validation pass.
README, .env.example, config example, schemas, fixtures and uv.lock are delivered.
The demo reconciles 10 inputs = 6 evaluated + 3 skipped + 1 error, and 6 evaluated
= 1 Satisfied + 1 Dissatisfied + 4 Neutral. These are synthetic demonstration
counts, not production outcome rates. No deployment was performed.

## Real-data operational pilot — 2026-11-24

Frozen 12 attributed sessions / 40 traces / 40 user messages after excluding
known tests and shared/unattributed headers from a bounded 1,000-header scan.
Stage 1 reconciles 30 actionable and 10 set-aside questions: 30 evaluate,
8 context-only and 2 excluded turns. One capability-only session is skipped.

Baseline: 8 evaluated, 1 skipped, 3 errors. Preserved baseline artifacts and
all 8 valid verdicts. Targeted retries of the 3 errors produce a consolidated
rollup of 11 evaluated, 1 skipped, 0 errors: 0 Satisfied, 8 Dissatisfied,
3 Neutral. This combines versioned runs, not one new uniform evaluation.
All 8 Dissatisfied conversation judgments are inferred task failures, without
explicit user rejection. Conditional requests and unavailable-data responses
need independent adjudication; these counts are not user satisfaction rates.

Pilot exposed a validator collision between fulfillment and correctness on the
same answer. Validator 1.1 allows only that compatible pair; conflicting events
still fail. Prompt v2.2 clarifies mandatory answer references on correctness
events. Larger explicit capacity was used for one long session without truncation;
its missing source-agent answer still yields Neutral / incomplete_trace.
All 11 evaluated records retain authoritative source turns and replay identically.

Private artifacts: `private/real-pilot-20261124/pilot_report.md`, original baseline,
per-row origin/checksum map, consolidated predictions and a label-free review
packet for 11 eligible conversations. No human annotations or accuracy metrics
were fabricated. C4's independent accuracy gate remains open.

Pilot verification: 148 synthetic tests pass on Python 3.11 and 3.12;
ConvoSignal lint/format, strict types, schema freshness tests and source/wheel
builds pass. Account360's 3 tests, lint/format, types and dev bundle validation
pass. An additional repository-root Ruff scan found 10 pre-existing findings
in campaign/evaluation scripts and tests outside this workstream; those files
were not changed. Private pilot artifacts are Git-ignored and excluded from
package distributions.

## 100-conversation expansion completed — 2026-11-24

Selected 100 latest attributed sessions from 2,000 headers, including the original
12 plus 88 additional sessions. Three source-read failures recovered on one
bounded retry before model evaluation; original acquisition artifacts remain.
Final frozen source: 173 user messages. Every conversation used identical limits
and the existing mechanical repair allowance; no verdict-driven retries or tuning.

Results: 100 inputs = 93 evaluated + 7 capability-only skips + 0 errors;
93 evaluated = 0 Satisfied + 40 Dissatisfied + 53 Neutral. The 88 additional
sessions alone yield 82 evaluated (0 Satisfied, 33 Dissatisfied, 49 Neutral),
6 skips and 0 errors. All 93 evaluated records preserve authoritative turns and
replay identically. One overlapping label changed on fresh model extraction;
this is not an accuracy or user-satisfaction improvement claim.

Of 40 Dissatisfied conversations, 39 rely solely on inferred unmet requirements;
one includes a directly rejected goal. A second rejected goal appears inside
a mixed-goal Neutral conversation. There are 64 single-user-message sessions.
One goal records productive use of only part of its scope but stays Neutral
under the implementation's all-material-requirement acceptance gate. Review
that gate against the plain-language criteria before interpreting zero Satisfied.
No business rule was changed during this experiment.

The fixed taxonomy leaves 83 of 173 user messages unclassified; all remain
evaluation targets. This is a category-coverage gap exposed by the expansion.
Private report, original/final source snapshots, per-case manifests, interpretation
audit and 93 blank independent reviews are in `private/real-pilot-100-20261124/`.
C4's independent accuracy gate remains unchecked. The unchanged core passes all
148 tests, lint/format and strict types; the private runner passes Ruff checks.
Account360's 3 tests, lint/format, types and dev bundle validation also pass.
