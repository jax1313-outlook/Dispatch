"""Dispatch Outbound Email Delivery.

Standalone email delivery transport for Dispatch.
Delivers emails via stdlib smtplib when configured, or writes .eml files
locally under Dispatch's outbox directory when offline/unconfigured.
"""

from __future__ import annotations

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path


def _get_data_dir() -> Path:
    explicit = os.environ.get("PORTAL_DATA_DIR")
    if explicit:
        return Path(explicit)
    env_dir = os.environ.get("DISPATCH_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    ops_root = os.environ.get("DISPATCH_OPERATIONS_ROOT")
    if ops_root:
        return Path(ops_root) / "Current Workspace" / "PortalData"
    return Path(__file__).resolve().parent.parent / "portal" / "data"


def _outbox_dir() -> Path:
    return _get_data_dir() / "Outbox"


def domain() -> str:
    return os.environ.get("DISPATCH_EMAIL_DOMAIN", "dispatch.local")


def from_address() -> str:
    return os.environ.get("DISPATCH_EMAIL_FROM", f"dispatch@{domain()}")


def reviewer_address() -> str:
    return os.environ.get("DISPATCH_EMAIL_REVIEWER", f"reviewer@{domain()}")


def _build(to: list[str], subject: str, body: str, html: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_address()
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def _write_fallback(fallback_id: str, msg: EmailMessage) -> Path:
    d = _outbox_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{fallback_id}.eml"
    path.write_bytes(bytes(msg))
    return path


def _send_or_write(fallback_id: str, msg: EmailMessage) -> str:
    host = os.environ.get("DISPATCH_SMTP_HOST")
    if not host:
        path = _write_fallback(fallback_id, msg)
        return f"not sent (SMTP not configured); written to {path}"

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
    except Exception as exc:
        path = _write_fallback(fallback_id, msg)
        print(f"dispatch: email delivery failed ({exc}); written to {path}", file=sys.stderr)
        return f"delivery failed ({exc}); written to {path}"


def send(subject: str, body: str, to: list[str], fallback_id: str) -> str:
    """Generic outbound email send function for Dispatch."""
    return _send_or_write(fallback_id, _build(to, subject, body))
