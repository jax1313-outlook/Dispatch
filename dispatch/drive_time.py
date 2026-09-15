"""The earliest a load can legally be delivered, from pickup time, miles and breaks.

CO-3/CO-4, 2026-09-14. The Owner's must-have: *"Assistance with pickup and
delivery times."* A listing that picks up at 06:00 and delivers 700 miles away
by 14:00 the same day is a load nobody can run legally, and the board will not
say so.

WHAT THIS IS
============

**A planning estimate, never an hours-of-service reading.** Dispatch is not an
ELD and holds no duty-clock data (`dispatch/scoring.py::compute_hos_risk` says
the same). It assumes the driver is loaded and rolling at the pickup time on a
fresh clock -- the most generous case -- so when it says a delivery cannot be
made, it cannot be made. When it says one can, the ELD is still the authority.

THE RULES IT APPLIES, and where they already live:

    30-minute break after 8 hours driving   dispatch.capacity.BREAK_TRIGGER_DRIVE_HOURS
                                            / REQUIRED_BREAK_HOURS
    11 hours driving per shift              dispatch.capacity.TimeCapacity.drive_limit_hours
    14-hour duty window per shift           dispatch.capacity.TimeCapacity.duty_limit_hours
    10 hours off before the next shift      OFF_DUTY_RESET_HOURS, below -- the one figure
                                            the capacity engine did not already carry
    planning speed                          dispatch.scoring._DRIVE_SPEED_MPH

Pure and deterministic: no clock, no database.
"""

from __future__ import annotations

import dataclasses
import re
from datetime import datetime, time, timedelta

from dispatch import capacity
from dispatch.scoring import _DRIVE_SPEED_MPH

#: Federal property-carrying rule: ten consecutive hours off duty before a new
#: 11-hour / 14-hour shift. Not held anywhere else in Dispatch.
OFF_DUTY_RESET_HOURS = 10.0

_TIME_FIELDS = {f.name: f.default for f in dataclasses.fields(capacity.TimeCapacity)}
DRIVE_LIMIT_HOURS = float(_TIME_FIELDS["drive_limit_hours"])
DUTY_LIMIT_HOURS = float(_TIME_FIELDS["duty_limit_hours"])
BREAK_TRIGGER_HOURS = capacity.BREAK_TRIGGER_DRIVE_HOURS
BREAK_HOURS = capacity.REQUIRED_BREAK_HOURS

ASSUMPTION = ("Estimate: rolling at the pickup time on a fresh clock, at %d mph. "
              "Not an ELD reading." % _DRIVE_SPEED_MPH)


def earliest_arrival(start: datetime, miles: float, *, mph: float = _DRIVE_SPEED_MPH) -> dict:
    """When the truck can arrive, legally, leaving at `start`.

    Returns `{"arrive", "drive_hours", "breaks", "resets"}`.
    """
    remaining = max(float(miles or 0), 0.0) / float(mph)
    drive_hours = remaining
    clock = start
    shift_start = start
    shift_drive = since_break = 0.0
    breaks = resets = 0
    guard = 0
    while remaining > 1e-9 and guard < 1000:
        guard += 1
        duty_left = DUTY_LIMIT_HOURS - (clock - shift_start).total_seconds() / 3600.0
        drive_left = DRIVE_LIMIT_HOURS - shift_drive
        until_break = BREAK_TRIGGER_HOURS - since_break
        if drive_left <= 1e-9 or duty_left <= 1e-9:
            clock += timedelta(hours=OFF_DUTY_RESET_HOURS)
            shift_start = clock
            shift_drive = since_break = 0.0
            resets += 1
            continue
        if until_break <= 1e-9:
            clock += timedelta(hours=BREAK_HOURS)
            since_break = 0.0
            breaks += 1
            continue
        chunk = min(remaining, drive_left, until_break, duty_left)
        clock += timedelta(hours=chunk)
        remaining -= chunk
        shift_drive += chunk
        since_break += chunk
    return {"arrive": clock, "drive_hours": round(drive_hours, 2),
            "breaks": breaks, "resets": resets}


def _clock_of(text: str):
    match = re.search(r"\b(\d{1,2}):(\d{2})\b", text or "")
    if not match or int(match.group(1)) > 23:
        return None
    return time(int(match.group(1)), int(match.group(2)))


def window_start(window: str):
    """The start of a window as a datetime, or None when no date and time are both there."""
    from dispatch import booking

    on = booking._as_date(window)
    if on is None:
        return None
    at = _clock_of(str(window).split(" - ")[0])
    return datetime.combine(on, at) if at else None


def window_deadline(window: str):
    """The latest a window allows: its end time, its only time, or the end of its day."""
    from dispatch import booking

    text = str(window or "")
    on = booking._as_date(text)
    if on is None:
        return None
    parts = text.split(" - ")
    at = _clock_of(parts[1]) if len(parts) == 2 else None
    at = at or _clock_of(parts[0])
    return datetime.combine(on, at or time(23, 59))


def delivery_check(pickup_window: str, delivery_window: str, miles) -> dict:
    """Can the delivery appointment be made from the pickup time? CO-4.3.

    Returns `{"known", "earliest", "deadline", "can_make", "line", "assumption", ...}`.
    `can_make` is None whenever a fact is missing -- pickup time, miles, or the
    delivery date -- and `line` says which.
    """
    start = window_start(pickup_window)
    deadline = window_deadline(delivery_window)
    try:
        miles = float(miles) if miles not in (None, "") else None
    except (TypeError, ValueError):
        miles = None

    if start is None or not miles:
        missing = [name for name, gone in (("a pickup date and time", start is None),
                                           ("miles", not miles)) if gone]
        return {"known": False, "earliest": None, "deadline": deadline, "can_make": None,
                "line": "Delivery timing not worked out: needs %s." % " and ".join(missing),
                "assumption": ASSUMPTION}

    trip = earliest_arrival(start, miles)
    earliest = trip["arrive"]
    parts = ["%.1f h driving" % trip["drive_hours"]]
    if trip["breaks"]:
        parts.append("%d break%s" % (trip["breaks"], "" if trip["breaks"] == 1 else "s"))
    if trip["resets"]:
        parts.append("%d overnight 10 h reset%s" % (trip["resets"], "" if trip["resets"] == 1 else "s"))
    line = "Earliest legal delivery %s (%s)." % (earliest.strftime("%a %d %b %H:%M"),
                                               ", ".join(parts))
    can_make = None if deadline is None else earliest <= deadline
    if can_make is False:
        line += " The delivery appointment %s cannot be made." % deadline.strftime("%a %d %b %H:%M")
    return {"known": True, "earliest": earliest, "deadline": deadline, "can_make": can_make,
            "line": line, "assumption": ASSUMPTION, **trip}
