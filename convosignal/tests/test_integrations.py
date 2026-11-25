"""SDK contracts tested without network, credentials or real workspace data."""

from types import SimpleNamespace

import pytest
from databricks.sdk import errors

from convosignal import config, llm, traces


def settings(**kwargs):
    return config.Settings(
        tracking_uri="databricks://placeholder",
        experiment_id="synthetic",
        **kwargs,
    )


def test_configuration_env_and_window_validation(monkeypatch, tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('experiment_id="example"\nlimit=3\n')
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "databricks://placeholder")
    assert config.load(path).limit == 3
    with pytest.raises(ValueError):
        settings(start_time_ms=3, end_time_ms=1)


class Query:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def query(self, name, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def answer(content="{}", finish="stop"):
    return {
        "choices": [{"finish_reason": finish, "message": {"content": content}}]
    }


def test_chat_temperature_fallback_is_specific_and_disclosed():
    query = Query(
        errors.BadRequest("temperature is not supported"), answer(), answer()
    )
    client = llm.DatabricksChat(
        settings(endpoint="fake"),
        workspace=SimpleNamespace(serving_endpoints=query),
    )
    with pytest.warns(UserWarning, match="temperature"):
        assert client.complete("system", "input") == "{}"
    client.complete("system", "input")
    assert len(query.calls) == 3
    assert query.calls[0]["temperature"] == 0.0
    assert "temperature" not in query.calls[1]
    assert "temperature" not in query.calls[2]


@pytest.mark.parametrize(
    "failure",
    [
        errors.BadRequest("unrelated invalid argument"),
        errors.PermissionDenied("authorization failed"),
        RuntimeError("temperature is not supported"),
    ],
)
def test_chat_does_not_retry_unrelated_failures(failure):
    query = Query(failure)
    client = llm.DatabricksChat(
        settings(endpoint="fake"),
        workspace=SimpleNamespace(serving_endpoints=query),
    )
    with pytest.raises(type(failure)):
        client.complete("system", "input")
    assert len(query.calls) == 1


def test_chat_handles_text_blocks_and_rejects_truncation():
    query = Query(
        answer(
            [
                {"type": "reasoning", "text": "hidden"},
                {"type": "text", "text": "{}"},
            ]
        ),
        answer("partial", "length"),
    )
    client = llm.DatabricksChat(
        settings(endpoint="fake"),
        workspace=SimpleNamespace(serving_endpoints=query),
    )
    assert client.complete("system", "input") == "{}"
    with pytest.raises(ValueError, match="truncated"):
        client.complete("system", "input")


class Page(list):
    def __init__(self, values, token=None):
        super().__init__(values)
        self.token = token


def header(key, timestamp, user="person"):
    return SimpleNamespace(
        info=SimpleNamespace(
            trace_id=key,
            timestamp_ms=timestamp,
            state="OK",
            trace_metadata={
                "mlflow.trace.user": user,
                "mlflow.trace.session": "session",
            },
        )
    )


class TraceClient:
    def __init__(self, pages, failure=None):
        self.pages = list(pages)
        self.searches = []
        self.downloads = []
        self.failure = failure

    def search_traces(self, **kwargs):
        self.searches.append(kwargs)
        return self.pages.pop(0)

    def get_trace(self, trace_id, display=False):
        self.downloads.append(trace_id)
        if self.failure == trace_id:
            raise OSError("not downloadable")
        span = SimpleNamespace(
            name="interaction",
            span_id="root",
            status="OK",
            inputs={"query": "Compare weeks"},
            outputs={"answer": "Result"},
        )
        return SimpleNamespace(data=SimpleNamespace(spans=[span]))


def test_trace_pagination_sorting_and_explicit_downloads():
    client = TraceClient(
        [Page([header("b", 2)], "next"), Page([header("a", 1)])]
    )
    result = traces.read(settings(limit=2), client=client)
    assert client.downloads == ["a", "b"]
    assert client.searches[0]["include_spans"] is False
    assert client.searches[1]["page_token"] == "next"
    assert result.batch.statistics["user_messages_extracted"] == 2
    assert result.batch.failures == ()


def test_download_failure_and_user_exclusion_are_not_silent():
    client = TraceClient(
        [Page([header("a", 1, "test"), header("b", 2)])], failure="b"
    )
    result = traces.read(
        settings(limit=2, excluded_users=("test",)), client=client
    )
    assert result.batch.statistics["traffic_excluded"] == 1
    assert result.batch.statistics["download_failures"] == 1
    assert result.batch.failures[0][0] == "b"
    assert client.downloads == ["b"]


def test_session_grouping_marks_bounded_history_incomplete():
    client = TraceClient([Page([header("a", 1)])])
    result = traces.read(
        settings(limit=1, session_path="session_id"), client=client
    )
    assert result.batch.conversations[0].conversation_id == "session"
    assert not result.batch.conversations[0].context_complete


def test_actual_endpoint_temperature_rejection_wording_is_supported():
    query = Query(
        errors.BadRequest("Model does not support the temperature parameter"),
        answer(),
    )
    client = llm.DatabricksChat(
        settings(endpoint="fake"),
        workspace=SimpleNamespace(serving_endpoints=query),
    )
    with pytest.warns(UserWarning, match="temperature"):
        assert client.complete("system", "input") == "{}"
    assert len(query.calls) == 2


def test_reliable_usage_exhaustion_is_rejected():
    response = answer()
    response["usage"] = {"completion_tokens": 8000}
    query = Query(response)
    client = llm.DatabricksChat(
        settings(endpoint="fake"),
        workspace=SimpleNamespace(serving_endpoints=query),
    )
    with pytest.raises(ValueError, match="token budget"):
        client.complete("system", "input")
