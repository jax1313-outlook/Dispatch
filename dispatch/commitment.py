"""COMMIT: where Booking ends and Dispatch begins.

    Everything before COMMIT is Booking.
    Everything after COMMIT is Mission Execution.

Dispatch is one program with two phases, and an owner-operator lives in the
first one far more than the software ever admitted:

    BOOKING     sweep -> candidate -> brief -> print -> call -> negotiate
                -> gather what is missing -> rate confirmation -> onboarding
                -> COMMIT

    DISPATCH    Outlook event -> booking board -> driver portal -> pickup
                -> transit -> delivery -> closeout -> archive

Many owner-operators spend a whole Monday on the first phase and nothing else.

WHAT COMMIT MEANS
=================

**Not** that a broker awarded the load. Not that a rate was agreed, not that a
carrier packet was sent, not that it is probably going to happen.

COMMIT means: *everything necessary to execute this mission now exists.* The
Mission Record is complete enough to operate from, and the moment the button
is pressed a calendar entry is held, capacity is taken, and the driver's
workflow becomes real.

That is why it is a gate and not a status. A broker saying "it's yours" is a
sentence; committing is an act with consequences.

ONE RECORD THROUGHOUT
=====================

Committing does not create anything. The same record that SWEEP found, or that
JOE took down by voice, carries a commitment timestamp and its purpose changes
from OPPORTUNITY to MISSION. Everything already attached to it -- research,
negotiation history, the brief, the gaps still open -- stays attached, because
it never went anywhere.

The gate has been in the data since the beginning as `accepted_at`. This
module gives it its name.
"""

from __future__ import annotations

#: Where a record sits relative to the gate.
CANDIDATE = "CANDIDATE"
COMMITTED = "COMMITTED"

#: Which phase of the program owns it.
PHASE_BOOKING = "BOOKING"
PHASE_DISPATCH = "DISPATCH"

#: **The commitment timestamp. The only one.**
#:
#: `accepted_at` used to be read here as a legacy name for the same fact, and
#: that alias was the hole: **BOOK wrote `accepted_at`**, so pressing *Book
#: Load* made `is_committed()` true everywhere -- the card left LOADS, took the
#: day on the Booking board, and the brief printed "Committed" -- with none of
#: COMMIT's consequences. Two doors, one gate, and only one of them did the
#: work. Found by the regression audit, 2026-09-16.
#:
#: **Owner's authoritative ruling, 2026-09-16:**
#:
#:     Dispatch contains no operational legacy data requiring backward
#:     compatibility. Do not preserve accepted_at as a commitment compatibility
#:     field ... COMMIT becomes the sole authoritative commitment operation.
#:
#:     One commitment operation. One commitment determination.
#:     One commitment state. One commitment authority.
#:
#: So there is no shim. BOOK records `booked_at`, which is its own fact and
#: opens nothing; `committed_at` is written by COMMIT and by nothing else.
COMMITTED_FIELD = "committed_at"

#: **AWARDED is doctrine and is not built.** The operator named it as the
#: missing middle state: the broker has said the load is his, and rate
#: confirmation, carrier packet, insurance and contact verification are still
#: outstanding. It is deliberately not wired here, because a state nothing sets
#: and nothing reads is a field that lies about being used. When the onboarding
#: steps exist, this is where the state belongs.
AWARDED = "AWARDED"


def committed_at(record: dict) -> str:
    """When this mission was committed, or empty while it is still a candidate.

    **One determination.** It reads the field COMMIT writes, and nothing else.
    """
    return str((record or {}).get(COMMITTED_FIELD) or "").strip()


def is_committed(record: dict) -> bool:
    """Whether Dispatch may act on this record.

    The one question the gate answers. Everything that takes capacity, holds a
    calendar entry, or reaches the driver asks it first.
    """
    return bool(committed_at(record))


def state_of(record: dict) -> str:
    return COMMITTED if is_committed(record) else CANDIDATE


def phase_of(record: dict) -> str:
    """Which half of the program owns this record right now."""
    return PHASE_DISPATCH if is_committed(record) else PHASE_BOOKING


def commit(record: dict, *, when: str) -> dict:
    """Mark the record committed. Additive, and never twice.

    Returns the fields to store. It does not save anything and it does not
    create anything: the record that SWEEP found is the record that runs.
    """
    if is_committed(record):
        return {}
    return {COMMITTED_FIELD: when}


def describe(record: dict) -> dict:
    """What to show about the gate, in the operator's language."""
    if is_committed(record):
        return {"state": COMMITTED, "phase": PHASE_DISPATCH,
                "committed_at": committed_at(record),
                "line": "Committed. Dispatch is running this one."}
    return {"state": CANDIDATE, "phase": PHASE_BOOKING, "committed_at": "",
            "line": "Not committed yet. Still yours to take or leave."}
