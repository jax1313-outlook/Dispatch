"""Targeted tests for previously uncovered branches across the codebase.

Covers edge-case paths in rule modules, email delivery SMTP branches,
agent ImportError fallbacks, log_config idempotency, and proposal workflow gaps.
"""

from __future__ import annotations

import logging
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from cin_lite.rules import (
    pricing_anomaly,
    vendor_network,
    subcontractor_dominance,
    foreign_influence,
    cyber_compliance,
    past_performance,
    jv_mp_structure,
)
from cin_lite import email_delivery


# =========================================================================== #
# Rule module edge-case branches                                              #
# =========================================================================== #


class TestPricingAnomaly:
    def test_value_below_band(self):
        contract = {"estimated_value": 10_000}
        r = pricing_anomaly.run(contract)
        assert "value_below_band" in r.flags

    def test_value_above_band(self):
        contract = {"estimated_value": 200_000_000}
        r = pricing_anomaly.run(contract)
        assert "value_above_band" in r.flags

    def test_value_below_and_not_round(self):
        contract = {"estimated_value": 5_000}
        r = pricing_anomaly.run(contract)
        assert "value_below_band" in r.flags
        assert "suspiciously_round" not in r.flags

    def test_value_above_and_round(self):
        contract = {"estimated_value": 200_000_000}
        r = pricing_anomaly.run(contract)
        assert "value_above_band" in r.flags
        assert "suspiciously_round" in r.flags


class TestVendorNetwork:
    def test_poc_emails_field_path(self):
        contract = {
            "title": "",
            "description": "",
            "notes": "",
            "poc_emails": ["vendor@gmail.com"],
        }
        r = vendor_network.run(contract)
        assert "gmail.com" in r.findings["poc_domains"]
        assert r.findings["network_score"] >= 2
        assert "vendor_network_signals" in r.flags

    def test_affiliation_language(self):
        contract = {
            "title": "",
            "description": "The parent company controls the subsidiary.",
            "notes": "",
        }
        r = vendor_network.run(contract)
        assert "affiliation" in r.findings["indicators"]
        assert r.findings["network_score"] == 2

    def test_risk_low(self):
        contract = {
            "title": "",
            "description": "Teaming agreement is referenced.",
            "notes": "",
        }
        r = vendor_network.run(contract)
        assert r.findings["network_risk"] == "low"
        assert r.findings["network_score"] == 1

    def test_risk_moderate(self):
        contract = {
            "title": "",
            "description": "The parent company subsidiary is under common control.",
            "notes": "",
            "poc_emails": ["user@gmail.com"],
        }
        r = vendor_network.run(contract)
        assert r.findings["network_risk"] == "moderate"
        assert 3 <= r.findings["network_score"] <= 5


class TestSubcontractorDominance:
    def test_emphasis_low_single_mention(self):
        contract = {
            "title": "IT Services",
            "description": "Subcontractor may assist with delivery.",
            "notes": "",
        }
        r = subcontractor_dominance.run(contract)
        assert r.findings["subcontract_mentions"] >= 1
        assert r.score == 1
        assert r.findings["dominance_risk"] == "low"

    def test_risk_low_one_mention(self):
        contract = {
            "title": "",
            "description": "Subcontract tasks are minimal.",
            "notes": "",
        }
        r = subcontractor_dominance.run(contract)
        assert r.findings["dominance_risk"] == "low"
        assert r.score <= 2

    def test_risk_moderate(self):
        contract = {
            "title": "",
            "description": (
                "Subcontractor subcontracting subcontract heavy reliance."
            ),
            "notes": "",
        }
        r = subcontractor_dominance.run(contract)
        assert r.findings["dominance_risk"] == "moderate"
        assert r.score == 3


class TestForeignInfluence:
    def test_citizenship_only(self):
        contract = {
            "title": "",
            "description": "All personnel must be a citizen of the United States.",
            "notes": "",
        }
        r = foreign_influence.run(contract)
        assert r.findings["citizenship_required"] is True
        assert r.findings["sensitivity"] == "low"
        assert r.score == 1

    def test_sensitivity_low(self):
        contract = {
            "title": "",
            "description": "U.S. persons only requirement.",
            "notes": "",
        }
        r = foreign_influence.run(contract)
        assert r.findings["sensitivity"] == "low"
        assert r.score == 1


class TestCyberCompliance:
    def test_readiness_burden_low(self):
        contract = {
            "title": "",
            "description": "Must comply with FISMA requirements.",
            "notes": "",
        }
        r = cyber_compliance.run(contract)
        assert r.findings["readiness_burden"] == "low"
        assert r.findings["burden_score"] <= 3
        assert "cyber_requirements_present" in r.flags


class TestPastPerformance:
    def test_demand_moderate(self):
        contract = {
            "title": "",
            "description": (
                "Past performance is required. Offerors must demonstrate "
                "relevant experience. CPARS records will be reviewed."
            ),
            "notes": "",
        }
        r = past_performance.run(contract)
        assert r.findings["demand"] == "moderate"
        assert 3 <= r.score <= 4


class TestJvMpStructure:
    def test_presence_low(self):
        contract = {
            "title": "",
            "description": "This is a joint venture opportunity.",
            "notes": "",
        }
        r = jv_mp_structure.run(contract)
        assert r.findings["presence"] == "low"
        assert r.score == 1
        assert "jv_structure" in r.flags


# =========================================================================== #
# Email delivery SMTP branches                                                #
# =========================================================================== #


class _FakeSMTP:
    def __init__(self, host, port, timeout=None):
        self.starttls_called = False
        self.login_called = False
        self.login_args = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        self.starttls_called = True

    def login(self, user, password):
        self.login_called = True
        self.login_args = (user, password)

    def send_message(self, msg):
        pass


class TestSmtpStarttls:
    def test_starttls_enabled(self, monkeypatch):
        instance = _FakeSMTP("smtp.test.com", 587)
        monkeypatch.setenv("CIN_LITE_SMTP_HOST", "smtp.test.com")
        monkeypatch.setenv("CIN_LITE_SMTP_STARTTLS", "1")
        monkeypatch.setattr(email_delivery.smtplib, "SMTP", lambda *a, **k: instance)
        status = email_delivery.send("S", "B", ["a@b.com"], "TLS-1")
        assert instance.starttls_called
        assert "sent via" in status

    def test_starttls_default(self, monkeypatch):
        instance = _FakeSMTP("smtp.test.com", 587)
        monkeypatch.setenv("CIN_LITE_SMTP_HOST", "smtp.test.com")
        monkeypatch.delenv("CIN_LITE_SMTP_STARTTLS", raising=False)
        monkeypatch.setattr(email_delivery.smtplib, "SMTP", lambda *a, **k: instance)
        status = email_delivery.send("S", "B", ["a@b.com"], "TLS-2")
        assert instance.starttls_called


class TestSmtpLogin:
    def test_login_with_credentials(self, monkeypatch):
        instance = _FakeSMTP("smtp.test.com", 587)
        monkeypatch.setenv("CIN_LITE_SMTP_HOST", "smtp.test.com")
        monkeypatch.setenv("CIN_LITE_SMTP_STARTTLS", "0")
        monkeypatch.setenv("CIN_LITE_SMTP_USER", "myuser")
        monkeypatch.setenv("CIN_LITE_SMTP_PASSWORD", "mypass")
        monkeypatch.setattr(email_delivery.smtplib, "SMTP", lambda *a, **k: instance)
        status = email_delivery.send("S", "B", ["a@b.com"], "LOGIN-1")
        assert instance.login_called
        assert instance.login_args == ("myuser", "mypass")
        assert "sent via" in status

    def test_login_with_user_no_password(self, monkeypatch):
        instance = _FakeSMTP("smtp.test.com", 587)
        monkeypatch.setenv("CIN_LITE_SMTP_HOST", "smtp.test.com")
        monkeypatch.setenv("CIN_LITE_SMTP_STARTTLS", "0")
        monkeypatch.setenv("CIN_LITE_SMTP_USER", "myuser")
        monkeypatch.delenv("CIN_LITE_SMTP_PASSWORD", raising=False)
        monkeypatch.setattr(email_delivery.smtplib, "SMTP", lambda *a, **k: instance)
        status = email_delivery.send("S", "B", ["a@b.com"], "LOGIN-2")
        assert instance.login_called
        assert instance.login_args == ("myuser", "")


# =========================================================================== #
# Agent ImportError fallback branches                                         #
# =========================================================================== #


class TestAgentImportErrorFallback:
    def _make_import_error_module(self, monkeypatch):
        """Install a fake anthropic module that raises ImportError on import."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        original_import = builtins_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def fake_import(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("No module named 'anthropic'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)

    def test_summarizer_import_error(self, monkeypatch, mapped_contract, intelligence, flags):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delitem(sys.modules, "anthropic", raising=False)

        from cin_lite.agents.summarizer import SummarizerAgent
        agent = SummarizerAgent()

        original_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("no anthropic")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            agent.initialize({})

        assert agent._client is None
        result = agent.execute({
            "contract": mapped_contract,
            "intelligence": intelligence,
            "flags": flags,
        })
        assert mapped_contract["title"] in result
        agent.shutdown()

    def test_router_import_error(self, monkeypatch, mapped_contract, intelligence, flags):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delitem(sys.modules, "anthropic", raising=False)

        from cin_lite.agents.router import RouterAgent
        agent = RouterAgent()

        original_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("no anthropic")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            agent.initialize({})

        assert agent._client is None
        result = agent.execute({
            "contract": mapped_contract,
            "intelligence": intelligence,
            "summary": "test summary",
            "flags": flags,
        })
        assert "action" in result
        agent.shutdown()

    def test_proposal_writer_import_error(self, monkeypatch, mapped_contract, intelligence):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delitem(sys.modules, "anthropic", raising=False)

        from cin_lite.agents.proposal_writer import ProposalWriterAgent
        agent = ProposalWriterAgent()

        original_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("no anthropic")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            agent.initialize({})

        assert agent._client is None
        result = agent.execute({
            "contract": mapped_contract,
            "intelligence": intelligence,
            "brief": {"flags": [], "response_deadline": "2026-08-15"},
            "summary": "test summary",
        })
        assert "Proposal Outline" in result
        agent.shutdown()


# =========================================================================== #
# log_config double-configure guard                                           #
# =========================================================================== #


class TestLogConfigIdempotent:
    def test_double_configure_is_noop(self, tmp_path, monkeypatch):
        from cin_lite import log_config

        log_config._configured = False

        log_config.configure(log_dir=tmp_path / "logs1")
        assert log_config._configured is True

        log_config.configure(log_dir=tmp_path / "logs2")
        assert not (tmp_path / "logs2").exists()

        log_config._configured = False


# =========================================================================== #
# Proposal workflow: value_missing flag branch                                #
# =========================================================================== #


class TestProposalValueMissingFlag:
    def test_requirements_checklist_includes_value_missing(self):
        from cin_lite.workflows import proposal

        intelligence = {
            "set_aside_detection": {"findings": {"set_asides": []}},
            "naics_sin_extraction": {"findings": {}},
            "cyber_compliance_readiness": {"findings": {}},
        }
        flags = ["value_missing"]
        checklist = proposal._requirements_checklist(intelligence, flags)
        assert any("bottoms-up" in item.lower() for item in checklist)

    def test_requirements_checklist_without_value_missing(self):
        from cin_lite.workflows import proposal

        intelligence = {
            "set_aside_detection": {"findings": {"set_asides": []}},
            "naics_sin_extraction": {"findings": {}},
            "cyber_compliance_readiness": {"findings": {}},
        }
        flags = []
        checklist = proposal._requirements_checklist(intelligence, flags)
        assert not any("bottoms-up" in item.lower() for item in checklist)


# =========================================================================== #
# Acquisition: non-string description branch                                  #
# =========================================================================== #


class TestAcquisitionDescriptionEdgeCases:
    def test_non_string_description_returns_empty(self):
        from cin_lite.acquisition import _fetch_description

        opp = {"description": 12345}
        result = _fetch_description(opp, api_key="FAKE")
        assert result == ""

    def test_none_description_returns_empty(self):
        from cin_lite.acquisition import _fetch_description

        opp = {"description": None}
        result = _fetch_description(opp, api_key="FAKE")
        assert result == ""

    def test_missing_description_returns_empty(self):
        from cin_lite.acquisition import _fetch_description

        opp = {}
        result = _fetch_description(opp, api_key="FAKE")
        assert result == ""

    def test_description_url_returns_non_json(self, monkeypatch):
        """Cover the JSONDecodeError path inside _fetch_description."""
        import io
        import urllib.request
        from cin_lite import acquisition

        raw_html = b"<html><body>Some description here</body></html>"
        mock_resp = io.BytesIO(raw_html)
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *a: None

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: mock_resp)
        opp = {"description": "https://api.sam.gov/opportunities/v2/desc/123"}
        result = acquisition._fetch_description(opp, api_key="FAKE")
        assert "Some description here" in result


# =========================================================================== #
# Proposal writer: no-compliance outline branch                               #
# =========================================================================== #


class TestProposalWriterNoCompliance:
    def test_outline_no_special_compliance(self):
        from cin_lite.agents.proposal_writer import _deterministic_outline

        contract = {"title": "Basic Services", "solicitation_number": "GS-01"}
        intelligence = {
            "set_aside_detection": {"findings": {"set_asides": []}},
            "naics_sin_extraction": {"findings": {"naics": [], "sins": []}},
            "cyber_compliance_readiness": {"findings": {"frameworks": []}},
        }
        brief = {"response_deadline": "2026-09-01", "flags": []}
        outline = _deterministic_outline(contract, intelligence, brief)
        assert "No special compliance requirements detected" in outline


# =========================================================================== #
# NAICS/SIN: naics_missing flag                                               #
# =========================================================================== #


class TestNaicsMissingFlag:
    def test_naics_missing_when_no_codes(self):
        from cin_lite.rules import naics_sin

        contract = {
            "title": "Consulting Services",
            "description": "General consulting without specific codes.",
            "naics_text": "",
            "notes": "",
        }
        r = naics_sin.run(contract)
        assert "naics_missing" in r.flags
        assert r.findings["naics"] == []
