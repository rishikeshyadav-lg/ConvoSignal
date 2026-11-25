"""Runtime settings using standard SDK authentication."""

import os
import pathlib
import tomllib
from typing import Literal

import pydantic


class Settings(pydantic.BaseModel):
    """Explicit bounds and identifiers; no real workspace/resource defaults."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)
    tracking_uri: str | None = None
    experiment_id: str | None = None
    endpoint: str | None = None
    profile: str | None = None
    limit: int = pydantic.Field(default=50, ge=1, le=10_000)
    start_time_ms: int | None = pydantic.Field(default=None, ge=0)
    end_time_ms: int | None = pydantic.Field(default=None, ge=0)
    shape: Literal["chat", "interaction"] = "interaction"
    messages_path: str = "messages"
    question_path: str = "query"
    answer_path: str = "answer"
    session_path: str | None = None
    root_span_name: str = "interaction"
    excluded_users: tuple[str, ...] = ()
    max_tokens: int = pydantic.Field(default=8000, ge=1, le=32000)
    timeout_seconds: int = pydantic.Field(default=120, ge=1, le=600)
    output_dir: pathlib.Path = pathlib.Path("results")
    max_input_chars: int = pydantic.Field(default=200_000, ge=1000)

    @pydantic.model_validator(mode="after")
    def validate_window(self) -> "Settings":
        """Reject inverted windows before performing remote reads."""
        if (
            self.start_time_ms is not None
            and self.end_time_ms is not None
            and self.start_time_ms > self.end_time_ms
        ):
            raise ValueError("start_time_ms must not exceed end_time_ms")
        return self


def load(path: pathlib.Path | None = None) -> Settings:
    """Read optional TOML plus standard connection environment overrides."""
    data = {}
    if path is not None:
        with path.open("rb") as stream:
            data.update(tomllib.load(stream))
    environment = {
        "tracking_uri": "MLFLOW_TRACKING_URI",
        "experiment_id": "MLFLOW_EXPERIMENT_ID",
        "profile": "DATABRICKS_CONFIG_PROFILE",
        "endpoint": "CONVOSIGNAL_ENDPOINT",
        "max_tokens": "CONVOSIGNAL_MAX_TOKENS",
        "limit": "CONVOSIGNAL_TRACE_LIMIT",
        "question_path": "CONVOSIGNAL_QUESTION_PATH",
        "answer_path": "CONVOSIGNAL_ANSWER_PATH",
        "messages_path": "CONVOSIGNAL_MESSAGES_PATH",
        "shape": "CONVOSIGNAL_TRACE_SHAPE",
        "session_path": "CONVOSIGNAL_SESSION_PATH",
        "output_dir": "CONVOSIGNAL_OUTPUT_DIR",
        "max_input_chars": "CONVOSIGNAL_MAX_INPUT_CHARS",
    }
    for key, variable in environment.items():
        value = os.environ.get(variable)
        if value:
            data[key] = value
    return Settings.model_validate(data)
