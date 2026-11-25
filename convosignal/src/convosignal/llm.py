"""Small chat interface and explicit fixture-backed offline responses."""

import json
import warnings
from collections.abc import Mapping
from typing import Any, Protocol

from convosignal import config


class ChatClient(Protocol):
    """The model operations needed by proposal and evidence extraction."""

    model_identifier: str

    def complete(self, system: str, user: str) -> str:
        """Return response text or raise a visible operational error."""
        ...


class FakeLLM:
    """Replay supplied responses by conversation ID; never infer evidence.

    Responses are synthetic evidence interpretations, not labels. Unknown inputs
    fail rather than silently producing favorable or generic results.
    """

    model_identifier = "fake-fixtures-v1"

    def __init__(self, responses: Mapping[str, object]):
        self.responses = dict(responses)
        self.calls: list[str] = []

    def complete(self, system: str, user: str) -> str:
        """Return the explicitly supplied response for this input."""
        key = json.loads(user).get("conversation_id", "taxonomy")
        self.calls.append(key)
        if key not in self.responses:
            raise RuntimeError("No fake response configured for this input")
        response = self.responses[key]
        if isinstance(response, str):
            return response
        return json.dumps(response)


class DatabricksChat:
    """Databricks serving-endpoint chat using standard SDK authentication."""

    def __init__(self, settings: "config.Settings", *, workspace: Any = None):
        if not settings.endpoint:
            raise ValueError(
                "Configure CONVOSIGNAL_ENDPOINT or endpoint in TOML"
            )
        if workspace is None:
            from databricks import sdk

            workspace = sdk.WorkspaceClient(
                config=sdk.config.Config(
                    profile=settings.profile,
                    http_timeout_seconds=settings.timeout_seconds,
                ),
            )
        self.workspace = workspace
        self.model_identifier = settings.endpoint
        self.max_tokens = settings.max_tokens
        self.temperature_supported = True
        self.diagnostics: list[str] = []

    def complete(self, system: str, user: str) -> str:
        """Query once, with one disclosed temperature-specific fallback only."""
        from databricks.sdk.service import serving

        messages = [
            serving.ChatMessage(
                content=system, role=serving.ChatMessageRole.SYSTEM
            ),
            serving.ChatMessage(
                content=user, role=serving.ChatMessageRole.USER
            ),
        ]
        kwargs: dict[str, Any] = {
            "messages": messages,
            "max_tokens": self.max_tokens,
        }
        if self.temperature_supported:
            kwargs["temperature"] = 0.0
        try:
            response = self.workspace.serving_endpoints.query(
                self.model_identifier, **kwargs
            )
        except Exception as error:
            message = str(error).lower()
            rejected_temperature = (
                "temperature" in message
                and any(
                    term in message
                    for term in (
                        "not supported",
                        "does not support",
                        "unsupported",
                        "not allowed",
                        "must be 1",
                    )
                )
                and type(error).__name__
                in {"BadRequest", "InvalidParameterValue"}
            )
            if not self.temperature_supported or not rejected_temperature:
                raise
            self.temperature_supported = False
            self.diagnostics.append(
                "Endpoint rejected temperature; retried without it"
            )
            warnings.warn(self.diagnostics[-1], UserWarning, stacklevel=2)
            del kwargs["temperature"]
            response = self.workspace.serving_endpoints.query(
                self.model_identifier, **kwargs
            )
        payload = (
            response.as_dict() if hasattr(response, "as_dict") else response
        )
        choices = payload.get("choices", [])
        if not choices:
            raise ValueError("Model response has no choices")
        choice = choices[0]
        used_tokens = payload.get("usage", {}).get("completion_tokens")
        if isinstance(used_tokens, int) and used_tokens >= self.max_tokens:
            raise ValueError("Model response exhausted the output token budget")
        if choice.get("finish_reason") in {
            "length",
            "max_tokens",
            "content_filter",
        }:
            raise ValueError("Model response was truncated or filtered")
        content = choice.get("message", {}).get("content")
        if isinstance(content, list):
            content = "\n".join(
                block["text"]
                for block in content
                if block.get("type") in {"text", "output_text"}
                and isinstance(block.get("text"), str)
            )
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Model returned no usable text content")
        return content


class UnconfiguredClient:
    """Permit excluded-only runs without pretending a model is connected."""

    model_identifier = "not_configured"

    def complete(self, system: str, user: str) -> str:
        """Fail explicitly if an eligible conversation needs a model."""
        raise ValueError("Configure a Databricks endpoint or fake responses")
