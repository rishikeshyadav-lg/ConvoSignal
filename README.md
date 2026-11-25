# ConvoSignal

Classifies agent questions, filters accepted low-value categories, and evaluates
conversations as Satisfied, Dissatisfied, or Neutral with traceable evidence.
An LLM extracts evidence; versioned Python rules calculate decisions and counts.

## Quick start

Requires Python 3.11 or 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/rishikeshyadav-lg/ConvoSignal.git
cd ConvoSignal/convosignal
uv sync --locked
uv run convosignal demo --output-dir demo-results
```

The demo runs offline with synthetic data. For real traces, configure your own
MLflow experiment and Databricks serving endpoint. Private traces, credentials,
and generated reports are excluded from this repository.

## Documentation

- [Package guide and CLI workflows](convosignal/README.md)
- [Replay, reports, and reproducibility](convosignal/docs/Reproducibility.md)
- [Product specification](convosignal/docs/Prod-Spec.md)
- [Architecture](convosignal/docs/Architecture.md)
- [Milestones and validation limits](convosignal/docs/Milestones.md)
- [Change history](convosignal/CHANGELOG.md)

## Development

Run from `convosignal/`:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv build
```

CI checks both supported Python versions and tests the installed wheel outside
the checkout. Independent human validation of label accuracy remains pending.
