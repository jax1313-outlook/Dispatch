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
  * `dispatch.opportunity.one_question`    -- the one question (RATE?)
  * `dispatch.opportunity.capture`         -- dedup, merge, rehearsal tag
  * `portal.models.opportunity_card.from_capture` -- the card at capture time
  * `dispatch.opportunity.echo`            -- the read-back

Rule 15, Reuse Before Create: the only new thing here is saying NEXT between
loads, and keeping a load's words while its one question is answered.

**Capture only.** Nothing here commits, passes, discards or sends. Class 1.

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

#: What he says instead of a rate to leave a load unlogged.
SKIP_WORDS = ("skip", "skip it", "drop", "drop it", "never mind", "nevermind", "cancel")

#: Status words for one load in the read-back list.
LOGGED = "LOGGED"
MERGED = "MERGED"
QUESTION = "QUESTION"
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
            "question": "", "verdict": "", "opportunity_id": "", "card_id": "",
            "carded": False, "note": note, "fields": fields}


def capture_one(words: str, *, driver: str, answer: str | None = None) -> dict:
    """Read one load's words, ask its one question or log it, and say what happened.

    `answer` is what he said back to the question. A rate logs the load; a skip
    word leaves it unlogged; anything else asks again. **Nothing is stored for a
    load that still has a question**, and its words come back so the question
    can be answered against them.
    """
    from dispatch import audit, opportunity

    parsed = opportunity.parse_dictation(words)
    fields = dict(parsed["fields"])
    missing = list(parsed["missing"])
    lane = _lane(fields)

    if answer is not None:
        said = " ".join(str(answer).split())
        if said.lower().strip(" .!?") in SKIP_WORDS:
            line = "NOT LOGGED. %s DROPPED." % (lane or "LOAD")
            return {"words": words, "status": NOT_LOGGED, "say": line, "speak": line,
                    "question": "", "verdict": "", "opportunity_id": "", "card_id": "",
                    "carded": False, "note": "dropped at the question", "fields": fields}
        rate = opportunity.parse_dictation(said).get("fields", {}).get("rate") if said else None
        if rate is not None:
            fields["rate"] = rate
            missing = [m for m in missing if m != "rate"]

    if "origin" in missing or "destination" in missing:
        line = "NOT LOGGED. LANE NOT HEARD."
        return _refused(words, driver, "lane not heard", line, fields)

    question = opportunity.one_question(missing)
    if question:
        line = ("%s. %s" % (lane, question)) if lane else question
        return {"words": words, "status": QUESTION, "say": line, "speak": line,
                "question": question, "verdict": "", "opportunity_id": "", "card_id": "",
                "carded": False, "note": "", "fields": fields}

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
            "say": line, "speak": spoken(line), "question": "", "verdict": verdict,
            "opportunity_id": record["opportunity_id"], "card_id": card_id,
            "carded": carded, "note": note,
            "flag": record.get("flag", ""),
            "possible_duplicate_of": record.get("possible_duplicate_of", ""),
            "filled": record.get("filled", []), "fields": fields}


def capture_spoken(text: str, *, driver: str, answer: str | None = None) -> dict:
    """One submission from the voice drawer: several loads split on NEXT, or one
    load's words with the answer to its question.

    Returns `{"ok", "loads", "say", "speak"}`. `say` is every load's line in
    order, with **only the first question** -- one question at a time; the
    screen asks the next one after this one is answered.
    """
    words = " ".join(str(text or "").split())
    if not words:
        line = "NOTHING HEARD."
        return {"ok": False, "loads": [], "say": line, "speak": line}

    pieces = [words] if answer is not None else split_loads(text)
    if not pieces:
        line = "NOTHING HEARD."
        return {"ok": False, "loads": [], "say": line, "speak": line}

    loads = [capture_one(p, driver=driver, answer=answer) for p in pieces]

    said, speak, asked = [], [], False
    for load in loads:
        if load["status"] == QUESTION:
            if asked:
                continue
            asked = True
        said.append(load["say"])
        speak.append(load["speak"])
    # Questions go last in what is said, so the last thing he hears is the one
    # thing he has to answer.
    order = sorted(range(len(said)), key=lambda i: said[i].endswith("?"))
    return {"ok": True, "loads": loads,
            "say": " ".join(said[i] for i in order),
            "speak": " ".join(speak[i] for i in order)}
