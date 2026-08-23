"""Dispatch lifecycle notifications — bridges the load engine to the email control system.

Sends styled HTML checkpoint emails at decision-worthy milestones in a load's
lifecycle.  Each email contains HMAC-signed action buttons that link back to the
portal's dispatch decision endpoint.

Trigger points:
    - Exception opened (severity high/critical)
    - Delivery completed
    - POD package generated
    - Load archived
"""

from __future__ import annotations

import hashlib
import hmac
import html as _html
import os
from typing import Callable

from dispatch import tokens

from cin_lite.email_delivery import (
    _build,
    _send_or_write,
    from_address,
    reviewer_address,
)

_LOAD_DECISION = "load_decision"
_STAKEHOLDER = "stakeholder_view"

DISPATCH_ACTIONS: dict[str, tuple[str, str]] = {
    "acknowledge": ("Acknowledge", "#2e7d32"),
    "flag_review": ("Flag for Review", "#e65100"),
    "escalate": ("Escalate", "#c62828"),
    "request_info": ("Request More Info", "#6a1b9a"),
}


def _secret() -> bytes:
    return os.environ.get("DISPATCH_EMAIL_SECRET", "dispatch-dev-secret").encode()


def _legacy_digest(namespace: str, *parts: str) -> str:
    """The pre-lifecycle token shape, kept for one purpose only: recognising a
    link that was mailed out before tokens could expire, so `tokens.verify()`
    can decide whether the operator's grace window still admits it. Nothing
    issues these any more."""
    material = ":".join((namespace, *parts))
    return hmac.new(_secret(), material.encode(), hashlib.sha256).hexdigest()


def make_token(load_id: str, action: str, *, issued_by: str = "") -> str:
    """Decision-link token for one action on one load.

    Was a bare digest of "dispatch:<load>:<action>" -- permanent, unrevocable,
    and identical every time it was generated. Now issued through
    dispatch.tokens with an expiry, a nonce and a revocation record. The
    signature is unchanged so the ~30 existing call sites did not have to move.
    """
    return tokens.issue(
        _LOAD_DECISION, f"{load_id}:{action}", issued_by=issued_by
    )


def verify_token(load_id: str, action: str, token: str) -> bool:
    return bool(
        tokens.verify(
            _LOAD_DECISION,
            f"{load_id}:{action}",
            token,
            legacy_digest=_legacy_digest("dispatch", load_id, action),
        )
    )


def explain_token(load_id: str, action: str, token: str) -> tokens.TokenVerdict:
    """The same check as verify_token(), with the reason attached -- for a
    caller that needs to tell an expired link apart from a revoked one."""
    return tokens.verify(
        _LOAD_DECISION,
        f"{load_id}:{action}",
        token,
        legacy_digest=_legacy_digest("dispatch", load_id, action),
    )


def make_stakeholder_token(load_id: str, *, issued_by: str = "") -> str:
    """Token for the external, non-PIN-gated stakeholder view of one load.

    Its own purpose namespace, so a stakeholder token can never be replayed
    against a decision endpoint or the reverse -- the property the old
    prefixed-digest design had, kept, and now backed by a signed `purpose`
    claim rather than a string prefix.
    """
    return tokens.issue(_STAKEHOLDER, load_id, issued_by=issued_by)


def verify_stakeholder_token(load_id: str, token: str) -> bool:
    return bool(
        tokens.verify(
            _STAKEHOLDER,
            load_id,
            token,
            legacy_digest=_legacy_digest("dispatch-stakeholder", load_id),
        )
    )


def explain_stakeholder_token(load_id: str, token: str) -> tokens.TokenVerdict:
    return tokens.verify(
        _STAKEHOLDER,
        load_id,
        token,
        legacy_digest=_legacy_digest("dispatch-stakeholder", load_id),
    )


def revoke_stakeholder_access(load_id: str, *, reason: str = "", actor: str = "") -> int:
    """Kill every live stakeholder link for a load. The control that did not
    exist before: previously the only way to stop a forwarded link was to
    rotate the global signing secret, which killed every other link too."""
    return tokens.revoke_for_object(_STAKEHOLDER, load_id, reason=reason, actor=actor)


def _action_url_base() -> str:
    portal = os.environ.get("DISPATCH_PORTAL_URL", "http://127.0.0.1:8080").rstrip("/")
    return f"{portal}/api/dispatch/decision"


def _action_buttons(load_id: str, recommended: str | None = None) -> str:
    base = _action_url_base()
    rows = []
    for key, (label, color) in DISPATCH_ACTIONS.items():
        token = make_token(load_id, key)
        url = f"{base}/{load_id}/{key}?token={token}"
        rec_badge = (
            ' <span style="background:#fff3e0;color:#e65100;padding:2px 6px;'
            'border-radius:3px;font-size:11px;">RECOMMENDED</span>'
            if key == recommended
            else ""
        )
        rows.append(
            f'<tr><td style="padding:8px 12px;">'
            f'<a href="{url}" style="display:inline-block;padding:8px 20px;'
            f"background:{color};color:#fff;text-decoration:none;border-radius:4px;"
            f'font-weight:600;font-size:14px;">{label}</a>{rec_badge}'
            f"</td></tr>"
        )
    return "\n".join(rows)


def _render_notification(
    load: dict,
    event_type: str,
    headline: str,
    detail_html: str,
    recommended: str | None = None,
) -> tuple[str, str]:
    """Render plain-text and HTML notification emails."""
    esc = _html.escape
    load_id = load["load_id"]

    text = "\n".join([
        "=" * 64,
        f"DISPATCH — {headline}",
        "=" * 64,
        f"Load ID   : {load_id}",
        f"Customer  : {load.get('customer', '')}",
        f"Status    : {load.get('status', '')}",
        f"Pickup    : {load.get('pickup_location', '')}",
        f"Delivery  : {load.get('delivery_location', '')}",
        f"Driver    : {load.get('driver', '')}",
        "",
        f"Event: {event_type}",
        "",
        "Respond via the HTML email or the portal.",
        "=" * 64,
    ])

    event_colors = {
        "exception": "#c62828",
        "delivered": "#2e7d32",
        "pod_generated": "#1565c0",
        "dispatched": "#2e7d32",
        "archived": "#6a1b9a",
        "invoice_created": "#1b5e20",
        "payment_received": "#2e7d32",
        "payment_overdue": "#c62828",
        "stalled": "#e65100",
    }
    header_color = event_colors.get(event_type, "#1a237e")

    html = f"""\
<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;color:#333;">
    <div style="background:{header_color};color:#fff;padding:16px 24px;">
        <h1 style="margin:0;font-size:20px;">DISPATCH — {esc(headline)}</h1>
    </div>

    <div style="padding:20px 24px;border:1px solid #ddd;border-top:none;">
        <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
            <tr><td style="padding:6px 0;color:#666;width:120px;">Load ID</td>
                <td style="padding:6px 0;font-weight:600;"><code>{esc(load_id)}</code></td></tr>
            <tr><td style="padding:6px 0;color:#666;">Customer</td>
                <td style="padding:6px 0;">{esc(load.get('customer', ''))}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Status</td>
                <td style="padding:6px 0;font-weight:600;">{esc(load.get('status', ''))}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Pickup</td>
                <td style="padding:6px 0;">{esc(load.get('pickup_location', ''))}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Delivery</td>
                <td style="padding:6px 0;">{esc(load.get('delivery_location', ''))}</td></tr>
            <tr><td style="padding:6px 0;color:#666;">Driver</td>
                <td style="padding:6px 0;">{esc(load.get('driver', ''))}</td></tr>
        </table>

        {detail_html}

        <div style="margin-top:24px;">
            <h2 style="font-size:16px;margin-bottom:12px;border-bottom:2px solid {header_color};padding-bottom:8px;">
                Select Action
            </h2>
            <table style="width:100%;border-collapse:collapse;">
                {_action_buttons(load_id, recommended)}
            </table>
        </div>
    </div>

    <div style="padding:12px 24px;font-size:11px;color:#999;border:1px solid #ddd;border-top:none;">
        DISPATCH &mdash; Load ID: {esc(load_id)}
    </div>
</div>"""

    return text, html


def notify_dispatched(load: dict) -> str:
    """Send notification when a load is dispatched (auto or manual)."""
    esc = _html.escape
    driver = load.get("driver", "")
    equipment = load.get("equipment", "")

    detail = f"""\
<div style="background:#e8f5e9;border-left:4px solid #2e7d32;padding:12px 16px;margin-bottom:16px;">
    <strong>Load Dispatched</strong><br>
    Driver: {esc(driver) or 'Not assigned'}<br>
    Equipment: {esc(equipment) or 'Not assigned'}
</div>
<p style="color:#666;font-size:13px;">
    The load has been dispatched and is ready for pickup.
</p>"""

    text, html = _render_notification(
        load,
        event_type="dispatched",
        headline="Load Dispatched",
        detail_html=detail,
        recommended="acknowledge",
    )

    subject = f"[DISPATCH] Dispatched — {load.get('customer', load['load_id'])}"
    msg = _build([reviewer_address()], subject, text, html=html)
    return _send_or_write(f"dispatch-dispatched-{load['load_id']}", msg)


def notify_exception(load: dict, exception: dict) -> str:
    """Send notification when a high/critical severity exception is opened."""
    esc = _html.escape
    severity = exception.get("severity", "unknown")
    exc_type = exception.get("exception_type", "other")
    desc = exception.get("description", "")

    detail = f"""\
<div style="background:#ffebee;border-left:4px solid #c62828;padding:12px 16px;margin-bottom:16px;">
    <strong>Exception Opened</strong><br>
    Type: {esc(exc_type)}<br>
    Severity: <strong style="color:#c62828;">{esc(severity)}</strong><br>
    Description: {esc(desc)}
</div>"""

    text, html = _render_notification(
        load,
        event_type="exception",
        headline=f"Exception — {severity.upper()} severity",
        detail_html=detail,
        recommended="escalate" if severity == "critical" else "flag_review",
    )

    subject = f"[DISPATCH] Exception ({severity}) — {load.get('customer', load['load_id'])}"
    msg = _build([reviewer_address()], subject, text, html=html)
    return _send_or_write(f"dispatch-exc-{exception.get('exception_id', load['load_id'])}", msg)


def notify_delivered(load: dict, milestone: dict) -> str:
    """Send notification when a load is delivered."""
    esc = _html.escape
    location = milestone.get("location", "")

    detail = f"""\
<div style="background:#e8f5e9;border-left:4px solid #2e7d32;padding:12px 16px;margin-bottom:16px;">
    <strong>Load Delivered</strong><br>
    Location: {esc(location) or 'Not specified'}<br>
    Time: {esc(milestone.get('event_time', ''))}
</div>
<p style="color:#666;font-size:13px;">
    Next steps: attach evidence, generate POD, or acknowledge delivery.
</p>"""

    text, html = _render_notification(
        load,
        event_type="delivered",
        headline="Load Delivered",
        detail_html=detail,
        recommended="acknowledge",
    )

    subject = f"[DISPATCH] Delivered — {load.get('customer', load['load_id'])}"
    msg = _build([reviewer_address()], subject, text, html=html)
    return _send_or_write(f"dispatch-delivered-{load['load_id']}", msg)


def notify_pod_generated(load: dict, pod: dict) -> str:
    """Send notification when a POD package is generated."""
    esc = _html.escape
    evidence_count = len(pod.get("evidence_ids", []))
    recipient = pod.get("recipient", "")

    detail = f"""\
<div style="background:#e3f2fd;border-left:4px solid #1565c0;padding:12px 16px;margin-bottom:16px;">
    <strong>POD Package Generated</strong><br>
    POD ID: <code>{esc(pod.get('pod_id', ''))}</code><br>
    Evidence items: {evidence_count}<br>
    Recipient: {esc(recipient) or 'Not specified'}
</div>
<p style="color:#666;font-size:13px;">
    The load is ready for archiving once all documentation is in order.
</p>"""

    text, html = _render_notification(
        load,
        event_type="pod_generated",
        headline="POD Package Ready",
        detail_html=detail,
        recommended="acknowledge",
    )

    subject = f"[DISPATCH] POD Ready — {load.get('customer', load['load_id'])}"
    msg = _build([reviewer_address()], subject, text, html=html)
    return _send_or_write(f"dispatch-pod-{pod.get('pod_id', load['load_id'])}", msg)


def notify_archived(load: dict, retention: dict) -> str:
    """Send notification when a load is archived."""
    esc = _html.escape
    evidence_count = len(retention.get("evidence_index", []))

    detail = f"""\
<div style="background:#f3e5f5;border-left:4px solid #6a1b9a;padding:12px 16px;margin-bottom:16px;">
    <strong>Load Archived</strong><br>
    Archive ID: <code>{esc(retention.get('archive_id', ''))}</code><br>
    Final status: {esc(retention.get('final_status', ''))}<br>
    Evidence items: {evidence_count}<br>
    Archive location: {esc(retention.get('archive_location', ''))}
</div>"""

    text, html = _render_notification(
        load,
        event_type="archived",
        headline="Load Archived",
        detail_html=detail,
        recommended="acknowledge",
    )

    subject = f"[DISPATCH] Archived — {load.get('customer', load['load_id'])}"
    msg = _build([reviewer_address()], subject, text, html=html)
    return _send_or_write(f"dispatch-archive-{load['load_id']}", msg)


def notify_invoice_created(load: dict, settlement: dict) -> str:
    """Send notification when an invoice/settlement is created for a load."""
    esc = _html.escape
    invoice_num = settlement.get("invoice_number", "")
    invoice_amt = settlement.get("invoice_amount", 0)
    due_date = settlement.get("due_date", "")

    detail = f"""\
<div style="background:#e8f5e9;border-left:4px solid #2e7d32;padding:12px 16px;margin-bottom:16px;">
    <strong>Invoice Created</strong><br>
    Invoice #: <code>{esc(invoice_num)}</code><br>
    Amount: <strong>${invoice_amt:,.2f}</strong><br>
    Due Date: {esc(due_date) or 'Not set'}<br>
    Status: Invoiced
</div>"""

    text, html = _render_notification(
        load,
        event_type="invoice_created",
        headline="Invoice Created",
        detail_html=detail,
        recommended="acknowledge",
    )

    subject = f"[DISPATCH] Invoice Created — {load.get('customer', load['load_id'])}"
    msg = _build([reviewer_address()], subject, text, html=html)
    return _send_or_write(f"dispatch-invoice-{load['load_id']}", msg)


def notify_payment_received(load: dict, settlement: dict) -> str:
    """Send notification when payment is recorded for a load."""
    esc = _html.escape
    invoice_num = settlement.get("invoice_number", "")
    payment_amt = settlement.get("payment_amount", 0)
    net_payment = settlement.get("net_payment", payment_amt)
    method = settlement.get("payment_method", "")
    factoring = settlement.get("factoring_fee", 0)

    factoring_line = ""
    if factoring:
        factoring_line = f"Factoring Fee: ${factoring:,.2f}<br>\n    Net Payment: <strong>${net_payment:,.2f}</strong><br>"

    detail = f"""\
<div style="background:#e8f5e9;border-left:4px solid #2e7d32;padding:12px 16px;margin-bottom:16px;">
    <strong>Payment Received</strong><br>
    Invoice #: <code>{esc(invoice_num)}</code><br>
    Payment: <strong>${payment_amt:,.2f}</strong><br>
    {factoring_line}
    Method: {esc(method)}
</div>"""

    text, html = _render_notification(
        load,
        event_type="payment_received",
        headline="Payment Received",
        detail_html=detail,
        recommended="acknowledge",
    )

    subject = f"[DISPATCH] Payment Received — {load.get('customer', load['load_id'])}"
    msg = _build([reviewer_address()], subject, text, html=html)
    return _send_or_write(f"dispatch-payment-{load['load_id']}", msg)


def notify_payment_overdue(load: dict, settlement: dict) -> str:
    """Send notification when a payment becomes overdue."""
    esc = _html.escape
    invoice_num = settlement.get("invoice_number", "")
    invoice_amt = settlement.get("invoice_amount", 0)
    due_date = settlement.get("due_date", "")

    detail = f"""\
<div style="background:#ffebee;border-left:4px solid #c62828;padding:12px 16px;margin-bottom:16px;">
    <strong>Payment Overdue</strong><br>
    Invoice #: <code>{esc(invoice_num)}</code><br>
    Amount Due: <strong>${invoice_amt:,.2f}</strong><br>
    Due Date: <strong style="color:#c62828;">{esc(due_date)}</strong>
</div>
<p style="color:#666;font-size:13px;">
    This invoice is past due. Follow up with the customer or escalate for collection.
</p>"""

    text, html = _render_notification(
        load,
        event_type="payment_overdue",
        headline="Payment Overdue",
        detail_html=detail,
        recommended="flag_review",
    )

    subject = f"[DISPATCH] OVERDUE — {load.get('customer', load['load_id'])}"
    msg = _build([reviewer_address()], subject, text, html=html)
    return _send_or_write(f"dispatch-overdue-{load['load_id']}", msg)


def notify_settlement_disputed(load: dict, settlement: dict, reason: str = "") -> str:
    esc = _html.escape
    invoice_num = settlement.get("invoice_number", "")
    invoice_amt = settlement.get("invoice_amount", 0)

    detail = f"""\
<div style="background:#fff3e0;border-left:4px solid #e65100;padding:12px 16px;margin-bottom:16px;">
    <strong>Settlement Disputed</strong><br>
    Invoice #: <code>{esc(invoice_num)}</code><br>
    Amount: <strong>${invoice_amt:,.2f}</strong><br>
    {f'Reason: {esc(reason)}' if reason else ''}
</div>
<p style="color:#666;font-size:13px;">
    This invoice has been disputed. Review and resolve the dispute or escalate.
</p>"""

    text, html = _render_notification(
        load,
        event_type="settlement_disputed",
        headline="Settlement Disputed",
        detail_html=detail,
        recommended="flag_review",
    )

    subject = f"[DISPATCH] DISPUTED — {load.get('customer', load['load_id'])}"
    msg = _build([reviewer_address()], subject, text, html=html)
    return _send_or_write(f"dispatch-disputed-{load['load_id']}", msg)


def notify_settlement_written_off(load: dict, settlement: dict, reason: str = "") -> str:
    esc = _html.escape
    invoice_num = settlement.get("invoice_number", "")
    invoice_amt = settlement.get("invoice_amount", 0)

    detail = f"""\
<div style="background:#fce4ec;border-left:4px solid #880e4f;padding:12px 16px;margin-bottom:16px;">
    <strong>Settlement Written Off</strong><br>
    Invoice #: <code>{esc(invoice_num)}</code><br>
    Amount: <strong>${invoice_amt:,.2f}</strong><br>
    {f'Reason: {esc(reason)}' if reason else ''}
</div>
<p style="color:#666;font-size:13px;">
    This invoice has been written off as uncollectible.
</p>"""

    text, html = _render_notification(
        load,
        event_type="settlement_written_off",
        headline="Settlement Written Off",
        detail_html=detail,
        recommended="acknowledge",
    )

    subject = f"[DISPATCH] WRITTEN OFF — {load.get('customer', load['load_id'])}"
    msg = _build([reviewer_address()], subject, text, html=html)
    return _send_or_write(f"dispatch-writeoff-{load['load_id']}", msg)


def notify_stalled(load: dict) -> str:
    """Send notification when a load has been stalled beyond its threshold."""
    esc = _html.escape
    hours = load.get("hours_in_status", 0)
    threshold = load.get("threshold_hours", 0)
    status = load.get("status", "unknown")

    detail = f"""\
<div style="background:#fff3e0;border-left:4px solid #e65100;padding:12px 16px;margin-bottom:16px;">
    <strong>Load Stalled</strong><br>
    Current Status: <strong>{esc(status.replace('_', ' ').title())}</strong><br>
    Time in Status: <strong style="color:#e65100;">{hours:.1f} hours</strong>
    (threshold: {threshold}h)<br>
    Driver: {esc(load.get('driver', '')) or 'Not assigned'}<br>
    Equipment: {esc(load.get('equipment', '')) or 'Not assigned'}
</div>
<p style="color:#666;font-size:13px;">
    This load has exceeded the expected time in its current status.
    Review and take action to keep it moving.
</p>"""

    text, html = _render_notification(
        load,
        event_type="stalled",
        headline=f"Load Stalled — {status.replace('_', ' ').title()} for {hours:.1f}h",
        detail_html=detail,
        recommended="flag_review",
    )

    subject = f"[DISPATCH] STALLED — {load.get('customer', load['load_id'])} ({hours:.0f}h in {status})"
    msg = _build([reviewer_address()], subject, text, html=html)
    return _send_or_write(f"dispatch-stalled-{load['load_id']}", msg)


# ── Email Template Preview ───────────────────────────────────────────

_SAMPLE_LOAD: dict = {
    "load_id": "LOAD-20260801-SAMPLE",
    "customer": "Acme Logistics",
    "broker_shipper": "National Freight Co",
    "status": "in_transit",
    "pickup_location": "Dallas, TX",
    "delivery_location": "Atlanta, GA",
    "driver": "John Smith",
    "equipment": "TRK-001 (Dry Van)",
    "pickup_datetime": "2026-08-01T08:00:00Z",
    "delivery_datetime": "2026-08-02T14:00:00Z",
}

EMAIL_TEMPLATES: dict[str, str] = {
    "dispatched": "Load Dispatched",
    "exception": "Exception Alert",
    "delivered": "Load Delivered",
    "pod_generated": "POD Package Generated",
    "archived": "Load Archived",
    "invoice_created": "Invoice Created",
    "payment_received": "Payment Received",
    "payment_overdue": "Payment Overdue",
    "stalled": "Load Stalled",
}


def preview_notification(template_key: str) -> dict | None:
    esc = _html.escape
    load = dict(_SAMPLE_LOAD)

    if template_key == "dispatched":
        detail = f"""\
<div style="background:#e8f5e9;border-left:4px solid #2e7d32;padding:12px 16px;margin-bottom:16px;">
    <strong>Load Dispatched</strong><br>
    Driver: {esc(load['driver'])}<br>
    Equipment: {esc(load['equipment'])}
</div>
<p style="color:#666;font-size:13px;">
    The load has been dispatched and is ready for pickup.
</p>"""
        text, html = _render_notification(load, "dispatched", "Load Dispatched", detail, "acknowledge")
        subject = f"[DISPATCH] Dispatched — {load['customer']}"

    elif template_key == "exception":
        detail = """\
<div style="background:#ffebee;border-left:4px solid #c62828;padding:12px 16px;margin-bottom:16px;">
    <strong style="color:#c62828;">Exception — Delay at Pickup</strong><br>
    Severity: <strong>high</strong><br>
    Driver reports mechanical issue at pickup facility.<br>
    <span style="font-size:12px;color:#888;">EXC-20260801-SAMPLE</span>
</div>
<p style="color:#666;font-size:13px;">
    An exception requires immediate attention.
</p>"""
        text, html = _render_notification(load, "exception", "Exception — Delay at Pickup", detail, "flag_review")
        subject = f"[DISPATCH] EXCEPTION — {load['customer']}"

    elif template_key == "delivered":
        detail = """\
<div style="background:#e8f5e9;border-left:4px solid #2e7d32;padding:12px 16px;margin-bottom:16px;">
    <strong>Delivery Confirmed</strong><br>
    Delivered at: 2026-08-02 14:30 UTC<br>
    Source: driver
</div>
<p style="color:#666;font-size:13px;">
    Load has been delivered. Generate POD and proceed to invoicing.
</p>"""
        load["status"] = "delivered"
        text, html = _render_notification(load, "delivered", "Load Delivered", detail, "acknowledge")
        subject = f"[DISPATCH] Delivered — {load['customer']}"

    elif template_key == "pod_generated":
        detail = """\
<div style="background:#e3f2fd;border-left:4px solid #1565c0;padding:12px 16px;margin-bottom:16px;">
    <strong>POD Package Generated</strong><br>
    Package ID: <code>POD-20260802-SAMPLE</code><br>
    BOL Included: Yes<br>
    Delivery Receipt: Yes<br>
    Photos: 2 attached
</div>
<p style="color:#666;font-size:13px;">
    Proof of delivery is ready for invoicing.
</p>"""
        load["status"] = "delivered"
        text, html = _render_notification(load, "pod_generated", "POD Package Ready", detail, "acknowledge")
        subject = f"[DISPATCH] POD Ready — {load['customer']}"

    elif template_key == "archived":
        detail = """\
<div style="background:#f3e5f5;border-left:4px solid #6a1b9a;padding:12px 16px;margin-bottom:16px;">
    <strong>Load Archived</strong><br>
    Archive ID: <code>RET-20260802-SAMPLE</code><br>
    Retention Period: 3 years<br>
    Archive Date: 2026-08-02
</div>
<p style="color:#666;font-size:13px;">
    Load has been archived per retention policy.
</p>"""
        load["status"] = "archived"
        text, html = _render_notification(load, "archived", "Load Archived", detail, "acknowledge")
        subject = f"[DISPATCH] Archived — {load['customer']}"

    elif template_key == "invoice_created":
        detail = """\
<div style="background:#e8f5e9;border-left:4px solid #1b5e20;padding:12px 16px;margin-bottom:16px;">
    <strong>Invoice Created</strong><br>
    Invoice: <code>INV-20260802-SAMPLE</code><br>
    Amount: <strong>$2,450.00</strong><br>
    Due Date: 2026-09-01<br>
    Payment Terms: Net 30
</div>
<p style="color:#666;font-size:13px;">
    Invoice has been generated and is ready for delivery.
</p>"""
        text, html = _render_notification(load, "invoice_created", "Invoice Created", detail, "acknowledge")
        subject = f"[DISPATCH] Invoice — {load['customer']}"

    elif template_key == "payment_received":
        detail = """\
<div style="background:#e8f5e9;border-left:4px solid #2e7d32;padding:12px 16px;margin-bottom:16px;">
    <strong>Payment Received</strong><br>
    Invoice: <code>INV-20260802-SAMPLE</code><br>
    Amount Paid: <strong>$2,450.00</strong><br>
    Method: ACH Transfer<br>
    Factoring Fee: $0.00<br>
    Net Payment: <strong>$2,450.00</strong>
</div>
<p style="color:#666;font-size:13px;">
    Payment has been received and recorded.
</p>"""
        text, html = _render_notification(load, "payment_received", "Payment Received", detail, "acknowledge")
        subject = f"[DISPATCH] Payment — {load['customer']}"

    elif template_key == "payment_overdue":
        detail = """\
<div style="background:#ffebee;border-left:4px solid #c62828;padding:12px 16px;margin-bottom:16px;">
    <strong style="color:#c62828;">Payment Overdue</strong><br>
    Invoice: <code>INV-20260802-SAMPLE</code><br>
    Amount Due: <strong>$2,450.00</strong><br>
    Due Date: 2026-07-01<br>
    Days Overdue: <strong style="color:#c62828;">32</strong>
</div>
<p style="color:#666;font-size:13px;">
    This invoice has exceeded its due date and requires follow-up.
</p>"""
        text, html = _render_notification(load, "payment_overdue", "Payment Overdue — 32 Days", detail, "flag_review")
        subject = f"[DISPATCH] OVERDUE — {load['customer']}"

    elif template_key == "stalled":
        load["status"] = "at_pickup"
        load["hours_in_status"] = 8.5
        load["threshold_hours"] = 4
        detail = f"""\
<div style="background:#fff3e0;border-left:4px solid #e65100;padding:12px 16px;margin-bottom:16px;">
    <strong>Load Stalled</strong><br>
    Current Status: <strong>At Pickup</strong><br>
    Time in Status: <strong style="color:#e65100;">8.5 hours</strong> (threshold: 4h)<br>
    Driver: {esc(load['driver'])}<br>
    Equipment: {esc(load['equipment'])}
</div>
<p style="color:#666;font-size:13px;">
    This load has exceeded the expected time in its current status.
</p>"""
        text, html = _render_notification(load, "stalled", "Load Stalled — At Pickup for 8.5h", detail, "flag_review")
        subject = f"[DISPATCH] STALLED — {load['customer']}"

    else:
        return None

    return {
        "key": template_key,
        "name": EMAIL_TEMPLATES.get(template_key, template_key),
        "subject": subject,
        "html": html,
        "text": text,
    }
