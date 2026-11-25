"""Safe target routing stays separate from literal category assignment."""

import dataclasses
import json
import pathlib

import pytest

from convosignal import conversations, models, routing, taxonomy


def source(*questions):
    return (
        conversations.Conversation(
            "c",
            tuple(
                models.Turn(f"u{index}", "user", question, "t", index)
                for index, question in enumerate(questions)
            ),
        ),
    )


def test_longest_literal_match_and_first_declared_tie():
    first = taxonomy.QuestionType(
        name="short",
        description="Short marker",
        markers=("hi",),
        asks_for=(),
        set_aside=True,
    )
    second = taxonomy.QuestionType(
        name="long",
        description="Long marker",
        markers=("this week", "hi"),
        asks_for=(),
        set_aside=False,
    )
    tax = taxonomy.Taxonomy(types=(first, second))
    assert taxonomy.assignment("THIS   WEEK", tax).name == "long"
    assert taxonomy.assignment("hi", tax).name == "short"
    assert (
        taxonomy.assignment("shipping", tax).name == "short"
    )  # Literal substring.
    assert taxonomy.assignment("No match", tax) is None


def test_policy_routing_protects_mixed_partial_and_unmatched_requests(accepted):
    snapshot = routing.route(
        source(
            "Hello",
            "What can you do?",
            "What can you do? Compare weeks",
            "shipping analysis",
            "Write a summary",
        ),
        accepted,
    )
    decisions = [
        (row.type_name, row.routing_decision, row.routing_reason)
        for row in snapshot.questions
    ]
    assert decisions[0] == (
        "greeting",
        "context_only",
        "accepted_standalone_context",
    )
    assert decisions[1] == (
        "capability",
        "context_only",
        "accepted_standalone_context",
    )
    assert decisions[2] == ("capability", "evaluate", "mixed_request")
    assert decisions[3] == ("greeting", "evaluate", "ambiguous_exclusion")
    assert decisions[4] == (None, "evaluate", "unclassified")
    assert snapshot.questions[4].classification_status == "unclassified"


def test_excluded_only_and_capability_policy_override(proposal):
    accepted = taxonomy.accept(proposal)
    snapshot = routing.route(source("What can you do?"), accepted)
    assert snapshot.excluded_only_conversation_ids == ("c",)
    assert snapshot.eligible_conversation_ids == ()
    assert snapshot.questions[0].routing_decision == "exclude"
    policy = taxonomy.FilterPolicy(
        excluded_type_ids=("greeting",),
        standalone_examples=proposal.filter_policy.standalone_examples,
    )
    changed = taxonomy.accept(
        proposal.model_copy(update={"filter_policy": policy})
    )
    included = routing.route(source("What can you do?"), changed)
    assert included.questions[0].classification_status == "set_aside"
    assert included.questions[0].routing_decision == "evaluate"
    assert accepted.filter_policy_checksum != changed.filter_policy_checksum
    with pytest.raises(ValueError, match="snapshot mismatch"):
        routing.validate_snapshot(snapshot, source("What can you do?"), changed)


def test_snapshot_rejects_input_taxonomy_policy_and_row_changes(accepted):
    original = source("Compare weeks")
    snapshot = routing.route(original, accepted)
    routing.validate_snapshot(snapshot, original, accepted)
    assert routing.route(original, accepted) == snapshot
    with pytest.raises(ValueError, match="snapshot mismatch"):
        routing.validate_snapshot(snapshot, source("Compare months"), accepted)
    corrupted = snapshot.model_copy(update={"questions": ()})
    with pytest.raises(ValueError):
        routing.validate_snapshot(corrupted, original, accepted)
    new_types = list(accepted.taxonomy.types)
    new_types[-1] = new_types[-1].model_copy(update={"markers": ("months",)})
    corrupt = accepted.model_copy(
        update={"taxonomy": taxonomy.Taxonomy(types=tuple(new_types))}
    )
    with pytest.raises(ValueError, match="checksum mismatch"):
        routing.route(original, corrupt)


def test_source_turns_and_tool_evidence_remain_unchanged(accepted):
    path = pathlib.Path(__file__).parent / "fixtures/chat_traces.json"
    source_data = conversations.extract_traces(
        json.loads(path.read_text())
    ).conversations
    before = conversations.conversation_data(source_data)
    snapshot = routing.route(source_data, accepted)
    assert conversations.conversation_data(source_data) == before
    closing = next(
        row for row in snapshot.questions if row.question.startswith("Thanks")
    )
    assert closing.routing_decision == "context_only"
    assert snapshot.excluded_only_conversation_ids == ("greeting",)
    assert snapshot.eligible_conversation_ids == ("analysis", "unmatched")


def test_duplicate_traffic_counts_and_question_conversation_denominators(
    accepted,
):
    snapshot = routing.route(
        source(
            "Compare weeks",
            "Compare weeks",
            "Compare weeks",
            "Hello",
            "Write a summary",
        ),
        accepted,
    )
    report = routing.summary(snapshot, accepted)
    assert report["total_nonblank_questions"] == 5
    assert (
        report["actionable_count"]
        + report["set_aside_count"]
        + report["unclassified_count"]
        == 5
    )
    assert report["actionable_types"][0]["count"] == 3
    assert report["actionable_types"][0]["enough"] is True
    assert report["actionable_types"][0]["traffic_share"] == 3 / 5
    assert report["filtering_rate"] == 1 / 5
    assert report["routing_counts"] == {
        "evaluate": 4,
        "context_only": 1,
        "exclude": 0,
    }
    assert report["conversations"] == {
        "unit": "conversation",
        "input": 1,
        "eligible": 1,
        "excluded_only": 0,
        "no_user_questions": 0,
    }


def test_empty_and_assistant_only_inputs_have_no_division_by_zero(accepted):
    snapshot = routing.route((), accepted)
    report = routing.summary(snapshot, accepted)
    assert report["total_nonblank_questions"] == 0
    assert report["filtering_rate"] is None
    assistant = conversations.Conversation(
        "c", (models.Turn("a", "assistant", "Hello"),)
    )
    assert routing.route((assistant,), accepted).no_user_conversation_ids == (
        "c",
    )


def test_proposal_is_not_implicitly_accepted(proposal):
    with pytest.raises(ValueError, match="explicitly accepted"):
        routing.route(source("Hello"), proposal)


def test_policy_can_exclude_an_actionable_category(proposal):
    policy = taxonomy.FilterPolicy(
        excluded_type_ids=("comparison",),
        standalone_examples={"comparison": ("Compare weeks",)},
    )
    accepted = taxonomy.accept(
        proposal.model_copy(update={"filter_policy": policy})
    )
    snapshot = routing.route(source("Compare weeks"), accepted)
    assert snapshot.questions[0].classification_status == "classified"
    assert snapshot.questions[0].routing_decision == "exclude"


def test_no_hidden_exclusion_for_unreviewed_paraphrase(accepted):
    row = routing.route(source("Hello there"), accepted).questions[0]
    assert (row.routing_decision, row.routing_reason) == (
        "evaluate",
        "ambiguous_exclusion",
    )


def test_snapshot_save_roundtrip_and_duplicate_conversation_ids(
    accepted, tmp_path
):
    snapshot = routing.route(source("Hello"), accepted)
    path = tmp_path / "routing_snapshot.json"
    routing.save_snapshot(path, snapshot)
    assert (
        routing.RoutingSnapshot.model_validate_json(path.read_text())
        == snapshot
    )
    with pytest.raises(FileExistsError):
        routing.save_snapshot(path, snapshot)
    with pytest.raises(ValueError, match="Conversation IDs"):
        routing.route((*source("Hello"), *source("Compare")), accepted)
    changed = dataclasses.replace(source("Hello")[0], context_complete=False)
    with pytest.raises(ValueError, match="snapshot mismatch"):
        routing.validate_snapshot(snapshot, (changed,), accepted)


def test_offline_artifacts_are_parseable_and_never_refetch_or_evaluate(
    accepted, tmp_path
):
    path = pathlib.Path(__file__).parent / "fixtures/chat_traces.json"
    original = conversations.extract_traces(
        json.loads(path.read_text())
    ).conversations
    snapshot = routing.write_classification(tmp_path, original, accepted)
    restored = conversations.load_conversations(
        tmp_path / "conversations.jsonl"
    )
    routing.validate_snapshot(snapshot, restored, accepted)
    report = json.loads((tmp_path / "summary.json").read_text())
    assert report["total_nonblank_questions"] == 4
    rows = [
        routing.RoutedQuestion.model_validate_json(line)
        for line in (tmp_path / "routing.jsonl").read_text().splitlines()
    ]
    assert tuple(rows) == snapshot.questions
    assert len((tmp_path / "questions.jsonl").read_text().splitlines()) == 4
    assert not (tmp_path / "evaluations.jsonl").exists()
    with pytest.raises(FileExistsError):
        routing.write_classification(tmp_path, original, accepted)
    assert (
        routing.write_classification(
            tmp_path, original, accepted, overwrite=True
        )
        == snapshot
    )


def test_output_preflight_preserves_existing_files(accepted, tmp_path):
    (tmp_path / "summary.json").write_text("existing content")
    with pytest.raises(FileExistsError):
        routing.write_classification(tmp_path, source("Hello"), accepted)
    assert not (tmp_path / "questions.jsonl").exists()
    assert (tmp_path / "summary.json").read_text() == "existing content"


def test_matching_is_literal_rather_than_regex():
    item = taxonomy.QuestionType(
        name="literal_example",
        description="Literal punctuation",
        markers=("a.b",),
        asks_for=(),
        set_aside=False,
    )
    tax = taxonomy.Taxonomy(types=(item,))
    assert taxonomy.assignment("a.b", tax) == item
    assert taxonomy.assignment("axb", tax) is None


def test_actionable_report_sorting_and_threshold_are_configurable(proposal):
    data = proposal.model_dump(mode="json")
    data["taxonomy"]["types"].append(
        {
            "name": "analysis",
            "description": "Other analysis",
            "markers": ["analyze"],
            "asks_for": ["findings"],
            "set_aside": False,
        }
    )
    accepted = taxonomy.accept(taxonomy.Proposal.model_validate(data))
    report = routing.summary(
        routing.route(source("Compare", "Analyze"), accepted),
        accepted,
        enough_threshold=1,
    )
    assert [row["name"] for row in report["actionable_types"]] == [
        "analysis",
        "comparison",
    ]
    assert all(row["enough"] for row in report["actionable_types"])
    assert report["actionable_asks_for"] == [
        "current_value",
        "findings",
        "previous_value",
    ]
