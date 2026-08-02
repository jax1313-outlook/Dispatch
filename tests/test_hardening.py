"""Tests for security hardening: HTML escaping, configurable portal URL, HMAC secret warning."""

from __future__ import annotations

from cin_lite import control, email_delivery


class TestHtmlEscaping:
    def test_checkpoint_email_escapes_title(self):
        contract = {"title": '<script>alert("xss")</script>', "agency": "GSA"}
        html = control.render_html_email(contract, {}, "summary", [])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_checkpoint_email_escapes_summary(self):
        contract = {"title": "Safe", "agency": "GSA"}
        html = control.render_html_email(contract, {}, '<img onerror="x">', [])
        assert 'onerror="x"' not in html
        assert "&lt;img" in html

    def test_checkpoint_email_escapes_flags(self):
        contract = {"title": "Safe", "agency": "GSA"}
        html = control.render_html_email(contract, {}, "summary", ['<b>bold</b>'])
        assert "<b>bold</b>" not in html
        assert "&lt;b&gt;" in html

    def test_decision_email_escapes_title(self):
        contract = {"title": '<script>alert("xss")</script>', "agency": "GSA"}
        decision = {"action": "reject", "priority": "low", "reason": "r", "notes": "n"}
        html = email_delivery._render_decision_html(
            contract, "CIN-001", "summary", decision, "reject", "REJECTED", [], "Reject",
        )
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_decision_email_escapes_flags(self):
        contract = {"title": "Safe", "agency": "GSA"}
        decision = {"action": "reject", "priority": "low", "reason": "r", "notes": "n"}
        html = email_delivery._render_decision_html(
            contract, "CIN-001", "summary", decision, "reject", "REJECTED",
            ['<img src=x>'], "Reject",
        )
        assert "<img src=x>" not in html
        assert "&lt;img" in html


class TestConfigurablePortalUrl:
    def test_default_url(self):
        html = control.render_html_email(
            {"title": "T"}, {}, "s", [], contract_id="CIN-001",
        )
        assert "http://127.0.0.1:8080/api/decision/CIN-001/" in html

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_PORTAL_URL", "https://portal.example.com")
        html = control.render_html_email(
            {"title": "T"}, {}, "s", [], contract_id="CIN-001",
        )
        assert "https://portal.example.com/api/decision/CIN-001/" in html
        assert "127.0.0.1" not in html

    def test_trailing_slash_stripped(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_PORTAL_URL", "https://portal.example.com/")
        html = control.render_html_email(
            {"title": "T"}, {}, "s", [], contract_id="CIN-001",
        )
        assert "https://portal.example.com/api/decision/CIN-001/" in html

    def test_explicit_base_overrides_env(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_PORTAL_URL", "https://portal.example.com")
        html = control.render_html_email(
            {"title": "T"}, {}, "s", [],
            action_url_base="http://custom:9090/decide",
            contract_id="CIN-001",
        )
        assert "http://custom:9090/decide/CIN-001/" in html


class TestHmacSecretWarning:
    def test_using_default_secret_true(self):
        assert email_delivery._using_default_secret() is True

    def test_using_default_secret_false(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_EMAIL_SECRET", "production-secret")
        assert email_delivery._using_default_secret() is False
