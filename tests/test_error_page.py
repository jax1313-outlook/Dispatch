"""The page Dispatch shows when a page fails.

This exists because of a real morning. The first time Dispatch ran on Mike's Windows
laptop, `/home` and `/dispatch` both returned Flask's bare *"Internal Server Error"*.
Everything before that had worked -- launcher, PIN, sign-in -- and the screen still gave
him nothing to act on and nothing to send. Two rounds went by hunting for a log file
whose location the failing page could simply have printed.

So the tests below are mostly about what the page *says*, not that it returns 500.
"""

from __future__ import annotations

import pytest
from flask import Flask

from portal import errors


@pytest.fixture
def crashing_app(monkeypatch):
    """A real app with the real handler and one deliberately broken route."""
    monkeypatch.setenv("PORTAL_SECRET_KEY", "a-real-per-machine-value")
    monkeypatch.setenv("DISPATCH_EMAIL_SECRET", "another-real-value")
    from portal.app import create_app

    app = create_app({"TESTING": True, "LOGIN_DISABLED": True})

    @app.route("/__crash")
    def _crash():
        raise RuntimeError("could not open the store")

    @app.route("/__crash_with_secret")
    def _crash_with_secret():
        raise RuntimeError(
            "connect failed: PORTAL_SECRET_KEY=sup3rs3cr3tvalue token=abc999xyz"
        )

    return app


class TestWhatTheOperatorSees:
    def test_it_replaces_flasks_bare_page(self, crashing_app):
        html = crashing_app.test_client().get("/__crash").data.decode()
        assert "Dispatch could not build this page" in html
        assert "The server encountered an internal error" not in html, (
            "Flask's default page came through -- the handler did not run"
        )

    def test_it_says_dispatch_is_still_running(self, crashing_app):
        """An operator who thinks the whole program is down stops using it."""
        html = crashing_app.test_client().get("/__crash").data.decode()
        assert "Dispatch is still running" in html
        assert "nothing was lost" in html.lower()

    def test_it_names_the_error_rather_than_describing_it_generically(self, crashing_app):
        html = crashing_app.test_client().get("/__crash").data.decode()
        assert "RuntimeError" in html
        assert "could not open the store" in html

    def test_it_names_which_page_failed(self, crashing_app):
        html = crashing_app.test_client().get("/__crash").data.decode()
        assert "/__crash" in html

    def test_it_prints_the_log_path_so_nobody_has_to_hunt_for_it(self, crashing_app):
        """The specific failure this page was built after."""
        html = crashing_app.test_client().get("/__crash").data.decode()
        assert str(errors.log_path()) in html

    def test_it_carries_the_traceback_in_one_selectable_block(self, crashing_app):
        html = crashing_app.test_client().get("/__crash").data.decode()
        assert "Traceback (most recent call last)" in html
        assert "<pre>" in html
        assert "user-select: all" in html, (
            "the block must select in one click -- an operator should not have to drag "
            "across a scrolling code block to send it"
        )

    def test_it_still_returns_500(self, crashing_app):
        assert crashing_app.test_client().get("/__crash").status_code == 500


class TestItNeverLeaksASecret:
    """This page is *meant* to be copied and sent. That makes redaction load-bearing."""

    def test_a_secret_in_the_message_is_redacted(self, crashing_app):
        html = crashing_app.test_client().get("/__crash_with_secret").data.decode()
        assert "sup3rs3cr3tvalue" not in html
        assert "abc999xyz" not in html
        assert "[REDACTED]" in html

    def test_the_setting_name_survives_because_the_name_is_what_helps(self, crashing_app):
        html = crashing_app.test_client().get("/__crash_with_secret").data.decode()
        assert "PORTAL_SECRET_KEY" in html

    @pytest.mark.parametrize(
        "line,secret",
        [
            ("PORTAL_SECRET_KEY=abc123", "abc123"),
            ("DISPATCH_EMAIL_SECRET: xyz789", "xyz789"),
            ('"api_key": "k-9999"', "k-9999"),
            ("/portal/view?token=t0k3nvalue", "t0k3nvalue"),
            ("DISPATCH_PIN=8265", "8265"),
            ("password=hunter2", "hunter2"),
            ("AWS_CREDENTIAL=zzz111", "zzz111"),
        ],
    )
    def test_every_shape_a_secret_appears_in(self, line, secret):
        out = errors.redact(line)
        assert secret not in out
        assert "[REDACTED]" in out

    def test_ordinary_values_are_left_alone(self):
        """Over-redaction is the chosen failure direction, not a licence to redact all."""
        assert errors.redact("load_id=LD-42") == "load_id=LD-42"
        assert errors.redact("status: delivered") == "status: delivered"

    def test_the_logged_copy_is_redacted_too(self, crashing_app, caplog):
        with caplog.at_level("ERROR"):
            crashing_app.test_client().get("/__crash_with_secret")
        assert "sup3rs3cr3tvalue" not in caplog.text
        assert "[REDACTED]" in caplog.text


class TestItNeverFailsItself:
    """An error page that raises replaces a useful message with a useless one, at the
    moment the operator most needs help."""

    def test_a_broken_template_falls_back_to_plain_text(self, crashing_app, monkeypatch):
        def _template_is_broken(*args, **kwargs):
            raise RuntimeError("the template itself is broken")

        monkeypatch.setattr(errors, "render_template", _template_is_broken)
        response = crashing_app.test_client().get("/__crash")

        assert response.status_code == 500
        body = response.data.decode()
        assert "DISPATCH" in body
        assert "Traceback" in body, "the fallback dropped the one thing worth sending"
        assert str(errors.log_path()) in body

    def test_describe_survives_an_exception_with_a_hostile_str(self):
        class Hostile(Exception):
            def __str__(self):
                raise ValueError("even my message raises")

        detail = errors.describe(Hostile())
        assert detail["kind"] == "Hostile"
        assert detail["message"]

    def test_describe_works_outside_a_request_context(self):
        detail = errors.describe(RuntimeError("no request here"))
        assert detail["where"] == "(unknown)"

    def test_redact_of_empty_input(self):
        assert errors.redact("") == ""


class TestHttpErrorsAreNotDressedUpAsCrashes:
    def test_a_404_stays_a_404(self, crashing_app):
        response = crashing_app.test_client().get("/__no_such_page")
        assert response.status_code == 404
        assert "Dispatch could not build this page" not in response.data.decode()

    def test_a_405_stays_a_405(self, crashing_app):
        response = crashing_app.test_client().post("/__crash")
        assert response.status_code == 405


class TestItDoesNotDriftFromTheOtherCopies:
    """Three subsystems redact secrets, deliberately without sharing code (THE MIKE
    RULE). Deliberate duplication still has to stay in step, and this is what keeps it
    honest rather than hoping."""

    def test_the_marker_lists_agree(self):
        from dispatch import backup
        from dispatch_launcher import redaction

        assert set(errors.SECRET_NAME_MARKERS) == set(redaction.SECRET_NAME_MARKERS)
        assert set(errors.SECRET_NAME_MARKERS) >= set(backup._SECRET_MARKERS)

    def test_the_log_path_matches_the_launchers(self, monkeypatch, tmp_path):
        """An error page that names the wrong log file is worse than one that names
        none: the operator looks there, finds nothing, and stops believing the page."""
        from dispatch_launcher import locations

        monkeypatch.delenv("DISPATCH_LAUNCHER_LOG_DIR", raising=False)
        monkeypatch.delenv("DISPATCH_OPERATIONS_ROOT", raising=False)
        assert errors.log_path() == locations.server_log()

        monkeypatch.setenv("DISPATCH_OPERATIONS_ROOT", str(tmp_path))
        assert errors.log_path() == locations.server_log()

        monkeypatch.setenv("DISPATCH_LAUNCHER_LOG_DIR", str(tmp_path / "elsewhere"))
        assert errors.log_path() == locations.server_log()
