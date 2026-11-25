"""Bounded MLflow header listing and explicit, audited artifact downloads."""

import dataclasses
from typing import Any

from convosignal import config, conversations


@dataclasses.dataclass(frozen=True)
class TraceRead:
    """Normalized records with source failures and provenance diagnostics."""

    batch: conversations.ExtractionBatch
    metadata: dict[str, Any]


def read(
    settings: config.Settings,
    *,
    client: Any = None,
) -> TraceRead:
    """Read each selected trace explicitly and record artifact failures.

    Header bounds apply before explicit excluded-user filtering. Session context
    outside the selected window/limit is not fetched; merged histories therefore
    remain marked incomplete. This bounded behavior avoids pretending that a
    historic session is complete merely because its newest traces were returned.
    """
    if not settings.experiment_id or not settings.tracking_uri:
        raise ValueError("MLflow tracking_uri and experiment_id are required")
    if client is None:
        from mlflow import tracking

        client = tracking.MlflowClient(tracking_uri=settings.tracking_uri)
    filters = []
    if settings.shape == "interaction":
        name = settings.root_span_name
        if "'" in name:
            raise ValueError("Root span name cannot contain a quote")
        filters.append(f"trace.name = '{name}'")
    if settings.start_time_ms is not None:
        filters.append(f"trace.timestamp_ms >= {settings.start_time_ms}")
    if settings.end_time_ms is not None:
        filters.append(f"trace.timestamp_ms <= {settings.end_time_ms}")
    headers: list[Any] = []
    token = None
    seen_tokens = set()
    while len(headers) < settings.limit:
        page = client.search_traces(
            locations=[settings.experiment_id],
            max_results=min(200, settings.limit - len(headers)),
            order_by=["timestamp_ms DESC"],
            page_token=token,
            filter_string=" and ".join(filters) or None,
            include_spans=False,
        )
        headers.extend(page)
        token = page.token
        if not token or not page:
            break
        if token in seen_tokens:
            raise ValueError("MLflow pagination repeated a page token")
        seen_tokens.add(token)
    headers.sort(key=lambda item: (item.info.timestamp_ms, item.info.trace_id))
    if len({header.info.trace_id for header in headers}) != len(headers):
        raise ValueError("MLflow returned duplicate trace headers")
    records = []
    selected_headers = []
    failures = []
    failure_conversations = {}
    excluded = 0
    provenance: dict[str, int] = {}
    for header in headers:
        info = header.info
        user = str(info.trace_metadata.get("mlflow.trace.user", ""))
        if user in settings.excluded_users:
            excluded += 1
            continue
        selected_headers.append(
            {
                "trace_id": info.trace_id,
                "session_id": str(
                    info.trace_metadata.get("mlflow.trace.session")
                    or info.trace_id
                )
                if settings.session_path
                else info.trace_id,
                "timestamp_ms": info.timestamp_ms,
                "user": user,
            }
        )
        cohort = "shared_a2a" if user == "a2a-user" else "unverified_identity"
        provenance[cohort] = provenance.get(cohort, 0) + 1
        try:
            trace = client.get_trace(info.trace_id, display=False)
        except Exception as error:  # Remote artifact boundary, recorded below.
            failure_conversations[info.trace_id] = (
                str(
                    info.trace_metadata.get("mlflow.trace.session")
                    or info.trace_id
                )
                if settings.session_path
                else info.trace_id
            )
            failures.append(
                (
                    info.trace_id,
                    f"Artifact download failed ({type(error).__name__})",
                )
            )
            continue
        spans = trace.data.spans
        normalized_spans = [
            {
                "name": span.name,
                "span_id": span.span_id,
                "inputs": span.inputs
                if span.name == settings.root_span_name
                else {},
                "outputs": span.outputs,
                "status": str(span.status),
            }
            for span in spans
        ]
        record = {
            "trace_id": info.trace_id,
            "timestamp_ms": info.timestamp_ms,
            "spans": normalized_spans,
            "state": str(info.state),
            "session_id": info.trace_metadata.get("mlflow.trace.session"),
            "incomplete": bool(settings.session_path),
        }
        if settings.shape == "chat":
            roots = [s for s in spans if s.name == settings.root_span_name]
            if len(roots) == 1 and isinstance(roots[0].inputs, dict):
                record["chat_input"] = roots[0].inputs
        records.append(record)
    batch = conversations.extract_traces(
        records,
        conversations.ExtractionConfig(
            shape=settings.shape,
            messages_path=(
                f"chat_input.{settings.messages_path}"
                if settings.shape == "chat"
                else settings.messages_path
            ),
            question_path=settings.question_path,
            answer_path=settings.answer_path,
            session_path=settings.session_path,
            root_span_name=settings.root_span_name,
        ),
        require_questions=False,
    )
    stats = dict(batch.statistics)
    stats["headers_scanned"] = len(headers)
    stats["traffic_excluded"] = excluded
    stats["download_failures"] = len(failures)
    stats["extraction_failures"] += len(failures)
    batch = dataclasses.replace(
        batch, statistics=stats, failures=(*batch.failures, *failures)
    )
    return TraceRead(
        batch,
        {
            "traces": selected_headers,
            "experiment_id": settings.experiment_id,
            "headers_scanned": len(headers),
            "has_more": bool(token),
            "selection": (
                "recent bounded headers; timestamp ties use server "
                "page boundaries"
            ),
            "session_context": "bounded; outside-window history not fetched",
            "traffic_excluded": excluded,
            "provenance": provenance,
            "failure_conversations": failure_conversations,
        },
    )
