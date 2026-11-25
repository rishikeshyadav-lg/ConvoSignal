"""Contract parsing, replay and publication checks."""

import dataclasses
import json
import pathlib

import pydantic
import pytest

from convosignal import models, schemas


def record():
    return models.EvidenceRecord(
        "synthetic-1",
        (
            models.Turn("u1", "user", "Summarize this report"),
            models.Turn("a1", "assistant", "Report summary"),
            models.Turn("u2", "user", "That answers my question"),
        ),
        (
            models.Goal(
                "summary",
                (models.Requirement("summary", "Summarize report", "u1"),),
                (
                    models.Event(
                        models.EventKind.ACCEPTANCE,
                        "u2",
                        ("summary",),
                        result_turn_id="a1",
                    ),
                ),
            ),
        ),
        models.Versions("synthetic-review", "fake", "fixture-v1", "synthetic"),
    )


def test_json_roundtrip_and_replay_keep_versions_and_citations():
    original = record()
    restored = schemas.parse_evidence(schemas.EVIDENCE.dump_json(original))
    assert restored == original
    evaluated = schemas.evaluate_record(restored)
    assert evaluated.label == models.Label.SATISFIED
    assert evaluated.versions == original.versions
    assert evaluated.conversation_id == original.conversation_id
    assert evaluated.source_turn_ids == ("u1", "a1", "u2")
    assert (
        schemas.EVALUATION.validate_json(
            schemas.EVALUATION.dump_json(evaluated)
        )
        == evaluated
    )


@pytest.mark.parametrize(
    "edit",
    [
        lambda payload: payload.update(label="Satisfied"),
        lambda payload: payload["goals"][0].update(awaiting_input="false"),
        lambda payload: payload["goals"][0]["events"][0].update(
            kind="sentiment"
        ),
        lambda payload: payload["versions"].update(rules="1"),
        lambda payload: payload["turns"][0].update(role="system"),
    ],
)
def test_invalid_types_versions_and_model_labels_are_rejected(edit):
    payload = schemas.EVIDENCE.dump_python(record(), mode="json")
    edit(payload)
    with pytest.raises(ValueError, match="Invalid evidence"):
        schemas.parse_evidence(json.dumps(payload))


def test_parse_errors_do_not_echo_sensitive_input():
    with pytest.raises(ValueError) as caught:
        schemas.parse_evidence('{"sensitive-account-name": "secret-value"')
    assert "secret-value" not in str(caught.value)
    assert "sensitive-account-name" not in str(caught.value)


def test_unsupported_citations_are_errors_not_neutral():
    original = record()
    goal = original.goals[0]
    bad = dataclasses.replace(goal.events[0], result_turn_id="missing")
    result = schemas.evaluate_record(
        dataclasses.replace(
            original, goals=(dataclasses.replace(goal, events=(bad,)),)
        )
    )
    assert result.status == "error"
    assert result.label is None
    assert result.errors


def test_skipped_and_failed_evaluations_cannot_have_labels():
    for status, reason in (
        ("skipped", "excluded_only"),
        ("error", "evaluation_error"),
    ):
        with pytest.raises(pydantic.ValidationError):
            models.Evaluation(status, models.Label.NEUTRAL, reason, ())
    with pytest.raises(pydantic.ValidationError):
        models.Evaluation(
            "evaluated", models.Label.SATISFIED, "consistent_goals", ()
        )


def test_published_schemas_match_their_models():
    directory = pathlib.Path(__file__).parents[1] / "schemas"
    for filename, expected in schemas.json_schemas().items():
        assert json.loads((directory / filename).read_text()) == expected
        assert expected["additionalProperties"] is False
    assert schemas.json_schemas()["evaluation.schema.json"]["allOf"]
