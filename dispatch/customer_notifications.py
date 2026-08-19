"""Customer/broker-facing email transport boundary.

Every existing function in dispatch/notifications.py sends to the internal
reviewer only (confirmed directly, all 11 notify_* functions, during the
deployment-hardening audit). Nothing in this codebase sends to a broker or
customer today. This module is the transport boundary for that gap --
and only the boundary.

It deliberately does NOT:
    - decide what triggers a customer email (which milestone, whether
      archiving a load should auto-send one, etc.)
    - decide what the email should say (subject/body are the caller's
      responsibility -- e.g. a future Publisher-assembled message)
    - resolve a recipient address from the Load record, because there
      isn't one to resolve: dispatch/models.py's Load dataclass has no
      broker_email/customer_email field (confirmed by inspection -- only
      `customer` and `broker_shipper`, both plain name strings). Callers
      must supply the address explicitly.

Those are exactly the kind of business-rule and schema decisions this
hardening pass is not authorized to invent -- see the deployment decision
register for the open questions this boundary exists to eventually answer.

Transport itself reuses the same proven degrade-to-local-file pattern as
every other email in this codebase (cin_lite.email_delivery._send_or_write):
if DISPATCH_SMTP_HOST isn't configured, or the send fails, the message is
written to Archive/Outbox instead of being lost, and the pipeline never
blocks on it.
"""

from __future__ import annotations

from dispatch.email_delivery import _build, _send_or_write


def notify_customer(to_address: str, subject: str, body: str, fallback_id: str) -> str:
    """Send a customer/broker-facing email, or write it to the local
    Outbox if SMTP isn't configured or the send fails. Never raises.

    Args:
        to_address: recipient email. Not resolved automatically -- see
            module docstring for why.
        subject, body: fully assembled by the caller. This function makes
            no decisions about content.
        fallback_id: a stable id used for the .eml filename if the send
            falls back to writing locally (matches the convention used by
            every other notify_* function in this codebase).
    """
    if not to_address:
        raise ValueError("notify_customer requires an explicit to_address")
    msg = _build([to_address], subject, body)
    return _send_or_write(fallback_id, msg)
