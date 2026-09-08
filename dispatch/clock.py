"""What day it is, for this business.

**Owner ruling, 2026-09-08:**

> *"All IFTA and HOS logs are based on the declared HOME location and never
> altered to accommodate the crossing of time zones. My HOME location is Eastern
> Time Zone."*

That is the whole of this module. A driver crosses four time zones in a day and
his logbook does not care; the day belongs to the home terminal, start to
finish, and the truck's position never moves it.

WHY IT EXISTS. Dispatch stamped every date from UTC. Between 8pm and midnight
Eastern that is tomorrow, so for four hours a day the program disagreed with the
business about what day it was:

  * a trip leg driven at 9pm on 31 March was dated 1 April and filed into the
    **wrong IFTA quarter**
  * a CDL read **expired the evening before it expired**
  * maintenance read **overdue a day early**
  * driver pay was stamped **tomorrow**

Found by a test that failed only in the evening, which is the only reason it was
found at all.

THE LINE THIS MODULE DRAWS, and it is the whole design:

    a TIMESTAMP orders events              -> UTC, always, `models._utc_now()`
    a DATE says what day something was on  -> home zone, always, here

Timestamps must never move: the audit trail, `created_at`, record ids. Dates
answer a different question and the answer is the home terminal's.

WHERE THE SETTING COMES FROM. `DISPATCH_HOME_TIMEZONE`, defaulting to
`America/New_York` -- **Mike's declared home.** That default is a placeholder for
a carrier of one, not a design. It belongs on the Company and Driver setup
screen, which does not exist yet and is specified in
`docs/specifications/COMPANY_AND_DRIVER_SETUP.md`.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

#: The environment variable that carries the declared home location, until the
#: setup screen owns it.
HOME_ZONE_VAR = "DISPATCH_HOME_TIMEZONE"

#: Level 1 Transport's home terminal is in the Eastern time zone. An IANA name,
#: not a fixed offset, so daylight saving is the database's problem and not
#: ours -- a hand-rolled offset is wrong twice a year, on the two days it is
#: hardest to notice.
DEFAULT_HOME_ZONE = "America/New_York"


def home_zone_name() -> str:
    """The configured home zone's name. Never empty."""
    return (os.environ.get(HOME_ZONE_VAR) or "").strip() or DEFAULT_HOME_ZONE


def zone_problem() -> str:
    """Why the configured zone could not be used, or "" when it could.

    Separate from the accessors so a status screen can ask without having to
    catch anything, and so the fallback below is never silent. *Degradation is
    permitted. Incapacity is not* -- a bad zone name must not stop Dispatch
    starting, and it must not pass unremarked either.
    """
    name = home_zone_name()
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ("The home time zone %r is not a name this machine knows. "
                "Dates are being stamped in UTC instead, which is wrong by "
                "several hours. On Windows this usually means the tzdata "
                "package is missing: py -m pip install --user tzdata" % name)
    except (ValueError, OSError) as bad:
        return ("The home time zone %r could not be loaded: %s. Dates are "
                "being stamped in UTC instead." % (name, bad))
    return ""


def home_zone() -> ZoneInfo | timezone:
    """The home zone itself, or UTC when the configured name cannot be loaded.

    Falling back rather than raising is deliberate, and so is `zone_problem()`
    existing beside it: Dispatch keeps running on a machine with a broken tzdata
    install, and says on its status screen that it is doing so.
    """
    try:
        return ZoneInfo(home_zone_name())
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return timezone.utc


def home_now() -> datetime:
    """Now, at the home terminal. Timezone-aware."""
    return datetime.now(home_zone())


def home_date() -> date:
    """Today's date at the home terminal, as a `date`."""
    return home_now().date()


def home_today() -> str:
    """Today at the home terminal, as `YYYY-MM-DD`.

    **This is the function every "what day is it" call should use.** It is the
    replacement for `_utc_now()[:10]`, which is now forbidden anywhere in the
    program -- `tests/test_home_time_zone.py` fails if it returns.
    """
    return home_date().isoformat()


def home_quarter(when: str | date | None = None) -> tuple[int, int]:
    """The IFTA quarter a date falls in, as `(year, quarter)`.

    Here rather than in the IFTA code because the quarter boundary is exactly
    where the time zone matters: a leg driven at 9pm Eastern on 31 March is
    Q1, and only a home-zone date says so.
    """
    if when is None:
        when = home_date()
    elif isinstance(when, str):
        when = date.fromisoformat(when[:10])
    return when.year, (when.month - 1) // 3 + 1
