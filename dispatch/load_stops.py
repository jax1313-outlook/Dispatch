"""Build capacity stops out of what a load actually records.

`dispatch/capacity.py` has evaluated stop sequences and appointment windows
since it was written: stop ceilings, out-of-route miles, windows that close
before they open, a delivery whose appointment opens before its pickup, and a
forward walk that arrives, waits for the window, serves and drives on.

None of it had ever run against a real load, because nothing in production
built a `Stop`. `scoring.assess_capacity()` called `capacity.evaluate()` without
the `stops=` argument, so every one of those checks was unreachable code with
passing unit tests -- the most convincing kind of dead code there is.

This module is the missing constructor, and almost all of it is about refusing
to hand the engine something it would be right to reject.

**Never a naive timestamp.** The engine treats a timestamp with no timezone as
BLOCKING, and it is right to: "06:00" is not an instant, and a truck cannot be
judged against an appointment nobody can place on a clock. But Dispatch's own
`pickup_datetime` is very often naive, so passing those through raw would have
turned a correct refusal into a false alarm on nearly every load. Values go
through `dispatch.timestamps.normalize()` first, which resolves a bare local
time against the configured operating timezone and *records that it did so*.
Anything that still cannot be read is left out and reported as a gap, so the
engine raises its advisory "cannot be evaluated" rather than a blocking
"unusable".

**Never an invented dwell.** Dispatch records no service time at any stop.
`service_hours` is left `None`, which is what stops the forward walk from
running -- deliberately. A dwell of zero would make every appointment look
reachable. `default_service_hours` exists so that recording one later turns the
walk on with no other change.

**Never an invented stop.** A load records a pickup and a delivery. This builds
those two and no others. Deriving intermediate stops would be route planning,
and `CLAUDE.md` §5.5 is explicit that Dispatch does not build a second
scheduling system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from dispatch import timestamps
from dispatch.capacity import Stop

#: How this repository already writes an appointment window, e.g.
#: "2026-07-30 06:00 - 10:00". `portal/models/conflict.py` has parsed this shape
#: on Opportunity Cards since it was written; reusing it means the operator
#: types what they already type.
WINDOW_SEPARATOR = " - "

#: A bare clock time on the closing side of a window: "06:00 - 10:00" means the
#: window closes at 10:00 *on the day it opened*.
_TIME_ONLY = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")

#: Appointment statuses, from the eight in `CLAUDE.md` §6.
USABLE = "LIVE"
UNREADABLE = "UNVERIFIED"
NOT_RECORDED = "ABSENT"


@dataclass(frozen=True)
class Appointment:
    """What a load's datetime field turned out to say.

    `start` and `end` are offset-bearing ISO strings or empty. Empty is not a
    failure to be hidden -- it is the input to the engine's own data-gap
    finding, and `note` is the plain-language version for the operator.
    """

    start: str = ""
    end: str = ""
    status: str = NOT_RECORDED
    note: str = ""

    @property
    def is_window(self) -> bool:
        return bool(self.start and self.end)


def _normalise_one(text: str) -> tuple[str, str]:
    """(offset-bearing ISO, note). Empty ISO means it could not be read."""
    result = timestamps.normalize(text)
    if result["instant"] is None:
        return "", result["note"]
    return result["value"], result["note"]


def parse_appointment(value: str | None) -> Appointment:
    """Read one `pickup_datetime`/`delivery_datetime` field.

    Three shapes, and the third one is the reason this is not a one-liner:

    - `""` -- nothing recorded.
    - `"<start> - <end>"` -- a window. A bare clock time on the closing side
      inherits the opening side's date, because "06:00 - 10:00" plainly means
      one morning and not a window that closes fifty years ago.
    - `"<when>"` -- a single instant. That is an appointment **time**, not a
      window, so `end` stays empty. It is tempting to set `end = start` and get
      a "complete" window out of it, and that would be wrong in the direction
      that costs money: a zero-width window demands arrival to the second, and
      the engine would report almost every load as infeasible. A single time
      earns an honest gap instead of a confident falsehood.
    """
    text = "" if value is None else str(value).strip()
    if not text:
        return Appointment(status=NOT_RECORDED)

    if WINDOW_SEPARATOR in text:
        raw_start, _, raw_end = text.partition(WINDOW_SEPARATOR)
        raw_start, raw_end = raw_start.strip(), raw_end.strip()
        if _TIME_ONLY.match(raw_end):
            date_part = raw_start.split("T")[0].split(" ")[0]
            raw_end = f"{date_part} {raw_end}"
        start, start_note = _normalise_one(raw_start)
        end, end_note = _normalise_one(raw_end)
        if not start or not end:
            return Appointment(
                status=UNREADABLE,
                note=(start_note or end_note)
                or f"Dispatch could not read {text!r} as an appointment window.",
            )
        return Appointment(start=start, end=end, status=USABLE, note=start_note)

    start, note = _normalise_one(text)
    if not start:
        return Appointment(status=UNREADABLE, note=note)
    return Appointment(
        start=start,
        status=USABLE,
        note=(
            f"{text!r} is a single appointment time, not a window, so Dispatch "
            "cannot say whether the truck arrives before it closes. Record it as "
            f"'{text}{WINDOW_SEPARATOR}<closing time>' to have that checked."
        ),
    )


#: The engine's planning speed, mirrored from `dispatch.scoring`. Kept as a
#: named constant here so the reason for the division is visible at the point
#: of use rather than three modules away.
PLANNING_SPEED_MPH = 50.0


def _confirmed_distance(load_id: str):
    """The miles on the load's rate confirmation, if it has one.

    Import-local and failure-tolerant: a capacity assessment is advisory, and a
    store that cannot answer should cost the caller a projected arrival time,
    never an exception on a page they were reading for something else.
    """
    if not load_id:
        return None
    try:
        from dispatch import store

        confirmation = store.get_rate_confirmation(load_id)
    except Exception:  # noqa: BLE001 - advisory path, never the caller's problem
        return None
    return (confirmation or {}).get("distance_miles")


def transit_hours(load: dict) -> float | None:
    """Recorded pickup-to-delivery drive time, or None when nobody recorded it.

    `scoring._requested_drive_hours()` answers the same question with `0.0` for
    an unknown distance, which is right for its caller -- a physical-capacity
    request for no drive time. It is wrong here. Zero drive hours on the
    delivery leg is a claim that the truck arrives the instant it leaves, and
    the engine would happily project arrivals from it and call tight
    appointments comfortable.

    None is the honest answer, and the engine already knows what to do with it:
    it declines to walk the sequence and says why.

    Where the distance comes from matters. `Load` has no `distance_miles` field
    and `create_load()` refuses the keyword -- so reading only the load record,
    as the first version of this did, returns None for every load in the system
    and the forward walk never runs. The distance is recorded one join away, on
    the load's **rate confirmation**, which is the document that states the
    miles the rate was agreed against. That is the right source anyway: it is
    the distance somebody committed to, not an estimate.

    A load dict that already carries `distance_miles` wins, so a caller holding
    a joined row or a candidate that is not yet a load is not forced through
    the database.
    """
    distance = load.get("distance_miles")
    if distance in (None, "", 0, 0.0):
        distance = _confirmed_distance(load.get("load_id") or "")
    if distance in (None, "", 0, 0.0):
        return None
    try:
        miles = float(distance)
    except (TypeError, ValueError):
        return None
    return miles / PLANNING_SPEED_MPH if miles > 0 else None


def stops_for_load(
    load: dict,
    *,
    drive_hours: float | None = None,
    default_service_hours: float | None = None,
) -> tuple[list[Stop], list[dict]]:
    """The load's own two stops, plus every reason a check could not be made.

    `drive_hours` is the recorded transit time from pickup to delivery. It sits
    on the delivery stop, because that is the leg it is. The pickup stop carries
    zero: getting *to* the pickup is deadhead, which is `PositionCapacity`'s
    question and not this one, and charging it here would double-count it.

    Returns `(stops, gaps)`. A gap is a dict with `field`, `status` and
    `message`, written for the person reading the load page rather than for a
    log.
    """
    gaps: list[dict] = []
    stops: list[Stop] = []

    plan = (
        # 0.0 on the pickup leg is an anchor, not a guess: the forward walk
        # starts the clock when the pickup window opens. Getting *to* the pickup
        # is deadhead, which PositionCapacity answers.
        ("pickup", 1, load.get("pickup_location") or "", load.get("pickup_datetime"), 0.0),
        ("delivery", 2, load.get("delivery_location") or "", load.get("delivery_datetime"), drive_hours),
    )

    for stop_type, sequence, location, raw_when, leg_hours in plan:
        appointment = parse_appointment(raw_when)
        field = f"{stop_type}_datetime"

        if appointment.status == NOT_RECORDED:
            gaps.append({
                "field": field,
                "status": NOT_RECORDED,
                "message": (
                    f"No {stop_type} appointment is recorded, so Dispatch cannot "
                    "check whether the truck can make it."
                ),
            })
        elif appointment.status == UNREADABLE:
            gaps.append({"field": field, "status": UNREADABLE, "message": appointment.note})
        elif not appointment.is_window:
            gaps.append({"field": field, "status": USABLE, "message": appointment.note})

        if not location:
            gaps.append({
                "field": f"{stop_type}_location",
                "status": NOT_RECORDED,
                "message": f"No {stop_type} location is recorded.",
            })

        stops.append(
            Stop(
                stop_id=f"{load.get('load_id', 'LOAD')}-{stop_type.upper()}",
                sequence=sequence,
                location=location,
                stop_type=stop_type,
                appointment_start=appointment.start,
                appointment_end=appointment.end,
                service_hours=default_service_hours,
                drive_hours_to_stop=leg_hours,
                out_of_route_miles=0.0,
            )
        )

    if drive_hours is None:
        gaps.append({
            "field": "distance_miles",
            "status": NOT_RECORDED,
            "message": (
                "No distance is recorded for this load, so Dispatch does not know "
                "how long the drive takes and will not project arrival times."
            ),
        })

    if default_service_hours is None:
        gaps.append({
            "field": "service_hours",
            "status": NOT_RECORDED,
            "message": (
                "No dwell time is recorded for any stop, so Dispatch will not "
                "project arrival times. A dwell of zero would make every "
                "appointment look reachable, which is worse than saying nothing."
            ),
        })

    return stops, gaps
