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

import re
import uuid
from datetime import datetime, timezone

from dispatch.db import get_connection

# --------------------------------------------------------------- the contract

#: Contract field -> the Mission Card field it corresponds to.
#:
#: Lifted out of `dictation_order()` on 2026-09-08 so it can be **published**
#: rather than re-derived. JOE asks Dispatch what the form is; this is the half
#: of the answer that says which of the Mission Card's fields feed the seventh
#: contract and which are for the card alone.
ONTO_MISSION_CARD = {
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

#: **Owner ruling, 2026-09-08:** *"At this moment, I don't think that which load
#: board the opportunity comes from is significant enough to track."*
#:
#: `source_board` was required and is now optional. The field stays -- rows
#: already carry it and it costs nothing to keep -- but no capture is refused
#: for want of it and nothing asks for it.
#:
#: **It also improves the dedup rule it was part of.** The board was matched as
#: part of a load's identity, so the same load posted to DAT and to Truckstop
#: read as two loads. Brokers post to several boards; a lane and a rate are what
#: make a load the same load, and where it was seen is not.
REQUIRED = ("origin", "destination", "rate")

#: Everything the contract carries. Freeform where the plan says freeform.
#:
#: `source_board` is here and not in REQUIRED: **kept, not tracked.** Rows
#: already carry it, dropping the column would lose what they hold, and a field
#: nobody is asked for costs nothing.
FIELDS = REQUIRED + (
    "source_board", "pieces_weight", "equipment", "pickup_date",
    "delivery_date", "contact", "notes", "captured_via",
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

    onto = ONTO_MISSION_CARD
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

    **Lane and rate. Nothing else.** §2: *"Sparse capture is valid capture ... a
    capture with gaps beats a listing lost to the next screen."* The board came
    off the list on 2026-09-08 by Owner ruling.
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
    from dispatch import rehearsal

    lane = _lane(payload)
    rate = _rate(payload.get("rate"))
    # A rehearsal capture and a live one are never the same load, however alike
    # they look. Merging across that line would put rehearsal data inside an
    # operational record and there would be no tag left to find it by.
    session = rehearsal.active_session_id()
    existing = [e for e in existing
                if str(e.get("rehearsal_session") or "") == session]

    ambiguous = None
    for candidate in existing:
        # The board is deliberately NOT part of a load's identity. Ruled
        # 2026-09-08: a broker posts the same load to several boards, and two
        # sightings of one load are one load. The lane and the rate decide.
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

    # **Tagged at creation** -- rule 1 of the rehearsal data doctrine. This is a
    # no-op when no rehearsal is active, so the operational path is unchanged.
    # It was missing when the contract was first built, which made the newest
    # records in the program the only ones that could not be told apart from
    # real freight.
    from dispatch import rehearsal

    rehearsal.tag_if_active("opportunities", opportunity_id)

    stored = get(opportunity_id)
    stored["verdict"] = "AMBIGUOUS" if verdict == "AMBIGUOUS" else "NEW"
    stored["filled"] = []
    stored["unrecognised_channel"] = unrecognised
    return stored


# ------------------------------------------------------------ the capture call

#: What the Owner says to start a capture. Matched loosely -- speech-to-text
#: drops commas and mishears names, and a capture lost to a strict prefix is the
#: exact failure OPP-CAPTURE was written to prevent.
#: Longest first, always. "capture this one" has to be tried before "capture
#: this", or the opener matches the shorter one and leaves "one" behind at the
#: front of the sentence -- which is how an origin came out as "one Savannah GA".
OPENERS = ("log this one", "capture this one", "log this", "capture this",
           "log a load", "new opportunity")

#: Words that end one field and begin the next. **Anchors, not grammar.** The
#: canonical order is the fast path, not a straitjacket (plan section 6), so the
#: parser looks for landmarks rather than requiring a sentence shape.
_ANCHORS = (
    ("delivery_date", ("deliver by", "delivering", "deliver", "delivery", "drop off", "drops")),
    ("pickup_date", ("picking up", "pick up", "pickup", "pu ", "loads", "loading")),
    ("contact", ("broker is", "broker", "contact is", "contact", "shipper is", "customer is")),
    ("notes", ("notes", "note that", "note:")),
)

#: Equipment the Owner actually runs or is offered. Recognised so it does not end
#: up inside the weight, never validated against -- an unknown trailer type is
#: still a real load and goes to notes rather than being dropped.
_EQUIPMENT = ("dry van", "van", "reefer", "flatbed", "step deck", "stepdeck",
              "box truck", "hotshot", "cargo van", "sprinter", "power only",
              "conestoga", "curtain side", "trailer")


#: The spoken-rate shape, in one place so that reading a rate and removing it
#: from the sentence can never drift apart.
_TENS = ("one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
         "thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
         "twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety")
_SPOKEN_RATE_RE = r"\b(?:%s)\s+(?:hundred|%s)\b" % (_TENS, _TENS)

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
_SCALE_WORDS = {"hundred": 100, "thousand": 1000}

#: A run of number words, however long. "twenty two hundred" is three words and
#: one number; the old pattern only ever looked at two, so it read that as
#: nothing at all.
_NUMBER_RUN_RE = r"\b(?:%s|hundred|thousand)(?:[\s-]+(?:%s|hundred|thousand))*\b" % (
    _TENS, _TENS)

#: What a quantity is measuring, when he says. Pulled out before the rate,
#: because "forty four thousand pounds, twenty two hundred" has two numbers in it
#: and the first one is not the money.
_QUANTITY_UNITS = ("pounds", "pound", "lbs", "lb", "pallets", "pallet",
                   "pieces", "piece", "skids", "skid", "cases", "case",
                   "boxes", "box", "crates", "crate", "bundles", "bundle")

#: A rate a board would actually post. Outside this, a bare number is more
#: likely a unit number, a road, or a year than money.
_PLAUSIBLE_RATE = (100.0, 100000.0)


def _words_to_number(phrase: str):
    """A number said out loud, of any shape. None when it is not one.

    Handles the three ways a rate gets spoken, which the two-word pattern this
    replaces could only manage the first of:

        seven fifty          -> 750     two words, telephone style
        nine hundred fifty   -> 950     a scale in the middle
        twenty two hundred   -> 2200    a scale at the end

    The telephone reading only applies when no scale word appears at all, which
    is what keeps "twenty two hundred" from being read as twenty, then two
    hundred.
    """
    tokens = [t for t in re.split(r"[\s-]+", phrase.lower().strip()) if t]
    if not tokens or any(t not in _NUMBER_WORDS and t not in _SCALE_WORDS for t in tokens):
        return None

    if not any(t in _SCALE_WORDS for t in tokens):
        if (len(tokens) == 2
                and _NUMBER_WORDS[tokens[0]] <= 20
                and 20 <= _NUMBER_WORDS[tokens[1]] <= 99):
            return float(_NUMBER_WORDS[tokens[0]] * 100 + _NUMBER_WORDS[tokens[1]])
        return float(sum(_NUMBER_WORDS[t] for t in tokens))

    total = current = 0
    for token in tokens:
        if token in _SCALE_WORDS:
            scale = _SCALE_WORDS[token]
            current = max(current, 1) * scale
            if scale == 1000:
                total += current
                current = 0
        else:
            current += _NUMBER_WORDS[token]
    return float(total + current)


def _spoken_number(text: str):
    """A rate, however it was said. Returns a float or None -- **never zero as a
    stand-in for silence.**

    Handles `$750`, `750`, `750 dollars`, `seven fifty`, `1,850`. A number it
    cannot read is left for the caller to ask about, because section 6 allows
    exactly one question and this is what it is for.
    """
    t = text.lower().replace(",", "")

    m = re.search(r"\$\s*(\d+(?:\.\d+)?)", t)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:dollars|bucks|usd)\b", t)
    if m:
        return float(m.group(1))

    # Spoken, of any shape. Longest run wins, because "twenty two hundred" and
    # "twenty two" both match and only one of them is the number he said.
    best = None
    for match in re.finditer(_NUMBER_RUN_RE, t):
        value = _words_to_number(match.group(0))
        if value is None:
            continue
        if best is None or len(match.group(0)) > len(best[0]):
            best = (match.group(0), value)
    if best:
        return best[1]

    # A bare number, last, and only inside a range a board would post. Reading a
    # listing aloud, "eighteen fifty" and "1850" are the same act -- but a bare
    # number is also a unit number, a road and a year, so this refuses anything
    # outside what a rate plausibly is rather than guessing.
    for candidate in re.findall(r"\b\d+(?:\.\d+)?\b", t):
        value = float(candidate)
        if _PLAUSIBLE_RATE[0] <= value <= _PLAUSIBLE_RATE[1]:
            return value
    return None


def parse_dictation(text: str) -> dict:
    """Turn a spoken capture into the contract's fields.

    **Pure. No microphone, no network, no database** -- so it is testable
    without hardware, which is the only way a voice feature ever gets tested
    honestly.

    Plan section 6: *"Parsing is tolerant of natural speech (order deviations,
    filler); the canonical order is the fast path, not a straitjacket."*

    Three rules it will not break:

    1. **Nothing is invented.** A field the Owner did not say comes back absent,
       not guessed. Sparse capture is valid capture.
    2. **Nothing he said is discarded.** Text the parser cannot place goes to
       `notes` rather than the floor. A capture that quietly loses half a
       sentence is worse than one that admits it did not understand.
    3. **At most one question, and only about the rate.** `missing` names what a
       caller may ask for; the rate is the only entry that ever justifies asking,
       per section 6.

    Returns `{"fields": {...}, "missing": [...], "heard": "..."}`.
    """
    import re

    heard = " ".join(str(text or "").split())
    body = heard
    low = body.lower()

    # Strip the wake phrase and any name in front of it. Longest match wins, so
    # "capture this one" is taken whole rather than leaving its "one" behind.
    hit = None
    for opener in OPENERS:
        i = low.find(opener)
        if i >= 0 and (hit is None or len(opener) > len(hit[1])):
            hit = (i, opener)
    if hit:
        body = body[hit[0] + len(hit[1]):]
    body = body.lstrip(" :,.-")

    fields, low = {}, body.lower()

    # --- notes first: everything after "notes" is his, verbatim, untouched ---
    for word in ("notes:", "notes", "note that", "note:"):
        i = low.find(word)
        if i >= 0:
            fields["notes"] = body[i + len(word):].strip(" :,.")
            body = body[:i]
            low = body.lower()
            break

    # --- pieces and weight, BEFORE the rate ---
    #
    # "forty four thousand pounds, twenty two hundred" carries two numbers and
    # the first one is not the money. Taking the measured quantity out first
    # means the rate reader never sees it, and it stops the weight ending up
    # inside the destination, which is how "Orlando FL forty four thousand
    # pounds" happened.
    quantity = re.search(
        r"((?:%s|\b[\d,]+(?:\.\d+)?)(?:[\s-]+(?:%s))*)\s*(%s)\b"
        % (_NUMBER_RUN_RE, _TENS, "|".join(_QUANTITY_UNITS)),
        body, flags=re.I)
    if quantity:
        fields["pieces_weight"] = quantity.group(0).strip(" :,.-")
        body = body[:quantity.start()] + " " + body[quantity.end():]
        low = body.lower()

    # --- rate ---
    rate = _spoken_number(body)
    if rate is not None:
        fields["rate"] = rate
        body = re.sub(r"\$\s*[\d,]+(?:\.\d+)?|\b[\d,]+(?:\.\d+)?\s*(?:dollars|bucks|usd)\b",
                      " ", body, flags=re.I)
        # Spoken numbers too -- "seven fifty" left in place ends up inside
        # the destination, which is how "Savannah seven fifty" happens. The
        # longest run goes, not the first two words of it, or "twenty two
        # hundred" leaves "hundred" behind in the city.
        runs = [m.group(0) for m in re.finditer(_NUMBER_RUN_RE, body, flags=re.I)]
        if runs:
            longest = max(runs, key=len)
            body = body.replace(longest, " ", 1)
        else:
            # A bare number that was read as the rate has to go too, or it lands
            # in whatever field claims the text around it.
            body = re.sub(r"\b%s\b" % re.escape(("%g" % rate)), " ", body, count=1)
        low = body.lower()

    # --- anchored segments, taken from the end backwards so each one only ever
    #     claims the text after its own landmark ---
    found = []
    for key, words in _ANCHORS:
        for word in words:
            i = low.find(word)
            if i >= 0:
                found.append((i, key, len(word)))
                break
    for start, key, width in sorted(found, reverse=True):
        if key in fields:
            continue
        value = body[start + width:].strip(" :,.-")
        if value:
            fields[key] = value
        body = body[:start]
        low = body.lower()

    # --- equipment, before the lane, so "dry van" never lands in a city ---
    for kind in sorted(_EQUIPMENT, key=len, reverse=True):
        # **Word boundaries, always.** "van" lives inside "Savannah", and a
        # substring match here once turned a destination into "Sa nah". A parser
        # that quietly mangles a city is worse than one that misses equipment.
        m = re.search(r"\b%s\b" % re.escape(kind), low)
        if m:
            fields["equipment"] = body[m.start():m.end()].strip()
            body = body[:m.start()] + " " + body[m.end():]
            low = body.lower()
            break

    # --- the lane: "X to Y", the one shape every board listing shares ---
    m = re.search(r"\bto\b", low)
    if m:
        left, right = body[:m.start()], body[m.end():]
        # The destination ends where the sentence does. "Tampa. One pallet" is
        # two facts and only the first is a city; the rest is cargo and is kept.
        halves = re.split(r"[.,;]", right, maxsplit=1)
        destination = halves[0].strip(" :,.-")
        tail = halves[1].strip(" :,.-") if len(halves) > 1 else ""
        # The board is whatever leads, before the origin. "DAT. Jacksonville"
        parts = [p.strip(" :,.-") for p in re.split(r"[.,;]| - ", left) if p.strip(" :,.-")]
        if len(parts) >= 2:
            fields["source_board"] = parts[0]
            fields["origin"] = " ".join(parts[1:]).strip()
        elif parts:
            fields["origin"] = parts[0]
        if destination:
            fields["destination"] = destination
        # Whatever followed the destination is still his. Pieces and weight ride
        # here most often, and the contract takes them freeform.
        body = tail

    # --- whatever is left is still his. It goes to notes, never to the floor ---
    leftover = " ".join(body.split()).strip(" :,.-")
    if leftover:
        fields["notes"] = (fields.get("notes", "") + " | " + leftover).strip(" |")

    # Pieces and weight ride inside whatever segment carried them; the contract
    # takes them freeform and the plan says so.
    for key in ("pieces_weight",):
        fields.setdefault(key, "")

    missing = [k for k in REQUIRED if not str(fields.get(k) or "").strip()]
    if fields.get("rate") is not None:
        missing = [m for m in missing if m != "rate"]

    return {"fields": {k: v for k, v in fields.items() if v not in ("", None)},
            "missing": missing,
            "heard": heard}


def one_question(missing: list) -> str:
    """The single question a capture may ask, and only about the rate.

    Section 6: *"Joe asks at most one question, and only for the rate. Missing
    rate -> 'RATE?' -- Owner answers or says 'skip'; Joe logs either way. Never
    more than one question per capture; speed outranks completeness."*

    Anything else missing is logged missing. Returns "" when there is nothing
    worth asking.
    """
    return "RATE?" if "rate" in (missing or []) else ""


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
