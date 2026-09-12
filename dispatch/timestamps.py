"""An appointment time that is not ambiguous, from an operator who typed one.

Found while wiring the capacity engine into production, and it is the reason
wiring it would otherwise have made every load unassessable.

`dispatch/capacity.py::parse_operational_timestamp` is right about the hard part:

    "A naive timestamp is rejected rather than assumed to be UTC -- a pickup
    window in an unstated zone is genuinely ambiguous, and guessing costs a load."

It returns TIMESTAMP_NAIVE for a value with no offset, and the caller raises a
**SEVERITY_BLOCKING** finding. Meanwhile the load form's own placeholder is
`YYYY-MM-DD HH:MM` -- a naive timestamp. So every load entered through the
portal in the documented format produces a blocking capacity finding, and Mike
would have concluded the capacity engine refuses everything rather than that the
input format and the engine disagree.

There is a second, quieter consequence of the same gap.
`services.get_load_calendar()` selects a month by string prefix -- `p[:7] ==
"2026-09"` -- on a free-text field. Type `9/14/2026 08:00`, which is the format a
US dispatcher writes by hand and which the `type="text"` input accepts without
complaint, and the load simply is not on the calendar. No error, no warning, no
row. Silent omission from the one view that is supposed to show everything.

So this module does the one thing that resolves both without weakening the
engine's rule: it makes the *stored* value unambiguous at the moment of entry.

**The operator's zone is configuration, not a guess.** `DISPATCH_OPERATING_TIMEZONE`
names it, and the normaliser attaches it to a value the operator typed without
one -- which is not guessing, it is recording what they meant, because a
dispatcher typing `08:00` means eight in the morning where they are. Attaching
UTC would be the guess. A value that already carries an offset is left exactly
as it is.

**What cannot be parsed is kept, not discarded.** The raw text is stored
unchanged and reported as UNVERIFIED. Rewriting or dropping a value somebody
typed because this module could not read it would be worse than the ambiguity.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

#: Where Level 1 Transport operates. An owner-operator types local time, so this
#: is what a bare "08:00" means. Configurable because the business can move and
#: because a second operator in another zone is a real possibility.
DEFAULT_TIMEZONE = "America/New_York"

#: Outcomes, in the fixed truth vocabulary where one fits.
NORMALIZED = "NORMALIZED"      #: an unambiguous instant, offset carried
ALREADY_OFFSET = "ALREADY_OFFSET"
MISSING = "MISSING"
UNVERIFIED = "UNVERIFIED"      #: kept verbatim; this module could not read it

#: Formats an operator plausibly types, most explicit first. Every one of them
#: is naive -- that is the point; the zone comes from configuration, not from
#: the string.
_NAIVE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y",
    "%m/%d/%y %H:%M",
    "%m/%d/%y %I:%M %p",
    "%m/%d/%y",
)

_COMPACT_MERIDIEM = re.compile(r"^(.*\d)\s*([AaPp])\.?[Mm]\.?$")


def operating_timezone() -> ZoneInfo:
    """The zone a bare time is in. Falls back to UTC, and says so by returning it.

    A missing tzdata is a deployment fact, not a reason to refuse to start: the
    fallback keeps every timestamp unambiguous (UTC is an offset) at the cost of
    being wrong about which hour, which `timezone_name()` makes visible so a
    screen can say it rather than a load quietly moving four hours.
    """
    name = os.environ.get("DISPATCH_OPERATING_TIMEZONE", DEFAULT_TIMEZONE).strip()
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return ZoneInfo("UTC") if _utc_available() else timezone.utc  # type: ignore[return-value]


def _utc_available() -> bool:
    try:
        ZoneInfo("UTC")
        return True
    except Exception:  # noqa: BLE001
        return False


def timezone_name() -> str:
    configured = os.environ.get("DISPATCH_OPERATING_TIMEZONE", DEFAULT_TIMEZONE).strip()
    zone = operating_timezone()
    actual = getattr(zone, "key", "UTC")
    return actual if actual == configured else f"{actual} (requested {configured}, unavailable)"


def normalize(value: str | None) -> dict:
    """Turn what an operator typed into an instant that cannot be misread.

    Returns `{"value", "status", "note", "instant"}`. `value` is what to store:
    an ISO-8601 string carrying an offset when the input could be read, and the
    original text unchanged when it could not.
    """
    if value is None:
        return {"value": "", "status": MISSING, "note": "", "instant": None}
    text = str(value).strip()
    if not text:
        return {"value": "", "status": MISSING, "note": "", "instant": None}

    # Already unambiguous. Left alone -- re-deriving an offset somebody supplied
    # is how a correct value gets changed.
    explicit = _parse_with_offset(text)
    if explicit is not None:
        # Returned verbatim, not re-serialised. "2026-09-14T08:00:00Z" and
        # "2026-09-14T08:00:00+00:00" are the same instant, and rewriting one
        # into the other changes a value that was already correct -- which is
        # both pointless and, for anything comparing stored strings, a change.
        return {
            "value": text,
            "status": ALREADY_OFFSET,
            "note": "",
            "instant": explicit,
        }

    naive = _parse_naive(text)
    if naive is None:
        return {
            "value": text,
            "status": UNVERIFIED,
            "note": (
                f"Dispatch could not read {text!r} as a date and time, so it is stored "
                "exactly as typed. It will not appear on the calendar and cannot be "
                "used to judge whether a truck can make an appointment."
            ),
            "instant": None,
        }

    zone = operating_timezone()
    localised = naive.replace(tzinfo=zone)
    return {
        "value": _iso(localised),
        "status": NORMALIZED,
        "note": f"Read as {timezone_name()} local time.",
        "instant": localised,
    }


def _parse_with_offset(text: str) -> datetime | None:
    candidate = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _parse_naive(text: str) -> datetime | None:
    # "8:00PM" and "8:00 p.m." are the same appointment; strptime only reads one.
    match = _COMPACT_MERIDIEM.match(text)
    if match:
        text = f"{match.group(1)} {match.group(2).upper()}M"
    for fmt in _NAIVE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is None else None


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def to_utc(value: str | None) -> datetime | None:
    """The instant, in UTC, or None when the value is unusable."""
    result = normalize(value)
    instant = result["instant"]
    return instant.astimezone(timezone.utc) if instant else None


def local_date(value: str | None) -> str:
    """The calendar day this appointment falls on, where the operator is.

    `get_load_calendar()` used to take `value[:10]`, which is the day in
    whatever zone the string happened to be written in -- so a delivery at
    `2026-09-15T01:00:00Z` showed on the 15th when for a dispatcher in Eastern
    time it is the evening of the 14th.
    """
    instant = normalize(value)["instant"]
    if instant is None:
        return ""
    return instant.astimezone(operating_timezone()).strftime("%Y-%m-%d")


def local_month(value: str | None) -> str:
    day = local_date(value)
    return day[:7] if day else ""


def describe(value: str | None) -> str:
    """What to show a person: local time, with the zone named.

    Every timestamp in this program is rendered raw -- `2026-09-12T17:04:00Z` --
    to a dispatcher and, through the stakeholder view, to a broker. UTC on a
    screen is a 70 MPH failure: the driver has to do arithmetic to find out when
    the appointment is.
    """
    result = normalize(value)
    instant = result["instant"]
    if instant is None:
        return str(value or "")
    local = instant.astimezone(operating_timezone())
    return local.strftime("%a %d %b %Y, %H:%M ") + (local.tzname() or "")
