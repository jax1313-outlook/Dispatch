"""Tests for the health check module."""

from __future__ import annotations

from cin_lite import health


class TestHealthChecks:
    def test_all_checks_return_expected_shape(self):
        results = health.run_checks()
        assert len(results) == 6
        for check in results:
            assert "name" in check
            assert "ok" in check
            assert "detail" in check
            assert isinstance(check["ok"], bool)

    def test_sample_data_present(self):
        result = health._check_sample_data()
        assert result["ok"] is True
        assert "sample file(s)" in result["detail"]

    def test_archive_writable(self, tmp_archive):
        result = health._check_archive_writable()
        assert result["ok"] is True

    def test_rules_registered(self):
        result = health._check_rules()
        assert result["ok"] is True
        assert "9 rule module(s)" in result["detail"]

    def test_claude_api_unconfigured(self):
        result = health._check_claude_api()
        assert result["ok"] is True
        assert "not configured" in result["detail"]

    def test_smtp_unconfigured(self):
        result = health._check_smtp()
        assert result["ok"] is True
        assert "not configured" in result["detail"]

    def test_sam_api_unconfigured(self):
        result = health._check_sam_api()
        assert result["ok"] is True
        assert "not configured" in result["detail"]

    def test_is_healthy(self, tmp_archive):
        assert health.is_healthy() is True

    def test_report_format(self, tmp_archive):
        report = health.report()
        assert "CIN-Lite Health Check" in report
        assert "HEALTHY" in report
        assert "sample_data" in report
        assert "rule_modules" in report


class TestHealthEdgeCases:
    def test_sam_api_configured(self, monkeypatch):
        monkeypatch.setenv("CIN_LITE_SAM_API_KEY", "test-key")
        result = health._check_sam_api()
        assert result["ok"] is True
        assert "API key present" in result["detail"]

    def test_claude_api_no_sdk(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delitem(__import__("sys").modules, "anthropic", raising=False)

        import builtins
        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("no anthropic")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        result = health._check_claude_api()
        assert result["ok"] is False
        assert "not installed" in result["detail"]

    def test_claude_api_success(self, monkeypatch, install_anthropic):
        install_anthropic("pong")
        result = health._check_claude_api()
        assert result["ok"] is True
        assert result["detail"] == "reachable"

    def test_claude_api_failure(self, monkeypatch, install_anthropic):
        install_anthropic(RuntimeError("connection refused"))
        result = health._check_claude_api()
        assert result["ok"] is False
        assert "unreachable" in result["detail"]

    def test_archive_write_failure(self, monkeypatch):
        from cin_lite import archive
        original_ensure = archive.ensure_tree

        def broken_ensure():
            raise PermissionError("read-only filesystem")

        monkeypatch.setattr(archive, "ensure_tree", broken_ensure)
        result = health._check_archive_writable()
        assert result["ok"] is False
        assert "read-only filesystem" in result["detail"]

    def test_smtp_connection_failure(self, monkeypatch):
        monkeypatch.setenv("CIN_LITE_SMTP_HOST", "nonexistent.invalid")
        monkeypatch.setenv("CIN_LITE_SMTP_PORT", "9999")

        import smtplib as _smtplib

        def boom(*a, **k):
            raise OSError("connection refused")

        monkeypatch.setattr(_smtplib, "SMTP", boom)
        result = health._check_smtp()
        assert result["ok"] is False
        assert "nonexistent.invalid" in result["detail"]

    def test_smtp_connection_success_no_tls(self, monkeypatch):
        monkeypatch.setenv("CIN_LITE_SMTP_HOST", "smtp.test.com")
        monkeypatch.setenv("CIN_LITE_SMTP_STARTTLS", "0")

        class FakeSMTP:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def starttls(self, **k): pass
            def noop(self): pass

        import smtplib as _smtplib
        monkeypatch.setattr(_smtplib, "SMTP", FakeSMTP)
        result = health._check_smtp()
        assert result["ok"] is True
        assert "connected to smtp.test.com" in result["detail"]

    def test_smtp_connection_success_with_tls(self, monkeypatch):
        monkeypatch.setenv("CIN_LITE_SMTP_HOST", "smtp.test.com")
        monkeypatch.setenv("CIN_LITE_SMTP_STARTTLS", "1")

        class FakeSMTP:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def starttls(self, **k): pass
            def noop(self): pass

        import smtplib as _smtplib
        monkeypatch.setattr(_smtplib, "SMTP", FakeSMTP)
        result = health._check_smtp()
        assert result["ok"] is True
        assert "connected to smtp.test.com" in result["detail"]
