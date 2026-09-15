"""The bridge from a captured Opportunity to the card the portal renders.

Built 2026-09-09, Mike's ruling: **at capture time.** The card exists the moment
he stops speaking, not later when some screen assembles one.

Until this existed there were two stores and nothing joined them. Voice captures
landed in the `opportunities` table and every screen read the sandbox store, so
a capture validated, deduplicated, minted its `OPP-` id, wrote its audit row,
returned its spoken echo, and then stopped somewhere nothing could see it.

Direction matters. This lives in the portal layer and imports from the engine,
never the other way round. `dispatch/opportunity.py` still knows nothing about
the portal, which is what keeps the capture contract usable without a UI.

**One card per Opportunity.** The sandbox keys entries by source type and source
id, so a re-capture of the same listing lands on the same card and updates it
rather than making a second. That is the same identity rule the capture contract
already applies -- a MERGED verdict carries the original `opportunity_id`, and
passing it here is what makes the merge visible on screen.

**Nothing is invented.** Only fields the Opportunity actually carries reach the
card. A capture with gaps produces a card with gaps, which is the point: the
contract's own rule is that *a capture with gaps beats a listing lost to the
next screen.*
"""

from __future__ import annotations

from portal.models import sandbox

#: Opportunity field -> the key the Dispatch card already reads.
#:
#: Only the counterparts that are real. `pieces_weight` is freeform on the
#: contract ("two pallets", "44,000") and the card's `weight_lbs` is a number it
#: formats as one, so mapping it there would turn a valid sparse capture into a
#: broken card. It travels on the entry instead, where nothing has to guess at
#: it. `source_board` and `captured_via` are facts about the capture, not the
#: freight, and are kept the same way.
ONTO_CARD = {
    "origin": "origin",
    "destination": "destination",
    "rate": "rate",
    "contact": "broker",
    "equipment": "equipment_required",
    "pickup_date": "pickup_window",
    "delivery_date": "delivery_window",
    "notes": "notes",
}

#: Kept on the entry, not shown on the card, so a capture loses nothing.
CARRIED = ("pieces_weight", "source_board", "captured_via", "captured_by",
           "captured_at", "state", "origins", "opportunity_id")

#: The Dispatch card lives under this source type. A dictated board listing is
#: an incoming load opportunity, which is exactly what that tab already holds.
SOURCE_TYPE = "dispatch"


def title_for(record: dict) -> str:
    """The card's headline, in the shape the existing cards already use:
    equipment, then the lane. Equipment is optional on a capture, so a listing
    dictated without it reads as just the lane rather than as an empty dash."""
    lane = " to ".join(p for p in (record.get("origin"), record.get("destination")) if p)
    equipment = (record.get("equipment") or "").strip()
    return f"{equipment} - {lane}" if equipment and lane else (lane or equipment or "Untitled")


#: The card's window field, and where the words he said are kept beside it once
#: they have been read as a date.
WINDOWS = (("pickup_window", "pickup_as_said"), ("delivery_window", "delivery_as_said"))


def capture_day(record: dict):
    """The home-terminal day the capture was taken on.

    A spoken "Thursday" means the Thursday after the day it was said, not the
    Thursday after whatever day a screen happens to be looked at. Reading it
    against the capture's own timestamp is what keeps a card from drifting a
    week when it is re-scored on Friday.
    """
    from datetime import datetime, timezone

    from dispatch import clock

    stamp = str(record.get("captured_at") or "").strip()
    if stamp:
        try:
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return when.astimezone(clock.home_zone()).date()
        except ValueError:
            pass
    return clock.home_date()


def resolve_windows(card: dict, *, day) -> dict:
    """Read spoken pickup and delivery words as dates, at capture (CO-2).

    A window that already carries a date is left exactly as written. One that
    can be read -- "Thursday 6am", "9/15" -- becomes `YYYY-MM-DD[ HH:MM]` so the
    calendar, scoring and COMMIT all see a date, and the words he said are kept
    beside it under `*_as_said`. One that cannot be read stays as the words,
    visibly undated, exactly as before.
    """
    from dispatch import spoken_date

    for window, as_said in WINDOWS:
        said = str(card.get(window) or "").strip()
        if not said or spoken_date.looks_resolved(said):
            continue
        resolved = spoken_date.resolve(said, today=day)
        if resolved:
            card[window] = resolved
            card[as_said] = said
    return card


def card_data_for(record: dict) -> dict:
    """The card body. Every mapped field the capture actually carries, plus the
    capture-time facts that have no place on the card but should not be lost."""
    card: dict = {}
    for field, key in ONTO_CARD.items():
        value = record.get(field)
        if value not in (None, ""):
            card[key] = value
    for field in CARRIED:
        value = record.get(field)
        if value not in (None, ""):
            card[field] = value
    return resolve_windows(card, day=capture_day(record))


def from_capture(record: dict, extras: dict | None = None) -> dict:
    """Create or update the card for one captured Opportunity, and score it.

    `extras` are card facts the capture contract has no field for -- miles, a
    numeric weight, the customer's load number, a phone -- read from a pasted
    listing or offer email (`dispatch/listing.py`). They fill the card and
    never overwrite what the capture itself carries. On a re-capture of the
    same load, facts the earlier card already held are kept rather than lost.

    Returns the sandbox entry. Safe to call on every capture: NEW makes the card,
    MERGED finds the same one, fills it in, and scores it again on what is now
    known.

    **The score is the engine's, not this module's.** `dispatch.scoring` is the
    deterministic chassis: same inputs, same policy profile, same score, every
    time. Running it here is not a screen deciding anything, it is a screen
    asking the engine that already owns the question. Nothing here computes,
    adjusts or overrides a number.

    A sparse capture scores on what it has. Position impact, drive-time risk and
    the rest come back as unknowns where the lane or the windows were not said,
    which is the honest answer and is visible on the card as such.

    Scoring never costs the card. If the engine cannot score this capture the
    card still exists, unscored, and can be scored later when the gaps are
    filled. A capture that reached a screen beats a capture held back for want
    of a number.
    """
    card = card_data_for(record)
    for key, value in (extras or {}).items():
        if value not in (None, "") and card.get(key) in (None, ""):
            card[key] = value
    earlier = sandbox.get(f"SBX-{SOURCE_TYPE.upper()}-{record['opportunity_id']}")
    for key, value in ((earlier or {}).get("card_data") or {}).items():
        if value not in (None, "") and card.get(key) in (None, ""):
            card[key] = value

    score = None
    scoring = None
    try:
        from dispatch.scoring import known_distance, score_load

        # A dictated listing carries no mileage -- nobody says "one hundred and
        # forty miles" reading a board. Without it, economics cannot compute and
        # every capture scores identically, which makes a stack of cards
        # impossible to rank. The engine's own table answers for the lanes this
        # truck runs, so ask it. Lanes the table does not hold stay absent, and
        # scoring says "rate or distance data missing" rather than pricing a
        # guess.
        if not card.get("distance_miles"):
            miles = known_distance(card.get("origin", ""), card.get("destination", ""))
            if miles:
                card["distance_miles"] = miles

        scoring = score_load(dict(card))
        score = scoring.get("score")
    except Exception:  # noqa: BLE001 - an unscored card still beats no card
        scoring = None

    entry = sandbox.create_entry(
        source_type=SOURCE_TYPE,
        source_id=record["opportunity_id"],
        title=title_for(record),
        card_data=card,
        score=score,
    )
    if scoring:
        updated = sandbox.update_scoring(entry["id"], scoring)
        if updated:
            entry = updated
    return entry


# ----------------------------------------------------------- one card story ----
#
# **Owner ruling D12, 2026-09-14:** *"program only processes committed loads. due
# to the life span of only hours to minuties it makes no sense to keep any
# uncommitted load information."* Discard on PASS, and when the pickup window
# expires uncommitted. Both stores go together -- the capture row and its card --
# so no screen can show a card whose capture is gone, or the reverse.
#
# The one thing that is never discarded is a committed record. Everything below
# asks the commitment gate first.


def is_protected(entry: dict) -> bool:
    """A record that may never be discarded: committed, or already opened as a load."""
    from dispatch import commitment

    entry = entry or {}
    return bool(commitment.is_committed(entry) or entry.get("engine_load_id")
                or entry.get("operational_load"))


def discard(sandbox_id: str, *, reason: str, driver: str) -> dict:
    """Discard one uncommitted card and the capture behind it (D12).

    Returns `{"discarded": bool, "note": str}`. A committed record is refused and
    left exactly as it was. Every discard is written to the audit log, because a
    record removed without a trace is a silent failure however right the rule.
    """
    from dispatch import audit, opportunity

    entry = sandbox.get(sandbox_id)
    if not entry:
        return {"discarded": False, "note": "There was no such card."}
    if is_protected(entry):
        return {"discarded": False,
                "note": "This load is committed. Committed loads are never discarded."}

    card = entry.get("card_data") or {}
    opportunity_id = card.get("opportunity_id") or (
        entry.get("source_id") if str(entry.get("source_id", "")).startswith("OPP-") else "")
    if opportunity_id:
        opportunity.discard(opportunity_id)
    sandbox.discard_entry(sandbox_id)
    audit.record(action="opportunity-discard", driver=driver or "dispatch",
                 channel=audit.CHANNEL_MISSION_SCREEN, mission_id=sandbox_id,
                 intent=entry.get("title", ""), result=audit.RESULT_SUCCESS,
                 note="D12: %s; uncommitted load information is not kept" % reason)
    return {"discarded": True, "note": "Discarded. Uncommitted loads are not kept."}


def pickup_deadline(window: str, *, day=None):
    """When a pickup window has gone by, as an aware home-zone datetime, or None.

    "2026-09-15 06:00 - 10:00" has gone by at 10:00 on the 15th. A window with
    only a day, or only a start time, has gone by when that day ends -- a board
    appointment at 06:00 is often a first-come window, and the rule is to discard
    a load that can no longer be run, not one that is merely late in the day.
    Words nothing can read have no deadline and are never discarded for expiry.
    """
    import re
    from datetime import datetime, time

    from dispatch import booking, clock, spoken_date

    said = str(window or "").strip()
    if not said:
        return None
    on = booking._as_date(said)
    if on is None:
        resolved = spoken_date.resolve(said, today=day) if day else ""
        on = booking._as_date(resolved) if resolved else None
    if on is None:
        return None
    end = time(23, 59, 59)
    parts = said.split(" - ")
    if len(parts) == 2:
        match = re.match(r"^\s*(\d{1,2}):(\d{2})", parts[1])
        if match and int(match.group(1)) < 24:
            end = time(int(match.group(1)), int(match.group(2)))
    return datetime.combine(on, end, tzinfo=clock.home_zone())


def expired_card_ids(*, now=None) -> list:
    """Uncommitted freight cards whose pickup has gone by. Reads; changes nothing.

    What a screen may show ("pickup passed") without discarding anything, because
    looking is not doing (D9).
    """
    from dispatch import clock

    now = now or clock.home_now()
    ids = []
    for sid, entry in sandbox.get_all_for_source(SOURCE_TYPE).items():
        if is_protected(entry):
            continue
        card = entry.get("card_data") or {}
        deadline = pickup_deadline(card.get("pickup_window")
                                   or entry.get("pickup_window") or "")
        if deadline is not None and now > deadline:
            ids.append(sid)
    return ids


def discard_expired(*, now=None, driver: str = "dispatch") -> list:
    """Discard every uncommitted freight card, and capture, whose pickup has gone by.

    Called when work is being done -- a paste, a sweep, the Loads screen's
    CLEAR -- never when a screen is merely looked at: D9, *retrieval is not
    modification*. It is deliberately not called from the seventh contract
    (`POST /api/joe/opportunity`): a side effect on a ratified contract is the
    Owner's to add. Returns the ids discarded.
    """
    from dispatch import clock, opportunity

    now = now or clock.home_now()
    gone = []
    for sid in expired_card_ids(now=now):
        if discard(sid, reason="pickup window passed uncommitted",
                   driver=driver)["discarded"]:
            gone.append(sid)

    # A capture whose card was never made still expires with its pickup.
    for row in opportunity.all_open():
        sid = f"SBX-{SOURCE_TYPE.upper()}-{row['opportunity_id']}"
        if sandbox.get(sid) is not None:
            continue
        deadline = pickup_deadline(row.get("pickup_date") or "",
                                   day=capture_day(row))
        if deadline is not None and now > deadline:
            opportunity.discard(row["opportunity_id"])
            gone.append(row["opportunity_id"])
    return gone


# ------------------------------------------------------ paste a listing ----

#: What a pasted text is. A listing is copied off a board's screen; an offer is
#: a broker's email, copied out of the mail program. Neither is ever fetched.
PASTE_KINDS = ("listing", "email")


def capture_from_text(text: str, *, kind: str = "listing", driver: str,
                      typed: dict | None = None) -> dict:
    """Paste a listing or an offer email; get a card, and a list of what is missing.

    CO-2, 2026-09-14. The text is read by `dispatch/listing.py` -- deterministic,
    no board-specific reading, nothing fetched. Anything the person typed into
    the form beside the paste (`typed`) wins over what was read, because he is
    looking at the listing and the parser is not.

    The capture goes through the same contract function the voice capture uses
    (`dispatch.opportunity.capture`), so deduplication, the rehearsal tag and
    the one-card rule all hold. The contract still refuses a capture without a
    lane and a rate; this returns `ok: False` with what was read so the screen
    can ask for exactly those, and stores nothing.

    Returns `{"ok", "parsed", "missing", "record", "entry", "note"}`.
    """
    from dispatch import audit, listing, opportunity

    parsed = (listing.parse_offer_email(text) if kind == "email"
              else listing.parse_listing(text))
    fields = dict(parsed["fields"])
    extras = dict(parsed["card_extras"])

    for key, value in (typed or {}).items():
        value = str(value if value is not None else "").strip()
        if not value:
            continue
        if key == "distance_miles":
            try:
                extras["distance_miles"] = float(value.replace(",", ""))
            except ValueError:
                continue
        elif key in opportunity.FIELDS:
            fields[key] = value

    required_missing = [k for k in listing.REQUIRED if not str(fields.get(k) or "").strip()]
    outcome = {"ok": False, "parsed": parsed, "fields": fields, "extras": extras,
               "missing": list(parsed["missing"]), "required_missing": required_missing,
               "record": None, "entry": None, "note": ""}
    outcome["missing"] = [name for key, name in listing.WANTED
                          if not dict(fields, **extras).get(key)]
    if required_missing:
        outcome["note"] = "Needs %s before it can be logged." % ", ".join(
            name for key, name in listing.WANTED if key in required_missing)
        return outcome

    fields["captured_via"] = "MISSIONSCREEN"
    try:
        record = opportunity.capture(fields, driver=driver, channel="MISSIONSCREEN")
    except opportunity.OpportunityError as refusal:
        audit.record(action="opportunity-capture", driver=driver,
                     channel=audit.CHANNEL_MISSION_SCREEN,
                     result=audit.RESULT_FAILURE, note=f"pasted {kind}: {refusal}")
        outcome["note"] = str(refusal)
        return outcome

    audit.record(action="opportunity-capture", driver=driver,
                 channel=audit.CHANNEL_MISSION_SCREEN,
                 mission_id=record["opportunity_id"],
                 intent="%s to %s" % (record.get("origin", ""), record.get("destination", "")),
                 new_value=str(record.get("rate") or ""), result=audit.RESULT_SUCCESS,
                 note="pasted %s; %s" % (kind, record.get("verdict", "NEW").lower()))
    outcome.update(ok=True, record=record, entry=from_capture(record, extras=extras))
    return outcome
