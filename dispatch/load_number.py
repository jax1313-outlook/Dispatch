"""The Load Number. Every Mission Record has one, and there are no exceptions.

    ONE MISSION TEMPLATE
    MULTIPLE INTAKE METHODS
    ONE MISSION RECORD
    ONE WORKFLOW

The Load Number is the retrieval key for the mission, the archive, the library,
document linkage, communication linkage and COMI processing. A record without
one is an orphan: it exists, and nothing can find it again.

So the number is assigned **at the start of intake, not at the end.** JOE hands
out the number before the template is filled in, which is what lets the number
be the email subject and lets COMI recognise the reply as mission intake rather
than as another message from a broker.

Two origins, one field:

    Supplied     847261, CVS-44912, ABC123 -- stored byte for byte.
    Generated    L1-8F42QC -- when nobody else has numbered the work.

**A generated number is not pretending to be a broker number.** It is a
legitimate Dispatch Load Number for work that arrived without one -- a direct
customer, a phone call, a courier run. The record says which of the two it is,
because "did they give us this number or did we" is a question that decides who
to quote it to.
"""

from __future__ import annotations

import re
import secrets

#: The house prefix. COMI treats any inbound subject beginning with this as
#: mission intake, so it is the hinge the whole email path turns on.
LOAD_NUMBER_PREFIX = "L1-"

#: Length of the generated code. Six characters keeps it short enough to read
#: aloud over a phone and write on a bill of lading, and long enough that the
#: numbers cannot be counted through.
LOAD_NUMBER_LENGTH = 6

#: No I, O, 0 or 1. A load number gets read over a phone at a gate and written
#: on paper in a cab; a character pair that can be misheard or miswritten costs
#: more than the handful of combinations it saves.
LOAD_NUMBER_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"

#: Where the number came from. Recorded, never inferred later.
SUPPLIED = "SUPPLIED"
GENERATED = "GENERATED"

_GENERATED_RE = re.compile(
    r"^%s[%s]{%d}$" % (re.escape(LOAD_NUMBER_PREFIX),
                       re.escape(LOAD_NUMBER_ALPHABET), LOAD_NUMBER_LENGTH),
    re.I)


class LoadNumberError(ValueError):
    """A Mission Record cannot be numbered, and says why."""


def is_generated(load_number: str) -> bool:
    """Whether this is one of ours rather than one we were given."""
    return bool(_GENERATED_RE.match(str(load_number or "").strip()))


def format_generated(code: str) -> str:
    return f"{LOAD_NUMBER_PREFIX}{str(code).upper()}"


def next_generated(existing=None) -> str:
    """A fresh house number, not the next one.

    Sequential numbering made every load countable: anyone holding L1-0007
    could try L1-0006 and L1-0008 and reach a different customer's load. The
    number is a shared credential by design -- any member of a broker's staff
    can use it, because the contact at 08:00 is not the contact at 18:00 and
    managing who-has-access would make this a security company. That model is
    right. What it needs is a number nobody can count through.

    So: drawn at random from an unambiguous alphabet, checked against what is
    already in use. Everything else about the scheme is unchanged.
    """
    taken = {str(v or "").strip().upper() for v in (existing or [])}
    for _ in range(64):
        candidate = format_generated(
            "".join(secrets.choice(LOAD_NUMBER_ALPHABET)
                    for _ in range(LOAD_NUMBER_LENGTH)))
        if candidate.upper() not in taken:
            return candidate
    raise LoadNumberError(
        "could not draw an unused Dispatch load number; archive completed "
        "missions before opening another")


def assign(supplied: str = "", *, existing=None) -> dict:
    """The Load Number for a new mission, and where it came from.

    A supplied number is stored exactly as given -- no case folding, no
    stripping of dashes, no normalising. `CVS-44912` is what the customer will
    quote back, and a number we tidied up is a number that no longer matches
    theirs on an invoice.
    """
    value = str(supplied or "").strip()
    if value:
        return {"load_number": value, "origin": SUPPLIED, "supplied": value}
    return {"load_number": next_generated(existing), "origin": GENERATED,
            "supplied": ""}


def is_mission_intake(subject: str) -> bool:
    """COMI's rule: a subject beginning `L1-` is mission intake.

    Not a general communication, not a broker message, not a customer message.
    The subject survives the driver's reply untouched, which is what threads the
    completed template back to the number JOE issued when he asked for it.
    """
    return str(subject or "").strip().upper().startswith(LOAD_NUMBER_PREFIX)


def from_subject(subject: str) -> str:
    """The Load Number carried on an intake subject line, or empty."""
    text = str(subject or "").strip()
    if not is_mission_intake(text):
        return ""
    return text.split()[0].strip() if text.split() else ""
