"""Parse, serialize, replay and export the C0 evidence contracts."""

import argparse
import dataclasses
import json
import pathlib
from typing import Any

import pydantic

from convosignal import (
    conversations,
    models,
    review_contracts,
    revision,
    routing,
    taxonomy,
    verdicts,
)

EVIDENCE = pydantic.TypeAdapter(models.EvidenceRecord)
EVALUATION = pydantic.TypeAdapter(models.Evaluation)
EVALUATION_RECORD = pydantic.TypeAdapter(models.EvaluationRecord)


def parse_evidence(
    payload: str | bytes,
) -> models.EvidenceRecord | revision.EvidenceRecord:
    """Parse structural JSON; goal-specific relationships are checked on replay.

    Reject unknown fields, invalid types and model-supplied labels. Errors omit
    input text. Semantic support for interpretations still needs review.
    """
    try:
        data = json.loads(payload)
        if not isinstance(data, dict) or not isinstance(
            data.get("versions"), dict
        ):
            raise ValueError("Evidence must be an object with versions")
        version = data["versions"].get("rules")
        adapter = revision.EVIDENCE if version == "3" else EVIDENCE
        return adapter.validate_json(payload, strict=True)
    except pydantic.ValidationError as error:
        locations = [
            f"{'.'.join(map(str, item['loc']))}: {item['type']}"
            for item in error.errors(include_input=False, include_context=False)
        ]
        raise ValueError("Invalid evidence: " + "; ".join(locations)) from None


def evidence_data(
    record: models.EvidenceRecord | revision.EvidenceRecord,
) -> dict[str, Any]:
    """Serialize evidence using its own declared contract."""
    data: dict[str, Any]
    if isinstance(record, revision.EvidenceRecord):
        data = revision.EVIDENCE.dump_python(record, mode="json")
    else:
        data = EVIDENCE.dump_python(record, mode="json")
    return data


def evaluate_record(
    record: models.EvidenceRecord | revision.EvidenceRecord,
) -> models.Evaluation:
    """Evaluate a versioned record without any network or model calls."""
    if not record.conversation_id.strip():
        raise ValueError("Conversation ID is required")
    result = verdicts.evaluate_conversation(
        record.goals,
        record.turns,
        excluded_only=record.excluded_only,
        overall_feedback=record.overall_feedback,
        rules_version=record.versions.rules,
    )
    return dataclasses.replace(
        result,
        conversation_id=record.conversation_id,
        versions=record.versions,
        source_turn_ids=tuple(turn.turn_id for turn in record.turns),
    )


def json_schemas() -> dict[str, Any]:
    """Return machine-readable contracts, including label/status conditions."""
    evaluation = EVALUATION.json_schema()
    evaluation["allOf"] = [
        {
            "if": {"properties": {"status": {"const": "evaluated"}}},
            "then": {"properties": {"label": {"$ref": "#/$defs/Label"}}},
            "else": {"properties": {"label": {"type": "null"}}},
        }
    ]
    evaluation["$defs"]["Verdict"]["allOf"] = evaluation["allOf"]
    review_context = review_contracts.ValidationContext.model_json_schema()
    return {
        "evidence.schema.json": EVIDENCE.json_schema(),
        "evidence_v3.schema.json": revision.EVIDENCE.json_schema(),
        "model_evidence_v3.schema.json": revision.MODEL_EVIDENCE.json_schema(),
        "evaluation_record.schema.json": EVALUATION_RECORD.json_schema(),
        "model_evidence.schema.json": pydantic.TypeAdapter(
            models.ModelEvidence
        ).json_schema(),
        "evaluation.schema.json": evaluation,
        "conversation.schema.json": pydantic.TypeAdapter(
            conversations.Conversation
        ).json_schema(),
        "review.schema.json": review_contracts.Review.model_json_schema(),
        "review_context.schema.json": review_context,
        "question.schema.json": pydantic.TypeAdapter(
            conversations.Question
        ).json_schema(),
        "proposal.schema.json": taxonomy.Proposal.model_json_schema(),
        "accepted_taxonomy.schema.json": (
            taxonomy.AcceptedTaxonomy.model_json_schema()
        ),
        "filter_policy.schema.json": (
            taxonomy.AcceptedPolicy.model_json_schema()
        ),
        "routing_snapshot.schema.json": (
            routing.RoutingSnapshot.model_json_schema()
        ),
        "routed_question.schema.json": (
            routing.RoutedQuestion.model_json_schema()
        ),
    }


def main() -> None:
    """Export generated schemas without creating or evaluating trace data."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=pathlib.Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, schema in json_schemas().items():
        (args.output_dir / name).write_text(
            json.dumps(schema, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
