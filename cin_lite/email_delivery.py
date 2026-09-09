"""Control Layer — contract-intelligence decision email.

The generic transport that used to live here moved to ``dispatch/mail.py`` on
2026-09-09, when SAM and this engine began being separated from Dispatch.
Dispatch must not depend on a module that is leaving, so the direction was
inverted: what remains here is the contract-side rendering and routing, and it
imports the transport from Dispatch.

When this package moves to its own repository it takes a copy of
``dispatch/mail.py`` with it and this import disappears. Nothing else here has
to change. See ``docs/tab-walk/PARKING_LOT.md``.

Contract mail keeps writing into the contract archive's own outbox, not
Dispatch's, so the two programs' undelivered mail never mix.
"""

from __future__ import annotations

import html as _html
from email.message import EmailMessage
from pathlib import Path

from cin_lite import archive, control

# Re-exported so existing callers and tests keep working unchanged.
from dispatch.mail import (  # noqa: F401
    DECISION_TOKEN_TTL_HOURS,
    _build,
    _using_default_secret,
    domain,
    from_address,
    make_token,
    queue_address,
    reviewer_address,
    smtplib,
    verify_token,
)
from dispatch import mail as _mail

_OUTBOX = archive.ARCHIVE_ROOT / "Outbox"


def _send_or_write(fallback_id: str, msg: EmailMessage, outbox: Path | None = None) -> str:
    """Contract mail, into the contract archive's outbox."""
    return _mail._send_or_write(fallback_id, msg, outbox or _OUTBOX)


def send(subject: str, body: str, to: list[str], fallback_id: str,
         outbox: Path | None = None) -> str:
    return _mail.send(subject, body, to, fallback_id, outbox or _OUTBOX)


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
    subject = f"[DISPATCH] Decision Required — {contract.get('title', contract_id)}"
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
    esc = _html.escape
    action_color = control._ACTION_COLORS.get(action, "#333")
    flags_html = ", ".join(esc(f) for f in flags) if flags else "<em>none</em>"
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
        <h1 style="margin:0;font-size:20px;">DISPATCH — Decision Recorded</h1>
    </div>

    <div style="padding:20px 24px;border:1px solid #ddd;border-top:none;">
        <div style="background:#f5f5f5;border-left:4px solid {action_color};padding:12px 16px;margin-bottom:16px;">
            <strong style="font-size:16px;">{label}</strong>
            <span style="color:#666;font-size:13px;margin-left:8px;">routed to {route}</span>
            <br>{followed_html}
        </div>

        <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
            <tr><td style="padding:6px 0;color:#666;width:120px;">Title</td>
                <td style="padding:6px 0;font-weight:600;">{esc(str(contract.get('title', '')))}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Agency</td>
                <td style="padding:6px 0;">{esc(str(contract.get('agency', '')))}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Solicitation</td>
                <td style="padding:6px 0;">{esc(str(contract.get('solicitation_number', '')))}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Contract ID</td>
                <td style="padding:6px 0;"><strong>{esc(contract_id)}</strong></td></tr>
        </table>

        <div style="background:#fafafa;padding:12px 16px;border-radius:4px;margin-bottom:16px;">
            <strong>Summary</strong><br>{esc(summary)}
        </div>

        <div style="margin-bottom:16px;">
            <strong>Flags:</strong> {flags_html}
        </div>

        <div style="background:#f5f5f5;padding:12px 16px;border-radius:4px;">
            <strong>Agent Recommendation</strong><br>
            Action: {esc(rec_label)} [{esc(str(recommended))}]<br>
            Priority: {esc(str(decision.get('priority', 'n/a')))}<br>
            Reason: {esc(str(decision.get('reason', '')))}
        </div>
    </div>

    <div style="padding:12px 24px;font-size:11px;color:#999;border:1px solid #ddd;border-top:none;">
        DISPATCH &mdash; Contract ID: {contract_id}
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
    subject = f"[DISPATCH] {contract_id} — {label} (priority {priority})"
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
