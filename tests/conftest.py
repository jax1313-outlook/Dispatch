"""Shared pytest fixtures for the CIN-Lite test suite.

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

from cin_lite import acquisition, processing

_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "CIN_LITE_MODEL",
    "CIN_LITE_SAM_API_KEY",
    "CIN_LITE_SAM_LIMIT",
    "CIN_LITE_SAM_POSTED_FROM",
    "CIN_LITE_SAM_POSTED_TO",
    "CIN_LITE_SAM_NAICS",
    "CIN_LITE_SAM_PTYPE",
    "CIN_LITE_SAM_FETCH_DESCRIPTION",
    "CIN_LITE_SMTP_HOST",
    "CIN_LITE_SMTP_PORT",
    "CIN_LITE_SMTP_USER",
    "CIN_LITE_SMTP_PASSWORD",
    "CIN_LITE_SMTP_STARTTLS",
    "CIN_LITE_EMAIL_FROM",
    "CIN_LITE_EMAIL_REVIEWER",
    "CIN_LITE_EMAIL_DOMAIN",
]


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch):
    """Remove all integration config so tests are deterministic and offline."""
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def tmp_archive(tmp_path, monkeypatch):
    """Redirect every archive + email write into a per-test tmp directory."""
    from cin_lite import archive, email_delivery

    root = tmp_path / "Archive"
    monkeypatch.setattr(archive, "ARCHIVE_ROOT", root)
    monkeypatch.setattr(email_delivery, "_OUTBOX", root / "Outbox")
    return root


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
