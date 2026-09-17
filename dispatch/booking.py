"""Booking: the forward view of the truck.

    How far out am I covered, and what is still sellable?

A verb, not a noun. It is the thing being done -- booking out two weeks -- and
not a record kept about it.

EVERY DAY BEGINS OPEN
=====================

**BOOKING CONFLICT PREVENTION DOCTRINE, 2026-09-16.** This module used to carry
a week pattern -- Mon to Wed sellable, Thu and Fri held for expedited, Saturday
maintenance, Sunday closed -- and that pattern decided things:

    *"Dispatch does not decide: when Mike works, when Mike rests, when Mike
    performs maintenance, when Mike reserves capacity, which days are closed.
    Human authority remains final."*

So it decides none of them now. Every day is OPEN until freight is on it.

    Booking exists to protect Mike from creating conflicts.
    Booking does NOT schedule Mike.
    Booking does NOT reserve days automatically.
    Booking does NOT close days automatically.
    Booking only identifies conflicts and consequences.

Dispatch is not a calendar and must not become one -- Outlook is the single
source of scheduling truth, and a stored day-state would be exactly the second
calendar that doctrine forbids. A day he wants off is a day he blocks in
Outlook, which this board already reads.

What is booked is read, never stored. Pattern plus commitments equals the view,
and there is nothing to keep in sync because nothing is kept.

AN EMPTY DAY IS A GAP, AND A GAP IS THE POINT
=============================================

**Open days are the number that matters.** They are unsold inventory and they
expire worthless. The month view exists to answer the owner-operator's
questions rather than the driver's: *"Where are my gaps? What capacity is
available? Where am I overcommitted? What opportunities exist?"*
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from dispatch import clock, commitment

#: How far out the operator books. Two weeks is the horizon he works to.
HORIZON_DAYS = 14

#: What a day is for. One state per day, resolved -- never stored.
BOOKED = "BOOKED"
OPEN = "OPEN"
HELD = "HELD"
MAINTENANCE = "MAINTENANCE"
CLOSED = "CLOSED"

#: **Every day begins OPEN. BOOKING CONFLICT PREVENTION DOCTRINE, 2026-09-16.**
#:
#: *"Dispatch does not decide: when Mike works, when Mike rests, when Mike
#: performs maintenance, when Mike reserves capacity, which days are closed.
#: Human authority remains final."*
#:
#: This finishes what his Saturday ruling started on 2026-09-10 -- *"just leave
#: it open not committed so I can close or take a run"* -- and the reason given
#: then is the reason for all seven days now: **open is the honest state for a
#: day he decides on when it arrives.** Thursday and Friday were HELD and Sunday
#: CLOSED on rulings made before he had seen the board work, and a held Thursday
#: reserved the day whether or not he wanted it reserved that week.
#:
#: **Where "which days I work" lives is already answered.** Outlook is the
#: scheduling authority (CLAUDE.md §5.5) and the board reads it, so a day he
#: blocks there is a day the board sees. Nothing is stored here -- a stored
#: day-state is the second calendar the scheduling doctrine forbids.
#:
#: `HELD`, `MAINTENANCE` and `CLOSED` are kept as states, not deleted. Nothing
#: in this pattern produces one now; they remain the vocabulary for a day
#: Outlook or a future ruling says is not sellable.
WEEK_PATTERN = {
    0: OPEN,          # Monday
    1: OPEN,          # Tuesday
    2: OPEN,          # Wednesday
    3: OPEN,          # Thursday
    4: OPEN,          # Friday
    5: OPEN,          # Saturday
    6: OPEN,          # Sunday
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


def windows_of(record: dict) -> tuple:
    """`(pickup_window, delivery_window)` as the record or its card carries them."""
    card = (record or {}).get("card_data") or {}
    return ((record or {}).get("pickup_window") or card.get("pickup_window") or "",
            (record or {}).get("delivery_window") or card.get("delivery_window") or "")


def span_of(record: dict) -> list:
    """Every day a load occupies, pickup through delivery. CO-4, 2026-09-14.

    A load that picks up Monday and delivers Wednesday takes Tuesday too -- the
    truck is not sellable on a day it is driving somebody's freight. Only one
    end known gives that one day; neither gives nothing. A delivery written
    before its pickup is not stretched backwards into a span.
    """
    pickup, delivery = (_as_date(w) for w in windows_of(record))
    if pickup and delivery and delivery >= pickup:
        return [pickup + timedelta(days=n) for n in range((delivery - pickup).days + 1)]
    return sorted({d for d in (pickup, delivery) if d})


def commitments_from(records) -> dict:
    """Freight already committed, by the day it happens.

    Read from the Mission Records, which are what say a load exists. Outlook
    holds when things happen; the record holds what the freight is, and this
    view needs both.
    """
    by_day = {}
    for record in _iter(records):
        # Only committed missions take capacity. A candidate still being
        # negotiated must not claim a Tuesday and shrink the unsold count on
        # freight that is not his yet -- that is the whole reason COMMIT is a
        # gate rather than a status. Candidates are gathered separately and
        # shown without being counted.
        if not commitment.is_committed(record):
            continue
        card = record.get("card_data") or {}
        pickup_window, delivery_window = windows_of(record)
        ends = {"Pickup": _as_date(pickup_window), "Delivery": _as_date(delivery_window)}
        for phase, window in (("Pickup", pickup_window), ("Delivery", delivery_window)):
            when = ends[phase]
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
        # CO-4, 2026-09-14: the days between are taken too. A truck driving
        # somebody's freight on Tuesday is not sellable on Tuesday, and a board
        # that shows it open is showing a gap that is not there.
        for day in span_of(record)[1:-1]:
            by_day.setdefault(day, []).append({
                "phase": "Transit",
                "record_id": record.get("id"),
                "load_number": record.get("load_number") or card.get("load_id") or "",
                "customer": record.get("customer") or card.get("broker") or "",
                "where": "%s to %s" % (card.get("origin") or "", card.get("destination") or ""),
                "when": "",
            })
    return by_day


def candidates_from(records) -> dict:
    """Loads being worked but not yet committed, by the day they would run.

    Shown so he can see what is in play on a day, and never counted as
    capacity. Until COMMIT, the day is still sellable to somebody else.
    """
    by_day = {}
    for record in _iter(records):
        if commitment.is_committed(record):
            continue
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
                "load_number": record.get("load_number") or card.get("load_id") or "",
                "where": (card.get("origin") if phase == "Pickup"
                          else card.get("destination")) or "",
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
    if today is None:
        from dispatch import clock

        today = clock.home_date()
    start = week_start(today)
    days = int(weeks) * 7
    commitments = commitments_from(records)
    candidates = candidates_from(records)
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
            "candidates": candidates.get(day, []),
            "appointments": appointments.get(day, []),
            "is_today": day == today,
            # Shown to keep the week whole, never counted as sellable. A day
            # that has gone is not unsold inventory; it is just gone.
            "past": day < today,
        })

    # **`held_count` and `held_and_taken` are gone.** Nothing produces HELD --
    # `day_state()` returns BOOKED or `pattern_for()`, and `pattern_for()` is
    # OPEN for all seven days since the BOOKING CONFLICT PREVENTION DOCTRINE.
    # They could only ever be 0 and False, and the screen printed them as
    # though the old week model were still in force. The states themselves stay
    # as vocabulary; see WEEK_PATTERN.
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


# ------------------------------------------------------------- the month ----

def month_of(year: int, month: int, records=None, *, today=None) -> dict:
    """One month of capacity: every day, its state, and what is on it.

    **One calendar, one source of truth, multiple views** (Owner, 2026-09-16).
    The Booking board and the driver's month grid are two presentations of this
    one calculation; neither computes capacity for itself, so neither can
    disagree with the other about a Tuesday.

    **A month rather than a week, and his reason for it:** *"Where are my gaps?
    What capacity is available? Where am I overcommitted? What opportunities
    exist?"* Those are the owner-operator's questions, and an empty square is
    the answer to the first one. `HORIZON_DAYS` bounds the Booking board's
    fortnight; it does not bound this, because a day's state is resolved from
    the pattern and the commitments rather than looked up in a window.

    **Nothing is stored and nothing is decided.** Days are OPEN unless freight
    is on them. Candidates are carried so he can see what is in play, and are
    never counted as capacity -- until COMMIT the day is still sellable to
    somebody else.

    Returns `{"year", "month", "label", "first", "weeks", "days",
    "committed_days", "open_days", "prev", "next"}`. `weeks` is a list of
    seven-day rows, Monday first, padded with `None` outside the month, ready
    for a grid. `days` is the same days flat.
    """
    import calendar as _calendar

    today = today or clock.home_date()
    first = date(year, month, 1)
    last = date(year, month, _calendar.monthrange(year, month)[1])

    committed = commitments_from(records)
    candidates = candidates_from(records)

    days = []
    for offset in range((last - first).days + 1):
        day = first + timedelta(days=offset)
        loads = committed.get(day, [])
        days.append({
            "date": day,
            "day": day.day,
            "state": day_state(day, loads),
            "loads": loads,
            "candidates": candidates.get(day, []),
            "past": day < today,
            "today": day == today,
            # An empty square is a day nobody has sold. That is the thing he
            # opens this screen to see.
            "gap": not loads and day >= today,
        })

    grid = []
    row = [None] * first.weekday()
    for entry in days:
        row.append(entry)
        if len(row) == 7:
            grid.append(row)
            row = []
    if row:
        grid.append(row + [None] * (7 - len(row)))

    prev_month = first - timedelta(days=1)
    next_month = last + timedelta(days=1)
    return {
        "year": year,
        "month": month,
        "label": first.strftime("%B %Y"),
        "first": first,
        "weeks": grid,
        "days": days,
        "committed_days": len([d for d in days if d["loads"]]),
        "open_days": len([d for d in days if d["gap"]]),
        "prev": {"year": prev_month.year, "month": prev_month.month},
        "next": {"year": next_month.year, "month": next_month.month},
    }


def loads_on(day: date, records=None) -> list:
    """What the truck is doing on one day: committed freight, then candidates.

    The driver taps a square and this is what is behind it. Candidates are
    included and marked, because "what is in play on Thursday" is a real
    question -- but they are not capacity and nothing here counts them as any.
    """
    committed = commitments_from(records).get(day, [])
    pending = candidates_from(records).get(day, [])
    return ([dict(entry, committed=True) for entry in committed]
            + [dict(entry, committed=False) for entry in pending])
