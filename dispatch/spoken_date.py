"""A date, however it was said.

Built 2026-09-09, before the first end-to-end run, because of a silent miss.

A voice capture is freeform by contract -- the input is what the Owner dictated
and nothing normalises it, which is correct: speed is the point and a capture
with gaps beats a listing lost to the next screen. So `pickup_date` arrives as
"Thursday".

Booking used to copy that word straight into the operational row's pickup
datetime. Nothing crashed. The calendar groups loads by matching the first seven
characters against a year and month, so it compared "Thursda" against "2026-09",
found nothing, and the load simply did not appear. No error, no warning, no load
on the calendar.

This module is where a spoken date becomes a real one, at booking, which is the
gate where a possibility becomes a commitment and the row starts needing dates
that arithmetic can be done on. The capture itself keeps the words. What the
Owner said is not overwritten anywhere.

**It refuses rather than guesses.** Anything it cannot read returns an empty
string, and the caller keeps the spoken words where a human can see them. An
undated load is visibly undated. That is recoverable. A load dated "Thursda" is
not, because it looks like data.

**Deterministic, given a day.** `today` is a parameter, defaulted rather than
assumed, so the same words on the same day always resolve the same way.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

#: Weekday words, including the short forms speech-to-text produces.
_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tues": 1, "tue": 1,
    "wednesday": 2, "weds": 2, "wed": 2,
    "thursday": 3, "thurs": 3, "thur": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_NUMERIC = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
_ORDINAL = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b")
#: A time, in the three shapes it gets said. Named groups because the branches
#: are read separately and positional numbers drift when one is added.
#:
#: This only ever runs on the words left after the date has been taken out. A
#: bare four-digit time and a four-digit year are the same characters, so
#: "2026-09-15" would otherwise resolve to twenty past eight in the evening.
_TIME = re.compile(
    r"\b(?P<h12>\d{1,2})(?::(?P<m12>\d{2}))?\s*(?P<ampm>am|pm)\b"
    r"|\b(?P<h24>[01]?\d|2[0-3]):(?P<m24>[0-5]\d)\b"
    r"|\b(?P<hmil>[01]\d|2[0-3])(?P<mmil>[0-5]\d)\b"
)


def looks_resolved(text: str) -> bool:
    """True when a value already carries a real date and needs nothing done."""
    return bool(_ISO.match(str(text or "").strip()))


def _next_weekday(target: int, today: date) -> date:
    """The soonest day that is `target`. Today counts.

    Said on a Thursday, "Thursday" means today, not a week away. A driver
    dictating a board listing is talking about the load in front of him.
    """
    return today + timedelta(days=(target - today.weekday()) % 7)


def _with_year(month: int, day: int, today: date) -> date | None:
    """A month and day, in the year that makes it upcoming rather than past.

    A listing dictated in December for the third of January is next year's
    third. Rolling forward is right far more often than assuming this year.
    """
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            return None
        if candidate >= today:
            return candidate
    return None


def _time_of(text: str) -> str:
    """The time, if one was said. Empty when none was.

    Call this on the words left after the date has been removed.
    """
    match = _TIME.search(text)
    if not match:
        return ""
    if match.group("ampm"):
        hour = int(match.group("h12")) % 12
        if match.group("ampm") == "pm":
            hour += 12
        return "%02d:%s" % (hour, match.group("m12") or "00")
    if match.group("h24"):
        return "%02d:%s" % (int(match.group("h24")), match.group("m24"))
    return "%02d:%s" % (int(match.group("hmil")), match.group("mmil"))


def resolve(text: str, *, today: date | None = None) -> str:
    """A spoken date as `YYYY-MM-DD`, with a time appended when one was said.

    Returns an empty string for anything it cannot read. It never guesses.
    """
    said = str(text or "").strip().lower()
    if not said:
        return ""

    today = today or date.today()
    when: date | None = None
    # What is left once the date has been taken out. The time is read from this
    # and never from the whole sentence, because a four-digit year and a bare
    # four-digit time are the same characters.
    rest = said

    iso = _ISO.search(said)
    if iso:
        try:
            when = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return ""
        rest = said.replace(iso.group(0), " ", 1)
    elif "today" in said or "tonight" in said:
        when = today
    elif "tomorrow" in said:
        when = today + timedelta(days=1)
    else:
        numeric = _NUMERIC.search(said)
        if numeric:
            year = numeric.group(3)
            if year:
                full = int(year) + 2000 if len(year) == 2 else int(year)
                try:
                    when = date(full, int(numeric.group(1)), int(numeric.group(2)))
                except ValueError:
                    return ""
            else:
                when = _with_year(int(numeric.group(1)), int(numeric.group(2)), today)
                if when is None:
                    return ""
            rest = said.replace(numeric.group(0), " ", 1)

    if when is None:
        for name, month in _MONTHS.items():
            if re.search(r"\b%s\b" % name, said):
                day = _ORDINAL.search(said) or re.search(r"\b(\d{1,2})\b", said)
                if day:
                    when = _with_year(month, int(day.group(1)), today)
                    if when is None:
                        return ""
                    rest = said.replace(day.group(0), " ", 1)
                break

    if when is None:
        for name, index in _WEEKDAYS.items():
            if re.search(r"\b%s\b" % name, said):
                when = _next_weekday(index, today)
                # "next Thursday" is the one after this week's.
                if "next" in said:
                    when += timedelta(days=7)
                break

    if when is None:
        ordinal = _ORDINAL.search(said)
        if ordinal:
            when = _with_year(today.month, int(ordinal.group(1)), today)
            if when is None:
                return ""
            rest = said.replace(ordinal.group(0), " ", 1)

    if when is None:
        return ""

    at = _time_of(rest)
    return f"{when.isoformat()} {at}" if at else when.isoformat()
