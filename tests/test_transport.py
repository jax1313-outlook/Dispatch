"""The transport port, its four adapters, and what each one is allowed to claim.

Two findings shaped this module and both are about honesty rather than code.

`dispatch/connectors/` is ~3,000 lines across eight connectors and contains no
HTTP client at all -- no requests, no httpx, no urllib, no msal. "Eight
connectors IMPLEMENTED" was true and meant something narrower than it reads.

And the two auth methods already chosen are the two Microsoft is closing:
`outlook_connector.py` declares oauth_client_credentials (app-only Graph, which
needs an Entra tenant, cannot authenticate a personal account, and grants
tenant-wide mailbox access), while `cin_lite/email_delivery.py` sends with
smtplib.login on port 587 -- SMTP AUTH basic authentication, disabled by default
on every Microsoft 365 tenant.

Nothing in this module has been run against Microsoft. These tests prove the
request shapes, the refusal shapes and the status words; they do not prove
connectivity, and no test here pretends to.
"""

from __future__ import annotations

import json
import smtplib
from pathlib import Path

import pytest

from dispatch.msauth import AuthError, AuthNotConfigured, NullTokenProvider
from dispatch.transport import OutboundMessage, select_transport
from dispatch.transport.adapters import (
    FileOutboxTransport,
    GraphMailTransport,
    SmtpBasicTransport,
    SmtpOAuth2Transport,
)
from dispatch.transport.contract import (
    CONFIGURED,
    LIVE,
    SIMULATED,
    UNCONFIGURED,
    TransportError,
    TransportUnconfigured,
)
from dispatch.transport.selection import describe_transports, outbound_status

MESSAGE = OutboundMessage(
    to=("ops@broker.test",),
    subject="Load LOAD-1 delivered",
    body_text="POD attached.",
    subject_ref="LOAD-1",
    from_address="dispatch@example.com",
)


class FakeToken:
    def __init__(self, status="LIVE", account="mike@example.com", token="tok"):
        self._status, self._account, self._token = status, account, token

    def status(self):
        return self._status

    def account(self):
        return self._account

    def access_token(self):
        if self._status == "UNCONFIGURED":
            raise AuthNotConfigured("no client id")
        if self._status == "UNAVAILABLE":
            raise AuthError("refresh refused")
        return self._token


class TestTheOutboxFallback:
    def test_it_writes_a_file_and_calls_it_simulated(self, tmp_path):
        transport = FileOutboxTransport(tmp_path / "Outbox")
        result = transport.send(MESSAGE)

        assert result.status == SIMULATED
        assert result.delivered is False, "a .eml on disk is not delivery"
        written = list((tmp_path / "Outbox").glob("*.eml"))
        assert len(written) == 1
        assert "ops@broker.test" in written[0].read_text(encoding="utf-8")

    def test_the_receipt_says_not_sent_so_the_delivery_record_classifies_it(self, tmp_path):
        """dispatch.delivery reads this prefix. The two must not drift apart."""
        from dispatch import delivery

        result = FileOutboxTransport(tmp_path / "Outbox").send(MESSAGE)
        assert result.receipt.startswith("not sent")
        assert delivery.SIMULATED == SIMULATED

    def test_it_is_always_available_so_there_is_never_nowhere_to_put_a_message(self, tmp_path):
        assert FileOutboxTransport(tmp_path / "Outbox").status() == SIMULATED

    def test_the_directory_it_names_is_the_directory_that_is_written(self):
        """The status line and the file must be the same sentence.

        With nothing configured, the writer is not this class. `install()`
        engages only for the genuinely new transports -- Graph and XOAUTH2 --
        so `cin_lite._send_or_write` runs its own fallback and writes under
        `Archive/CIN/Outbox`. This transport used to compute its own answer,
        `$DISPATCH_ARCHIVE_ROOT/Outbox`, and `describe()` is the only thing any
        surface reads for the default transport. An operator who followed the
        status to find their unsent mail found an empty directory.

        Asking cin_lite is what keeps the two from drifting apart again, and
        this test is what notices if someone stops asking.
        """
        from cin_lite import email_delivery

        assert FileOutboxTransport().outbox() == email_delivery.outbox_dir()

    def test_an_explicit_directory_still_wins(self, tmp_path):
        """A constructor argument is a decision, not a hint."""
        chosen = tmp_path / "Elsewhere"
        assert FileOutboxTransport(chosen).outbox() == chosen

    def test_the_described_path_is_the_path_it_would_write_to(self, tmp_path):
        transport = FileOutboxTransport(tmp_path / "Outbox")
        transport.send(MESSAGE)
        written = next((tmp_path / "Outbox").glob("*.eml"))
        assert str(transport.outbox()) in transport.describe()
        assert written.parent == transport.outbox()


class TestSmtpBasic:
    def test_it_is_unconfigured_without_a_host(self, monkeypatch):
        monkeypatch.delenv("DISPATCH_SMTP_HOST", raising=False)
        assert SmtpBasicTransport().status() == UNCONFIGURED

    def test_it_names_the_relay_so_live_is_checkable(self):
        transport = SmtpBasicTransport(host="smtp.example.com", user="u", password="p")
        assert transport.status() == LIVE
        assert "smtp.example.com" in transport.describe()

    def test_a_host_with_no_credentials_is_configured_not_live(self):
        assert SmtpBasicTransport(host="smtp.example.com").status() == CONFIGURED

    def test_sending_without_a_host_refuses_and_is_not_retried(self, monkeypatch):
        monkeypatch.delenv("DISPATCH_SMTP_HOST", raising=False)
        with pytest.raises(TransportUnconfigured) as caught:
            SmtpBasicTransport().send(MESSAGE)
        assert caught.value.retryable is False

    def test_an_auth_failure_names_the_microsoft_cause(self, monkeypatch):
        """535 against an M365 mailbox means basic auth is off, and the operator
        cannot act on "authentication failed" alone."""
        transport = SmtpBasicTransport(host="smtp.office365.com", user="u", password="p")

        class Refusing:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def login(self, *a):
                raise smtplib.SMTPAuthenticationError(535, b"5.7.139 Authentication unsuccessful")

        monkeypatch.setattr(transport, "_connect", lambda: Refusing())
        with pytest.raises(TransportError) as caught:
            transport.send(MESSAGE)
        assert "basic authentication is disabled" in str(caught.value)
        assert "smtp_oauth2" in str(caught.value)


class TestSmtpOAuth2:
    def test_it_is_unconfigured_without_a_token_provider(self):
        assert SmtpOAuth2Transport().status() == UNCONFIGURED

    def test_a_live_provider_makes_it_live_and_names_the_account(self):
        transport = SmtpOAuth2Transport(token_provider=FakeToken())
        assert transport.status() == LIVE
        assert "mike@example.com" in transport.describe()
        assert "XOAUTH2" in transport.describe()

    def test_it_defaults_to_the_microsoft_relay(self):
        assert SmtpOAuth2Transport(token_provider=FakeToken()).host == "smtp.office365.com"

    def test_the_xoauth2_string_is_the_documented_shape(self):
        import base64

        raw = base64.b64decode(SmtpOAuth2Transport._xoauth2("mike@example.com", "tok"))
        assert raw == b"user=mike@example.com\x01auth=Bearer tok\x01\x01"

    def test_an_unconfigured_provider_refuses_without_connecting(self):
        transport = SmtpOAuth2Transport(token_provider=FakeToken(status="UNCONFIGURED"))
        with pytest.raises(TransportUnconfigured):
            transport.send(MESSAGE)

    def test_a_refused_refresh_is_a_retryable_transport_error(self):
        transport = SmtpOAuth2Transport(token_provider=FakeToken(status="UNAVAILABLE"))
        with pytest.raises(TransportError) as caught:
            transport.send(MESSAGE)
        assert caught.value.retryable is True


class TestGraph:
    def test_it_is_unconfigured_with_the_null_provider(self):
        assert GraphMailTransport(token_provider=NullTokenProvider()).status() == UNCONFIGURED

    def test_the_payload_is_graph_json_not_mime(self):
        payload = GraphMailTransport._payload(MESSAGE)
        assert payload["message"]["subject"] == "Load LOAD-1 delivered"
        assert payload["message"]["toRecipients"] == [
            {"emailAddress": {"address": "ops@broker.test"}}
        ]
        assert payload["message"]["body"]["contentType"] == "Text"
        assert payload["saveToSentItems"] is True

    def test_html_is_sent_as_html(self):
        payload = GraphMailTransport._payload(
            OutboundMessage(to=("a@b.test",), subject="s", body_text="t", body_html="<p>t</p>")
        )
        assert payload["message"]["body"]["contentType"] == "HTML"

    def test_a_send_carries_the_bearer_token(self):
        sent = {}

        class Response:
            status = 202

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(request, timeout=None):
            sent["headers"] = dict(request.headers)
            sent["body"] = json.loads(request.data.decode("utf-8"))
            sent["url"] = request.full_url
            return Response()

        transport = GraphMailTransport(token_provider=FakeToken(), opener=opener)
        result = transport.send(MESSAGE)

        assert sent["url"] == "https://graph.microsoft.com/v1.0/me/sendMail"
        assert sent["headers"]["Authorization"] == "Bearer tok"
        assert sent["body"]["message"]["subject"] == MESSAGE.subject
        assert result.delivered is True
        assert "mike@example.com" in result.receipt

    def test_a_403_is_not_retried_and_a_429_is(self):
        import io
        import urllib.error

        def refusing(code):
            def opener(request, timeout=None):
                raise urllib.error.HTTPError(
                    request.full_url, code, "refused", {},
                    io.BytesIO(json.dumps({"error": {"message": "no"}}).encode()),
                )

            return opener

        for code, retryable in ((403, False), (400, False), (429, True), (503, True)):
            transport = GraphMailTransport(token_provider=FakeToken(), opener=refusing(code))
            with pytest.raises(TransportError) as caught:
                transport.send(MESSAGE)
            assert caught.value.retryable is retryable, code

    def test_it_never_reaches_the_network_without_a_token(self):
        called = []
        transport = GraphMailTransport(
            token_provider=NullTokenProvider(),
            opener=lambda *a, **k: called.append(a),
        )
        with pytest.raises(TransportUnconfigured):
            transport.send(MESSAGE)
        assert called == [], "an anonymous Graph call would fail confusingly at the server"


class TestSelection:
    @pytest.fixture(autouse=True)
    def _clean(self, monkeypatch, tmp_path):
        for var in ("DISPATCH_TRANSPORT", "DISPATCH_SMTP_HOST", "DISPATCH_SMTP_USER",
                    "DISPATCH_MS_CLIENT_ID"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(tmp_path / "Archive"))

    def test_nothing_configured_selects_the_outbox_and_says_simulated(self):
        transport = select_transport()
        assert transport.transport_id == "file_outbox"
        assert outbound_status()["simulated"] is True
        assert outbound_status()["delivering"] is False

    def test_an_smtp_host_alone_selects_smtp(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_SMTP_HOST", "smtp.example.com")
        assert select_transport().transport_id == "smtp_basic"

    def test_a_microsoft_client_id_takes_precedence_over_a_legacy_relay(self, monkeypatch):
        """The newer setting is the one somebody configured deliberately."""
        monkeypatch.setenv("DISPATCH_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("DISPATCH_MS_CLIENT_ID", "00000000-0000-0000-0000-000000000000")
        assert select_transport().transport_id == "graph"

    def test_an_operator_can_pin_one_while_migrating(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("DISPATCH_MS_CLIENT_ID", "00000000-0000-0000-0000-000000000000")
        monkeypatch.setenv("DISPATCH_TRANSPORT", "smtp_basic")
        assert select_transport().transport_id == "smtp_basic"

    def test_every_transport_is_described_not_just_the_chosen_one(self):
        rows = describe_transports()
        assert {r["transport_id"] for r in rows} == {
            "graph", "smtp_oauth2", "smtp_basic", "file_outbox"
        }
        assert sum(1 for r in rows if r["selected"]) == 1
        # The question an operator actually has is "why is it still writing
        # .eml files", and the answer is only visible when the UNCONFIGURED ones
        # are shown alongside the one that was picked.
        assert any(r["status"] == UNCONFIGURED for r in rows)

    def test_the_words_are_the_eight(self):
        allowed = {"LIVE", "CONFIGURED", "UNCONFIGURED", "SIMULATED", "UNAVAILABLE",
                   "MANUAL", "ABSENT", "UNVERIFIED"}
        assert all(row["status"] in allowed for row in describe_transports())
