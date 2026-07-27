"""Control Layer — outbound email delivery (L2-COS Dispatch).

Cloned from cin_lite/email_delivery.py (Rule 15): delivers control-system
emails as real outbound mail via stdlib `smtplib`, so it works with any
provider's SMTP relay. Falls back to writing a `.eml` file under
Archive/Outbox and printing a notice when SMTP is not configured, sending
fails, or `L2_COS_EMAIL_DRY_RUN=1` is set.

The dry-run switch exists because the publisher/auto-contact workflow
(l2_cos/workflows/publisher.py) fires WITHOUT a human decision gate — the
Intelligence Score threshold is the approval — so test and staging
environments need a way to force the safe `.eml` fallback even if
`L2_COS_SMTP_HOST` happens to be configured, rather than relying solely on
that variable being unset.

Configuration (environment):
    L2_COS_SMTP_HOST        SMTP server host (its presence enables real sending)
    L2_COS_SMTP_PORT        default 587
    L2_COS_SMTP_USER        SMTP username (optional)
    L2_COS_SMTP_PASSWORD    SMTP password (optional)
    L2_COS_SMTP_STARTTLS    "1"/"0", default "1"
    L2_COS_EMAIL_FROM       From address (default dispatch@<domain>)
    L2_COS_EMAIL_DOMAIN     domain for fallback recipient addresses (default l2-cos.local)
    L2_COS_EMAIL_DRY_RUN    "1" forces the .eml fallback even when SMTP is configured
"""

from __future__ import annotations

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

from l2_cos import archive

_OUTBOX = archive.ARCHIVE_ROOT / "Outbox"


def domain() -> str:
    return os.environ.get("L2_COS_EMAIL_DOMAIN", "l2-cos.local")


def from_address() -> str:
    return os.environ.get("L2_COS_EMAIL_FROM", f"dispatch@{domain()}")


def fallback_broker_address() -> str:
    """Used only when a broker record has no `contact_email` on file, so the
    inquiry is still delivered (or archived to Outbox) rather than dropped."""
    return f"unassigned-broker@{domain()}"


def _dry_run() -> bool:
    return os.environ.get("L2_COS_EMAIL_DRY_RUN", "0") == "1"


def _build(to: list[str], subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_address()
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def _write_fallback(fallback_id: str, msg: EmailMessage) -> Path:
    _OUTBOX.mkdir(parents=True, exist_ok=True)
    path = _OUTBOX / f"{fallback_id}.eml"
    path.write_bytes(bytes(msg))
    return path


def _send_or_write(fallback_id: str, msg: EmailMessage) -> str:
    """Send via SMTP if configured and not dry-run; else write to Archive/Outbox."""
    if _dry_run():
        path = _write_fallback(fallback_id, msg)
        return f"dry-run (L2_COS_EMAIL_DRY_RUN=1); written to {path}"

    host = os.environ.get("L2_COS_SMTP_HOST")
    if not host:
        path = _write_fallback(fallback_id, msg)
        return f"not sent (SMTP not configured); written to {path}"

    port = int(os.environ.get("L2_COS_SMTP_PORT", "587"))
    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if os.environ.get("L2_COS_SMTP_STARTTLS", "1") == "1":
                server.starttls(context=ssl.create_default_context())
            user = os.environ.get("L2_COS_SMTP_USER")
            if user:
                server.login(user, os.environ.get("L2_COS_SMTP_PASSWORD", ""))
            server.send_message(msg)
        return f"sent via {host} to {msg['To']}"
    except Exception as exc:  # never break the pipeline on a delivery failure
        path = _write_fallback(fallback_id, msg)
        print(f"l2_cos: email delivery failed ({exc}); written to {path}", file=sys.stderr)
        return f"delivery failed ({exc}); written to {path}"


def send(subject: str, body: str, to: list[str], fallback_id: str) -> str:
    """Generic outbound email: send via SMTP (unless dry-run) or write to Archive/Outbox."""
    return _send_or_write(fallback_id, _build(to, subject, body))
