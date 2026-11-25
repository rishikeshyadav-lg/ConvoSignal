"""Shared synthetic accepted artifacts; no network or model involved."""

import json
import socket

import pytest

from convosignal import taxonomy


@pytest.fixture
def proposal():
    return taxonomy.propose(
        json.dumps(
            {
                "types": [
                    {
                        "name": "greeting",
                        "description": "Standalone greetings/thanks",
                        "markers": ["hi", "hello", "thanks"],
                        "asks_for": [],
                        "set_aside": True,
                    },
                    {
                        "name": "capability",
                        "description": "Agent capabilities",
                        "markers": [
                            "what can you do",
                            "your capabilities",
                            "which kpis",
                        ],
                        "asks_for": ["supported_tasks"],
                        "set_aside": True,
                    },
                    {
                        "name": "comparison",
                        "description": "Compare requested values",
                        "markers": ["compare", "week over week", "ctr"],
                        "asks_for": ["current_value", "previous_value"],
                        "set_aside": False,
                    },
                ]
            }
        ),
        [
            "Hello",
            "Hi",
            "Thanks, that's what I needed",
            "What can you do?",
            "Compare this week with last week",
            "Write a summary",
        ],
        model_identifier="synthetic-fixture-v1",
    )


@pytest.fixture
def accepted(proposal):
    return taxonomy.accept(proposal)


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    """Prevent network access throughout the synthetic test suite."""

    def blocked(*args, **kwargs):
        raise AssertionError("Offline tests must not open network connections")

    monkeypatch.delenv("CONVOSIGNAL_ENDPOINT", raising=False)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
