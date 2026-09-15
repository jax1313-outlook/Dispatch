"""No test reaches the operator's Outlook.

2026-09-15: with classic Outlook open on the node, a test's confirmed send-notice went
out through the real mail adapter twice, to an undeliverable test address. The guard
in tests/conftest.py closes every COM entry point for every test; this holds it there.
"""

from __future__ import annotations

import importlib

import pytest

from tests.conftest import _OUTLOOK_MODULES


@pytest.mark.parametrize("name", _OUTLOOK_MODULES)
def test_every_outlook_adapter_believes_outlook_is_closed(name):
    module = importlib.import_module(name)
    assert module._outlook_is_running() is False


def test_com_attach_is_refused():
    com = pytest.importorskip("win32com.client")
    for attr in ("Dispatch", "GetActiveObject"):
        with pytest.raises(RuntimeError, match="never reach a real Outlook"):
            getattr(com, attr)("Outlook.Application")


def test_a_confirmed_send_notice_cannot_send_for_real(monkeypatch):
    """The exact path that sent on 2026-09-15: the real mail adapter, Outlook forced open."""
    from dispatch.connectors import outlook_mail

    monkeypatch.setattr(outlook_mail, "_outlook_is_running", lambda: True)
    result = outlook_mail.OutlookMailAdapter().send(["a@b.test"], "S", "M")
    assert not result.get("sent")
