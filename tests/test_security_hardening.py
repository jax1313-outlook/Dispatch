"""Workstream C: the security findings the whole-program audit rated highest.

S-1 and S-3 were the same defect twice: both `PORTAL_SECRET_KEY` and
`DISPATCH_EMAIL_SECRET` fell back to strings published in this repository, and
the only consequence was a line on stderr. A deployment that missed one
environment variable had forgeable sessions and mintable links, and started
anyway. These tests assert that it no longer does.
"""

from __future__ import annotations

import io

import pytest

from portal import config as portal_config
from portal.config import InsecureConfigurationError, check_secrets, development_host


def _clear_secrets(monkeypatch):
    for name in ("PORTAL_SECRET_KEY", "DISPATCH_EMAIL_SECRET", "DISPATCH_MODE"):
        monkeypatch.delenv(name, raising=False)


class TestSecretRefusal:
    def test_operational_mode_refuses_a_missing_secret(self, monkeypatch):
        _clear_secrets(monkeypatch)
        with pytest.raises(InsecureConfigurationError) as exc:
            check_secrets()
        assert "PORTAL_SECRET_KEY" in str(exc.value)
        assert "DISPATCH_EMAIL_SECRET" in str(exc.value)

    def test_operational_mode_refuses_the_published_default_explicitly_set(self, monkeypatch):
        """Setting the variable to the published value is not configuration."""
        _clear_secrets(monkeypatch)
        monkeypatch.setenv("PORTAL_SECRET_KEY", "dev-portal-key-change-in-production")
        monkeypatch.setenv("DISPATCH_EMAIL_SECRET", "dispatch-dev-secret")
        with pytest.raises(InsecureConfigurationError):
            check_secrets()

    def test_operational_mode_starts_on_real_secrets(self, monkeypatch):
        _clear_secrets(monkeypatch)
        monkeypatch.setenv("PORTAL_SECRET_KEY", "a-real-and-sufficiently-unguessable-value")
        monkeypatch.setenv("DISPATCH_EMAIL_SECRET", "another-real-unguessable-value")
        assert check_secrets() == []

    def test_one_missing_secret_is_still_a_refusal(self, monkeypatch):
        _clear_secrets(monkeypatch)
        monkeypatch.setenv("PORTAL_SECRET_KEY", "a-real-value")
        with pytest.raises(InsecureConfigurationError) as exc:
            check_secrets()
        assert "DISPATCH_EMAIL_SECRET" in str(exc.value)
        assert "PORTAL_SECRET_KEY" not in str(exc.value)

    def test_development_mode_warns_instead_of_refusing(self, monkeypatch):
        _clear_secrets(monkeypatch)
        monkeypatch.setenv("DISPATCH_MODE", "development")
        warnings = check_secrets()
        assert warnings
        assert "DEVELOPMENT MODE" in warnings[0]

    def test_development_mode_objects_to_a_non_loopback_bind(self, monkeypatch):
        _clear_secrets(monkeypatch)
        monkeypatch.setenv("DISPATCH_MODE", "development")
        warnings = check_secrets(host="0.0.0.0")
        assert any("loopback" in w for w in warnings)

    def test_development_mode_pins_the_bind_to_loopback(self, monkeypatch):
        """The mode restricts behaviour, not just the log output. A process
        running on published secrets does not get to listen on 0.0.0.0."""
        monkeypatch.setenv("DISPATCH_MODE", "development")
        assert development_host("0.0.0.0") == "127.0.0.1"
        assert development_host("127.0.0.1") == "127.0.0.1"

    def test_operational_mode_does_not_rewrite_the_bind(self, monkeypatch):
        monkeypatch.delenv("DISPATCH_MODE", raising=False)
        assert development_host("0.0.0.0") == "0.0.0.0"

    def test_the_default_mode_is_operational(self, monkeypatch):
        """A deployment that forgets DISPATCH_MODE must get the strict
        behaviour, not the permissive one."""
        monkeypatch.delenv("DISPATCH_MODE", raising=False)
        assert portal_config.is_development_mode() is False


class TestSessionCookiePolicy:
    def test_cookie_flags_and_lifetime_are_set(self):
        from portal.app import create_app
        app = create_app({"TESTING": True})
        assert app.config["SESSION_COOKIE_HTTPONLY"] is True
        assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
        assert app.config["PERMANENT_SESSION_LIFETIME"].total_seconds() > 0

    def test_secure_cookie_is_env_gated(self, monkeypatch):
        """Defaulting SECURE on would silently break every local HTTP run, so
        it is opt-in -- but it must be reachable."""
        import importlib
        monkeypatch.setenv("PORTAL_COOKIE_SECURE", "1")
        importlib.reload(portal_config)
        assert portal_config.Config.SESSION_COOKIE_SECURE is True
        monkeypatch.setenv("PORTAL_COOKIE_SECURE", "0")
        importlib.reload(portal_config)
        assert portal_config.Config.SESSION_COOKIE_SECURE is False


class TestUploadSafety:
    """C4. Every upload path must refuse what it cannot store, tell the person
    why, and leave nothing behind."""

    def test_disallowed_extension_is_refused_and_stores_nothing(self, tmp_path, monkeypatch):
        from dispatch import services
        from dispatch.db import set_db_path
        set_db_path(tmp_path / "uploads.db")
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        try:
            load = services.create_load(customer="Upload Co")
            with pytest.raises(ValueError, match="File type not allowed"):
                services.attach_evidence(
                    load["load_id"], file_data=b"x", original_filename="payload.exe"
                )
            assert services.list_evidence(load["load_id"]) == []
        finally:
            set_db_path(None)

    def test_oversize_file_is_refused_and_stores_nothing(self, tmp_path, monkeypatch):
        from dispatch import services
        from dispatch.db import set_db_path
        from dispatch.models import MAX_FILE_SIZE
        set_db_path(tmp_path / "uploads2.db")
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        try:
            load = services.create_load(customer="Upload Co")
            with pytest.raises(ValueError, match="exceeds"):
                services.attach_evidence(
                    load["load_id"],
                    file_data=b"x" * (MAX_FILE_SIZE + 1),
                    original_filename="huge.pdf",
                )
            assert services.list_evidence(load["load_id"]) == []
        finally:
            set_db_path(None)

    def test_stored_filename_is_regenerated_not_taken_from_the_upload(self, tmp_path, monkeypatch):
        """A hostile filename must not reach the filesystem."""
        from dispatch import services
        from dispatch.db import set_db_path
        set_db_path(tmp_path / "uploads3.db")
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        try:
            load = services.create_load(customer="Upload Co")
            evidence = services.attach_evidence(
                load["load_id"], file_data=b"real bytes",
                original_filename="../../../etc/passwd.jpg",
            )
            stored = evidence["file_path"]
            assert ".." not in stored
            assert evidence["evidence_id"] in stored
            assert stored.endswith(".jpg")
        finally:
            set_db_path(None)

    def test_checksum_is_recorded_for_every_stored_file(self, tmp_path, monkeypatch):
        from dispatch import services
        from dispatch.db import set_db_path
        set_db_path(tmp_path / "uploads4.db")
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        try:
            load = services.create_load(customer="Upload Co")
            evidence = services.attach_evidence(
                load["load_id"], file_data=b"real bytes", original_filename="pod.jpg"
            )
            assert evidence["checksum"]
        finally:
            set_db_path(None)


class TestRepositoryHygiene:
    """C5. The ignore rules must actually cover what leaked before."""

    def test_runtime_logs_are_ignored(self):
        from pathlib import Path
        rules = Path(".gitignore").read_text(encoding="utf-8")
        assert "*.log" in rules

    def test_secret_bearing_files_are_ignored(self):
        from pathlib import Path
        rules = Path(".gitignore").read_text(encoding="utf-8")
        for pattern in (".env", "*.pem", "*.key", "secrets.json"):
            assert pattern in rules

    def test_the_example_env_file_is_still_shareable(self):
        """.env.* must not hide the documented template."""
        from pathlib import Path
        rules = Path(".gitignore").read_text(encoding="utf-8")
        assert "!.env.example" in rules
