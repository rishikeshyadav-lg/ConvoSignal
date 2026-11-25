# ConvoSignal contributor instructions

Read `convosignal/docs/Prod-Spec.md`, `convosignal/docs/Architecture.md`, and
`convosignal/docs/Milestones.md` before changing behavior. This repository owns
ConvoSignal independently of the campaign agent.

Run commands from `convosignal/`: `uv sync --locked`, `uv run pytest`,
`uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`,
and `uv build`. CI also verifies installed-wheel behavior on Python 3.11/3.12.

Preserve versioned rules, prompts, source checksums, and replay compatibility.
Models extract evidence; Python derives labels and counts. Errors and skips
must remain separate from Neutral. Record implementation decisions and milestone
changes in the same session. Keep private source traces, generated reports,
credentials, and runtime artifacts out of commits and distributions.

Functional checks do not establish real-world label accuracy. Independent human
validation remains pending. Do not claim it has passed or weaken its gate.

Commits and pull requests must contain no AI attribution or Co-Authored-By lines.
