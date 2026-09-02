"""What Dispatch can reach, asked fresh rather than remembered.

Outlook can be running now and closed in ten minutes. A connector status
cached at import time is a status that will eventually be wrong at the moment
it matters -- the instant a driver presses ARRIVE -- so this probes on demand
and never caches a LIVE.
"""

from __future__ import annotations

STATUS_LIVE = "LIVE"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_UNCONFIGURED = "UNCONFIGURED"


def mail():
    """The outbound mail connector, or None when there is none on this build."""
    try:
        from dispatch.connectors.outlook_mail import OutlookMailAdapter
    except Exception:  # noqa: BLE001 - an absent connector is not an error
        return None
    return OutlookMailAdapter()


def mail_status() -> str:
    """Whether mail can actually leave this machine right now.

    Probed, never assumed. Reported in the fixed vocabulary and translated
    into the driver's language on its way to the glass.
    """
    adapter = mail()
    if adapter is None:
        return STATUS_UNCONFIGURED
    try:
        probe = adapter.probe()
    except Exception:  # noqa: BLE001
        return STATUS_UNAVAILABLE
    if not probe.get("live"):
        return STATUS_UNAVAILABLE
    # Reachable, but unable to send from the operations mailbox. Not LIVE:
    # a broker receiving arrival evidence from a personal address has been
    # given a reason to wonder who he is dealing with.
    if not probe.get("sends_from"):
        return STATUS_UNAVAILABLE
    return STATUS_LIVE


def calendar_status() -> str:
    """Whether Outlook's calendar is reachable right now."""
    try:
        from dispatch import scheduling
    except Exception:  # noqa: BLE001
        return STATUS_UNCONFIGURED
    try:
        return scheduling.OutlookCalendarAdapter().probe().get(
            "status", STATUS_UNAVAILABLE)
    except Exception:  # noqa: BLE001
        return STATUS_UNAVAILABLE


def status() -> dict:
    """Everything, for a status panel that is read rather than guessed at."""
    return {"mail": mail_status(), "calendar": calendar_status()}
