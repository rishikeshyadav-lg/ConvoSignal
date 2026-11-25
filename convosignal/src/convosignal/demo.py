"""Synthetic offline demonstration; no keyword-based fake satisfaction judge."""

import json
import pathlib

from convosignal import conversations, llm, pipeline, taxonomy


def run(
    output_dir: pathlib.Path, *, overwrite: bool = False
) -> dict[str, object]:
    """Load bundled synthetic sources and explicitly prepared model evidence."""
    directory = pathlib.Path(__file__).parent / "fixtures"
    traces = json.loads((directory / "demo_traces.json").read_text())
    responses = json.loads((directory / "demo_responses.json").read_text())
    batch = conversations.extract_traces(traces)
    questions = [
        q.question for q in conversations.extract_questions(batch.conversations)
    ]
    proposal = taxonomy.propose(
        json.dumps(responses["taxonomy"]),
        questions,
        model_identifier="fake-fixtures-v1",
        source_statistics=batch.statistics,
    )
    # Demo operates only on bundled synthetic artifacts. Normal propose never
    # accepts anything; the demo command explicitly authorizes this example.
    accepted = taxonomy.accept(proposal)
    if not overwrite and output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Demo directory is not empty; request overwrite")
    output_dir.mkdir(parents=True, exist_ok=True)
    taxonomy.save_json(
        output_dir / "proposal.json", proposal, overwrite=overwrite
    )
    taxonomy.save_accepted(
        output_dir / "taxonomy.json",
        output_dir / "filter_policy.json",
        accepted,
        overwrite=overwrite,
    )
    report = pipeline.evaluate(
        batch.conversations,
        accepted,
        llm.FakeLLM(responses),
        output_dir,
        overwrite=overwrite,
    )
    return report
