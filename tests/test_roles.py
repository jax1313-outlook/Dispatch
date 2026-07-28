"""Tests for role-based access control on agents."""

from __future__ import annotations

import logging

import pytest

from cin_lite.agents.base import BaseAgent, PermissionDeniedError
from cin_lite.agents.roles import Roles, ROLE_PERMISSIONS, permissions_for
from cin_lite.agents.summarizer import SummarizerAgent
from cin_lite.agents.router import RouterAgent
from cin_lite.agents.proposal_writer import ProposalWriterAgent


# ----------------------------------------------------------------- Roles module

class TestRolesModule:
    def test_all_roles_have_permissions(self):
        for role in (Roles.ACQUISITION, Roles.PROCESSING, Roles.ROUTING,
                     Roles.PUBLISHING, Roles.ARCHIVING, Roles.AUTOMATION):
            assert permissions_for(role), f"{role} has no permissions"

    def test_permissions_are_frozensets(self):
        for perms in ROLE_PERMISSIONS.values():
            assert isinstance(perms, frozenset)

    def test_unknown_role_returns_empty(self):
        assert permissions_for("nonexistent") == frozenset()

    def test_processing_includes_summarize(self):
        assert "summarize" in permissions_for(Roles.PROCESSING)

    def test_routing_includes_route(self):
        assert "route" in permissions_for(Roles.ROUTING)

    def test_publishing_includes_draft(self):
        assert "draft" in permissions_for(Roles.PUBLISHING)


# ----------------------------------------------------------------- check_permission

class PermittedAgent(BaseAgent):
    NAME = "permitted"
    VERSION = "0.1.0"
    ROLE = "processing"
    ACTION = "summarize"

    def initialize(self, config):
        pass

    def _execute(self, payload):
        return "done"

    def shutdown(self):
        pass


class TestCheckPermission:
    def test_permitted_action(self):
        agent = PermittedAgent()
        assert agent.check_permission("summarize") is True

    def test_denied_action(self):
        agent = PermittedAgent()
        assert agent.check_permission("route") is False

    def test_unknown_action(self):
        agent = PermittedAgent()
        assert agent.check_permission("hack_mainframe") is False


# ----------------------------------------------------------------- execute enforcement

class TestExecuteEnforcement:
    def test_execute_succeeds_with_default_action(self):
        agent = PermittedAgent()
        assert agent.execute({"data": 1}) == "done"

    def test_execute_succeeds_with_explicit_permitted_action(self):
        agent = PermittedAgent()
        assert agent.execute({"action": "analyze", "data": 1}) == "done"

    def test_execute_raises_on_denied_action(self):
        agent = PermittedAgent()
        with pytest.raises(PermissionDeniedError, match="route"):
            agent.execute({"action": "route"})

    def test_permission_denied_error_attrs(self):
        agent = PermittedAgent()
        with pytest.raises(PermissionDeniedError) as exc_info:
            agent.execute({"action": "route"})
        err = exc_info.value
        assert err.agent_name == "permitted"
        assert err.role == "processing"
        assert err.action == "route"

    def test_execute_logs_denial(self, caplog):
        agent = PermittedAgent()
        with caplog.at_level(logging.WARNING, logger="cin_lite.agents.base"):
            with pytest.raises(PermissionDeniedError):
                agent.execute({"action": "route"})
        assert any("denied" in r.message for r in caplog.records)

    def test_no_action_and_no_default_skips_check(self):
        class NoActionAgent(PermittedAgent):
            ACTION = ""

        agent = NoActionAgent()
        assert agent.execute({}) == "done"


# ----------------------------------------------------------------- concrete agents

class TestConcreteAgentRoles:
    def test_summarizer_role(self):
        agent = SummarizerAgent()
        assert agent.ROLE == "processing"
        assert agent.ACTION == "summarize"
        assert agent.check_permission("summarize") is True

    def test_router_role(self):
        agent = RouterAgent()
        assert agent.ROLE == "routing"
        assert agent.ACTION == "route"
        assert agent.check_permission("route") is True

    def test_proposal_writer_role(self):
        agent = ProposalWriterAgent()
        assert agent.ROLE == "publishing"
        assert agent.ACTION == "draft"
        assert agent.check_permission("draft") is True

    def test_summarizer_cannot_route(self):
        agent = SummarizerAgent()
        assert agent.check_permission("route") is False

    def test_router_cannot_draft(self):
        agent = RouterAgent()
        assert agent.check_permission("draft") is False

    def test_proposal_writer_cannot_summarize(self):
        agent = ProposalWriterAgent()
        assert agent.check_permission("summarize") is False

    def test_summarizer_execute_passes_permission(self, mapped_contract, intelligence, flags):
        agent = SummarizerAgent()
        agent.initialize({})
        result = agent.execute({
            "contract": mapped_contract,
            "intelligence": intelligence,
            "flags": flags,
        })
        assert isinstance(result, str) and result

    def test_router_execute_passes_permission(self, mapped_contract, intelligence, flags):
        agent = RouterAgent()
        agent.initialize({})
        result = agent.execute({
            "contract": mapped_contract,
            "intelligence": intelligence,
            "summary": "test",
            "flags": flags,
        })
        assert isinstance(result, dict)
        assert "action" in result
