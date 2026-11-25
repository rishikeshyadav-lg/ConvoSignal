"""Independent integration probes; no credentials or trace text are printed."""

import importlib.metadata
from typing import Any

from convosignal import config, llm, traces


def doctor(
    settings: config.Settings, *, probe_llm: bool = False
) -> dict[str, Any]:
    """Read one MLflow trace and optionally send a synthetic model probe."""
    result: dict[str, Any] = {
        "status": "ok",
        "mlflow": "not_configured",
        "llm": "not_checked",
        "versions": {
            name: importlib.metadata.version(name)
            for name in (
                "mlflow-skinny",
                "databricks-sdk",
                "pydantic",
            )
        },
        "calls": [],
    }
    if settings.tracking_uri and settings.experiment_id:
        try:
            result["calls"].append(
                "MLflow header search and download of at most one trace"
            )
            fetched = traces.read(settings.model_copy(update={"limit": 1}))
            result["mlflow"] = (
                "ok" if not fetched.batch.failures else "source_error"
            )
            result["trace_headers"] = fetched.metadata["headers_scanned"]
            result["source_failures"] = len(fetched.batch.failures)
            if fetched.batch.failures:
                result["status"] = "error"
        except Exception as error:
            result["mlflow"] = f"error ({type(error).__name__})"
            result["status"] = "error"
    if probe_llm:
        try:
            result["calls"].append("Synthetic model probe; no trace text sent")
            client = llm.DatabricksChat(
                settings.model_copy(update={"max_tokens": 256})
            )
            client.complete("Reply with OK only.", "Connectivity check.")
            result["llm"] = "ok"
            result["model_diagnostics"] = client.diagnostics
        except Exception as error:
            result["llm"] = f"error ({type(error).__name__})"
            result["status"] = "error"
    return result
