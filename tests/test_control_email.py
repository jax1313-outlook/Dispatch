"""Tests for the Control Layer: email rendering, decision collection, delivery."""

from __future__ import annotations

import builtins

import pytest

from cin_lite import control, email_delivery


# --------------------------------------------------------------------------- actions

def test_actions_and_resolve():
    assert set(control.ACTIONS) == {
        "approve_archive", "approve_proposal", "reject", "flag_review", "deeper_analysis"
    }
    label, route = control.resolve("approve_proposal")
    assert (label, route) == ("Approve for proposal", "PROPOSAL_QUEUE")


def test_resolve_unknown_raises():
    with pytest.raises(ValueError):
        control.resolve("bogus")


# --------------------------------------------------------------------------- render_email

def test_render_email_contains_all_sections(mapped_contract, intelligence, flags):
    decision = {"action": "approve_proposal", "priority": "high",
                "recipient": "proposal-team", "reason": "fit", "notes": "n"}
    email = control.render_email(mapped_contract, intelligence, "THE SUMMARY", flags, decision)

    assert "THE SUMMARY" in email
    assert "Flags raised:" in email
    assert "Risk scores:" in email
    assert "vendor_network_indicators:" in email          # scored module shown
    assert "Recommended decision (routing agent):" in email
    assert "[*] approve_proposal" in email                 # recommended marked
    assert "<- recommended" in email
    assert "Module notes:" in email                        # cyber/vendor summaries


def test_render_email_without_decision(mapped_contract, intelligence, flags):
    email = control.render_email(mapped_contract, intelligence, "S", flags)
    assert "Recommended decision" not in email
    assert "[ ] approve_proposal" in email  # no recommendation marker


# --------------------------------------------------------------------------- collect

def test_collect_non_interactive_default():
    assert control.collect(default="reject") == "reject"


def test_collect_empty_accepts_recommended(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda *_: "")
    assert control.collect(recommended="approve_proposal") == "approve_proposal"


def test_collect_rejects_invalid_then_accepts(monkeypatch):
    answers = iter(["nonsense", "flag_review"])
    monkeypatch.setattr(builtins, "input", lambda *_: next(answers))
    assert control.collect() == "flag_review"


# --------------------------------------------------------------------------- delivery (offline)

def test_deliver_decision_offline_writes_eml(tmp_archive, mapped_contract):
    decision = {"action": "approve_proposal", "priority": "high",
                "recipient": "proposal-team", "reason": "r", "notes": "n"}
    status = email_delivery.deliver_decision(mapped_contract, "CIN-TEST-1", "summary",
                                             decision, "approve_proposal", "PROPOSAL_QUEUE", ["f"])
    assert "written to" in status
    eml = (tmp_archive / "Outbox" / "CIN-TEST-1.eml").read_text(encoding="utf-8")
    assert "Subject: [CIN-Lite] CIN-TEST-1" in eml
    assert "reviewer@cin-lite.local" in eml
    assert "proposal-team@cin-lite.local" in eml
    assert "summary" in eml


def test_decision_recipients_skips_none():
    addrs = email_delivery._decision_recipients({"recipient": "none"})
    assert addrs == [email_delivery.reviewer_address()]


def test_generic_send_offline(tmp_archive):
    status = email_delivery.send("Subj", "Body", ["a@b.com"], "FALLBACK-1")
    assert "written to" in status
    assert (tmp_archive / "Outbox" / "FALLBACK-1.eml").exists()


# --------------------------------------------------------------------------- delivery (SMTP, faked)

class _FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout=None):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        _FakeSMTP.sent.append(msg)


def test_smtp_success_path(monkeypatch):
    _FakeSMTP.sent.clear()
    monkeypatch.setenv("CIN_LITE_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("CIN_LITE_SMTP_STARTTLS", "0")
    monkeypatch.setattr(email_delivery.smtplib, "SMTP", _FakeSMTP)

    status = email_delivery.send("S", "B", ["x@y.com"], "ID-1")
    assert status.startswith("sent via smtp.example.com")
    assert len(_FakeSMTP.sent) == 1
    assert _FakeSMTP.sent[0]["Subject"] == "S"


def test_smtp_failure_falls_back(tmp_archive, monkeypatch):
    def _boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setenv("CIN_LITE_SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(email_delivery.smtplib, "SMTP", _boom)

    status = email_delivery.send("S", "B", ["x@y.com"], "ID-2")
    assert "delivery failed" in status
    assert (tmp_archive / "Outbox" / "ID-2.eml").exists()
