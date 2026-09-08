"""Who this carrier is.

**Owner ruling, 2026-09-08: keep it tiny.** One gear, four things -- Home Base,
Home Time Zone, Driver, Company -- and nothing else. Everything larger parks in
`D:\\MD Files\\EXPANSION_PARKING_LOT.md`.

WHAT THIS IS FOR. Operational Static Information: the facts about this business
that almost never change, that every screen quietly assumes, and that until now
lived in environment variables, in code defaults, or nowhere at all. The one
that forced the issue was the home time zone -- `dispatch/clock.py` needed a
declared home and there was nowhere in Dispatch to declare it.

**Exactly one row.** A `CHECK` in the schema holds it to `carrier_id = 'carrier'`,
because a business has one identity and a second row would be a second answer to
"what is our USDOT number".

WHAT THIS IS NOT. It is not machine configuration. `DISPATCH_JOE_TOKEN`,
`PORTAL_HOST`, the storage roots and the secret key are read **before Dispatch
has a database to open**, which is exactly why they cannot live here. They belong
to the launcher. The line is:

    Launcher Settings   what this MACHINE needs in order to start Dispatch
    Registration        what this BUSINESS is

**The driver is not here either.** `drivers` already has a table, the Fleet
screen already has `+ Add Driver`, and the Driver Portal already logs in per
driver by phone and PIN. Duplicating that here would be a second place to edit
one truth. Registration points at it.
"""

from __future__ import annotations

import os

from dispatch import clock
from dispatch.db import get_connection

#: The only row id this table will accept.
ROW_ID = "carrier"

#: Everything the screen can write. Ordered as the screen shows them, so the
#: form and the store cannot drift apart.
FIELDS = (
    # Company
    "legal_name", "dba", "usdot", "mc_number", "ifta_account",
    "base_jurisdiction", "phone", "email",
    # Home Base
    "home_street", "home_city", "home_state", "home_zip",
    # Home Time Zone
    "home_time_zone",
)

BLANK = {name: "" for name in FIELDS}


def get() -> dict:
    """The carrier, or a blank one.

    **Never None.** A screen that has to check for absence before it can render
    is a screen that will forget to, and an empty carrier is a perfectly valid
    state -- it is the state every new node starts in.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM carrier WHERE carrier_id = ?", (ROW_ID,)).fetchone()
    record = dict(BLANK)
    record["configured"] = False
    if row is not None:
        stored = dict(row)
        record.update({name: stored.get(name) or "" for name in FIELDS})
        record["configured"] = bool(record["legal_name"])
        record["updated_at"] = stored.get("updated_at", "")
    return record


def save(values: dict) -> dict:
    """Write the carrier and make the home time zone take effect immediately.

    Returns the stored record. Unknown keys are ignored rather than refused: the
    form posts a CSRF token and a submit button along with the fields, and
    failing the save over those would be theatre.
    """
    from dispatch.models import _utc_now

    incoming = {name: str(values.get(name, "") or "").strip() for name in FIELDS}
    stamp = _utc_now()

    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM carrier WHERE carrier_id = ?", (ROW_ID,)).fetchone()
        if exists:
            conn.execute(
                "UPDATE carrier SET %s, updated_at = ? WHERE carrier_id = ?"
                % ", ".join("%s = ?" % name for name in FIELDS),
                [incoming[name] for name in FIELDS] + [stamp, ROW_ID])
        else:
            conn.execute(
                "INSERT INTO carrier (carrier_id, %s, created_at, updated_at) "
                "VALUES (%s)" % (", ".join(FIELDS),
                                 ", ".join("?" * (len(FIELDS) + 3))),
                [ROW_ID] + [incoming[name] for name in FIELDS] + [stamp, stamp])

    apply_to_environment()
    return get()


def apply_to_environment() -> str:
    """Make the declared home time zone the one `clock` reads. Returns it.

    WHY THIS EXISTS RATHER THAN `clock` READING THE DATABASE. `clock.home_today()`
    is called from `__post_init__` on several dataclasses and from properties
    like `is_expired` -- hot paths, on every record. A database read in there
    would be a query per date, and it would make `dispatch.clock` depend on
    `dispatch.db`, which `models` imports. **Setting the variable once keeps
    `clock` free of both.**

    Called on save, and once at startup by the portal.

    PRECEDENCE, stated because it will be asked: the declared value wins over an
    environment variable set by hand. A value Mike typed into the screen is a
    value Mike meant; the variable is what a machine with no carrier row falls
    back to.
    """
    declared = (get().get("home_time_zone") or "").strip()
    if declared:
        os.environ[clock.HOME_ZONE_VAR] = declared
    return clock.home_zone_name()


def missing() -> list:
    """Which facts are not set yet, in plain words.

    *Degradation is permitted. Incapacity is not.* Nothing here blocks Dispatch
    from starting or from running a load. A surface that needs one of these says
    `UNCONFIGURED` and names it, exactly as the connectors do.
    """
    record = get()
    labels = {
        "legal_name": "Company legal name",
        "usdot": "USDOT number",
        "mc_number": "MC number",
        "ifta_account": "IFTA account number",
        "base_jurisdiction": "IFTA base jurisdiction",
        "home_city": "Home base city",
        "home_state": "Home base state",
        "home_time_zone": "Home time zone",
    }
    return [label for name, label in labels.items() if not record.get(name)]
