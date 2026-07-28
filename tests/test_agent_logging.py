"""Tests for agent lifecycle logging."""

from __future__ import annotations

import logging

from cin_lite.agents.summarizer import SummarizerAgent
from cin_lite.agents.router import RouterAgent
from cin_lite.agents.proposal_writer import ProposalWriterAgent
from cin_lite.agents.manager import AgentManager


def test_summarizer_logs_initialize(caplog):
    agent = SummarizerAgent()
    with caplog.at_level(logging.INFO, logger="cin_lite.agents.summarizer"):
        agent.initialize({})
    assert any("summarizer" in r.message and "initialized" in r.message for r in caplog.records)


def test_summarizer_logs_execute(caplog, mapped_contract, intelligence, flags):
    agent = SummarizerAgent()
    agent.initialize({})
    with caplog.at_level(logging.DEBUG, logger="cin_lite.agents.summarizer"):
        agent.execute({"contract": mapped_contract, "intelligence": intelligence, "flags": flags})
    assert any("executing" in r.message for r in caplog.records)


def test_summarizer_logs_shutdown(caplog):
    agent = SummarizerAgent()
    agent.initialize({})
    with caplog.at_level(logging.INFO, logger="cin_lite.agents.summarizer"):
        agent.shutdown()
    assert any("shut down" in r.message for r in caplog.records)


def test_summarizer_logs_claude_failure(caplog, mapped_contract, intelligence, flags, install_anthropic):
    install_anthropic(RuntimeError("api down"))
    agent = SummarizerAgent()
    agent.initialize({})
    with caplog.at_level(logging.ERROR, logger="cin_lite.agents.summarizer"):
        agent.execute({"contract": mapped_contract, "intelligence": intelligence, "flags": flags})
    assert any("failed" in r.message and r.levelno == logging.ERROR for r in caplog.records)


def test_router_logs_initialize(caplog):
    agent = RouterAgent()
    with caplog.at_level(logging.INFO, logger="cin_lite.agents.router"):
        agent.initialize({})
    assert any("router" in r.message and "initialized" in r.message for r in caplog.records)


def test_router_logs_shutdown(caplog):
    agent = RouterAgent()
    agent.initialize({})
    with caplog.at_level(logging.INFO, logger="cin_lite.agents.router"):
        agent.shutdown()
    assert any("shut down" in r.message for r in caplog.records)


def test_proposal_writer_logs_initialize(caplog):
    agent = ProposalWriterAgent()
    with caplog.at_level(logging.INFO, logger="cin_lite.agents.proposal_writer"):
        agent.initialize({})
    assert any("proposal-writer" in r.message and "initialized" in r.message
               for r in caplog.records)


def test_proposal_writer_logs_shutdown(caplog):
    agent = ProposalWriterAgent()
    agent.initialize({})
    with caplog.at_level(logging.INFO, logger="cin_lite.agents.proposal_writer"):
        agent.shutdown()
    assert any("shut down" in r.message for r in caplog.records)


def test_manager_logs_register(caplog):
    mgr = AgentManager()
    with caplog.at_level(logging.INFO, logger="cin_lite.agents.manager"):
        mgr.register(SummarizerAgent())
    assert any("registered" in r.message and "summarizer" in r.message for r in caplog.records)


def test_manager_logs_initialize_all(caplog):
    mgr = AgentManager()
    mgr.register(SummarizerAgent())
    mgr.register(RouterAgent())
    with caplog.at_level(logging.INFO, logger="cin_lite.agents.manager"):
        mgr.initialize_all({})
    assert any("initializing 2 agent(s)" in r.message for r in caplog.records)


def test_manager_logs_shutdown_all(caplog):
    mgr = AgentManager()
    mgr.register(SummarizerAgent())
    mgr.initialize_all({})
    with caplog.at_level(logging.INFO, logger="cin_lite.agents.manager"):
        mgr.shutdown_all()
    assert any("shutting down" in r.message for r in caplog.records)


def test_claude_mode_logs_model(caplog, install_anthropic):
    install_anthropic("test")
    agent = SummarizerAgent()
    with caplog.at_level(logging.INFO, logger="cin_lite.agents.summarizer"):
        agent.initialize({})
    assert any("Claude mode" in r.message for r in caplog.records)
