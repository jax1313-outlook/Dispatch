"""Log loads by voice from the Driver Cockpit.

Owner direction, 2026-09-15: a second voice channel created wholly inside
Dispatch, separate from any outside platform, *"used to capture load board
information"* -- then *"i use head set"* and *"Start the voice mic button on the
cockpit next"*. The need it serves is CO-2's: *"A rapid way to capture load
information for later decision making."* (His full words, which name a vendor,
are in the decision-log proposal, not in contract code.)

WHAT THIS IS, AND WHAT IT IS NOT
================================

The tablet turns speech into words -- the browser's own speech recognition, or
the keyboard's microphone key. **Only those words reach Dispatch.** No audio is
sent here, stored here or processed here, and nothing in this module listens to
anything. There is no speech model in Dispatch (Rent-the-Trailer; no AI built
or hosted in-house).

The words are read by the existing dictation reader, exactly as the seventh
contract reads them:

  * `dispatch.opportunity.parse_dictation` -- the words into fields
  * `dispatch.opportunity.capture`         -- dedup, merge, rehearsal tag
  * `portal.models.opportunity_card.from_capture` -- the card at capture time
  * `dispatch.opportunity.echo`            -- the read-back
  * `portal.models.opportunity_card.discard_expired` -- clears expired
    uncommitted cards first, as a paste does

Rule 15, Reuse Before Create: the only new thing here is saying NEXT between
loads.

**Owner rulings, 2026-09-15.** On "NOT LOGGED. LANE NOT HEARD.": *"i do not know
where this came from. I do not use lane for any thing. delete."* -- then **"1a"**:
no lane message and no question; a load with no pickup or delivery city still
saves what was heard. On the rate question: **"3 yes stop asking rate"** -- a load
with no rate is logged and the read-back says RATE PENDING. And *"clear expired
cards too"*. So every load with at least one fact is logged, nothing is asked,
and only a load with nothing in it is NOT LOGGED.

**Capture only.** *"Capture only: it never commits, passes or sends anything."*
Nothing here commits, passes or sends. The one removal it makes is the one a
paste makes: uncommitted cards whose pickup has already gone by (D12), through
the card model's own gate, which never touches a committed load. Class 1.

The ratified contract `POST /api/joe/opportunity` is not called and not
changed: it is a machine contract with a bearer token the tablet never holds
(CONOPS R9). This is the cockpit's browser path to the same functions, the way
`/loads/paste` is.
"""

from __future__ import annotations

import re

#: The capture channel, named by nature. One of `dispatch.opportunity.CHANNELS`;
#: a test holds that it stays one of them.
CHANNEL = "VOICE"

#: Said on its own between two listings. "next load" and "next one" are the same
#: word. "next Tuesday" and "next week" are a pickup date, not a new load, so a
#: day word after it keeps it inside the listing.
_DAY_WORDS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
              "sunday", "week", "weekend", "day", "month", "morning", "afternoon",
              "evening", "night", "tonight")
_NEXT_RE = re.compile(
    r"\bnext\b(?![\s,.;:!?-]+(?:%s)\b)(?:[\s,.;:!?-]+(?:load|one)\b)?[\s,.;:!?-]*"
    % "|".join(_DAY_WORDS),
    flags=re.IGNORECASE)

#: Status words for one load in the read-back list. There is no question status:
#: nothing asks (Owner ruling 2026-09-15, "3 yes stop asking rate").
LOGGED = "LOGGED"
MERGED = "MERGED"
NOT_LOGGED = "NOT LOGGED"

_OPPORTUNITY_ID_RE = re.compile(r"\s*OPPORTUNITY [A-Z]+-[0-9A-F]+\.", flags=re.IGNORECASE)


def split_loads(text: str) -> list:
    """The listings in one submission, in the order they were said.

    NEXT on its own separates them, spoken or typed on its own line. Empty
    pieces -- "next next", a trailing "next" -- are dropped; they carry no load.
    """
    pieces = _NEXT_RE.split(str(text or ""))
    return [" ".join(p.split()) for p in pieces if p and p.strip(" \t\r\n.,;:!?-")]


def _lane(fields: dict) -> str:
    return " TO ".join(str(fields.get(k) or "").strip().upper()
                       for k in ("origin", "destination") if str(fields.get(k) or "").strip())


def spoken(line: str) -> str:
    """The read-back as the headset says it: the echo, without the record number.

    The number stays on the screen and on the card. Read aloud it is ten
    letters and digits of noise between the lane and the rate.
    """
    return " ".join(_OPPORTUNITY_ID_RE.sub("", str(line or "")).split())


def _refused(words: str, driver: str, note: str, say: str, fields: dict) -> dict:
    from dispatch import audit

    audit.record(action="opportunity-capture", driver=driver, channel=audit.CHANNEL_VOICE,
                 result=audit.RESULT_FAILURE, note="cockpit voice: %s" % note)
    return {"words": words, "status": NOT_LOGGED, "say": say, "speak": say,
            "verdict": "", "opportunity_id": "", "card_id": "",
            "carded": False, "note": note, "fields": fields, "missing": []}


def capture_one(words: str, *, driver: str) -> dict:
    """Read one load's words, log it, and say what happened.

    **Nothing is asked.** A load with no rate is logged and read back with RATE
    PENDING; a load with no pickup or delivery city is logged with what was
    heard (Owner rulings 2026-09-15). Only words with no freight fact in them
    are NOT LOGGED, and those words come back so they can be read again.
    """
    from dispatch import audit, opportunity

    parsed = opportunity.parse_dictation(words)
    fields = dict(parsed["fields"])
    lane = _lane(fields)

    if not opportunity.has_freight_fact(fields):
        return _refused(words, driver, "nothing heard", "NOT LOGGED. NOTHING HEARD.", fields)

    fields["captured_via"] = CHANNEL
    try:
        record = opportunity.capture(fields, driver=driver, channel=CHANNEL)
    except opportunity.OpportunityError as refusal:
        return _refused(words, driver, str(refusal), "NOT LOGGED. %s" % (lane or "LOAD"), fields)

    verdict = record.get("verdict", "NEW")
    # The same audit entry the seventh contract writes, on the VOICE channel.
    audit.record(
        action="opportunity-capture", driver=driver, channel=audit.CHANNEL_VOICE,
        mission_id=record["opportunity_id"],
        intent="%s to %s" % (record.get("origin", ""), record.get("destination", "")),
        new_value=str(record.get("rate") or ""),
        result=audit.RESULT_SUCCESS,
        note="cockpit voice; " + (
            "merged into existing capture; filled %s"
            % (", ".join(record.get("filled") or []) or "nothing")
            if verdict == "MERGED" else
            "flagged %s of %s" % (opportunity.FLAG_POSSIBLE_DUPLICATE,
                                  record.get("possible_duplicate_of", ""))
            if verdict == "AMBIGUOUS" else "captured"))

    # The card at capture time, after the capture is stored and audited -- the
    # contract's order. A card that cannot be made never costs the capture, and
    # the failure is said rather than swallowed.
    carded, card_id, note = False, "", ""
    try:
        from portal.models import opportunity_card

        entry = opportunity_card.from_capture(record)
        carded, card_id = True, str((entry or {}).get("id") or "")
    except Exception as exc:  # noqa: BLE001 - a card must never lose a capture
        note = "capture stored; card not made (%s)" % exc
        audit.record(action="opportunity-card", driver=driver, channel=audit.CHANNEL_VOICE,
                     mission_id=record["opportunity_id"], result=audit.RESULT_FAILURE, note=note)

    line = opportunity.echo(record)
    # The echo ends on its last fact ("$900"); a full stop keeps two loads read
    # back together from running into one sentence.
    if not line.endswith((".", "?")):
        line += "."
    return {"words": words, "status": MERGED if verdict == "MERGED" else LOGGED,
            "say": line, "speak": spoken(line), "verdict": verdict,
            "opportunity_id": record["opportunity_id"], "card_id": card_id,
            "carded": carded, "note": note,
            "flag": record.get("flag", ""),
            "possible_duplicate_of": record.get("possible_duplicate_of", ""),
            "filled": record.get("filled", []), "fields": fields,
            "rate_pending": record.get("rate") is None,
            # What was not heard, for the screen. Nothing asks for it.
            "missing": list(parsed["missing"]),
            "lane": lane}


def capture_spoken(text: str, *, driver: str) -> dict:
    """One submission from the voice drawer: one or more loads, split on NEXT.

    Clears expired uncommitted cards first, the way `/loads/paste` does (Owner
    ruling 2026-09-15: *"clear expired cards too"*), then logs every load that
    carries a fact. Returns `{"ok", "loads", "say", "speak", "cleared_expired"}`;
    `say` is every load's line in the order they were said.
    """
    words = " ".join(str(text or "").split())
    pieces = split_loads(text) if words else []
    if not pieces:
        line = "NOTHING HEARD."
        return {"ok": False, "loads": [], "say": line, "speak": line, "cleared_expired": 0}

    # D12: expired uncommitted loads go when work is done, never on a look (D9).
    # The card model's own gate refuses to remove a committed load.
    from portal.models import opportunity_card

    cleared = opportunity_card.discard_expired(driver=driver)

    loads = [capture_one(p, driver=driver) for p in pieces]
    return {"ok": True, "loads": loads,
            "say": " ".join(load["say"] for load in loads),
            "speak": " ".join(load["speak"] for load in loads),
            "cleared_expired": len(cleared)}
