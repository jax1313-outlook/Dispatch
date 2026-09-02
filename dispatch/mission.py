"""The Mission Record: one record, one identity, opportunity through closeout.

DOCTRINE THIS FILE IMPLEMENTS
=============================

The Intelligence sweep creates an Opportunity Record. When the owner activates
ACCEPT LOAD, that *same record* becomes the Mission Record. Its purpose
changes, its workflow state changes, its displayed name changes. Its identity
does not.

    Do not create a second operational record.
    Do not copy the Opportunity Record into a new Mission Record.
    Do not build a promotion engine.

WHAT THIS REPLACES
==================

The previous booking path in `portal/routes/api.py` called
`dispatch_svc.create_load(...)`, which minted a NEW `load_id` and copied the
card's broker, origin, destination, windows and equipment into it. Two records
existed from that moment on, joined by a one-way `engine_load_id` pointer, and
the opportunity's intelligence - its research, scoring, negotiation history and
Route Risk - stopped travelling with the mission it had produced.

Here, the operational row is created under the **opportunity's own identity**.
`Load.load_id` is only auto-generated when empty, so passing the record id
keeps one key across the whole lifecycle. Nothing is minted. Nothing is joined.

THE ONE HONEST APPROXIMATION
============================

The `loads` table carries descriptive columns (pickup_location, broker_shipper
and so on) that seventy-eight test files and every existing view already read.
`accept_load()` fills them at commitment, which is technically a denormalised
projection of card data.

It is not a second record: same id, one authoritative origin. `get_mission()`
always prefers the Opportunity's value and falls back to the operational row,
so the opportunity stays the source of truth and the columns are a cache for
code that has not been moved across yet.

Flagged rather than hidden: if Mike wants those columns empty and every reader
routed through `get_mission()`, that is a larger change to existing views and
should be his call, not a silent one.

NUMBERING
=========

Two distinct concepts, never interchangeable:

    MISSION NUMBER   internal, machine generated, numeric only, max four
                     digits. A short tracking number for Dispatch. Assigned
                     once at ACCEPT LOAD and never reissued to that record.

    LOAD NUMBER      the broker's, shipper's or customer's own reference.
                     Preserved exactly as received. Used on documents,
                     invoices and every external communication. Never
                     overwritten by the Mission Number.

    Mission 1847     <- ours
    Load 847261      <- theirs
"""

from __future__ import annotations

# ---- vocabulary --------------------------------------------------------

VIEW_CURRENT = "CURRENT"
VIEW_PICKUP = "PICKUP"
VIEW_DELIVERY = "DELIVERY"
VIEWS = (VIEW_CURRENT, VIEW_PICKUP, VIEW_DELIVERY)

# Purpose of the record. The record is the same; only this changes.
PURPOSE_OPPORTUNITY = "OPPORTUNITY"
PURPOSE_MISSION = "MISSION"

MISSION_NUMBER_MAX = 9999

# Statuses that sit on the pickup side of the run, and on the delivery side.
# Everything before the freight is loaded is pickup work; everything after it
# is delivery work. `in_transit` is the hinge and belongs to delivery, because
# once loaded the next thing that matters is where it has to be.
PICKUP_STATUSES = frozenset({
    "created", "dispatched", "en_route_pickup", "at_pickup",
})
DELIVERY_STATUSES = frozenset({
    "picked_up", "in_transit", "at_delivery", "delivered",
    "completed", "archived",
})

# Milestones, split on the same axis.
PICKUP_MILESTONES = frozenset({
    "dispatched", "en_route_pickup", "arrived_pickup", "loaded",
    "departed_pickup",
})
DELIVERY_MILESTONES = frozenset({
    "in_transit", "checkpoint", "arrived_delivery", "delivered",
    "pod_received", "completed",
})

# Evidence belongs to the end of the run that produces it.
PICKUP_EVIDENCE = frozenset({"bol", "photo", "screenshot"})
DELIVERY_EVIDENCE = frozenset({"pod", "photo", "document"})


class MissionError(RuntimeError):
    """Raised when a commitment cannot honestly be made."""


# ---- numbering ---------------------------------------------------------

def next_mission_number(existing: list[int] | None = None) -> int:
    """The lowest free internal number, 1 to 9999.

    Numeric only, four digits at most, and reused only after a record that
    held one is gone. Sequential-with-gap-filling keeps the numbers short for
    years rather than marching toward five digits.
    """
    taken = {int(n) for n in (existing or []) if str(n).isdigit()}
    for candidate in range(1, MISSION_NUMBER_MAX + 1):
        if candidate not in taken:
            return candidate
    raise MissionError(
        "all %d internal mission numbers are in use; archive completed "
        "missions before accepting another" % MISSION_NUMBER_MAX
    )


def assigned_mission_numbers(entries: dict) -> list[int]:
    """Every internal number currently attached to a record."""
    out = []
    for entry in (entries or {}).values():
        number = entry.get("mission_number")
        if str(number).isdigit():
            out.append(int(number))
    return out


def external_load_number(record: dict) -> str:
    """The broker's own reference, exactly as received.

    Read from the card, never from the operational row, and never defaulted to
    the internal number - showing our tracking number where a broker's
    reference belongs is how a payment goes missing.
    """
    card = (record or {}).get("card_data") or {}
    for field in ("load_id", "load_number", "reference", "po_number",
                  "order_number", "work_order"):
        value = str(card.get(field) or "").strip()
        if value:
            return value
    return ""


def display_numbers(record: dict) -> dict:
    """Both numbers, labelled, for anywhere they are shown together."""
    number = (record or {}).get("mission_number")
    return {
        "mission_number": number,
        "mission_label": ("Mission %s" % number) if number else "",
        "load_number": external_load_number(record),
        "load_label": (("Load %s" % external_load_number(record))
                       if external_load_number(record) else ""),
    }


# ---- purpose and phase -------------------------------------------------

def purpose_of(record: dict) -> str:
    """OPPORTUNITY before commitment, MISSION after. Same record throughout.

    The commitment is the COMMIT gate: everything before it is Booking and
    everything after it is Dispatch. See `dispatch/commitment.py`, which names
    what this field has always been.
    """
    from dispatch import commitment

    if commitment.is_committed(record):
        return PURPOSE_MISSION
    return PURPOSE_OPPORTUNITY


def is_mission(record: dict) -> bool:
    return purpose_of(record) == PURPOSE_MISSION


def phase_for(status: str) -> str:
    """Which end of the run a status belongs to. PICKUP or DELIVERY.

    This is what makes CURRENT deterministic rather than a third data set:
    CURRENT is not stored anywhere, it is resolved from the status the record
    already has.
    """
    wanted = str(status or "").strip().lower()
    if wanted in DELIVERY_STATUSES:
        return VIEW_DELIVERY
    return VIEW_PICKUP


def resolve_view(record: dict, requested: str = VIEW_CURRENT) -> str:
    """Turn a requested view into the phase whose information to reveal.

    CURRENT resolves to PICKUP or DELIVERY by the record's own status. It is
    never a third branch, because a third branch is how one record quietly
    becomes three.
    """
    wanted = str(requested or VIEW_CURRENT).strip().upper()
    if wanted in (VIEW_PICKUP, VIEW_DELIVERY):
        return wanted
    load = (record or {}).get("load") or {}
    status = load.get("status") or (record or {}).get("status") or ""
    return phase_for(status)


# ---- the deterministic view filter -------------------------------------

def filter_bundle(bundle: dict, phase: str) -> dict:
    """Reveal the facets that belong to one phase. Reveals; never deletes.

    Takes an already-assembled bundle and returns a filtered copy. It performs
    no I/O and issues no second query, which is the property that keeps "many
    views" from becoming "many records". The test that guards this asserts one
    store read per request.
    """
    wanted = str(phase or VIEW_PICKUP).strip().upper()
    if wanted not in (VIEW_PICKUP, VIEW_DELIVERY):
        wanted = VIEW_PICKUP

    milestones = PICKUP_MILESTONES if wanted == VIEW_PICKUP else DELIVERY_MILESTONES
    evidence_kinds = PICKUP_EVIDENCE if wanted == VIEW_PICKUP else DELIVERY_EVIDENCE
    side = "pickup" if wanted == VIEW_PICKUP else "delivery"

    view = dict(bundle or {})
    view["phase"] = wanted
    # The stored column is `event_type`. Filtering on `milestone_type` matched
    # nothing and the timeline read "nothing recorded for this phase yet"
    # while the record held the milestone - a silent empty state, which is the
    # worst kind. `milestone_type` is accepted too, for any caller that hands
    # the facet over under that name.
    view["milestones"] = [
        m for m in (bundle.get("milestones") or [])
        if str(m.get("event_type") or m.get("milestone_type") or "").lower()
        in milestones
    ]
    view["evidence"] = [
        e for e in (bundle.get("evidence") or [])
        if str(e.get("evidence_type", "")).lower() in evidence_kinds
    ]
    view["detentions"] = [
        d for d in (bundle.get("detentions") or [])
        if str(d.get("location_type", "")).lower() == side
    ]
    # A PoD is delivery work. Showing it under PICKUP invites it to be filed
    # from the wrong dock.
    view["pods"] = (bundle.get("pods") or []) if wanted == VIEW_DELIVERY else []
    # Exceptions are not phase-tagged in the record, so every open one is
    # shown in both views. An unresolved problem is never irrelevant.
    view["exceptions"] = [
        x for x in (bundle.get("exceptions") or [])
        if str(x.get("status", "")).lower() in ("open", "investigating")
    ]
    return view


# ---- assembly ----------------------------------------------------------

def merge_record(opportunity: dict, bundle: dict | None) -> dict:
    """The whole record: opportunity spine plus operational facets.

    The opportunity is the origin and wins every descriptive field. The
    operational row supplies workflow state. Nothing is copied between them -
    this is a read-time assembly, the same shape `get_load_bundle()` already
    uses, one level higher.
    """
    record = dict(opportunity or {})
    bundle = dict(bundle or {})
    load = dict(bundle.get("load") or {})

    card = record.get("card_data") or {}
    # Descriptive truth comes from the opportunity, which is where it was
    # collected. The operational row is only consulted where the opportunity
    # is silent.
    record["pickup_location"] = card.get("origin") or load.get("pickup_location", "")
    record["delivery_location"] = card.get("destination") or load.get("delivery_location", "")
    record["pickup_window"] = card.get("pickup_window", "")
    record["delivery_window"] = card.get("delivery_window", "")
    record["broker"] = card.get("broker") or load.get("broker_shipper", "")
    record["broker_email"] = card.get("broker_email", "")
    record["broker_phone"] = card.get("broker_phone", "")
    record["equipment"] = card.get("equipment_required") or load.get("equipment", "")
    record["rate"] = card.get("rate")
    record["rpm"] = card.get("rpm")
    record["distance_miles"] = card.get("distance_miles")

    record["load"] = load
    record["status"] = load.get("status") or record.get("status", "")
    record["purpose"] = purpose_of(record)
    record["numbers"] = display_numbers(record)
    for facet in ("milestones", "evidence", "exceptions", "pods", "detentions",
                  "activities", "visibility", "financials", "settlement",
                  "lane_history"):
        record[facet] = bundle.get(facet)
    return record


# ---- the commitment event ----------------------------------------------

def accept_load(record_id: str, sandbox_module, dispatch_services,
                store_module) -> dict:
    """ACCEPT LOAD. The human commitment event.

    The same record becomes the Mission Record. Assigns the internal Mission
    Number, opens the operational row **under the record's own identity**, and
    marks the moment of commitment.

    Dependencies are passed in rather than imported so this can be exercised
    without a database and without the portal.
    """
    entries = sandbox_module.get_all()
    record = entries.get(record_id)
    if not record:
        raise MissionError("no such record: %s" % record_id)
    if record.get("accepted_at"):
        raise MissionError(
            "Mission %s was already accepted" % record.get("mission_number"))

    number = next_mission_number(assigned_mission_numbers(entries))

    # The operational row is opened under the OPPORTUNITY'S OWN ID. This one
    # argument is the whole doctrine: no new key is minted, so no second record
    # can exist.
    existing = dispatch_services.get_load(record_id)
    if not existing:
        card = record.get("card_data") or {}
        # `source` names the load BOARD the freight came from, and only
        # accepts a fixed vocabulary. The record's source_type ("dispatch")
        # describes the sweep that found it, which is a different fact - and
        # passing it here raised ValueError on every booking. Left unset unless
        # the card names a board Dispatch recognises.
        from dispatch.models import LOAD_SOURCES

        board = str(card.get("source") or "").strip().lower()
        dispatch_services.create_load_with_id(
            load_id=record_id,
            customer=card.get("broker", record.get("title", "")),
            broker_shipper=card.get("broker", ""),
            pickup_location=card.get("origin", ""),
            delivery_location=card.get("destination", ""),
            equipment=card.get("equipment_required", ""),
            source=board if board in LOAD_SOURCES else "",
        )

    return sandbox_module.mark_accepted(record_id, number)
