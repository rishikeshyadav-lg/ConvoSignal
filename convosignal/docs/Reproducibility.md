# Running and reproducing ConvoSignal

The CLI and all report assets are installed with the package. No developer's
Desktop, private script, browser executable or office application is required.
Python 3.11 and 3.12 are supported. Run the examples below from `convosignal/`
after `uv sync --locked`. Use a new output directory for every new operation.

## What “same outcome” means

`replay` and `report` read frozen source and evidence without calling MLflow or a
model. They check source coverage, source hashes, taxonomy/filter hashes, version
metadata, cited source turns and deterministic verdicts. A changed label or
incompatible saved evidence fails instead of silently being accepted.

Fresh model extraction can interpret the same conversation differently. Even
unchanged endpoint settings do not guarantee the same extracted evidence or
labels; a serving endpoint can also be updated externally. Neither a replay nor
an automated report establishes agreement with human reviewers or real feelings.
The independent human validation gate remains pending.

The original evaluation command still defaults to rules 2. The new batch command
explicitly defaults to rules 3. Always specify the version in operational scripts.
The rules and prompts have not been changed by this packaging work.

## Generate reports offline

```bash
uv run convosignal demo --output-dir runs/example
uv run convosignal report \
  --run-dir runs/example \
  --metadata report.example.json \
  --output-dir runs/example-report
```

The demo contains synthetic examples, including intentional skips and an error.
It does not need credentials. Edit the metadata file for your agent, stage,
source description and report date. Counts are derived from saved records; they
cannot be overridden in metadata. The explicit date makes regeneration stable.

Outputs:

- `One-Page-Summary.html`: criteria, research links, source details and counts;
  use browser Print / Save as PDF when a PDF is needed.
- `Explore-Every-Sample.html`: offline search/filter/inspect with actual captured
  answers, conversation context, goal states, reasons and evaluator prompts.
- `One-Page-Summary.docx` and `Explore-Every-Sample.docx`: editable Word documents
  with research links, headings, sample bookmarks and conversation links.
- `decisions.csv` and `decision-data.json`: human-readable export data, with raw
  tool outputs, identity metadata and provider attempts excluded.
- `manifest.json`: source/policy hashes, replay coverage, error/skip counts,
  output hashes and explicit absence of model/source calls during rendering.

`--formats html` or `--formats docx` selects one format; CSV/JSON/manifest are
always emitted. Word cannot represent illegal XML control characters, so a Word
export fails explicitly rather than silently deleting source characters. Source
text is never interpreted as HTML. CSV cells that could execute as formulas are
prefixed with an apostrophe; the JSON/HTML/Word source text remains unchanged.

The selected trace count can differ from the user-message count for chat-shaped
traces. Each selected trace row carries the final decision of its containing
conversation. Several trace rows may share one decision. Conversation counts
refer to distinct complete run records. Skips/errors have no satisfaction label;
they are never included in the Satisfied/Dissatisfied/Neutral denominator.

By default reports cover all captured trace groups. If the run contains a
`selection.json`, reports use those captured headers; `--selection PATH` can
supply the headers explicitly. Date bounds and normalized distinct user-ID counts
require captured headers. Without them, the report says “Not captured.”
Attribution is not proof of unique humans. Owner-declared stage/source text is
labelled separately from captured facts.

## Replay a saved run

A saved run directory contains these four files:

```text
conversations.jsonl
evaluations.jsonl
taxonomy.json
filter_policy.json
```

```bash
uv run convosignal replay --run-dir runs/example --output-dir runs/replayed
```

Exit 1 means the saved run contains processing errors, even when all classified
records replay correctly. Exit 2 means invalid input, a provenance/replay mismatch
or an integration failure. `report` returns zero when report generation succeeds;
that does not assert that every source row was classified. Inspect the counts.

For an internal historical run, securely supply its exact four files and its
captured `selection.json` to reproduce its source/date/user coverage. These
private files are intentionally not distributed with the library. A fresh clone
can reproduce the synthetic demo immediately; actual campaign results require
access to the original authorized snapshots. Do not substitute newly fetched
traffic and call it an exact replay.

## Freeze new MLflow input

Copy `config.example.toml` to `private/config.toml`, configure your own workspace,
experiment, source shape/paths, time window and excluded test identities, then:

```bash
databricks auth login --profile YOUR_PROFILE
uv run convosignal --config private/config.toml doctor --llm
uv run convosignal --config private/config.toml acquire \
  --output-dir runs/source
```

`acquire` freezes the read cutoff before listing headers and performs read-only
MLflow calls. It writes normalized conversations, captured headers, source
failures and checksum/coverage diagnostics. The trace limit is applied to headers
before explicit user exclusions. It does not silently pad excluded traffic to
reach a quota. Downloads are serial to avoid concurrent credential refreshes.

Session merging is bounded by the configured window/limit. Outside-window
history is not fetched, and merged histories are marked incomplete. For a full
historical-session study, supply an authorized complete snapshot with explicit
boundaries; do not remove completeness diagnostics to obtain directional labels.
Missing downloads and extraction failures remain source errors, not Neutral.
A run with no eligible captured source fails clearly.

## Evaluate with checkpoints

Review/accept taxonomy and filter policy as described in the README. Then:

```bash
uv run convosignal --config private/config.toml batch-evaluate \
  --input-jsonl runs/source/conversations.jsonl \
  --selection runs/source/selection.json \
  --source-errors runs/source/source_errors.json \
  --taxonomy taxonomy.json --filter-policy filter_policy.json \
  --rules-version 3 --workers 4 --output-dir runs/evaluation
```

Each conversation has a private staging directory and is published as a
checkpoint only after its complete artifacts validate. The final canonical run
is in `runs/evaluation/completed/`. Pass that directory to `replay` or `report`.
A single source error is retained without aborting unrelated conversations.
Large inputs fail visibly; no turns are truncated to force a label.

A worker creates its own model adapter and reuses it for its tasks. Worker count
is bounded to 1–32; choose a value your serving capacity can sustain. Model token,
input-character and HTTP-timeout budgets come from the explicit configuration.
Library progress logging uses checkpoint numbers, not captured source text.

Resume using exactly the same command with `--resume`. Completed checkpoints,
including errors, are reused without model calls. Source, policy, rules, prompt,
model identity/serving settings, fixture identity, captured headers, Python minor
version, dependency versions and evaluator-code changes reject resume. Worker
count may change. Interrupted staging attempts are retained under
`incomplete-attempts/` before those unfinished inputs are retried.

A `.writer.lock` prevents simultaneous writers. If a process was forcibly killed,
first verify that no writer is running, then remove only that run's stale lock
and resume. Do not remove locks belonging to live processes. A corrupted completed
checkpoint fails validation rather than being silently regenerated. There is no
automatic retry of completed error records or verdict-based label retry. For a
planned operational recovery, retain the original run and create a separate,
explicitly documented run with the same frozen source and declared new budgets.

## Handoff and release checks

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv build
```

CI runs these checks for Python 3.11 and 3.12, then installs the built wheel into
a separate environment and exercises the offline commands outside the checkout.
HTML/CSS/JavaScript templates ship in both distributions. Private datasets,
credentials, test-run artifacts and Desktop files must never enter a wheel or
source distribution. Reports contain actual source text; keep them in approved
private storage and share them only with authorized readers.

No public registry release, service deployment or production accuracy claim is
implied by passing these software checks.

For a wheel-only installation, create your own metadata file, for example:

```json
{
  "agent_name": "Your agent",
  "stage": "production",
  "stage_basis": "Owner-provided",
  "report_date": "2026-11-24",
  "source_description": "Your authorized frozen source"
}
```

Then run `convosignal report --run-dir YOUR_RUN --metadata metadata.json
--output-dir NEW_REPORT_DIRECTORY` from any working directory. A wheel install
also supports `python -m convosignal` using that installation's interpreter.
