"""Tests for the BaseAgent abstract interface."""

from __future__ import annotations

import pytest

from cin_lite.agents.base import BaseAgent, PermissionDeniedError


class ConcreteAgent(BaseAgent):
    NAME = "test-agent"
    VERSION = "0.1.0"
    ROLE = "processing"
    ACTION = "summarize"

    def __init__(self):
        self.initialized = False
        self.last_payload = None
        self.shut_down = False

    def initialize(self, config):
        self.initialized = True
        self.config = config

    def _execute(self, payload):
        self.last_payload = payload
        return {"ok": True}

    def shutdown(self):
        self.shut_down = True


def test_concrete_lifecycle():
    agent = ConcreteAgent()
    agent.initialize({"key": "val"})
    assert agent.initialized
    result = agent.execute({"data": 1})
    assert result == {"ok": True}
    agent.shutdown()
    assert agent.shut_down


def test_cannot_instantiate_without_all_methods():
    class Incomplete(BaseAgent):
        def initialize(self, config):
            pass

    with pytest.raises(TypeError):
        Incomplete()


def test_name_and_version():
    agent = ConcreteAgent()
    assert agent.NAME == "test-agent"
    assert agent.VERSION == "0.1.0"
