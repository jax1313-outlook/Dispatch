"""Dispatch — outbound email transport.

The one place Dispatch builds and sends mail. Every load notification, customer
update, completion packet and IFTA approval link goes out through here.

This module used to live at ``cin_lite/email_delivery.py``. It was moved to the
Dispatch side on 2026-09-09 because SAM and its contract-intelligence engine are
being separated into their own program, and Dispatch cannot depend on a module
that is leaving. ``cin_lite`` now imports the transport from here; when it moves
to its own repository it takes a copy and this dependency disappears.

Delivers mail via stdlib ``smtplib``, so it works with any provider's SMTP relay.
Falls back to writing a ``.eml`` into the outbox and printing a notice when SMTP
is not configured or sending fails, so the truck keeps working offline. Per
Mike's ruling of 2026-09-09 the outbox is not a failure state, it is required:
creation and delivery are separate events. See
``docs/tab-walk/builder-notes/alerts-detection-generation-delivery-tracking.md``.

Configuration (environment):
    DISPATCH_SMTP_HOST       SMTP server host (its presence enables real sending)
    DISPATCH_SMTP_PORT       default 587
    DISPATCH_SMTP_USER       SMTP username (optional)
    DISPATCH_SMTP_PASSWORD   SMTP password (optional)
    DISPATCH_SMTP_STARTTLS   "1"/"0", default "1"
    DISPATCH_EMAIL_FROM      From address (default dispatch@<domain>)
    DISPATCH_EMAIL_REVIEWER  Reviewer address (always receives decision emails)
    DISPATCH_EMAIL_DOMAIN    domain for queue recipient addresses (default dispatch.local)
    DISPATCH_OUTBOX_PATH     explicit outbox directory
    DISPATCH_ARCHIVE_ROOT    outbox becomes <root>/Dispatch/Outbox
"""
from __future__ import annotations

import hashlib
import hmac
import os
import base64
import smtplib
import ssl
import sys
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from pathlib import Path

def _resolve_outbox() -> Path:
    """Where undelivered mail is written. Dispatch's own, not the contract
    archive's -- that shared path was the entanglement this move removes."""
    explicit = os.environ.get("DISPATCH_OUTBOX_PATH")
    if explicit:
        return Path(explicit)
    archive_root = os.environ.get("DISPATCH_ARCHIVE_ROOT")
    if archive_root:
        return Path(archive_root) / "Dispatch" / "Outbox"
    return Path(__file__).resolve().parent.parent / "Archive" / "Outbox"


_OUTBOX = _resolve_outbox()


def _secret() -> bytes:
    return os.environ.get("DISPATCH_EMAIL_SECRET", "dispatch-dev-secret").encode()


_TOKEN_VERSION = "ce1"
DECISION_TOKEN_TTL_HOURS = 14 * 24


def _legacy_token(contract_id: str, action: str) -> str:
    """The pre-expiry token shape. Nothing issues these any more; it exists so
    verify_token() can recognise a link mailed before expiry existed and decide
    whether the operator's grace window still admits it."""
    return hmac.new(_secret(), f"{contract_id}:{action}".encode(), hashlib.sha256).hexdigest()


def _legacy_grace_open() -> bool:
    until = os.environ.get("DISPATCH_LEGACY_TOKENS_UNTIL", "").strip()
    if not until:
        return False
    try:
        deadline = datetime.strptime(until, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return datetime.now(timezone.utc) <= deadline + timedelta(days=1)


def make_token(contract_id: str, action: str, *, ttl_hours: int = DECISION_TOKEN_TTL_HOURS) -> str:
    """Scoped, expiring token for an email action link.

    Was a bare digest of "<contract>:<action>" -- correct about scope, and
    valid forever. The expiry now travels inside the signed payload, so this
    module needs no store to enforce it, which matters: cin_lite is standalone
    by design (THE MIKE RULE) and has no database to keep a revocation ledger
    in. Revocation here is by consumption instead, and it is real: a decision
    can only be resolved once, after which pending.load() returns nothing and
    portal/routes/decisions.py answers "already processed" regardless of how
    good the token is. Dispatch's own operational tokens, which do have a
    database, carry explicit per-token revocation -- see dispatch/tokens.py.
    """
    expires = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    # "|" rather than ":" as the field separator: the ISO timestamp contains
    # colons of its own, so a colon-delimited payload cannot be split back
    # apart unambiguously.
    payload = f"{contract_id}|{action}|{expires.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    signature = hmac.new(_secret(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{_TOKEN_VERSION}.{encoded}.{signature}"


def verify_token(contract_id: str, action: str, token: str) -> bool:
    """Constant-time verification, failing closed on every non-success path:
    malformed, wrong version, bad signature, wrong contract, wrong action, or
    expired."""
    if not token:
        return False

    parts = token.split(".")
    if len(parts) != 3 or parts[0] != _TOKEN_VERSION:
        if hmac.compare_digest(_legacy_token(contract_id, action), token):
            return _legacy_grace_open()
        return False

    _, encoded, signature = parts
    expected = hmac.new(_secret(), encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False

    try:
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        signed_contract, signed_action, expires_at = decoded.split("|")
        expires = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, UnicodeDecodeError):
        return False

    if signed_contract != contract_id or signed_action != action:
        return False
    return datetime.now(timezone.utc) <= expires


def domain() -> str:
    return os.environ.get("DISPATCH_EMAIL_DOMAIN", "dispatch.local")


def from_address() -> str:
    return os.environ.get("DISPATCH_EMAIL_FROM", f"dispatch@{domain()}")


def reviewer_address() -> str:
    return os.environ.get("DISPATCH_EMAIL_REVIEWER", f"reviewer@{domain()}")


def queue_address(queue: str | None) -> str | None:
    """Email address for a routing queue (e.g. 'proposal-team') or None."""
    if not queue or queue == "none":
        return None
    return f"{queue}@{domain()}"


def _build(to: list[str], subject: str, body: str, html: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_address()
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def _write_fallback(fallback_id: str, msg: EmailMessage, outbox: Path | None = None) -> Path:
    box = outbox or _OUTBOX
    box.mkdir(parents=True, exist_ok=True)
    path = box / f"{fallback_id}.eml"
    path.write_bytes(bytes(msg))
    return path


def _using_default_secret() -> bool:
    return not os.environ.get("DISPATCH_EMAIL_SECRET")


def _send_or_write(fallback_id: str, msg: EmailMessage, outbox: Path | None = None) -> str:
    """Send via SMTP if configured, else write the message to Archive/Outbox."""
    host = os.environ.get("DISPATCH_SMTP_HOST")
    if not host:
        path = _write_fallback(fallback_id, msg, outbox)
        return f"not sent (SMTP not configured); written to {path}"

    if _using_default_secret():
        print("dispatch: WARNING — sending emails with the default HMAC secret; "
              "set DISPATCH_EMAIL_SECRET for production use.", file=sys.stderr)

    port = int(os.environ.get("DISPATCH_SMTP_PORT", "587"))
    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if os.environ.get("DISPATCH_SMTP_STARTTLS", "1") == "1":
                server.starttls(context=ssl.create_default_context())
            user = os.environ.get("DISPATCH_SMTP_USER")
            if user:
                server.login(user, os.environ.get("DISPATCH_SMTP_PASSWORD", ""))
            server.send_message(msg)
        return f"sent via {host} to {msg['To']}"
    except Exception as exc:  # never break the pipeline on delivery
        path = _write_fallback(fallback_id, msg, outbox)
        print(f"dispatch: email delivery failed ({exc}); written to {path}", file=sys.stderr)
        return f"delivery failed ({exc}); written to {path}"


def send(subject: str, body: str, to: list[str], fallback_id: str,
         outbox: Path | None = None) -> str:
    """Generic outbound email: send via SMTP, or write it to the outbox."""
    return _send_or_write(fallback_id, _build(to, subject, body), outbox)
