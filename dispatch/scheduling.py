"""The scheduling boundary. Outlook is the single source of scheduling truth.

    Dispatch is not a calendar. Dispatch is not a scheduling database.
    The Calendar Display is a VIEW of Outlook, and ACCEPT LOAD asks Outlook
    to hold the time. Outlook answers.

This module is the Loading Dock for that: one port, two adapters, and no
pretending.

    OutlookCalendarAdapter    the real thing, over Outlook's COM interface
                              on this machine. Reads are read-only; writes are
                              additive and never delete or move anything
                              already in the calendar. When Outlook is not
                              answering it reports itself UNAVAILABLE rather
                              than failing at the moment a load is accepted.

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

from datetime import datetime, timedelta, timezone

STATUS_LIVE = "LIVE"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_DEMONSTRATION = "DEMONSTRATION"


def _outlook_is_running() -> bool:
    """Whether Outlook is open right now.

    Checked before any COM call. Attaching to a running Outlook is instant;
    asking COM to start one produces a headless instance that wedges every
    call after it, and a hang on a driver's screen is worse than an error he
    can act on.

    GetActiveObject would be the obvious way to attach-only and does not work:
    Outlook does not reliably register in the running-object table, so it
    reports unavailable while Outlook sits open on the screen.
    """
    try:
        import subprocess

        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq OUTLOOK.EXE", "/NH"],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return "OUTLOOK.EXE" in (result.stdout or "").upper()
    except Exception:  # noqa: BLE001 - a failed check means do not attempt COM
        return False


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
    """The real connection, over Outlook's COM interface on this machine.

    Outlook is the single source of scheduling truth. This adapter reads it and
    asks it to hold time; it never becomes a second record of when things
    happen, because that is the one thing the doctrine forbids.

    **Reads are read-only and writes are additive.** It creates appointments and
    it does not delete, move or modify anything already there -- a scheduling
    integration that can quietly remove a meeting is not one worth having on a
    machine that also holds a man's own diary.

    When Outlook is not reachable -- not installed, not running, COM refused --
    it says so and returns nothing, rather than raising at the instant a load is
    accepted.
    """

    name = "outlook"

    #: Outlook's own constant for the default calendar folder.
    _CALENDAR_FOLDER = 9

    BLOCKER = (
        "Outlook is not answering on this machine. Scheduling truth still "
        "lives in Outlook; Dispatch cannot read or write it right now."
    )

    NOT_RUNNING = (
        "Outlook is not open on this machine. Dispatch reads the calendar "
        "from Outlook and can only do that while Outlook is running."
    )

    def _session(self):
        """A COM connection on this thread, or None and the reason.

        Flask serves on worker threads and COM is per-thread, so this
        initialises each time rather than holding a handle open -- a connection
        cached from another thread fails in ways that look like Outlook being
        broken.
        """
        try:
            import pythoncom
            import win32com.client
        except ImportError:
            return None, "The Outlook connection is not installed on this machine."

        if not _outlook_is_running():
            return None, self.NOT_RUNNING

        try:
            pythoncom.CoInitialize()
            app = win32com.client.Dispatch("Outlook.Application")
            return app.GetNamespace("MAPI"), ""
        except Exception:  # noqa: BLE001 - COM raises many shapes
            return None, self.NOT_RUNNING

    def _release(self):
        try:
            import pythoncom

            pythoncom.CoUninitialize()
        except Exception:  # noqa: BLE001 - releasing must never raise
            pass

    def probe(self) -> dict:
        namespace, blocker = self._session()
        if namespace is None:
            return {"name": self.name, "status": STATUS_UNAVAILABLE,
                    "live": False, "demonstration": False, "blocker": blocker}
        try:
            folder = namespace.GetDefaultFolder(self._CALENDAR_FOLDER)
            return {"name": self.name, "status": STATUS_LIVE, "live": True,
                    "demonstration": False, "blocker": "",
                    "folder": str(folder.Name)}
        except Exception as exc:  # noqa: BLE001
            return {"name": self.name, "status": STATUS_UNAVAILABLE,
                    "live": False, "demonstration": False,
                    "blocker": "%s (%s)" % (self.BLOCKER, type(exc).__name__)}
        finally:
            self._release()

    def upcoming(self, days: int = 14) -> dict:
        """What Outlook holds between now and `days` out. Read only."""
        namespace, blocker = self._session()
        if namespace is None:
            return {"ok": False, "source": "Outlook (not connected)",
                    "status": STATUS_UNAVAILABLE, "demonstration": False,
                    "entries": [], "blocker": blocker}

        try:
            start = datetime.now()
            finish = start + timedelta(days=int(days))
            items = namespace.GetDefaultFolder(self._CALENDAR_FOLDER).Items
            # Both, and in this order. A recurring appointment is not expanded
            # into its occurrences unless the collection is sorted by start
            # first, and an unexpanded series simply does not appear.
            items.IncludeRecurrences = True
            items.Sort("[Start]")
            items = items.Restrict(
                "[Start] >= '%s' AND [Start] <= '%s'"
                % (start.strftime("%m/%d/%Y %I:%M %p"),
                   finish.strftime("%m/%d/%Y %I:%M %p")))

            entries = []
            for item in items:
                try:
                    entries.append({
                        "subject": str(item.Subject or ""),
                        "when": str(item.Start),
                        "start": str(item.Start),
                        "end": str(item.End),
                        "location": str(item.Location or ""),
                        "all_day": bool(item.AllDayEvent),
                        "demonstration": False,
                    })
                except Exception:  # noqa: BLE001 - one bad item is not a failure
                    continue

            return {"ok": True, "source": "Outlook", "status": STATUS_LIVE,
                    "demonstration": False, "entries": entries, "blocker": ""}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "source": "Outlook", "status": STATUS_UNAVAILABLE,
                    "demonstration": False, "entries": [],
                    "blocker": "%s (%s)" % (self.BLOCKER, type(exc).__name__)}
        finally:
            self._release()

    def hold_appointment(self, mission: dict) -> dict:
        """Ask Outlook to hold the time, at the moment of commitment.

        Additive only: it creates an appointment and touches nothing already
        there. If it cannot, it says so and tells the driver to put it in
        himself -- a mission that quietly failed to reach the calendar is how an
        appointment gets missed.
        """
        namespace, blocker = self._session()
        if namespace is None:
            return {"ok": False, "held": False, "status": STATUS_UNAVAILABLE,
                    "demonstration": False, "blocker": blocker,
                    "note": ("The mission was accepted. The calendar entry was "
                             "NOT created. Put it in your calendar yourself.")}

        try:
            import win32com.client

            subject = "Mission %s - %s to %s" % (
                mission.get("mission_number", "?"),
                mission.get("pickup_location", ""),
                mission.get("delivery_location", ""))

            appointment = win32com.client.Dispatch(
                "Outlook.Application").CreateItem(1)  # olAppointmentItem
            appointment.Subject = subject
            appointment.Location = str(mission.get("pickup_location") or "")
            appointment.Body = _appointment_body(mission)
            starts = _parse_when(mission.get("pickup_window"))
            if starts:
                # As a formatted string, never a datetime object. A naive
                # datetime is handed to Outlook as UTC and comes back shifted
                # by the local offset: a 06:00 gate time in Savannah was
                # landing in the calendar at 10:00, four hours after the truck
                # was supposed to be there. A string is interpreted in local
                # time, which is the time the driver was told.
                appointment.Start = starts.strftime("%m/%d/%Y %I:%M %p")
                appointment.Duration = 60
            else:
                appointment.AllDayEvent = True
            appointment.ReminderSet = True
            appointment.ReminderMinutesBeforeStart = 120
            appointment.Save()

            return {"ok": True, "held": True, "status": STATUS_LIVE,
                    "demonstration": False, "blocker": "", "subject": subject,
                    "note": "Outlook is holding the time.",
                    "requested_at": datetime.now(timezone.utc).isoformat()}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "held": False, "status": STATUS_UNAVAILABLE,
                    "demonstration": False,
                    "blocker": "%s (%s)" % (self.BLOCKER, type(exc).__name__),
                    "note": ("The mission was accepted. The calendar entry was "
                             "NOT created. Put it in your calendar yourself.")}
        finally:
            self._release()


def _appointment_body(mission: dict) -> str:
    """What the entry says when he opens it on a phone."""
    lines = []
    for label, key in (("Load", "load_number"), ("Customer", "customer"),
                       ("Pickup", "pickup_location"),
                       ("Delivery", "delivery_location"),
                       ("Cargo", "commodity")):
        value = str(mission.get(key) or "").strip()
        if value:
            lines.append("%s: %s" % (label, value))
    return chr(10).join(lines)


def _parse_when(window):
    """A start time out of whatever the record carries, or None.

    Deliberately narrow. An appointment placed at a guessed time is worse than
    an all-day block saying the day is spoken for.
    """
    text = str(window or "").strip()
    if not text:
        return None
    text = text.split("(")[0].strip().split(" - ")[0].strip()
    for shape in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, shape)
        except ValueError:
            continue
    return None


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
