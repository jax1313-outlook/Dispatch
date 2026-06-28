"""Control Layer — outbound email delivery.

Delivers control-system emails (routing decisions, proposal kickoffs) as real
outbound mail via stdlib `smtplib`, so it works with any provider's SMTP relay
(SendGrid, Amazon SES, Mailgun, Postmark, Gmail, etc.). Falls back to writing a
`.eml` file under Archive/Outbox and printing a notice when SMTP is not configured
or sending fails, so the pipeline still runs end-to-end offline.

Configuration (environment):
    CIN_LITE_SMTP_HOST       SMTP server host (its presence enables real sending)
    CIN_LITE_SMTP_PORT       default 587
    CIN_LITE_SMTP_USER       SMTP username (optional)
    CIN_LITE_SMTP_PASSWORD   SMTP password (optional)
    CIN_LITE_SMTP_STARTTLS   "1"/"0", default "1"
    CIN_LITE_EMAIL_FROM      From address (default cin-lite@<domain>)
    CIN_LITE_EMAIL_REVIEWER  Reviewer address (always receives decision emails)
    CIN_LITE_EMAIL_DOMAIN    domain for queue recipient addresses (default cin-lite.local)
"""

from __future__ import annotations

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

from cin_lite import archive, control

_OUTBOX = archive.ARCHIVE_ROOT / "Outbox"


def domain() -> str:
    return os.environ.get("CIN_LITE_EMAIL_DOMAIN", "cin-lite.local")


def from_address() -> str:
    return os.environ.get("CIN_LITE_EMAIL_FROM", f"cin-lite@{domain()}")


def reviewer_address() -> str:
    return os.environ.get("CIN_LITE_EMAIL_REVIEWER", f"reviewer@{domain()}")


def queue_address(queue: str | None) -> str | None:
    """Email address for a routing queue (e.g. 'proposal-team') or None."""
    if not queue or queue == "none":
        return None
    return f"{queue}@{domain()}"


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
    """Send via SMTP if configured, else write the message to Archive/Outbox."""
    host = os.environ.get("CIN_LITE_SMTP_HOST")
    if not host:
        path = _write_fallback(fallback_id, msg)
        return f"not sent (SMTP not configured); written to {path}"

    port = int(os.environ.get("CIN_LITE_SMTP_PORT", "587"))
    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if os.environ.get("CIN_LITE_SMTP_STARTTLS", "1") == "1":
                server.starttls(context=ssl.create_default_context())
            user = os.environ.get("CIN_LITE_SMTP_USER")
            if user:
                server.login(user, os.environ.get("CIN_LITE_SMTP_PASSWORD", ""))
            server.send_message(msg)
        return f"sent via {host} to {msg['To']}"
    except Exception as exc:  # never break the pipeline on delivery
        path = _write_fallback(fallback_id, msg)
        print(f"cin_lite: email delivery failed ({exc}); written to {path}", file=sys.stderr)
        return f"delivery failed ({exc}); written to {path}"


def send(subject: str, body: str, to: list[str], fallback_id: str) -> str:
    """Generic outbound email: send via SMTP or write to Archive/Outbox."""
    return _send_or_write(fallback_id, _build(to, subject, body))


def _decision_recipients(decision: dict) -> list[str]:
    """Reviewer always; plus the routing-queue address unless recipient is 'none'."""
    addrs = [reviewer_address()]
    queue_addr = queue_address(decision.get("recipient"))
    if queue_addr and queue_addr not in addrs:
        addrs.append(queue_addr)
    return addrs


def deliver_decision(
    contract: dict,
    contract_id: str,
    summary: str,
    decision: dict,
    action: str,
    route: str,
    flags: list[str],
) -> str:
    """Send the decision email (summary + routing decision)."""
    label = control.ACTIONS.get(action, (action, route))[0]
    priority = decision.get("priority", "n/a")
    subject = f"[CIN-Lite] {contract_id} — {label} (priority {priority})"
    body = "\n".join(
        [
            f"Contract   : {contract.get('title')}",
            f"Agency     : {contract.get('agency')}",
            f"Solicitation: {contract.get('solicitation_number')}",
            f"Contract ID: {contract_id}",
            "",
            "Summary:",
            f"  {summary}",
            "",
            "Routing decision (human):",
            f"  Action   : {label} [{action}]",
            f"  Route    : {route}",
            "",
            "Routing recommendation (agent):",
            f"  Action   : {decision.get('action')}",
            f"  Priority : {decision.get('priority')}",
            f"  Recipient: {decision.get('recipient')}",
            f"  Reason   : {decision.get('reason')}",
            f"  Notes    : {decision.get('notes')}",
            "",
            f"Flags raised: {', '.join(flags) if flags else 'none'}",
        ]
    )
    return _send_or_write(contract_id, _build(_decision_recipients(decision), subject, body))
