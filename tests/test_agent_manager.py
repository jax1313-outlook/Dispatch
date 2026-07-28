"""Tests for the AgentManager lifecycle coordinator."""

from __future__ import annotations

import pytest

from cin_lite.agents.base import BaseAgent
from cin_lite.agents.manager import AgentManager


class StubAgent(BaseAgent):
    NAME = "stub"
    VERSION = "0.1.0"

    def __init__(self):
        self.init_config = None
        self.last_payload = None
        self.is_shut_down = False

    def initialize(self, config):
        self.init_config = config

    def execute(self, payload):
        self.last_payload = payload
        return {"agent": self.NAME, "ok": True}

    def shutdown(self):
        self.is_shut_down = True


class SecondStub(StubAgent):
    NAME = "second"
    VERSION = "0.1.0"


class FailShutdown(StubAgent):
    NAME = "fail-shutdown"
    VERSION = "0.1.0"

    def shutdown(self):
        raise OSError("cleanup failed")


def test_register_and_get():
    mgr = AgentManager()
    agent = StubAgent()
    mgr.register(agent)
    assert mgr.get("stub") is agent


def test_register_rejects_empty_name():
    class NoName(StubAgent):
        NAME = ""

    mgr = AgentManager()
    with pytest.raises(ValueError, match="no NAME"):
        mgr.register(NoName())


def test_agents_property_returns_copy():
    mgr = AgentManager()
    mgr.register(StubAgent())
    snapshot = mgr.agents
    snapshot["injected"] = "bad"
    assert "injected" not in mgr.agents


def test_initialize_all():
    mgr = AgentManager()
    a, b = StubAgent(), SecondStub()
    mgr.register(a)
    mgr.register(b)
    mgr.initialize_all({"key": "val"})
    assert a.init_config == {"key": "val"}
    assert b.init_config == {"key": "val"}


def test_execute_by_name():
    mgr = AgentManager()
    mgr.register(StubAgent())
    mgr.initialize_all({})
    result = mgr.execute("stub", {"data": 1})
    assert result == {"agent": "stub", "ok": True}


def test_execute_unknown_name_raises():
    mgr = AgentManager()
    with pytest.raises(KeyError):
        mgr.execute("missing", {})


def test_shutdown_all():
    mgr = AgentManager()
    a, b = StubAgent(), SecondStub()
    mgr.register(a)
    mgr.register(b)
    mgr.shutdown_all()
    assert a.is_shut_down
    assert b.is_shut_down


def test_shutdown_all_continues_on_error():
    mgr = AgentManager()
    good = SecondStub()
    mgr.register(FailShutdown())
    mgr.register(good)
    with pytest.raises(RuntimeError, match="fail-shutdown"):
        mgr.shutdown_all()
    assert good.is_shut_down


def test_context_manager_shuts_down():
    a = StubAgent()
    with AgentManager() as mgr:
        mgr.register(a)
        mgr.initialize_all({})
        mgr.execute("stub", {"x": 1})
    assert a.is_shut_down


def test_context_manager_shuts_down_on_exception():
    a = StubAgent()
    with pytest.raises(ValueError):
        with AgentManager() as mgr:
            mgr.register(a)
            mgr.initialize_all({})
            raise ValueError("boom")
    assert a.is_shut_down


def test_pipeline_pattern():
    """Demonstrates the intended usage: sequential agents with data flow."""
    mgr = AgentManager()
    mgr.register(StubAgent())
    mgr.register(SecondStub())
    mgr.initialize_all({})

    r1 = mgr.execute("stub", {"step": 1})
    r2 = mgr.execute("second", {"step": 2, "prev": r1})

    assert r1["agent"] == "stub"
    assert r2["agent"] == "second"
    assert mgr.get("second").last_payload["prev"] == r1
    mgr.shutdown_all()
