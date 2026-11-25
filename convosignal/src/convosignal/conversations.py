"""Offline extraction from explicit chat or interaction trace snapshots."""

import dataclasses
import json
import pathlib
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import pydantic
from pydantic import dataclasses as validated_dataclasses

from convosignal import models

EXTRACTION_VERSION = "1"


@validated_dataclasses.dataclass(frozen=True, config=models.CONTRACT_CONFIG)
class Conversation:
    """Source turns retained in order, with an explicit boundary assumption."""

    conversation_id: str
    turns: tuple[models.Turn, ...]
    boundary: Literal["trace", "session", "snapshot"] = "snapshot"
    context_complete: pydantic.StrictBool = True
    diagnostics: tuple[str, ...] = ()


@validated_dataclasses.dataclass(frozen=True, config=models.CONTRACT_CONFIG)
class Question:
    """A nonblank user message; questions need not end in a question mark."""

    conversation_id: str
    trace_id: str
    turn_id: str
    message_position: int
    question: str


@dataclasses.dataclass(frozen=True)
class ExtractionConfig:
    """Explicit supported shape and dotted object/list paths; no wildcards."""

    shape: Literal["chat", "interaction"] = "chat"
    messages_path: str = "messages"
    question_path: str = "query"
    answer_path: str = "answer"
    session_path: str | None = None
    root_span_name: str = "interaction"


@dataclasses.dataclass(frozen=True)
class ExtractionBatch:
    """Successful conversations together with every failed source record."""

    conversations: tuple[Conversation, ...]
    statistics: dict[str, int]
    failures: tuple[tuple[str, str], ...]


class ExtractionError(ValueError):
    """No usable user questions, with the extraction diagnostics preserved."""

    def __init__(self, batch: ExtractionBatch):
        self.batch = batch
        super().__init__(
            "No user questions extracted; check shape/messages_path or "
            "question_path and inspect batch.failures"
        )


def read_path(value: Any, path: str) -> Any:
    """Read a dotted key path with numeric list indices; missing paths fail."""
    if not path or any(not part for part in path.split(".")):
        raise ValueError(
            "Extraction path must contain nonempty dotted segments"
        )
    current = value
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        elif (
            isinstance(current, list)
            and part.isdecimal()
            and int(part) < len(current)
        ):
            current = current[int(part)]
        else:
            raise ValueError(f"Missing extraction path: {path}")
    return current


def _interaction_messages(
    record: Mapping[str, Any], config: ExtractionConfig
) -> list[dict[str, Any]]:
    """Keep root query/answer and available tool outputs in span-list order."""
    spans = record.get("spans")
    if not isinstance(spans, list):
        raise ValueError("Interaction shape requires a spans list")
    roots = [
        s
        for s in spans
        if isinstance(s, dict) and s.get("name") == config.root_span_name
    ]
    if len(roots) != 1:
        raise ValueError("Expected exactly one configured interaction span")
    root = roots[0]
    question = read_path(root.get("inputs"), config.question_path)
    messages = [{"role": "user", "content": question}]
    for index, span in enumerate(spans):
        if not isinstance(span, dict):
            raise ValueError("Spans must be objects")
        name = span.get("name")
        if not isinstance(name, str) or not name.startswith("tool:"):
            continue
        outputs = span.get("outputs")
        result = (
            outputs.get("result", outputs)
            if isinstance(outputs, dict)
            else outputs
        )
        content = json.dumps(
            {"tool_name": name, "result": result, "status": span.get("status")},
            ensure_ascii=False,
        )
        span_id = span.get("span_id", str(index))
        messages.append(
            {
                "role": "tool",
                "content": content,
                "turn_id": f"{record['trace_id']}:tool:{span_id}",
            }
        )
    outputs = root.get("outputs")
    if outputs is not None:
        messages.append(
            {
                "role": "assistant",
                "content": read_path(outputs, config.answer_path),
                "turn_id": f"{record['trace_id']}:answer",
            }
        )
    return messages


def _trace_turns(
    record: Mapping[str, Any], config: ExtractionConfig
) -> tuple[list[models.Turn], int, int]:
    """Extract one trace atomically, without dropping malformed messages."""
    trace_id = record["trace_id"]
    if config.shape == "chat":
        messages = read_path(record, config.messages_path)
    elif config.shape == "interaction":
        messages = _interaction_messages(record, config)
    else:
        raise ValueError("Unsupported trace shape; choose chat or interaction")
    if not isinstance(messages, list) or not messages:
        raise ValueError("Configured message path must contain a nonempty list")
    turns = []
    blank = blank_users = 0
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object")
        role, content = message.get("role"), message.get("content")
        if role not in {"user", "assistant", "tool"}:
            raise ValueError("Unsupported/missing message role")
        if not isinstance(content, str):
            raise ValueError(
                "Message content must be text; configure an adapter"
            )
        if not content.strip():
            blank += 1
            blank_users += role == "user"
            continue
        turn_id = message.get("turn_id", f"{trace_id}:message:{index}")
        if not isinstance(turn_id, str) or not turn_id.strip():
            raise ValueError("Native turn IDs must be nonblank strings")
        turns.append(
            models.Turn(
                turn_id,
                role,
                content,
                trace_id,
                index,
            )
        )
    return turns, blank, blank_users


def extract_traces(
    records: Sequence[Mapping[str, Any]],
    config: ExtractionConfig = ExtractionConfig(),
    *,
    require_questions: bool = True,
) -> ExtractionBatch:
    """Sort timestamp/ID, extract user/assistant/tool turns and expose failures.

    Session merging requires an explicitly configured key. Native turn IDs
    identify duplicate captures only when content/role agree. Text duplicates
    with different IDs are real occurrences and are preserved.
    """
    statistics = dict.fromkeys(
        (
            "traces_scanned",
            "extraction_failures",
            "duplicate_traces",
            "duplicate_turns",
            "messages_extracted",
            "user_messages_extracted",
            "blank_messages_excluded",
            "blank_user_messages_excluded",
        ),
        0,
    )
    statistics["traces_scanned"] = len(records)
    failures: list[tuple[str, str]] = []
    valid = []
    for record in records:
        if not isinstance(record, Mapping):
            failures.append(("<missing>", "Trace record must be an object"))
            continue
        trace_id, timestamp = record.get("trace_id"), record.get("timestamp_ms")
        if (
            not isinstance(trace_id, str)
            or not trace_id.strip()
            or type(timestamp) is not int
            or timestamp < 0
        ):
            failures.append(
                (
                    str(trace_id or "<missing>"),
                    "Nonblank trace_id and integer timestamp_ms required",
                )
            )
        else:
            valid.append(record)
    groups: dict[str, list[models.Turn]] = {}
    seen_traces: dict[str, Mapping[str, Any]] = {}
    group_diagnostics: dict[str, list[str]] = {}
    for record in sorted(
        valid, key=lambda row: (row["timestamp_ms"], row["trace_id"])
    ):
        trace_id = record["trace_id"]
        conversation_id = trace_id
        try:
            if config.session_path is not None:
                session = read_path(record, config.session_path)
                if not isinstance(session, str) or not session.strip():
                    raise ValueError("Configured session key must be nonblank")
                conversation_id = session
            if trace_id in seen_traces:
                if record != seen_traces[trace_id]:
                    raise ValueError(
                        "Conflicting captures for the same trace ID"
                    )
                statistics["duplicate_traces"] += 1
                continue
            seen_traces[trace_id] = record
            turns, blanks, blank_users = _trace_turns(record, config)
            existing = {t.turn_id: t for t in groups.get(conversation_id, [])}
            additions = []
            duplicate_count = 0
            for turn in turns:
                old = existing.get(turn.turn_id)
                if old is not None:
                    if (old.role, old.text) != (turn.role, turn.text):
                        raise ValueError(
                            "Conflicting capture for native turn ID"
                        )
                    duplicate_count += 1
                else:
                    existing[turn.turn_id] = turn
                    additions.append(turn)
            groups.setdefault(conversation_id, []).extend(additions)
            statistics["duplicate_turns"] += duplicate_count
            statistics["blank_messages_excluded"] += blanks
            statistics["blank_user_messages_excluded"] += blank_users
            if (
                record.get("incomplete")
                or record.get("state") == "ERROR"
                or (
                    config.shape == "interaction"
                    and not any(turn.role == "assistant" for turn in turns)
                )
            ):
                group_diagnostics.setdefault(conversation_id, []).append(
                    f"{trace_id}: incomplete/source-error trace"
                )
        except ValueError as error:
            failures.append((trace_id, str(error)))
            group_diagnostics.setdefault(conversation_id, []).append(
                f"{trace_id}: extraction failed"
            )
    conversations = tuple(
        Conversation(
            key,
            tuple(turns),
            "session" if config.session_path else "trace",
            not bool(group_diagnostics.get(key)),
            tuple(group_diagnostics.get(key, ())),
        )
        for key, turns in groups.items()
    )
    statistics["messages_extracted"] = sum(
        len(item.turns) for item in conversations
    )
    statistics["user_messages_extracted"] = sum(
        turn.role == "user" for item in conversations for turn in item.turns
    )
    statistics["extraction_failures"] = len(failures)
    batch = ExtractionBatch(conversations, statistics, tuple(failures))
    if require_questions and not statistics["user_messages_extracted"]:
        raise ExtractionError(batch)
    return batch


def extract_questions(
    conversations: Sequence[Conversation],
) -> tuple[Question, ...]:
    """Keep every nonblank user message, with original source positions."""
    return tuple(
        Question(
            item.conversation_id,
            turn.trace_id or item.conversation_id,
            turn.turn_id,
            turn.source_position if turn.source_position is not None else index,
            turn.text,
        )
        for item in conversations
        for index, turn in enumerate(item.turns)
        if turn.role == "user" and turn.text.strip()
    )


def validate_conversations(conversations: Sequence[Conversation]) -> None:
    """Reject ambiguous identities before constructing an input checksum."""
    ids = [item.conversation_id for item in conversations]
    if len(set(ids)) != len(ids) or any(not key.strip() for key in ids):
        raise ValueError("Conversation IDs must be nonblank and unique")
    for item in conversations:
        turn_ids = [turn.turn_id for turn in item.turns]
        if len(set(turn_ids)) != len(turn_ids) or any(
            not key.strip() for key in turn_ids
        ):
            raise ValueError(
                "Turn IDs must be nonblank and unique per conversation"
            )


def load_conversations(path: pathlib.Path) -> tuple[Conversation, ...]:
    """Load conversation JSONL in file order; question-only input is invalid."""
    adapter = pydantic.TypeAdapter(Conversation)
    conversations = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                conversations.append(adapter.validate_json(line, strict=True))
            except ValueError:
                raise ValueError(
                    f"Invalid conversation snapshot at line {line_number}"
                ) from None
    validate_conversations(conversations)
    return tuple(conversations)


def save_conversations(
    path: pathlib.Path,
    conversations: Sequence[Conversation],
    *,
    overwrite: bool = False,
) -> None:
    """Save replayable source turns without raw trace configuration."""
    validate_conversations(conversations)
    adapter = pydantic.TypeAdapter(Conversation)
    with path.open("w" if overwrite else "x", encoding="utf-8") as stream:
        for item in conversations:
            stream.write(adapter.dump_json(item).decode("utf-8") + "\n")


def conversation_data(conversations: Sequence[Conversation]) -> list[Any]:
    """Return normalized JSON data in order for canonical input hashing."""
    adapter = pydantic.TypeAdapter(Conversation)
    return [json.loads(adapter.dump_json(item)) for item in conversations]


def load_questions(path: pathlib.Path) -> tuple[Conversation, ...]:
    """Read question-only JSONL for classification, never satisfaction evidence.

    Conversation groups must be contiguous, as in questions.jsonl written by
    this package. Interleaved groups are rejected instead of silently reordered.
    """
    adapter = pydantic.TypeAdapter(Question)
    grouped: dict[str, list[models.Turn]] = {}
    previous = None
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                question = adapter.validate_json(line, strict=True)
            except ValueError:
                raise ValueError(
                    f"Invalid question snapshot at line {number}"
                ) from None
            key = question.conversation_id
            if key != previous and key in grouped:
                raise ValueError(
                    "Question snapshots require contiguous conversation groups"
                )
            grouped.setdefault(key, []).append(
                models.Turn(
                    question.turn_id,
                    "user",
                    question.question,
                    question.trace_id,
                    question.message_position,
                )
            )
            previous = key
    result = tuple(
        Conversation(
            key,
            tuple(turns),
            context_complete=False,
            diagnostics=("question_only_snapshot",),
        )
        for key, turns in grouped.items()
    )
    validate_conversations(result)
    return result
