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
    return card


def from_capture(record: dict) -> dict:
    """Create or update the card for one captured Opportunity, and score it.

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

    score = None
    scoring = None
    try:
        from dispatch.scoring import score_load

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
