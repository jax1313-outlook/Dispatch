"""Opportunity capture — the seventh contract.

**OPP-CAPTURE v1.0 §§2–4.** The Owner reads a board with his own eye, dictates
what he sees, and Joe logs it. **No board automation, scraping, screen capture
or session tooling exists anywhere in this workflow** and none may be added
here — the input is the Owner's eye and voice, period.

**Class 1.** Internal, reversible, touches no Mission Record and no outside
party. No read-back. *Speed is the point: capture in seconds, move to the next
listing.*

WHAT LIVES HERE
===============

The store, the canonical field order, and the deduplication rule. The endpoint
is in `portal/routes/joe_api.py`; this module knows nothing about HTTP.

**Vendor-agnostic per the Contract-First Rule.** `source_board` is stored **as
the Owner says it** — never an enum of vendor products, never validated against
a list of boards. A board Level 1 signs up for next year must not require a code
change to be captured. `captured_via` is named by nature — VOICE, CHAT,
MISSIONSCREEN, SWEEP — never by product.

FIELD ORDER IS NOT DECIDED HERE
===============================

§6 is explicit: *"the form definition in Dispatch is the single source of truth
for field order, and Code derives the parser's expected sequence from it — the
protocol follows the form automatically if the form ever changes."*

So `dictation_order()` reads `mission_template.TEMPLATE` and never hardcodes a
sequence. Reorder the Mission Card and the dictation protocol reorders with it.
That is also why capture and Mission Record are the same shape from birth:
graduation on "book it" is a promotion, not a field mapping.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from dispatch.db import get_connection

# --------------------------------------------------------------- the contract

#: Required by voice: board, lane, rate. **Everything after money is optional.**
#: §2: *"Sparse capture is valid capture ... A capture with gaps beats a listing
#: lost to the next screen."*
REQUIRED = ("source_board", "origin", "destination", "rate")

#: Everything the contract carries. Freeform where the plan says freeform.
FIELDS = REQUIRED + (
    "pieces_weight", "equipment", "pickup_date", "delivery_date",
    "contact", "notes", "captured_via",
)

#: Channels, **named by nature and never by product** (Contract-First Rule).
CHANNELS = ("VOICE", "CHAT", "MISSIONSCREEN", "SWEEP")

#: What a capture is when nothing has happened to it yet.
STATE_OPEN = "OPEN"

#: §3: *"the engine never silently guesses two loads are one."*
FLAG_POSSIBLE_DUPLICATE = "POSSIBLE DUPLICATE"

#: How far two rates may differ and still be one load. A board re-post often
#: moves the number a little; a different load usually moves it a lot.
RATE_TOLERANCE = 0.10


class OpportunityError(ValueError):
    """A capture could not be logged, and says why."""


# ------------------------------------------------------- the dictation order

def dictation_order() -> tuple:
    """The canonical dictation sequence, **derived from the Mission Card.**

    Never hardcoded. §6 makes the form definition the single source of truth,
    so this maps the contract's fields onto the order the form already declares
    and follows it if the form changes.

    Fields the Mission Card has no counterpart for keep their contract order at
    the end — `source_board` and `captured_via` are capture-time facts about
    where a listing came from, not freight facts the card carries.
    """
    from dispatch import mission_template as mt

    #: contract field -> the Mission Card field it corresponds to.
    onto = {
        "origin": "pickup_location",
        "destination": "delivery_location",
        "pieces_weight": "cargo_lines",
        "equipment": "service",
        "rate": "rate",
        "pickup_date": "pickup_window",
        "delivery_date": "delivery_window",
        "contact": "customer_poc",
        "notes": "notes",
    }
    card = [f.key for f in mt.TEMPLATE]
    positioned = sorted(
        (k for k in FIELDS if onto.get(k) in card),
        key=lambda k: card.index(onto[k]),
    )
    rest = [k for k in FIELDS if k not in positioned]
    return tuple(positioned + rest)


# --------------------------------------------------------------- normalising

def _clean(value) -> str:
    return str(value if value is not None else "").strip()


def _rate(value):
    """A rate, or None. **Never invented, never defaulted to zero** — zero is a
    number a broker could have said, and a missing rate is not free freight."""
    text = _clean(value).replace("$", "").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        raise OpportunityError("rate must be a number, or left out entirely")


def _lane(record: dict) -> tuple:
    return (_clean(record.get("origin")).lower(),
            _clean(record.get("destination")).lower())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate(payload: dict) -> list:
    """What is missing. Empty list means the capture is loggable.

    Only the four. Everything else may be absent and the capture still stands.
    """
    problems = []
    for key in REQUIRED:
        if key == "rate":
            continue
        if not _clean(payload.get(key)):
            problems.append("%s is required" % key)
    if _rate(payload.get("rate")) is None:
        problems.append("rate is required")
    # **The channel is deliberately not validated here.** It is a server-side
    # classification of how a capture arrived, not freight the Owner dictated,
    # and §2 is clear about the priority: *"a capture with gaps beats a listing
    # lost to the next screen."* Refusing a whole listing over a label would
    # invert that. `capture()` falls back to CHAT and says so in the audit,
    # which is tolerance without silence.
    return problems


# ---------------------------------------------------------------- the store

def _row_to_record(row) -> dict:
    record = {k: row[k] for k in row.keys()}
    trail = record.get("origins") or ""
    record["origins"] = [t for t in trail.split("|") if t]
    return record


def all_open() -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM opportunities WHERE state=? ORDER BY captured_at DESC",
            (STATE_OPEN,),
        ).fetchall()
    return [_row_to_record(r) for r in rows]


def get(opportunity_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM opportunities WHERE opportunity_id=?",
            (str(opportunity_id),),
        ).fetchone()
    return _row_to_record(row) if row else None


# ----------------------------------------------------------- deduplication

def _dates_overlap(a: str, b: str) -> bool | None:
    """Whether two pickup dates describe the same day.

    **Returns None when it cannot tell** — one of them is missing. That is not
    a match and not a mismatch, and pretending otherwise is how two loads
    silently become one. Sparse capture makes this common, so it is a real
    third answer rather than an edge case.
    """
    a, b = _clean(a), _clean(b)
    if not a or not b:
        return None
    return a[:10].lower() == b[:10].lower()


def classify(payload: dict, existing: list) -> tuple:
    """`(verdict, record_or_None)` — MATCH, AMBIGUOUS or NEW.

    §3, and the rule that governs the whole thing: *"Ambiguous: new record
    flagged POSSIBLE DUPLICATE ... the engine never silently guesses two loads
    are one."*

    A different board or a different lane is a different load; nothing else is
    considered. Same board and same lane makes it a candidate, and then the
    money and the date have to agree before it is called one load.
    """
    board = _clean(payload.get("source_board")).lower()
    lane = _lane(payload)
    rate = _rate(payload.get("rate"))

    ambiguous = None
    for candidate in existing:
        if _clean(candidate.get("source_board")).lower() != board:
            continue
        if _lane(candidate) != lane:
            continue

        other = candidate.get("rate")
        if rate is None or other is None:
            ambiguous = ambiguous or candidate
            continue
        spread = abs(rate - other) / max(rate, other, 1.0)
        if spread > RATE_TOLERANCE:
            # Same lane, same board, materially different money. Could be a
            # re-post at a new rate, could be a second load. Not ours to decide.
            ambiguous = ambiguous or candidate
            continue

        overlap = _dates_overlap(payload.get("pickup_date"),
                                 candidate.get("pickup_date"))
        if overlap is True:
            return "MATCH", candidate
        ambiguous = ambiguous or candidate

    if ambiguous is not None:
        return "AMBIGUOUS", ambiguous
    return "NEW", None


# --------------------------------------------------------------- capture

def capture(payload: dict, *, driver: str, channel: str = "") -> dict:
    """Log one Opportunity. **Class 1 — no read-back, no confirmation.**

    Returns the stored record with `verdict` on it: NEW, MERGED or AMBIGUOUS.

    On MERGED, §3 governs what may change: *"Sweep data enriches sparse voice
    captures (fills gaps), never overwrites Owner-dictated values."* So a merge
    fills empty fields and **overwrites nothing**, whichever direction it came
    from. Where the second sighting came from is appended to the record's own
    origin trail, so a card can show *captured VOICE 09:14, seen SWEEP 09:30*.
    """
    driver = _clean(driver)
    if not driver:
        raise OpportunityError(
            "a capture carries somebody's authority; driver is required")

    problems = validate(payload)
    if problems:
        raise OpportunityError("; ".join(problems))

    asked = (_clean(payload.get("captured_via")) or _clean(channel) or "CHAT").upper()
    via = asked if asked in CHANNELS else "CHAT"
    unrecognised = "" if via == asked else asked
    now = _utc_now()

    verdict, twin = classify(payload, all_open())

    if verdict == "MATCH":
        filled = []
        with get_connection() as conn:
            for key in FIELDS:
                if key in ("source_board", "captured_via"):
                    continue
                incoming = payload.get(key)
                incoming = _rate(incoming) if key == "rate" else _clean(incoming)
                if not incoming:
                    continue
                # Fills a gap. Never replaces what is already recorded.
                if twin.get(key) in (None, "", 0):
                    conn.execute(
                        "UPDATE opportunities SET %s=? WHERE opportunity_id=?" % key,
                        (incoming, twin["opportunity_id"]))
                    filled.append(key)
            trail = list(twin.get("origins") or []) + ["%s %s" % (via, now)]
            conn.execute(
                "UPDATE opportunities SET origins=?, updated_at=? "
                "WHERE opportunity_id=?",
                ("|".join(trail), now, twin["opportunity_id"]))
        merged = get(twin["opportunity_id"])
        merged["verdict"] = "MERGED"
        merged["filled"] = filled
        merged["unrecognised_channel"] = unrecognised
        return merged

    opportunity_id = "OPP-%s" % uuid.uuid4().hex[:10].upper()
    flag = FLAG_POSSIBLE_DUPLICATE if verdict == "AMBIGUOUS" else ""
    row = {
        "opportunity_id": opportunity_id,
        "source_board": _clean(payload.get("source_board")),
        "origin": _clean(payload.get("origin")),
        "destination": _clean(payload.get("destination")),
        "rate": _rate(payload.get("rate")),
        "pieces_weight": _clean(payload.get("pieces_weight")),
        "equipment": _clean(payload.get("equipment")),
        "pickup_date": _clean(payload.get("pickup_date")),
        "delivery_date": _clean(payload.get("delivery_date")),
        "contact": _clean(payload.get("contact")),
        "notes": _clean(payload.get("notes")),
        "captured_via": via,
        "captured_by": driver,
        "captured_at": now,
        "updated_at": now,
        "state": STATE_OPEN,
        "flag": flag,
        "possible_duplicate_of": twin["opportunity_id"] if twin else "",
        "origins": "%s %s" % (via, now),
    }
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO opportunities (%s) VALUES (%s)"
            % (", ".join(row), ", ".join("?" * len(row))),
            tuple(row.values()))

    stored = get(opportunity_id)
    stored["verdict"] = "AMBIGUOUS" if verdict == "AMBIGUOUS" else "NEW"
    stored["filled"] = []
    stored["unrecognised_channel"] = unrecognised
    return stored


def echo(record: dict) -> str:
    """The line Joe says back. §6: *"LOGGED. OPPORTUNITY [id]. [board], [lane],
    $[rate], [pickup]."*

    Declarative, in the locked voice. Nothing that was not captured appears.
    """
    parts = ["LOGGED.", "OPPORTUNITY %s." % record.get("opportunity_id", "")]
    board = _clean(record.get("source_board"))
    if board:
        parts.append("%s," % board.upper())
    lane = "%s TO %s" % (_clean(record.get("origin")).upper(),
                         _clean(record.get("destination")).upper())
    parts.append("%s," % lane)
    rate = record.get("rate")
    if rate is not None:
        parts.append("$%s," % ("%.2f" % rate).rstrip("0").rstrip("."))
    pickup = _clean(record.get("pickup_date"))
    if pickup:
        parts.append("PICKUP %s." % pickup.upper())
    line = " ".join(parts).rstrip(",")
    if record.get("flag"):
        line += " FLAGGED %s." % record["flag"]
    if record.get("verdict") == "MERGED":
        line = line.replace("LOGGED.", "MERGED INTO EXISTING.", 1)
    return line
