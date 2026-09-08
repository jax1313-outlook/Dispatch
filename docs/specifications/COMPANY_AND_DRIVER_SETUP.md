# SPECIFICATION — Company and Driver setup

**Status: SPECIFIED, NOT BUILT. Not authorized.**
Raised by Owner ruling 2026-09-08. Nothing in this document authorizes code.

---

## WHY IT EXISTS

> *"This is a gap I never thought of and will need to be addressed in a system
> setup screen we have yet to create. I never thought of needing a setup screen
> to enter the needed information regarding the Company and the Driver using
> Dispatch until now."* — Mike Zachary, 2026-09-08

It was found the way real gaps are found: a test failed for four hours a day
because Dispatch stamped dates in UTC while the business lives in Eastern. The
fix needed a home time zone, and there was nowhere in Dispatch to put one.

**The home time zone is not the interesting part.** It is the first item in a
category that has no home: **Operational Static Information** — the facts about
this carrier and this driver that almost never change, that every screen assumes,
and that currently live in environment variables, in code defaults, or nowhere at
all.

This is the tab walk's **F-6** in a different disguise: *the settings that gate
Dispatch are the only ones you cannot set from Dispatch.*

---

## WHAT BELONGS ON IT

Everything here is currently hardcoded, defaulted, or absent.

### Carrier

| Field | Today | Why it matters |
|---|---|---|
| Legal name | Absent | Every notice, every rate confirmation, every packet |
| DBA | Absent | What the customer calls him |
| **Home terminal address** | Absent | The IFTA and HOS home base |
| **Home time zone** | `DISPATCH_HOME_TIMEZONE`, defaulted to `America/New_York` | **The business day.** `dispatch/clock.py` |
| USDOT number | Absent | On documents, and on every broker packet |
| MC / docket number | Absent | Same |
| IFTA account number | Absent | On the quarterly return |
| Base jurisdiction | Absent | Which state the IFTA return is filed in |
| Phone, email | Partly in connector config | Arrival notices already need these |

### Driver

| Field | Today | Why it matters |
|---|---|---|
| Name | `"mike"`, defaulted in three places | **Every audit record carries it** |
| CDL number and state | Absent | Compliance documents point at a driver that has no record |
| CDL expiry | In `ComplianceDocument`, entered by hand | Already checked daily; the driver record is what is missing |
| Medical card expiry | Same | Same |
| Home terminal | Absent | HOS |

**Owner ruling, 2026-09-08: up to five drivers. Not one, and not unlimited.**

> *"no it will not always be one driver. I am build MAX at 5 possible."*

Five is a designed number and it settles several things at once. The screen is a
**short list, not a table with paging**; five rows fit on one screen and always
will. There is no search, no filter and no bulk import, and none of those should
be built. It also rules out the opposite simplification: the driver is **not** a
single value that can live in configuration, so `driver: "mike"` in JOE's
configuration and the `"mike"` defaults in the code are placeholders for a
lookup, not settings.

### Truck

Deliberately left out of the first version. Equipment already has records; this
screen is about the facts that have no home, not about duplicating ones that do.

---

## WHAT IT MUST NOT BECOME

**Not a settings dumping ground.** `DISPATCH_JOE_TOKEN`, `PORTAL_HOST`,
`DISPATCH_SECRET_KEY` and the storage roots are **machine** configuration, not
operational facts, and they are read before Dispatch has a database to read from.
They belong to the launcher's Settings screen, which already has them.

The division is simple and should stay so:

| | |
|---|---|
| **Launcher Settings** | What this **machine** needs to start Dispatch at all |
| **Registration** | What this **business** is |

**Not a second source of truth.** The driver's name here is the driver record.
It does not become a copy that drifts from `drivers`.

**Not a wizard that blocks the program.** *Degradation is permitted; incapacity
is not.* Dispatch must start with this screen never having been opened, showing
`UNCONFIGURED` where a fact is missing, exactly as the connectors do now.

---

## OPEN QUESTIONS FOR THE OWNER

1. **Does a blank Registration screen block anything?** The recommendation is
   no — it makes surfaces report `UNCONFIGURED` and nothing more. But a rate
   confirmation with no USDOT number on it is arguably worse than a refusal.
2. ~~One driver or several?~~ **Ruled: up to five.** See above.
3. **Where does it store?** A `carrier` table in the same database is the
   obvious answer, and makes it survivable by the same backup. **Drivers already
   have a table** -- see below.
4. ~~Five drivers, how many nodes?~~ **Ruled 2026-09-08: five nodes, one per
   truck, no base server.** The reason is cost and it is a design constraint:
   *"the cost for a static base operation with a server communicating across the
   vast USA is more than any small Owner Operator can afford."* Ruled *"until
   another cost based solution is discovered"* -- what it forecloses is hosting,
   not reconciliation. `DECISION_LOG.md`, 2026-09-08.
5. **What follows from it, and is open.** Five independent nodes means the
   carrier facts on this screen are typed five times, or copied. Carrier identity
   should be exportable from one node and importable into the others -- it is the
   same USDOT number on all five. The driver list is **not**: each node knows the
   driver in its own truck.

---

## WHAT IS ALREADY TRUE

`dispatch/clock.py` reads `DISPATCH_HOME_TIMEZONE` and defaults to
`America/New_York`. **When this screen is built, it takes ownership of that
value** and the environment variable becomes the override rather than the source.
Nothing else needs to change: every date in the program already comes from
`clock.home_today()`.

---

## WHAT IS ALREADY MULTI-DRIVER, AND WHAT IS NOT

Measured on 2026-09-08 rather than assumed. **More of this exists than the
`"mike"` defaults suggest.**

| | State |
|---|---|
| `drivers` table | **Exists.** `driver_id`, name, licence number and class, phone, email, status, hire date |
| Driver Portal login | **Already multi-driver.** Phone plus PIN through `portal/models/driver_pin_registry.py`; the session carries `driver_id` |
| PIN reset | Already per-driver, with a recovery word |
| Load assignment | Already by `driver_id` |

**What is not:**

| | State |
|---|---|
| **The `drivers` table is empty** | Zero rows on the live node. Nothing has ever created a driver record, which is why the defaults were never noticed |
| **JOE's attribution is free text** | `captured_by` takes whatever string the caller sends. `driver: "nobody"` would be accepted and recorded |
| **`joe.config.json` carries `driver: "mike"`** | A single default, added 2026-09-07. With five drivers it is a placeholder for a lookup |

**So the screen is smaller than it looks.** The driver half is mostly a way to
put rows in a table that already exists, and to make attribution point at one of
them instead of at a string.
