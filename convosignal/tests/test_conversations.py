"""Extraction ordering and audit behavior for supported offline shapes."""

import dataclasses
import json
import pathlib

import pytest

from convosignal import conversations


def trace(trace_id="t1", timestamp=1, messages=None, **extra):
    return dict(
        trace_id=trace_id,
        timestamp_ms=timestamp,
        messages=messages
        if messages is not None
        else [
            {"role": "user", "content": "Compare weeks"},
            {"role": "assistant", "content": "A comparison"},
        ],
        **extra,
    )


def test_user_only_questions_keep_turns_order_and_positions():
    raw = trace(
        messages=[
            {"role": "assistant", "content": "Assistant question?"},
            {"role": "user", "content": "   "},
            {"role": "user", "content": "Compare weeks"},
            {"role": "tool", "content": "Synthetic data"},
            {"role": "user", "content": "Compare weeks"},
        ]
    )
    batch = conversations.extract_traces([raw])
    questions = conversations.extract_questions(batch.conversations)
    assert [q.question for q in questions] == ["Compare weeks"] * 2
    assert [q.message_position for q in questions] == [2, 4]
    assert questions[0].trace_id == "t1"
    assert len(batch.conversations[0].turns) == 4
    assert batch.statistics["blank_user_messages_excluded"] == 1
    assert batch.statistics["user_messages_extracted"] == 2


def test_sorting_timestamp_id_and_stable_turn_ids():
    raw = [trace("z", 2), trace("b", 1), trace("a", 1)]
    first = conversations.extract_traces(raw)
    second = conversations.extract_traces(list(reversed(raw)))
    assert first == second
    assert [c.conversation_id for c in first.conversations] == ["a", "b", "z"]


def test_explicit_session_merging_and_source_identity_deduplication():
    messages = [{"role": "user", "content": "Compare weeks", "turn_id": "u1"}]
    raw = [
        trace("t1", 1, messages, session="s"),
        trace(
            "t2",
            2,
            [*messages, {"role": "assistant", "content": "Result"}],
            session="s",
        ),
    ]
    merged = conversations.extract_traces(
        raw, conversations.ExtractionConfig(session_path="session")
    )
    assert len(merged.conversations) == 1
    assert len(merged.conversations[0].turns) == 2
    assert merged.statistics["duplicate_turns"] == 1
    assert len(conversations.extract_traces(raw).conversations) == 2


def test_duplicate_trace_capture_is_not_duplicate_traffic():
    raw = trace()
    batch = conversations.extract_traces([raw, raw])
    assert batch.statistics["duplicate_traces"] == 1
    assert batch.statistics["user_messages_extracted"] == 1
    conflict = dict(raw, messages=[{"role": "user", "content": "Changed"}])
    batch = conversations.extract_traces([raw, conflict])
    assert batch.failures
    assert not batch.conversations[0].context_complete


def test_interaction_query_answer_and_custom_paths():
    raw = {
        "trace_id": "t",
        "timestamp_ms": 1,
        "spans": [
            {
                "name": "interaction",
                "inputs": {"payload": {"query": "Compare"}},
                "outputs": {"payload": {"answer": "Result"}},
            }
        ],
    }
    config = conversations.ExtractionConfig(
        shape="interaction",
        question_path="payload.query",
        answer_path="payload.answer",
    )
    batch = conversations.extract_traces([raw], config)
    assert [t.text for t in batch.conversations[0].turns] == [
        "Compare",
        "Result",
    ]
    raw["spans"][0]["outputs"] = None
    raw["state"] = "ERROR"
    failed_source = conversations.extract_traces([raw], config)
    assert not failed_source.conversations[0].context_complete
    assert failed_source.statistics["extraction_failures"] == 0


def test_custom_chat_path_and_numeric_index():
    raw = {
        "trace_id": "t",
        "timestamp_ms": 1,
        "data": [{"chat": [{"role": "user", "content": "Compare"}]}],
    }
    config = conversations.ExtractionConfig(messages_path="data.0.chat")
    assert (
        conversations.extract_traces([raw], config).statistics[
            "user_messages_extracted"
        ]
        == 1
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"trace_id": "x", "timestamp_ms": 2},
        trace("x", 2, [{"role": "system", "content": "Instructions"}]),
        trace("x", 2, [{"role": "user", "content": 5}]),
        trace("x", 2, ["not an object"]),
        trace("x", True),
    ],
)
def test_partial_failures_are_visible_and_do_not_erase_good_records(bad):
    batch = conversations.extract_traces([trace(), bad])
    assert batch.statistics["traces_scanned"] == 2
    assert batch.statistics["extraction_failures"] == 1
    assert batch.statistics["user_messages_extracted"] == 1
    assert batch.failures[0][0] == "x"


def test_no_questions_raises_with_actionable_diagnostics():
    with pytest.raises(
        conversations.ExtractionError, match="check shape"
    ) as error:
        conversations.extract_traces(
            [trace(messages=[{"role": "user", "content": " "}])]
        )
    assert error.value.batch.statistics["blank_user_messages_excluded"] == 1
    empty = conversations.extract_traces([], require_questions=False)
    assert empty.conversations == ()


def test_jsonl_roundtrip_preserves_snapshot_order_and_rejects_question_input(
    tmp_path,
):
    raw = [trace("b", 2), trace("a", 1)]
    source = conversations.extract_traces(raw).conversations[::-1]
    path = tmp_path / "conversations.jsonl"
    conversations.save_conversations(path, source)
    assert conversations.load_conversations(path) == source
    with pytest.raises(FileExistsError):
        conversations.save_conversations(path, source)
    path.write_text('{"question":"A question-only snapshot"}\n')
    with pytest.raises(ValueError, match="line 1"):
        conversations.load_conversations(path)


def test_conflicting_native_capture_fails_whole_record():
    first = trace(
        "a",
        1,
        [{"role": "user", "content": "One", "turn_id": "u"}],
        session="s",
    )
    second = trace(
        "b",
        2,
        [{"role": "user", "content": "Two", "turn_id": "u"}],
        session="s",
    )
    batch = conversations.extract_traces(
        [first, second], conversations.ExtractionConfig(session_path="session")
    )
    assert len(batch.failures) == 1
    assert not batch.conversations[0].context_complete
    assert batch.conversations[0].turns[0].text == "One"


def test_synthetic_fixture_retains_assistant_and_tool_context():
    path = pathlib.Path(__file__).parent / "fixtures/chat_traces.json"
    batch = conversations.extract_traces(json.loads(path.read_text()))
    assert batch.statistics["user_messages_extracted"] == 4
    roles = [t.role for t in batch.conversations[1].turns]
    assert roles == ["user", "tool", "assistant", "user"]
    duplicate = dataclasses.replace(
        batch.conversations[0],
        turns=(
            batch.conversations[0].turns[0],
            batch.conversations[0].turns[0],
        ),
    )
    with pytest.raises(ValueError, match="Turn IDs"):
        conversations.validate_conversations([duplicate])


def test_non_object_record_is_reported_as_extraction_failure():
    batch = conversations.extract_traces([trace(), None])
    assert batch.statistics["extraction_failures"] == 1
    assert batch.failures[0][1] == "Trace record must be an object"


def test_interaction_tool_results_remain_evidence_not_user_questions():
    record = {
        "trace_id": "t",
        "timestamp_ms": 1,
        "spans": [
            {
                "name": "interaction",
                "inputs": {"query": "Compare weeks"},
                "outputs": {"answer": "Synthetic result"},
            },
            {
                "name": "tool:query",
                "span_id": "s1",
                "inputs": {"secret": "not-exported"},
                "outputs": {"result": {"synthetic_total": 12}},
                "status": "OK",
            },
        ],
    }
    batch = conversations.extract_traces(
        [record], conversations.ExtractionConfig(shape="interaction")
    )
    turns = batch.conversations[0].turns
    assert [turn.role for turn in turns] == ["user", "tool", "assistant"]
    assert turns[1].turn_id == "t:tool:s1"
    assert "synthetic_total" in turns[1].text
    assert "not-exported" not in str(batch.conversations)
    assert len(conversations.extract_questions(batch.conversations)) == 1
