"""Shared pytest fixtures for the DISPATCH test suite.

Guarantees deterministic, side-effect-free tests:
- scrubs every integration env var so agents take their deterministic fallback
  and acquisition stays on local data (autouse);
- redirects all archive/email writes to a tmp dir (autouse);
- provides a fake `anthropic` injector to exercise the Claude code paths offline.
"""

from __future__ import annotations

import sys
import types

import pytest

from flask import Flask
from flask.testing import FlaskClient

from cin_lite import acquisition, processing

_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "DISPATCH_MODEL",
    "DISPATCH_SAM_API_KEY",
    "DISPATCH_SAM_LIMIT",
    "DISPATCH_SAM_POSTED_FROM",
    "DISPATCH_SAM_POSTED_TO",
    "DISPATCH_SAM_NAICS",
    "DISPATCH_SAM_PTYPE",
    "DISPATCH_SAM_FETCH_DESCRIPTION",
    "DISPATCH_SMTP_HOST",
    "DISPATCH_SMTP_PORT",
    "DISPATCH_SMTP_USER",
    "DISPATCH_SMTP_PASSWORD",
    "DISPATCH_SMTP_STARTTLS",
    "DISPATCH_EMAIL_FROM",
    "DISPATCH_EMAIL_REVIEWER",
    "DISPATCH_EMAIL_DOMAIN",
    "DISPATCH_EMAIL_SECRET",
    "DISPATCH_PORTAL_URL",
    "DISPATCH_OPERATIONS_ROOT",
    "DISPATCH_ARCHIVE_ROOT",
    "DISPATCH_MEMORY_ROOT",
    "DISPATCH_ARCHIVE_PATH",
    "PORTAL_DATA_DIR",
    "PORTAL_UPLOAD_DIR",
]


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch):
    """Remove all integration config so tests are deterministic and offline.

    The two signing secrets are then set to fixed test values rather than left
    unset. Since the security-hardening campaign, `portal.config.check_secrets()`
    REFUSES to build an app on a published default outside development mode --
    so leaving them unset would mean 87 `create_app()` call sites in this suite
    either had to change or had to be exempted. Supplying real (if
    well-known-to-the-suite) values instead means the tests exercise the actual
    production path with no bypass at all, which is the point.

    Tests that care about the refusal itself delete these deliberately -- see
    tests/test_security_hardening.py::_clear_secrets.
    """
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("PORTAL_SECRET_KEY", "test-suite-portal-secret")
    monkeypatch.setenv("DISPATCH_EMAIL_SECRET", "test-suite-email-secret")


@pytest.fixture(autouse=True)
def tmp_archive(tmp_path, monkeypatch):
    """Redirect every archive + email + pending write into a per-test tmp directory."""
    from cin_lite import archive, email_delivery, pending

    root = tmp_path / "Archive"
    monkeypatch.setattr(archive, "ARCHIVE_ROOT", root)
    monkeypatch.setattr(email_delivery, "_OUTBOX", root / "Outbox")
    monkeypatch.setattr(pending, "_PENDING_DIR", root / "Pending")
    # The portal's JSON stores resolve through PORTAL_DATA_DIR
    # (portal/models/__init__.py::get_data_dir). _scrub_env deletes that var,
    # so without this the stores fall back to the real portal/data/ directory
    # and the suite writes into a developer's live conflict/publisher/sandbox
    # files -- exactly what this fixture exists to prevent for archive writes.
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "PortalData"))
    return root



# --------------------------------------------------------------------------- CSRF

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class CSRFTestClient(FlaskClient):
    """A test client that carries the CSRF token, so the suite runs WITH the
    protection on rather than around it.

    The alternative was to disable CSRF under TESTING, which would have meant
    the ~1,160 HTTP tests in this suite proving that routes work with the
    protection switched off -- the exact thing the campaign brief forbids
    ("do not declare completion while most HTTP tests bypass the security
    gates being claimed as protected").

    The token is read from the `csrf_token` cookie on every mutating call
    rather than cached, because logging in and out calls session.clear(),
    which mints a new one. Tests that are ABOUT csrf pass an explicit
    X-CSRF-Token header (or `csrf=False`) and this wrapper leaves them alone.
    """

    def open(self, *args, **kwargs):
        method = (kwargs.get("method") or (args[1] if len(args) > 1 else "GET")).upper()
        send_token = kwargs.pop("csrf", True)

        if send_token and method in _MUTATING_METHODS:
            headers = kwargs.get("headers") or {}
            already = any(str(k).lower() == "x-csrf-token" for k in headers)
            if not already:
                token = self._csrf_token()
                if token:
                    headers = dict(headers)
                    headers["X-CSRF-Token"] = token
                    kwargs["headers"] = headers
        return super().open(*args, **kwargs)

    def _csrf_token(self) -> str:
        cookie = self.get_cookie("csrf_token")
        if cookie is not None:
            return cookie.value
        # No session yet. A GET on any non-exempt endpoint mints one.
        super().open("/login", method="GET")
        cookie = self.get_cookie("csrf_token")
        return cookie.value if cookie is not None else ""


@pytest.fixture(autouse=True)
def _csrf_aware_test_client(monkeypatch):
    """Every app built in this suite gets the CSRF-carrying client, without
    each of the 87 create_app() call sites having to know."""
    monkeypatch.setattr(Flask, "test_client_class", CSRFTestClient, raising=False)

@pytest.fixture
def sam_opportunity() -> dict:
    """A rich SAM.gov opportunitiesData[] record that exercises all nine rules.

    `description` is plain text so acquisition._fetch_description returns it
    without a network call.
    """
    return {
        "noticeId": "TESTNOTICE001",
        "title": "Zero Trust Cybersecurity and Cloud Engineering Support",
        "solicitationNumber": "FA8773-26-R-0007",
        "fullParentPathName": "DEPT OF DEFENSE.DEPT OF THE AIR FORCE.AFMC",
        "naicsCode": "541512",
        "naicsCodes": ["541512", "541519"],
        "typeOfSetAsideDescription": "8(a) Set-Aside (FAR 19.8)",
        "responseDeadLine": "2026-08-15T17:00:00-04:00",
        "uiLink": "https://sam.gov/opp/TESTNOTICE001/view",
        "pointOfContact": [{"email": "jane.doe@gmail.com"}, {"email": "ko@gmail.com"}],
        "award": {"awardee": {"name": "Acme Holdings LLC"}, "amount": "5000000", "number": "W-1"},
        "description": (
            "The contractor shall implement NIST SP 800-171 controls and achieve CMMC Level 2 "
            "certification. Work involves CUI handling per DFARS 252.204-7012 and ITAR-controlled "
            "items; U.S. persons only. This is a sole source follow-on to the incumbent. A "
            "subcontracting plan is required and subcontractor support is expected. SBA-approved "
            "joint venture and mentor-protégé arrangements are encouraged. Offerors must "
            "demonstrate past performance similar in scope and complexity; CPARS will be evaluated; "
            "references within the last 3 years. SIN 54151S applies."
        ),
    }


@pytest.fixture
def clean_opportunity() -> dict:
    """A minimal opportunity with no special indicators (negative-case)."""
    return {
        "noticeId": "TESTNOTICE002",
        "title": "Routine Custodial Services",
        "solicitationNumber": "GS-00-26-Q-0002",
        "fullParentPathName": "GENERAL SERVICES ADMINISTRATION",
        "naicsCode": "561720",
        "typeOfSetAsideDescription": "",
        "responseDeadLine": "2026-09-01T17:00:00-04:00",
        "description": "Routine custodial and janitorial services for Building 5.",
    }


@pytest.fixture
def mapped_contract(sam_opportunity) -> dict:
    """The rich opportunity mapped into the pipeline's contract shape."""
    return acquisition._map_opportunity(sam_opportunity, api_key="FAKE", fetch_desc=True)


@pytest.fixture
def clean_contract(clean_opportunity) -> dict:
    return acquisition._map_opportunity(clean_opportunity, api_key="FAKE", fetch_desc=True)


@pytest.fixture
def intelligence(mapped_contract) -> dict:
    return processing.process(mapped_contract)


@pytest.fixture
def flags(intelligence) -> list[str]:
    return processing.all_flags(intelligence)


@pytest.fixture
def install_anthropic(monkeypatch):
    """Factory: install a fake `anthropic` module + API key.

    behavior is either a string (returned as the text block) or an Exception
    instance (raised by messages.create), letting tests drive the Claude code
    path's success and failure branches deterministically.
    """

    def _install(behavior):
        class _Block:
            type = "text"

            def __init__(self, text):
                self.text = text

        class _Resp:
            def __init__(self, text):
                self.content = [_Block(text)]

        class _Messages:
            def create(self, **kwargs):
                if isinstance(behavior, Exception):
                    raise behavior
                return _Resp(behavior)

        class _Client:
            def __init__(self, *a, **k):
                self.messages = _Messages()

        mod = types.ModuleType("anthropic")
        mod.Anthropic = _Client
        monkeypatch.setitem(sys.modules, "anthropic", mod)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    return _install
