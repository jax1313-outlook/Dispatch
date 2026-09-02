"""Booking: the forward view of the truck.

    How far out am I covered, and what is still sellable?

A verb, not a noun. It is the thing being done -- booking out two weeks -- and
not a record kept about it.

THE WEEK IS A BUSINESS MODEL, NOT A CALENDAR
============================================

    MON TUE WED     sellable
    THU FRI         held for high-value expedited
    SAT             maintenance
    SUN             closed

That pattern is **policy**: it is true every week regardless of what is on it,
so it lives here as four lines rather than as fourteen stored days. Dispatch is
not a calendar and must not become one -- Outlook is the single source of
scheduling truth, and a stored day-state would be exactly the second calendar
that doctrine forbids.

What is actually booked is read, never stored. Pattern plus commitments equals
the view, and there is nothing to keep in sync because nothing is kept.

THURSDAY AND FRIDAY ARE NOT EMPTY
=================================

They are unsold on purpose. Capacity held for expedited freight is a position,
and a screen that draws it as a gap is telling the operator he has a problem
where he has a strategy. Saturday maintenance is the same: a decision, not an
absence.

**Open Monday to Wednesday days are the number that matters.** They are the
unsold inventory, and they expire worthless. Thursday empty is success;
Monday empty in four days is not.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

#: How far out the operator books. Two weeks is the horizon he works to.
HORIZON_DAYS = 14

#: What a day is for. One state per day, resolved -- never stored.
BOOKED = "BOOKED"
OPEN = "OPEN"
HELD = "HELD"
MAINTENANCE = "MAINTENANCE"
CLOSED = "CLOSED"

#: The week, by weekday number (Monday is 0). Change the business model here
#: and the whole view follows; there is no migration because there is no data.
#:
#: Maintenance is Saturday only. Thursday and Friday are both held, on the
#: operator's ruling: Friday afternoon is prime expedited freight -- the
#: weekend deadline is what makes shippers pay premium -- and giving it up to
#: maintenance would cost the best-paying loads of the week.
WEEK_PATTERN = {
    0: OPEN,          # Monday
    1: OPEN,          # Tuesday
    2: OPEN,          # Wednesday
    3: HELD,          # Thursday
    4: HELD,          # Friday
    5: MAINTENANCE,   # Saturday
    6: CLOSED,        # Sunday
}

#: Days whose whole purpose is being available. Empty is the point.
SELLABLE = (OPEN,)

LABELS = {
    BOOKED: "BOOKED",
    OPEN: "OPEN",
    HELD: "HELD",
    MAINTENANCE: "MAINT",
    CLOSED: "CLOSED",
}

SUBTITLES = {
    OPEN: "Unsold",
    HELD: "Expedited capacity",
    MAINTENANCE: "Maintenance",
    CLOSED: "Closed",
    BOOKED: "",
}


def pattern_for(day: date) -> str:
    return WEEK_PATTERN.get(day.weekday(), OPEN)


def _as_date(value):
    """A date out of whatever a record or Outlook carries, or None.

    Deliberately narrow. A day placed by a guessed parse is worse than a day
    left out: the whole screen answers how far out he is covered.
    """
    text = str(value or "").strip()
    if not text:
        return None
    text = text.split("(")[0].strip()
    head = text.split(" - ")[0].strip()
    for shape in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%m/%d/%Y %H:%M", "%m/%d/%Y",
                  "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(head[:len(datetime.now().strftime(shape))],
                                     shape).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(head).date()
    except ValueError:
        return None


def commitments_from(records) -> dict:
    """Freight already committed, by the day it happens.

    Read from the Mission Records, which are what say a load exists. Outlook
    holds when things happen; the record holds what the freight is, and this
    view needs both.
    """
    by_day = {}
    for record in _iter(records):
        card = record.get("card_data") or {}
        for phase, window in (
                ("Pickup", record.get("pickup_window") or card.get("pickup_window")),
                ("Delivery", record.get("delivery_window") or card.get("delivery_window"))):
            when = _as_date(window)
            if not when:
                continue
            by_day.setdefault(when, []).append({
                "phase": phase,
                "record_id": record.get("id"),
                "load_number": record.get("load_number")
                or card.get("load_id") or "",
                "customer": record.get("customer") or card.get("broker") or "",
                "where": (card.get("origin") if phase == "Pickup"
                          else card.get("destination")) or "",
                "when": str(window or ""),
            })
    return by_day


def appointments_from(calendar: dict) -> dict:
    """Everything else on the calendar, by day.

    Personal commitments are **flagged, never blocking** -- ruled by the
    operator. A 09:00 dentist does not stop a Monday delivery, but it does sit
    across a 06:00 gate time in Savannah, and only he can weigh that.
    """
    by_day = {}
    for entry in (calendar or {}).get("entries") or []:
        when = _as_date(entry.get("start") or entry.get("when"))
        if not when:
            continue
        by_day.setdefault(when, []).append({
            "subject": entry.get("subject") or "",
            "when": entry.get("start") or entry.get("when") or "",
            "all_day": bool(entry.get("all_day")),
        })
    return by_day


def _iter(records):
    if records is None:
        return []
    if hasattr(records, "values"):
        return [r for r in records.values() if isinstance(r, dict)]
    return [r for r in records if isinstance(r, dict)]


def day_state(day: date, loads: list) -> str:
    """One state per day. A day cannot be two things, so nothing can disagree.

    A load on a held Thursday makes it BOOKED -- taking expedited freight is
    what the day was held for, and the screen should say what happened rather
    than what was planned.
    """
    if loads:
        return BOOKED
    return pattern_for(day)


def week_start(day: date) -> date:
    """The Monday of that day's week.

    The board runs Monday to Sunday because that is the shape of the week the
    business model describes -- Mon to Wed sellable, Thu and Fri held, Saturday
    maintenance. A fortnight starting on whatever today happens to be splits
    that pattern across rows and makes it unreadable.
    """
    return day - timedelta(days=day.weekday())


def build(records=None, calendar=None, *, today=None, weeks=2) -> dict:
    """The book: what is committed, what is held, what is still sellable.

    Laid out in calendar weeks, Monday to Sunday. Days already gone are shown
    to keep the week whole and are marked past -- they cannot be sold and are
    not counted among the days that can.
    """
    today = today or date.today()
    start = week_start(today)
    days = int(weeks) * 7
    commitments = commitments_from(records)
    appointments = appointments_from(calendar)

    board = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        loads = commitments.get(day, [])
        state = day_state(day, loads)
        board.append({
            "date": day,
            "iso": day.isoformat(),
            "weekday": day.strftime("%a").upper(),
            "day_number": day.day,
            "month": day.strftime("%b"),
            "state": state,
            "label": LABELS[state],
            "sub": SUBTITLES.get(state, ""),
            "planned": pattern_for(day),
            "loads": loads,
            "appointments": appointments.get(day, []),
            "is_today": day == today,
            # Shown to keep the week whole, never counted as sellable. A day
            # that has gone is not unsold inventory; it is just gone.
            "past": day < today,
            # Held for expedited, and something got booked into it. Not a
            # problem -- it is the position paying off -- but worth seeing.
            "held_and_taken": state == BOOKED and pattern_for(day) == HELD,
        })

    sellable = [d for d in board if d["planned"] in SELLABLE and not d["past"]]
    unsold = [d for d in sellable if d["state"] == OPEN]
    booked = [d for d in board if d["state"] == BOOKED and not d["past"]]

    return {
        "days": days,
        "weeks_shown": int(weeks),
        "today": today,
        "starts": start,
        "ends": start + timedelta(days=days - 1),
        "board": board,
        # Two weeks laid out as weeks, because that is how he thinks about it.
        "weeks": [board[i:i + 7] for i in range(0, len(board), 7)],
        "unsold": unsold,
        "unsold_count": len(unsold),
        "sellable_count": len(sellable),
        "booked_count": len(booked),
        "held_count": len([d for d in board if d["state"] == HELD
                           and not d["past"]]),
        "depth": depth_of([d for d in board if not d["past"]]),
        "calendar_status": (calendar or {}).get("status", "UNAVAILABLE"),
    }


def depth_of(board: list) -> dict:
    """How far out the book runs before it goes quiet.

    Counted to the last committed day, not to the horizon. "Booked through
    Thursday" is the answer to how far out am I covered; "14 days shown" is
    not an answer to anything.
    """
    booked = [d for d in board if d["state"] == BOOKED]
    if not booked or not board:
        return {"has_work": False, "through": None, "days_out": 0,
                "line": "Nothing booked."}
    last = booked[-1]
    days_out = (last["date"] - board[0]["date"]).days
    return {
        "has_work": True,
        "through": last["date"],
        "days_out": days_out,
        "line": "Booked through %s" % last["date"].strftime("%a %d %b"),
    }
