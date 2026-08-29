"""The scheduling boundary. Outlook is the single source of scheduling truth.

    Dispatch is not a calendar. Dispatch is not a scheduling database.
    The Calendar Display is a VIEW of Outlook, and ACCEPT LOAD asks Outlook
    to hold the time. Outlook answers.

This module is the Loading Dock for that: one port, two adapters, and no
pretending.

    OutlookCalendarAdapter    the real thing. Not wired in this repository -
                              Outlook is reached through JOE's read-only COM
                              adapter on the driver's machine, and Dispatch
                              has no such connection today. It reports itself
                              UNAVAILABLE rather than failing at the moment a
                              load is accepted.

    DemonstrationAdapter      a local, labelled stand-in so the portal stays
                              operable while the real connection is absent.
                              Everything it returns carries
                              `demonstration: True` and the word
                              DEMONSTRATION in its source, in every payload,
                              every time. It is not a mock hiding in
                              production - it announces itself on the screen.

WHY A DEMONSTRATION ADAPTER AND NOT A SILENT STUB
=================================================

A stub that returns plausible calendar entries is indistinguishable from a
working integration until the day it matters. The rule here is the one the
rest of this system already follows: SAMPLE DATA is labelled SAMPLE DATA, and
anything not connected says so in words. A driver must never look at this
screen and believe Outlook has his appointment when it does not.
"""

from __future__ import annotations

from datetime import datetime, timezone

STATUS_LIVE = "LIVE"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_DEMONSTRATION = "DEMONSTRATION"


class CalendarPort:
    """What Dispatch is allowed to ask a calendar. Deliberately small.

    Read the schedule, and ask for an appointment to be held. Dispatch may not
    delete, may not move somebody else's meeting, and may not become the
    record of when things happen - that is Outlook's job, and duplicating it
    here would create exactly the second source of truth the doctrine forbids.
    """

    name = "calendar"
    status = STATUS_UNAVAILABLE

    def probe(self) -> dict:
        raise NotImplementedError

    def upcoming(self, days: int = 14) -> dict:
        raise NotImplementedError

    def hold_appointment(self, mission: dict) -> dict:
        raise NotImplementedError


class OutlookCalendarAdapter(CalendarPort):
    """The real connection. Present as a boundary; not wired here.

    Outlook lives on the driver's machine and is reached through JOE's
    read-only COM adapter. Dispatch has no route to it in this repository, so
    every method reports unavailability in plain language instead of raising
    at the worst possible moment - the instant a load is accepted.
    """

    name = "outlook"

    BLOCKER = (
        "Outlook is not connected to Dispatch. Scheduling truth still lives "
        "in Outlook; Dispatch simply cannot read or write it from here yet."
    )

    def probe(self) -> dict:
        return {
            "name": self.name,
            "status": STATUS_UNAVAILABLE,
            "live": False,
            "demonstration": False,
            "blocker": self.BLOCKER,
        }

    def upcoming(self, days: int = 14) -> dict:
        return {
            "ok": False,
            "source": "Outlook (not connected)",
            "status": STATUS_UNAVAILABLE,
            "demonstration": False,
            "entries": [],
            "blocker": self.BLOCKER,
        }

    def hold_appointment(self, mission: dict) -> dict:
        return {
            "ok": False,
            "held": False,
            "status": STATUS_UNAVAILABLE,
            "demonstration": False,
            "blocker": self.BLOCKER,
            "note": (
                "The mission was accepted. The calendar entry was NOT created, "
                "because Dispatch cannot reach Outlook. Put it in your calendar "
                "yourself."
            ),
        }


class DemonstrationAdapter(CalendarPort):
    """A labelled local stand-in. Never mistaken for the real thing.

    It derives its entries from the mission records that actually exist, so
    the portal shows something coherent - but every payload says
    DEMONSTRATION, and `demonstration` is True on every one.
    """

    name = "demonstration"
    status = STATUS_DEMONSTRATION

    LABEL = "DEMONSTRATION - not Outlook, not a real appointment"

    def probe(self) -> dict:
        return {
            "name": self.name,
            "status": STATUS_DEMONSTRATION,
            "live": False,
            "demonstration": True,
            "blocker": self.LABEL,
        }

    def upcoming(self, days: int = 14) -> dict:
        entries = []
        try:
            from portal.models import sandbox
            from dispatch import mission as mission_svc

            for record in sandbox.get_all().values():
                if not mission_svc.is_mission(record):
                    continue
                card = record.get("card_data") or {}
                for label, window in (("Pickup", card.get("pickup_window")),
                                      ("Delivery", card.get("delivery_window"))):
                    if not window:
                        continue
                    entries.append({
                        "subject": "%s — %s (Mission %s)" % (
                            label,
                            card.get("origin" if label == "Pickup"
                                     else "destination", ""),
                            record.get("mission_number", "?"),
                        ),
                        "when": window,
                        "record_id": record.get("id"),
                        "demonstration": True,
                    })
        except Exception:  # noqa: BLE001 - a demo must never break the portal
            entries = []
        return {
            "ok": True,
            "source": self.LABEL,
            "status": STATUS_DEMONSTRATION,
            "demonstration": True,
            "entries": entries,
            "blocker": self.LABEL,
        }

    def hold_appointment(self, mission: dict) -> dict:
        return {
            "ok": True,
            "held": False,
            "status": STATUS_DEMONSTRATION,
            "demonstration": True,
            "blocker": self.LABEL,
            "note": (
                "DEMONSTRATION ONLY. No appointment was created anywhere. "
                "Outlook does not know about this mission."
            ),
            "would_create": {
                "subject": "Mission %s — %s to %s" % (
                    mission.get("mission_number", "?"),
                    mission.get("pickup_location", ""),
                    mission.get("delivery_location", ""),
                ),
                "pickup": mission.get("pickup_window", ""),
                "delivery": mission.get("delivery_window", ""),
            },
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }


def get_adapter(prefer_real: bool = True) -> CalendarPort:
    """The calendar Dispatch will actually talk to.

    Real first. It reports UNAVAILABLE honestly, and the demonstration adapter
    is used only where a working screen matters more than a working
    integration - never silently, because both label themselves.
    """
    real = OutlookCalendarAdapter()
    if prefer_real and real.probe().get("live"):
        return real
    return DemonstrationAdapter()


def on_accept_load(mission: dict, adapter: CalendarPort | None = None) -> dict:
    """Ask the calendar to hold the time, at the moment of commitment.

    Called by ACCEPT LOAD. Its answer is reported to the driver as given -
    including "I could not, do it yourself" - because a mission that quietly
    failed to reach the calendar is how an appointment gets missed.
    """
    adapter = adapter or get_adapter()
    return adapter.hold_appointment(mission)
