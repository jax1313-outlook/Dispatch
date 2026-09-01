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
    Generated    L1-0001, L1-0002 -- when nobody else has numbered the work.

**A generated number is not pretending to be a broker number.** It is a
legitimate Dispatch Load Number for work that arrived without one -- a direct
customer, a phone call, a courier run. The record says which of the two it is,
because "did they give us this number or did we" is a question that decides who
to quote it to.
"""

from __future__ import annotations

import re

#: The house prefix. COMI treats any inbound subject beginning with this as
#: mission intake, so it is the hinge the whole email path turns on.
LOAD_NUMBER_PREFIX = "L1-"

#: Width of the generated sequence. Four digits keeps the number short enough
#: to read aloud over a phone and write on a bill of lading.
LOAD_NUMBER_DIGITS = 4
LOAD_NUMBER_MAX = 10 ** LOAD_NUMBER_DIGITS - 1

#: Where the number came from. Recorded, never inferred later.
SUPPLIED = "SUPPLIED"
GENERATED = "GENERATED"

_GENERATED_RE = re.compile(r"^%s(\d+)$" % re.escape(LOAD_NUMBER_PREFIX), re.I)


class LoadNumberError(ValueError):
    """A Mission Record cannot be numbered, and says why."""


def is_generated(load_number: str) -> bool:
    """Whether this is one of ours rather than one we were given."""
    return bool(_GENERATED_RE.match(str(load_number or "").strip()))


def format_generated(sequence: int) -> str:
    return f"{LOAD_NUMBER_PREFIX}{int(sequence):0{LOAD_NUMBER_DIGITS}d}"


def taken_sequences(load_numbers) -> set:
    """The generated sequences already in use, ignoring supplied numbers."""
    taken = set()
    for value in load_numbers or []:
        match = _GENERATED_RE.match(str(value or "").strip())
        if match:
            taken.add(int(match.group(1)))
    return taken


def next_generated(existing=None) -> str:
    """The lowest free house number.

    Gap-filling, like the internal mission number: a number freed by an
    archived mission comes back into use rather than marching the sequence
    upward forever.
    """
    taken = taken_sequences(existing)
    for candidate in range(1, LOAD_NUMBER_MAX + 1):
        if candidate not in taken:
            return format_generated(candidate)
    raise LoadNumberError(
        "all %d Dispatch load numbers are in use; archive completed missions "
        "before opening another" % LOAD_NUMBER_MAX)


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
