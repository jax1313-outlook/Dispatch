"""What Joe may do without asking, what he must read back, and what he may not do.

    Joe may think broadly.
    Joe may act within delegated authority.
    Joe may never replace human command authority.

Three classes, and the rule is that **confirmation matches consequence**:

    Class 1  EXECUTE AND REPORT     low-risk, reversible, covered by direction
    Class 2  READ BACK, THEN EXECUTE external comms and persistent changes
    Class 3  RECOMMEND AND HOLD     decisions reserved to human command

Class 2 exists because of transcription risk, not because of trust. A phone
number heard wrongly and written silently is a corrupted record nobody knows
is corrupted; read back, it is caught in four seconds. So the read-back states
the *material effect* -- the field, what it holds now, what it would hold --
and nothing changes until a confirmation comes back.

Class 3 is the hard wall. Committing a load, signing, spending beyond policy,
changing doctrine: Joe does the staff work and waits. Limits on authority do
not limit awareness, investigation or recommendation.

PLATFORM AGNOSTIC
=================

Joe is an operational role. Nothing here names a vendor -- these classes hold
whatever brain is rented and whatever channel the words arrive through, because
they describe consequence rather than technology. The first certified stack is
one implementation, not the definition.
"""

from __future__ import annotations

CLASS_EXECUTE = 1
CLASS_READ_BACK = 2
CLASS_HOLD = 3

#: Class 1. Done, then reported.
EXECUTE_ACTIONS = (
    "mission-status", "driver-status", "facility-intel", "schedule-fit",
    "read-email", "summarise", "research", "retrieve", "draft", "compare",
    "add-note",
)

#: Class 2. Read back, then done on confirmation.
READ_BACK_ACTIONS = (
    "mission-record-update", "send-notice", "send-email", "change-contact",
    "change-stops", "change-schedule", "notify-broker",
)

#: Class 3. Recommended, then held. Joe does the staff work and waits.
HOLD_ACTIONS = (
    "commit-load", "accept-load", "reject-load", "sign", "spend",
    "reopen-plan", "change-doctrine", "change-policy",
)

#: The status vocabulary, locked. Joe's output is declarative operational
#: statement, never chat and never filler.
ON_TIME = "ON TIME"
DELAYED = "DELAYED"
AT_RISK = "AT RISK"
STATUS_VOCABULARY = (ON_TIME, DELAYED, AT_RISK)


class AuthorityError(Exception):
    """An action outside delegated authority, saying which and why."""


def class_of(action: str) -> int:
    """Which class an action falls in. Unknown actions are held, never run.

    An action nobody classified is an action nobody thought about, and the safe
    reading of that is Class 3.
    """
    name = str(action or "").strip().lower()
    if name in EXECUTE_ACTIONS:
        return CLASS_EXECUTE
    if name in READ_BACK_ACTIONS:
        return CLASS_READ_BACK
    return CLASS_HOLD


def needs_confirmation(action: str) -> bool:
    return class_of(action) == CLASS_READ_BACK


def is_reserved(action: str) -> bool:
    """Whether this is the driver's decision and nobody else's."""
    return class_of(action) == CLASS_HOLD


def read_back(*, field_label: str, current, proposed) -> str:
    """What Joe says before a Class 2 change, stating the material effect.

    Names the field, what it holds now and what it would hold. "Updated the
    broker email" is a report; this is the sentence that lets a mishearing be
    caught before it becomes a record.
    """
    current = str(current or "").strip()
    proposed = str(proposed or "").strip()
    if current:
        return "%s is currently %s. Change to %s. Confirm?" % (
            field_label, current, proposed)
    return "%s has no entry. Set to %s. Confirm?" % (field_label, proposed)


def held(action: str, reasoning: str = "") -> dict:
    """The Class 3 answer: the staff work, then a stop.

    Not a refusal. Joe has done the thinking and is waiting, which is a
    different thing from being unable.
    """
    return {
        "ok": False,
        "class": CLASS_HOLD,
        "held": True,
        "action": action,
        "note": "That one is yours. I have not done it.",
        "reasoning": reasoning,
    }


def refuse_unconfirmed(action: str) -> dict:
    """The Class 2 answer when nothing was read back."""
    return {
        "ok": False,
        "class": CLASS_READ_BACK,
        "needs_confirmation": True,
        "action": action,
        "note": "Read it back to me first. Nothing has changed.",
    }


def report(parts: list) -> str:
    """A result report, part by part.

        EMAIL SENT. MISSION RECORD UPDATED. CALENDAR UPDATE FAILED.
        CURRENT MISSION SCHEDULE REMAINS UNCHANGED.

    No false success and no silent failure: every part says what happened to
    it, and a part that failed says so in the same sentence as the parts that
    did not.
    """
    return " ".join(str(p).strip().rstrip(".") + "." for p in parts if str(p).strip())
