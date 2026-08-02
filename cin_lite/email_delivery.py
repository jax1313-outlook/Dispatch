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

import hashlib
import hmac
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

from cin_lite import archive, control

_OUTBOX = archive.ARCHIVE_ROOT / "Outbox"


def _secret() -> bytes:
    return os.environ.get("CIN_LITE_EMAIL_SECRET", "cin-lite-dev-secret").encode()


def make_token(contract_id: str, action: str) -> str:
    """HMAC-SHA256 token for an email action link."""
    return hmac.new(_secret(), f"{contract_id}:{action}".encode(), hashlib.sha256).hexdigest()


def verify_token(contract_id: str, action: str, token: str) -> bool:
    """Constant-time verification of an email action token."""
    expected = make_token(contract_id, action)
    return hmac.compare_digest(expected, token)


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


def deliver_checkpoint(
    contract: dict,
    contract_id: str,
    text_body: str,
    html_body: str,
) -> str:
    """Send the checkpoint email (HTML with action buttons + text fallback)."""
    subject = f"[CIN-Lite] Decision Required — {contract.get('title', contract_id)}"
    to = [reviewer_address()]
    return _send_or_write(
        f"{contract_id}-checkpoint",
        _build(to, subject, text_body, html=html_body),
    )


def _render_decision_html(
    contract: dict,
    contract_id: str,
    summary: str,
    decision: dict,
    action: str,
    route: str,
    flags: list[str],
    label: str,
) -> str:
    """Render the decision confirmation email as styled HTML."""
    action_color = control._ACTION_COLORS.get(action, "#333")
    flags_html = ", ".join(flags) if flags else "<em>none</em>"
    recommended = decision.get("action", "")
    rec_label = control.ACTIONS.get(recommended, (recommended, ""))[0]
    followed = decision.get("action") == action

    followed_html = (
        '<span style="background:#e8f5e9;color:#2e7d32;padding:2px 8px;'
        'border-radius:3px;font-size:12px;font-weight:600;">Followed recommendation</span>'
        if followed else
        '<span style="background:#fff3e0;color:#e65100;padding:2px 8px;'
        'border-radius:3px;font-size:12px;font-weight:600;">Overrode recommendation</span>'
    )

    return f"""\
<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;color:#333;">
    <div style="background:{action_color};color:#fff;padding:16px 24px;">
        <h1 style="margin:0;font-size:20px;">CIN-Lite — Decision Recorded</h1>
    </div>

    <div style="padding:20px 24px;border:1px solid #ddd;border-top:none;">
        <div style="background:#f5f5f5;border-left:4px solid {action_color};padding:12px 16px;margin-bottom:16px;">
            <strong style="font-size:16px;">{label}</strong>
            <span style="color:#666;font-size:13px;margin-left:8px;">routed to {route}</span>
            <br>{followed_html}
        </div>

        <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
            <tr><td style="padding:6px 0;color:#666;width:120px;">Title</td>
                <td style="padding:6px 0;font-weight:600;">{contract.get('title', '')}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Agency</td>
                <td style="padding:6px 0;">{contract.get('agency', '')}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Solicitation</td>
                <td style="padding:6px 0;">{contract.get('solicitation_number', '')}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Contract ID</td>
                <td style="padding:6px 0;"><strong>{contract_id}</strong></td></tr>
        </table>

        <div style="background:#fafafa;padding:12px 16px;border-radius:4px;margin-bottom:16px;">
            <strong>Summary</strong><br>{summary}
        </div>

        <div style="margin-bottom:16px;">
            <strong>Flags:</strong> {flags_html}
        </div>

        <div style="background:#f5f5f5;padding:12px 16px;border-radius:4px;">
            <strong>Agent Recommendation</strong><br>
            Action: {rec_label} [{recommended}]<br>
            Priority: {decision.get('priority', 'n/a')}<br>
            Reason: {decision.get('reason', '')}
        </div>
    </div>

    <div style="padding:12px 24px;font-size:11px;color:#999;border:1px solid #ddd;border-top:none;">
        CIN-Lite Hybrid System &mdash; Contract ID: {contract_id}
    </div>
</div>"""


def deliver_decision(
    contract: dict,
    contract_id: str,
    summary: str,
    decision: dict,
    action: str,
    route: str,
    flags: list[str],
) -> str:
    """Send the decision confirmation email (HTML + text fallback)."""
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
    html = _render_decision_html(
        contract, contract_id, summary, decision, action, route, flags, label,
    )
    return _send_or_write(
        contract_id, _build(_decision_recipients(decision), subject, body, html=html),
    )
