"""Routing Dispatch's mail through the transport port, without crossing a boundary.

`cin_lite/email_delivery._send_or_write()` is the one function every outbound
message in this program passes through. It speaks SMTP with a username and a
password, which is the mechanism Microsoft 365 disables by default on every
tenant.

cin_lite must not import dispatch -- the dependency points one way, and THE MIKE
RULE keeps subsystems liftable. So this module registers *into* cin_lite rather
than cin_lite reaching out: `install()` hands it a callable, and with nothing
installed every existing path behaves byte for byte as it did.

**Only the genuinely new transports are installed.** When the selected transport
is `smtp_basic` or the `.eml` outbox, this stays out of the way entirely and
`_send_or_write` runs its own code -- same receipt strings, same fallback file,
same behaviour a working install already depends on. The hook engages only for
Graph and XOAUTH2, which had no path at all before.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage

from dispatch.observability import event, get_logger
from dispatch.transport import OutboundMessage, select_transport
from dispatch.transport.contract import TransportError

log = get_logger("dispatch.outbound")

#: The transports that did not previously exist. Everything else keeps the
#: original code path, because replacing a working install's send function with
#: an equivalent one is risk with no benefit.
NEW_TRANSPORTS = ("graph", "smtp_oauth2")


def _addresses(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def to_outbound(msg: EmailMessage, *, subject_ref: str = "") -> OutboundMessage:
    """An EmailMessage as the port's own type.

    Graph takes JSON, not MIME, so the port cannot speak MIME -- and going
    through a neutral shape is what lets the same message reach either.
    """
    text = ""
    html = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not text:
                text = part.get_content()
            elif part.get_content_type() == "text/html" and not html:
                html = part.get_content()
    else:
        text = msg.get_content()

    return OutboundMessage(
        to=_addresses(msg.get("To")),
        cc=_addresses(msg.get("Cc")),
        subject=msg.get("Subject", ""),
        body_text=text,
        body_html=html,
        reply_to=msg.get("Reply-To", "") or "",
        from_address=msg.get("From", "") or "",
        subject_ref=subject_ref,
    )


def _sender(fallback_id: str, msg: EmailMessage) -> str:
    """The callable cin_lite calls. Returns a receipt; never raises.

    A failure here falls back to the .eml file and returns the same
    "delivery failed (...); written to ..." shape the SMTP path returns, because
    `dispatch.delivery` classifies receipts by that shape and a new transport
    must not need it to learn a second one.
    """
    transport = select_transport()
    try:
        result = transport.send(to_outbound(msg))
    except TransportError as exc:
        from cin_lite.email_delivery import _write_fallback

        path = _write_fallback(fallback_id, msg)
        event(
            log, logging.WARNING, "transport send failed",
            transport=transport.transport_id, error=str(exc)[:200], fallback=str(path),
        )
        return f"delivery failed ({exc}); written to {path}"
    return result.receipt


def install(*, force: bool = False) -> str | None:
    """Register the transport if this machine is configured for a new one.

    Returns the transport id that was installed, or None. Idempotent.
    """
    from cin_lite import email_delivery

    transport = select_transport()
    if not force and transport.transport_id not in NEW_TRANSPORTS:
        email_delivery.clear_transport()
        return None
    email_delivery.set_transport(_sender)
    event(log, logging.INFO, "outbound transport installed", transport=transport.transport_id)
    return transport.transport_id


def uninstall() -> None:
    from cin_lite import email_delivery

    email_delivery.clear_transport()
