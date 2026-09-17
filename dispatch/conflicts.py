"""What Booking has to say about a commitment, and never decides.

**BOOKING CONFLICT PREVENTION DOCTRINE, Mike Zachary, 2026-09-16:**

    LEVEL 1 - Position Conflict
        "Truck physically unlikely to be where the next commitment requires."
    LEVEL 2 - Time Conflict
        "Two commitments overlap or create an impossible sequence."
    LEVEL 3 - HOS Awareness
        "Route duration and commitments suggest an unusually long duty day."

    RULE
        "Display warning only. Do not block. Do not reserve capacity.
         Do not reject commitment. Human authority remains final."

**They are types, not severities.** One display rule for all three -- pale red,
black text, no modal, no response required, no buttons. Nothing in the doctrine
asks for three colours or a ranking, and inventing one would be an engineer
grading the Owner's freight.

**Nothing here writes, holds or refuses.** Booking exists to *protect* him from
creating a conflict, not to prevent him from choosing one: *"Dispatch does not
decide: when Mike works, when Mike rests ... Human authority remains final."*
Every day begins OPEN and stays OPEN; a warning is a sentence on a screen.

LEVEL 3, AND THE CLAUSE IT LOOKED LIKE IT BROKE
===============================================

An engineer read *"route duration"* as something to compute from a route, which
`load_assessment.py:225` forbids outright -- *"this system does not need to
track drive times for nay reason."* The Owner settled it on 2026-09-16:

    "this is an advisory warning base on prior day destination and the
     beginning time for the proposed next start. if less than 12 hours a
     warning should go out. example: return back to Jacksonville at 11pm and
     next proposed load is 4am there is not enough time for 10hr break"

So it is **the gap between two times already typed on two records** -- no route,
no drive time, nothing computed about how long anything takes. Twelve rather
than ten because the break is ten and fuelling, paperwork, a shower and getting
to the shipper are not part of it. The margin is his.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from dispatch import booking, commitment

POSITION = "Position Conflict"
TIME = "Time Conflict"
HOS = "HOS Awareness"

#: Hours that must sit between a delivery and the next pickup. His number, and
#: his reason: the ten-hour break is not the whole of what has to fit.
HOS_GAP_HOURS = 12

#: Miles beyond which the truck is unlikely to make the next pickup from where
#: this one leaves it. A repositioning distance, not a drive-time judgement --
#: the doctrine says *"physically unlikely"*, which is a distance question.
POSITION_MILES = 400


def _moment(window: str):
    """A date and time out of a window string, or None.

    Deliberately narrow, like `booking._as_date`. A warning raised on a guessed
    parse is worse than no warning: it teaches him to ignore the line.
    """
    text = str(window or "").strip()
    if not text:
        return None
    for shape in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S",
                  "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:len(shape) + 2].strip(), shape)
        except ValueError:
            continue
    return None


def _place(record: dict, end: str) -> str:
    card = (record or {}).get("card_data") or {}
    return str((record or {}).get("%s_location" % end)
               or card.get("destination" if end == "delivery" else "origin")
               or "").strip()


def _committed(records, *, excluding: str = "") -> list:
    out = []
    for record in booking._iter(records):
        if str(record.get("id") or "") == excluding:
            continue
        if commitment.is_committed(record):
            out.append(record)
    return out


def check(card: dict, records=None) -> list:
    """Every warning this commitment raises against what is already committed.

    Returns a list of `{"level", "line"}`. **Empty is the normal answer.**
    Nothing is written, nothing is reserved, and the caller is free to ignore
    all of it -- which is the doctrine, not a shortcut.
    """
    card = dict(card or {})
    others = _committed(records, excluding=str(card.get("id") or ""))
    found = []

    found += _time_conflicts(card, others)
    found += _hos_gaps(card, others)
    found += _position_conflicts(card, others)
    return found


def _time_conflicts(card: dict, others: list) -> list:
    """*"Two commitments overlap or create an impossible sequence."*

    Computable from what is already stored: `span_of` gives every day a load
    occupies, and two spans that intersect are an overlap. The truck is not
    sellable on a day it is driving somebody else's freight.
    """
    mine = set(booking.span_of(card))
    if not mine:
        return []
    out = []
    for other in others:
        shared = mine & set(booking.span_of(other))
        if not shared:
            continue
        day = min(shared)
        out.append({
            "level": TIME,
            "line": "%s is already committed to %s." % (
                day.strftime("%a %d %b"), _name(other)),
        })
    return out


def _hos_gaps(card: dict, others: list) -> list:
    """*"if less than 12 hours a warning should go out."*

    The hours between a delivery already agreed and the pickup being agreed
    now. Both times were typed by the man who agreed them; nothing is computed
    about how long the driving takes, which the 2026-09-15 ruling forbids.
    """
    start = _moment(booking.windows_of(card)[0])
    if not start:
        return []
    out = []
    for other in others:
        ended = _moment(booking.windows_of(other)[1])
        if not ended or ended >= start:
            continue
        gap = start - ended
        if gap >= timedelta(hours=HOS_GAP_HOURS):
            continue
        hours = gap.total_seconds() / 3600.0
        out.append({
            "level": HOS,
            "line": ("%.0f hours between delivering %s and picking this up. "
                     "A 10-hour break does not fit." % (hours, _name(other))),
        })
    return out


def _position_conflicts(card: dict, others: list) -> list:
    """*"Truck physically unlikely to be where the next commitment requires."*

    Where the truck is left by the commitment before this one, against where
    this one starts. Miles only -- `dispatch/distance.py` answers it and the
    basis is always said, so a number he cannot check is never shown as fact.
    """
    start = _moment(booking.windows_of(card)[0])
    origin = _place(card, "pickup")
    if not start or not origin:
        return []

    previous, ended_at = None, None
    for other in others:
        ends = _moment(booking.windows_of(other)[1])
        if not ends or ends >= start:
            continue
        if ended_at is None or ends > ended_at:
            previous, ended_at = other, ends
    if previous is None:
        return []

    left_at = _place(previous, "delivery")
    if not left_at:
        return []

    from dispatch import distance

    answer = distance.miles_between(left_at, origin)
    miles = answer.get("miles") or 0
    if not miles or miles < POSITION_MILES:
        return []
    return [{
        "level": POSITION,
        # The basis, always. A mileage he cannot check is not evidence.
        "line": "%s miles from %s, where %s leaves the truck (%s)." % (
            int(miles), origin, _name(previous), answer.get("basis") or "estimate"),
    }]


def _name(record: dict) -> str:
    """What to call the other commitment on a warning line. His number if it
    has one: the load number is the thing he recognises."""
    numbers = (record or {}).get("numbers") or {}
    return str(numbers.get("load_label")
               or (record or {}).get("load_number")
               or (record or {}).get("title")
               or "another commitment")
