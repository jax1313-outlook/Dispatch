"""The four ways a message can leave, behind one port.

Each adapter answers `status()` honestly before it is asked to send anything, so
a surface can render what this machine will actually do without a test message
going to a broker to find out.
"""

from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path

from dispatch.msauth import AuthError, AuthNotConfigured, NullTokenProvider, TokenProvider
from dispatch.transport.contract import (
    CONFIGURED,
    LIVE,
    SIMULATED,
    UNAVAILABLE,
    UNCONFIGURED,
    OutboundMessage,
    TransportError,
    TransportResult,
    TransportUnconfigured,
)


def _build_mime(message: OutboundMessage, sender: str) -> EmailMessage:
    mail = EmailMessage()
    mail["From"] = sender
    mail["To"] = ", ".join(message.to)
    if message.cc:
        mail["Cc"] = ", ".join(message.cc)
    if message.reply_to:
        mail["Reply-To"] = message.reply_to
    mail["Subject"] = message.subject
    for key, value in (message.headers or {}).items():
        mail[key] = value
    mail.set_content(message.body_text)
    if message.body_html:
        mail.add_alternative(message.body_html, subtype="html")
    return mail


# --------------------------------------------------------------------- outbox


class FileOutboxTransport:
    """Writes a .eml and says SIMULATED. The default, and the honest one.

    This is what Dispatch does today with nothing configured, and it is right
    that it does: an operator with no relay still gets a complete, reviewable
    message on disk. What matters is the label. A .eml in Archive/Outbox is a
    record that Dispatch *would have* sent something. Reporting it as sent is
    the single mistake this whole layer exists to make impossible.
    """

    transport_id = "file_outbox"
    provider_name = "Archive/Outbox .eml fallback"

    def __init__(self, outbox: Path | str | None = None):
        self._outbox = Path(outbox) if outbox else None

    def outbox(self) -> Path:
        if self._outbox:
            return self._outbox
        root = os.environ.get("DISPATCH_ARCHIVE_ROOT")
        return (Path(root) if root else Path.cwd() / "Archive") / "Outbox"

    def status(self) -> str:
        return SIMULATED

    def describe(self) -> str:
        return f"{SIMULATED} -- {self.provider_name} ({self.outbox()})"

    def send(self, message: OutboundMessage) -> TransportResult:
        directory = self.outbox()
        directory.mkdir(parents=True, exist_ok=True)
        sender = message.from_address or os.environ.get("DISPATCH_EMAIL_FROM", "dispatch@localhost")
        mime = _build_mime(message, sender)
        import hashlib
        from datetime import datetime, timezone

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        digest = hashlib.sha256(mime.as_bytes()).hexdigest()[:8]
        path = directory / f"{stamp}-{digest}.eml"
        path.write_bytes(mime.as_bytes())
        return TransportResult(
            status=SIMULATED,
            # The prefix dispatch.delivery reads to classify this as not-delivery.
            receipt=f"not sent (no transport configured); written to {path}",
            provider=self.provider_name,
            detail="A person can open this file. Nobody received it.",
        )


# ----------------------------------------------------------------------- smtp


class SmtpBasicTransport:
    """SMTP with a username and password. Works today; closing on M365.

    Kept because it is what every non-Microsoft relay still accepts, and because
    removing the path an operator is currently using in order to make a point
    about Microsoft's roadmap would break a working install. `describe()` says
    which relay, so "LIVE" is a claim about a host a person can check.
    """

    transport_id = "smtp_basic"
    provider_name = "SMTP relay"

    def __init__(self, *, host: str = "", port: int = 0, user: str = "", password: str = "",
                 sender: str = "", starttls: bool = True, timeout: int = 30):
        self.host = host or os.environ.get("DISPATCH_SMTP_HOST", "")
        self.port = port or int(os.environ.get("DISPATCH_SMTP_PORT", "587"))
        self.user = user or os.environ.get("DISPATCH_SMTP_USER", "")
        self.password = password or os.environ.get("DISPATCH_SMTP_PASSWORD", "")
        self.sender = sender or os.environ.get("DISPATCH_EMAIL_FROM", "") or self.user
        self.starttls = starttls
        self.timeout = timeout

    def status(self) -> str:
        if not self.host:
            return UNCONFIGURED
        return LIVE if self.user else CONFIGURED

    def describe(self) -> str:
        if not self.host:
            return f"{UNCONFIGURED} -- no DISPATCH_SMTP_HOST"
        return f"{self.status()} -- SMTP relay {self.host}:{self.port}"

    def _connect(self) -> smtplib.SMTP:
        server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
        if self.starttls:
            server.starttls(context=ssl.create_default_context())
        return server

    def send(self, message: OutboundMessage) -> TransportResult:
        if not self.host:
            raise TransportUnconfigured("DISPATCH_SMTP_HOST is not set")
        mime = _build_mime(message, message.from_address or self.sender)
        try:
            with self._connect() as server:
                if self.user:
                    server.login(self.user, self.password)
                server.send_message(mime)
        except smtplib.SMTPAuthenticationError as exc:
            # The specific failure an M365 tenant now gives for basic auth, and
            # the operator cannot act on "authentication failed" alone.
            raise TransportError(
                f"{exc.smtp_code} {exc.smtp_error!r} -- if this mailbox is Microsoft 365, "
                "SMTP AUTH basic authentication is disabled by default on every tenant. "
                "Use the smtp_oauth2 or graph transport instead "
                "(docs/connectors/MICROSOFT_365_ACTIVATION.md)."
            ) from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise TransportError(f"{type(exc).__name__}: {exc}") from exc
        return TransportResult(LIVE, f"sent via {self.host}", f"SMTP relay {self.host}")


class SmtpOAuth2Transport(SmtpBasicTransport):
    """SMTP AUTH XOAUTH2 — the same relay, a token instead of a password.

    Microsoft 365 keeps SMTP submission available; what it withdraws is the
    password. XOAUTH2 is the supported replacement and is the smallest possible
    change for an install already sending through smtp.office365.com: the host,
    the port and the message are identical, and only the credential changes.

    The token comes from `dispatch.msauth`, so it is the operator's own
    delegated grant -- not a tenant-wide application permission.
    """

    transport_id = "smtp_oauth2"
    provider_name = "SMTP relay (XOAUTH2)"

    def __init__(self, *, token_provider: TokenProvider | None = None, **kwargs):
        super().__init__(**kwargs)
        self.token_provider = token_provider or NullTokenProvider()
        self.host = self.host or "smtp.office365.com"

    def status(self) -> str:
        provider_status = self.token_provider.status()
        if provider_status == UNCONFIGURED:
            return UNCONFIGURED
        if not self.host:
            return UNCONFIGURED
        return LIVE if provider_status == LIVE else CONFIGURED

    def describe(self) -> str:
        account = self.token_provider.account()
        who = f" as {account}" if account else ""
        return f"{self.status()} -- SMTP relay {self.host} via XOAUTH2{who}"

    @staticmethod
    def _xoauth2(user: str, token: str) -> bytes:
        import base64

        return base64.b64encode(f"user={user}\x01auth=Bearer {token}\x01\x01".encode()).decode().encode()

    def send(self, message: OutboundMessage) -> TransportResult:
        try:
            token = self.token_provider.access_token()
        except AuthNotConfigured as exc:
            raise TransportUnconfigured(str(exc)) from exc
        except AuthError as exc:
            raise TransportError(str(exc)) from exc

        account = self.token_provider.account() or self.user or self.sender
        mime = _build_mime(message, message.from_address or account)
        try:
            with self._connect() as server:
                server.docmd("AUTH", "XOAUTH2 " + self._xoauth2(account, token).decode())
                server.send_message(mime)
        except (smtplib.SMTPException, OSError) as exc:
            raise TransportError(f"{type(exc).__name__}: {exc}") from exc
        return TransportResult(LIVE, f"sent via {self.host} (XOAUTH2)", f"SMTP relay {self.host}")


# ---------------------------------------------------------------------- graph


class GraphMailTransport:
    """Microsoft Graph `sendMail`, as the signed-in operator.

    Preferred over SMTP where it is available: it is the path Microsoft is
    keeping, it puts the message in the operator's Sent Items (so a broker
    replying goes to a thread Mike can see in Outlook), and it needs no relay
    host to be configured at all.

    JSON, not MIME -- which is exactly why `OutboundMessage` is not an
    `EmailMessage`.
    """

    transport_id = "graph"
    provider_name = "Microsoft Graph"
    endpoint = "https://graph.microsoft.com/v1.0/me/sendMail"

    def __init__(self, *, token_provider: TokenProvider | None = None, timeout: int = 30, opener=None):
        self.token_provider = token_provider or NullTokenProvider()
        self.timeout = timeout
        #: Injected so the request shape can be tested without a network. The
        #: default is urllib; nothing here reaches Microsoft unless a real token
        #: provider is configured and a real call is made.
        self.opener = opener or urllib.request.urlopen

    def status(self) -> str:
        provider_status = self.token_provider.status()
        return provider_status if provider_status in (UNCONFIGURED, LIVE) else CONFIGURED

    def describe(self) -> str:
        account = self.token_provider.account()
        who = f" as {account}" if account else ""
        return f"{self.status()} -- {self.provider_name}{who}"

    @staticmethod
    def _payload(message: OutboundMessage) -> dict:
        def recipients(addresses):
            return [{"emailAddress": {"address": a}} for a in addresses]

        body = (
            {"contentType": "HTML", "content": message.body_html}
            if message.body_html
            else {"contentType": "Text", "content": message.body_text}
        )
        payload = {
            "message": {
                "subject": message.subject,
                "body": body,
                "toRecipients": recipients(message.to),
            },
            # The operator's Sent Items. A broker's reply then lands in a thread
            # that exists in Outlook rather than appearing out of nowhere.
            "saveToSentItems": True,
        }
        if message.cc:
            payload["message"]["ccRecipients"] = recipients(message.cc)
        if message.reply_to:
            payload["message"]["replyTo"] = recipients([message.reply_to])
        return payload

    def send(self, message: OutboundMessage) -> TransportResult:
        try:
            token = self.token_provider.access_token()
        except AuthNotConfigured as exc:
            raise TransportUnconfigured(str(exc)) from exc
        except AuthError as exc:
            raise TransportError(str(exc)) from exc

        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(self._payload(message)).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                code = getattr(response, "status", 202)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", "")
            except Exception:  # noqa: BLE001
                pass
            error = TransportError(f"Graph sendMail refused: {exc.code} {detail or exc.reason}")
            # 4xx other than 429 will not be fixed by trying again in five
            # minutes; 429 and 5xx will.
            error.retryable = exc.code == 429 or exc.code >= 500
            raise error from exc
        except urllib.error.URLError as exc:
            raise TransportError(f"could not reach Microsoft Graph: {exc.reason}") from exc

        if code not in (200, 202):
            raise TransportError(f"Graph sendMail returned {code}")
        account = self.token_provider.account()
        return TransportResult(
            LIVE, f"sent via Microsoft Graph{f' as {account}' if account else ''}", self.provider_name
        )


class UnavailableTransport:
    """A configured transport that cannot currently be reached.

    Distinct from UNCONFIGURED, and the distinction is the point: "you have not
    set this up" and "you set it up and it is not answering" need different
    actions from the operator.
    """

    transport_id = "unavailable"

    def __init__(self, provider_name: str, reason: str):
        self.provider_name = provider_name
        self.reason = reason

    def status(self) -> str:
        return UNAVAILABLE

    def describe(self) -> str:
        return f"{UNAVAILABLE} -- {self.provider_name}: {self.reason}"

    def send(self, message: OutboundMessage) -> TransportResult:
        raise TransportError(self.reason)
