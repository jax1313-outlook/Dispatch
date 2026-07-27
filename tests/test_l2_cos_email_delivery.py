"""Tests for the L2-COS Control Layer's outbound email delivery, including
the dry-run safety switch used by the publisher/auto-contact workflow."""

from __future__ import annotations

from l2_cos import email_delivery


def test_generic_send_offline_writes_eml(tmp_archive):
    status = email_delivery.send("Subj", "Body", ["a@b.com"], "FALLBACK-1")
    assert "not sent" in status
    eml_path = email_delivery._OUTBOX / "FALLBACK-1.eml"
    assert eml_path.exists()
    assert "Subj" in eml_path.read_text(encoding="utf-8")


def test_dry_run_forces_fallback_even_with_smtp_configured(monkeypatch):
    monkeypatch.setenv("L2_COS_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("L2_COS_EMAIL_DRY_RUN", "1")
    monkeypatch.setattr(email_delivery.smtplib, "SMTP", _BoomSMTP)

    status = email_delivery.send("Subj", "Body", ["broker@example.com"], "DRY-1")
    assert status.startswith("dry-run (L2_COS_EMAIL_DRY_RUN=1)")
    assert (email_delivery._OUTBOX / "DRY-1.eml").exists()


def test_fallback_broker_address_uses_domain(monkeypatch):
    monkeypatch.setenv("L2_COS_EMAIL_DOMAIN", "carrier.example")
    assert email_delivery.fallback_broker_address() == "unassigned-broker@carrier.example"


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


class _BoomSMTP:
    def __init__(self, *a, **k):
        raise AssertionError("SMTP must never be contacted during a dry run")


def test_smtp_success_path(monkeypatch):
    _FakeSMTP.sent.clear()
    monkeypatch.setenv("L2_COS_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("L2_COS_SMTP_STARTTLS", "0")
    monkeypatch.setattr(email_delivery.smtplib, "SMTP", _FakeSMTP)

    status = email_delivery.send("S", "B", ["broker@example.com"], "ID-1")
    assert status.startswith("sent via smtp.example.com")
    assert len(_FakeSMTP.sent) == 1
    assert _FakeSMTP.sent[0]["Subject"] == "S"


def test_smtp_failure_falls_back(monkeypatch):
    def _boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setenv("L2_COS_SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(email_delivery.smtplib, "SMTP", _boom)

    status = email_delivery.send("S", "B", ["broker@example.com"], "ID-2")
    assert "delivery failed" in status
    assert (email_delivery._OUTBOX / "ID-2.eml").exists()


def test_smtp_login_used_when_user_configured(monkeypatch):
    _FakeSMTP.sent.clear()
    monkeypatch.setenv("L2_COS_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("L2_COS_SMTP_USER", "apikey")
    monkeypatch.setenv("L2_COS_SMTP_PASSWORD", "secret")
    monkeypatch.setattr(email_delivery.smtplib, "SMTP", _FakeSMTP)

    status = email_delivery.send("S", "B", ["broker@example.com"], "ID-3")
    assert status.startswith("sent via smtp.example.com")
