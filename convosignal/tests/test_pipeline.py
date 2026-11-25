"""Both stages share an immutable source snapshot and expose model failures."""

import dataclasses
import json
import pathlib

import pytest

from convosignal import cli, conversations, demo, llm, models, pipeline, routing


def source():
    return (
        conversations.Conversation(
            "task",
            (
                models.Turn("u", "user", "Compare weeks"),
                models.Turn("a", "assistant", "A comparison"),
                models.Turn("v", "user", "That answers it"),
            ),
        ),
    )


def response():
    return {
        "goals": [
            {
                "goal_id": "g",
                "category": "comparison",
                "requirements": [
                    {
                        "requirement_id": "r",
                        "text": "Compare weeks",
                        "source_turn_id": "u",
                    }
                ],
                "events": [
                    {
                        "kind": "acceptance",
                        "turn_id": "v",
                        "requirement_ids": ["r"],
                        "result_turn_id": "a",
                    }
                ],
            }
        ]
    }


def test_demo_covers_labels_skips_errors_and_reconciles(tmp_path, capsys):
    assert cli.main(["demo", "--output-dir", str(tmp_path)]) == 0
    summary = json.loads((tmp_path / "summary.json").read_text())
    outcomes = summary["outcomes"]
    assert outcomes["input_conversations"] == 10
    assert outcomes["outcome_counts"] == {
        "Satisfied": 1,
        "Dissatisfied": 1,
        "Neutral": 4,
    }
    assert outcomes["evaluated_conversations"] == 6
    assert outcomes["skip_reasons"] == {
        "excluded_only": 2,
        "no_eligible_goal": 1,
    }
    assert outcomes["error_conversations"] == 1
    assert outcomes["neutral_reasons"] == {"no_clear_user_response": 4}
    assert cli.main(["demo", "--output-dir", str(tmp_path)]) == 2
    assert "not empty" in capsys.readouterr().err


def test_sources_are_attached_by_application_not_model(accepted, tmp_path):
    fake = llm.FakeLLM({"task": response()})
    report = pipeline.evaluate(source(), accepted, fake, tmp_path)
    assert report["outcomes"]["outcome_counts"]["Satisfied"] == 1
    record = json.loads((tmp_path / "evaluations.jsonl").read_text())
    assert (
        record["evidence_details"]["evidence"]["turns"][0]["text"]
        == "Compare weeks"
    )
    assert fake.calls == ["task"]


@pytest.mark.parametrize(
    "edit",
    [
        lambda r: r.update(turns=[]),
        lambda r: r.update(label="Satisfied"),
        lambda r: r["goals"][0].update(category="greeting"),
        lambda r: r["goals"][0]["events"][0].update(result_turn_id="missing"),
    ],
)
def test_invalid_model_evidence_retries_then_errors(accepted, tmp_path, edit):
    payload = response()
    edit(payload)
    fake = llm.FakeLLM({"task": payload})
    report = pipeline.evaluate(source(), accepted, fake, tmp_path)
    assert fake.calls == ["task", "task"]
    assert report["outcomes"]["error_conversations"] == 1
    result = json.loads((tmp_path / "evaluations.jsonl").read_text())
    assert result["label"] is None
    assert (
        result["evaluation_status"] == "error"
        if "evaluation_status" in result
        else result["status"] == "error"
    )


def test_excluded_only_conversation_bypasses_model(accepted, tmp_path):
    fake = llm.FakeLLM({})
    greeting = conversations.Conversation(
        "hello", (models.Turn("u", "user", "Hello"),)
    )
    report = pipeline.evaluate((greeting,), accepted, fake, tmp_path)
    assert fake.calls == []
    assert report["outcomes"]["outcome_shares"]["Satisfied"] is None


def test_context_only_cannot_open_goal(accepted, tmp_path):
    conv = dataclasses.replace(
        source()[0],
        turns=(
            models.Turn("hi", "user", "Hello"),
            *source()[0].turns,
        ),
    )
    payload = response()
    payload["goals"][0]["requirements"][0]["source_turn_id"] = "hi"
    fake = llm.FakeLLM({"task": payload})
    report = pipeline.evaluate((conv,), accepted, fake, tmp_path)
    assert report["outcomes"]["error_conversations"] == 1


def test_partial_semantic_errors_preserve_completed_goals(accepted, tmp_path):
    payload = response()
    payload["goals"].append({"goal_id": "bad", "requirements": []})
    report = pipeline.evaluate(
        source(), accepted, llm.FakeLLM({"task": payload}), tmp_path
    )
    assert report["outcomes"]["error_conversations"] == 1
    result = json.loads((tmp_path / "evaluations.jsonl").read_text())
    assert len(result["goals"]) == 1
    assert result["label"] is None
    assert result["evidence_details"]["evidence"]


def test_provider_failure_is_not_retried_as_schema_error(accepted, tmp_path):
    class Broken:
        model_identifier = "broken"
        calls = 0

        def complete(self, system, user):
            self.calls += 1
            raise RuntimeError("sensitive provider message")

    client = Broken()
    report = pipeline.evaluate(source(), accepted, client, tmp_path)
    assert client.calls == 1
    assert report["outcomes"]["error_conversations"] == 1
    assert (
        "sensitive provider" not in (tmp_path / "evaluations.jsonl").read_text()
    )


def test_wrong_cached_input_is_rejected_before_model(accepted, tmp_path):
    snapshot = routing.route(source(), accepted)
    changed = (dataclasses.replace(source()[0], context_complete=False),)
    fake = llm.FakeLLM({"task": response()})
    with pytest.raises(ValueError, match="mismatch"):
        pipeline.evaluate(
            changed, accepted, fake, tmp_path, cached_routing=snapshot
        )
    assert fake.calls == []


def test_budget_rejection_never_drops_turns_or_calls_model(accepted):
    fake = llm.FakeLLM({"task": response()})
    snapshot = routing.route(source(), accepted)
    result, details = pipeline.evaluate_one(
        source()[0], snapshot.questions, accepted, fake, max_input_chars=1
    )
    assert result.status == "error"
    assert fake.calls == []
    assert "budget" in details["errors"][0]


def test_source_download_failure_is_error_and_bypasses_evaluator(
    accepted, tmp_path
):
    fake = llm.FakeLLM({})
    result = pipeline.evaluate(
        source(),
        accepted,
        fake,
        tmp_path,
        source_errors={"task": "Artifact download failed"},
    )
    assert result["outcomes"]["error_conversations"] == 1
    assert fake.calls == []


def test_cli_proposal_accept_classify_evaluate_roundtrip(tmp_path, capsys):
    folder = pathlib.Path(demo.__file__).parent / "fixtures"
    proposal_path = tmp_path / "proposal.json"
    raw = json.loads((folder / "demo_responses.json").read_text())
    response_path = tmp_path / "taxonomy_response.json"
    response_path.write_text(json.dumps(raw["taxonomy"]))
    assert (
        cli.main(
            [
                "propose",
                "--trace-json",
                str(folder / "demo_traces.json"),
                "--response-json",
                str(response_path),
                "--output",
                str(proposal_path),
            ]
        )
        == 0
    )
    tax, policy = tmp_path / "taxonomy.json", tmp_path / "filter_policy.json"
    assert (
        cli.main(
            ["accept", "--input", str(proposal_path), "--output", str(tax)]
        )
        == 0
    )
    common = ["--taxonomy", str(tax), "--filter-policy", str(policy)]
    classification = tmp_path / "classified"
    assert (
        cli.main(
            [
                "classify",
                "--trace-json",
                str(folder / "demo_traces.json"),
                *common,
                "--output-dir",
                str(classification),
            ]
        )
        == 0
    )
    # One intentional error fixture yields exit 1, with all results persisted.
    assert (
        cli.main(
            [
                "evaluate",
                "--input-jsonl",
                str(classification / "conversations.jsonl"),
                *common,
                "--fake-responses",
                str(folder / "demo_responses.json"),
                "--output-dir",
                str(tmp_path / "evaluated"),
            ]
        )
        == 1
    )
    assert "Synthetic comparison" not in capsys.readouterr().out


def test_cli_partial_trace_failure_persists_error_record(tmp_path, accepted):
    from convosignal import taxonomy

    tax, policy = tmp_path / "taxonomy.json", tmp_path / "filter_policy.json"
    taxonomy.save_accepted(tax, policy, accepted)
    trace_file = tmp_path / "traces.json"
    trace_file.write_text(json.dumps([{"trace_id": "bad", "timestamp_ms": 1}]))
    result = tmp_path / "output"
    assert (
        cli.main(
            [
                "evaluate",
                "--trace-json",
                str(trace_file),
                "--taxonomy",
                str(tax),
                "--filter-policy",
                str(policy),
                "--output-dir",
                str(result),
            ]
        )
        == 1
    )
    assert (
        json.loads((result / "summary.json").read_text())["outcomes"][
            "error_conversations"
        ]
        == 1
    )


def test_persisted_records_match_their_schema_and_status_alias(tmp_path):
    from convosignal import schemas

    demo.run(tmp_path)
    for line in (tmp_path / "evaluations.jsonl").read_text().splitlines():
        record = schemas.EVALUATION_RECORD.validate_json(line)
        assert record.evaluation_status == record.status
        assert record.versions is not None


def test_question_only_snapshots_classify_but_cannot_evaluate(tmp_path, capsys):
    demo.run(tmp_path)
    common = [
        "--input-jsonl",
        str(tmp_path / "questions.jsonl"),
        "--input-kind",
        "questions",
        "--taxonomy",
        str(tmp_path / "taxonomy.json"),
        "--filter-policy",
        str(tmp_path / "filter_policy.json"),
        "--output-dir",
        str(tmp_path / "question_classification"),
    ]
    assert cli.main(["classify", *common]) == 0
    assert cli.main(["evaluate", *common]) == 2
    assert "Question-only" in capsys.readouterr().err


def test_independent_template_has_no_predicted_labels(tmp_path):
    demo.run(tmp_path)
    template = tmp_path / "reviews.jsonl"
    assert (
        cli.main(
            [
                "review-template",
                "--predictions",
                str(tmp_path / "evaluations.jsonl"),
                "--output",
                str(template),
            ]
        )
        == 0
    )
    reviews = [json.loads(line) for line in template.read_text().splitlines()]
    assert len(reviews) == 10
    assert all(
        row["label"] is None and row["reviewer"] == "" for row in reviews
    )
    # Synthetic labels below test the comparison command only; these are not
    # independently reviewed real data or a claim of evaluator accuracy.
    predictions = [
        json.loads(line)
        for line in (tmp_path / "evaluations.jsonl").read_text().splitlines()
    ]
    synthetic = [
        {
            "conversation_id": row["conversation_id"],
            "input_checksum": row["input_checksum"],
            "reviewer": "synthetic-format-test",
            "label": "Neutral",
        }
        for row in predictions
    ]
    template.write_text("\n".join(json.dumps(row) for row in synthetic) + "\n")
    assert (
        cli.main(
            [
                "compare",
                "--predictions",
                str(tmp_path / "evaluations.jsonl"),
                "--reviews",
                str(template),
                "--output",
                str(tmp_path / "comparison.json"),
            ]
        )
        == 0
    )
