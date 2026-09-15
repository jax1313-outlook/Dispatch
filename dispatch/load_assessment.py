"""What Mike may not see: the checks a card carries beside its score.

CO-3, 2026-09-14. The Owner's must-have: *"Assistance scoring the loads to see
what I may not see."*

**Advisory, all of it.** Nothing here approves, rejects, hides or ranks a load
out of sight. Score does not decide (CLAUDE.md section 4), and a warning does not
either: it names a fact the board did not put in front of him -- a delivery that
cannot legally be made, a Sunday drop, a day the truck is already committed, a
Wednesday left stranded between two loads -- and he decides.

**Reality and Possibility never merge.** Collisions and stranded days are worked
out against *committed* loads only. Other candidates never count as commitments,
so two cards for the same Tuesday do not warn each other off.

One pure function, `assess(card, ...)`, given the records and the fleet. The
portal gathers those and stores the answer on the card; this module reads no
store of its own beyond the carrier's declared home base.
"""

from __future__ import annotations

import re
from datetime import date

#: Load facts a card is expected to carry, and what to call each one when it is missing.
CARD_FACTS = (
    ("origin", "pickup city"),
    ("destination", "delivery city"),
    ("pickup_window", "pickup date"),
    ("delivery_window", "delivery date"),
    ("equipment_required", "equipment"),
    ("weight_lbs", "weight"),
    ("distance_miles", "miles"),
)

#: Words a listing uses for a trailer, onto the fleet's own equipment types
#: (`dispatch.models.EQUIPMENT_TYPES`). Longest phrase wins.
EQUIPMENT_WORDS = (
    ("refrigerated", "reefer"), ("reefer", "reefer"),
    ("step deck", "step_deck"), ("stepdeck", "step_deck"),
    ("flatbed", "flatbed"), ("flat bed", "flatbed"),
    ("lowboy", "lowboy"), ("tanker", "tanker"), ("container", "container"),
    ("box truck", "box_truck"), ("straight truck", "straight_truck"),
    ("cargo van", "cargo_van"), ("sprinter", "cargo_van"),
    ("enclosed trailer", "enclosed_trailer"),
    ("dry van", "dry_van"), ("van", "dry_van"),
)


def home_base() -> str:
    """The declared home base (Settings > Registration), else the scoring engine's."""
    from dispatch import scoring

    try:
        from dispatch import carrier

        declared = carrier.get()
        city = str(declared.get("home_city") or "").strip()
        state = str(declared.get("home_state") or "").strip()
        if city:
            return f"{city}, {state}" if state else city
    except Exception:  # noqa: BLE001 - a missing registration degrades to the default
        pass
    return scoring._HOME_BASE


def truck_position(records, *, before: date | None, exclude_id: str = "") -> dict:
    """Where the truck is when this load would start. CO-3.2.

    The delivery city of the last committed load that delivers on or before the
    pickup day, if one is known; otherwise home base. The basis is always said.
    """
    from dispatch import booking, commitment

    best = None
    for record in booking._iter(records):
        if record.get("id") == exclude_id or not commitment.is_committed(record):
            continue
        card = record.get("card_data") or {}
        where = card.get("destination") or record.get("delivery_location") or ""
        _, delivery = booking.windows_of(record)
        delivered = booking._as_date(delivery)
        if not where or delivered is None or (before and delivered > before):
            continue
        if best is None or delivered > best[0]:
            best = (delivered, where, record)
    if best:
        delivered, where, record = best
        number = record.get("load_number") or (record.get("card_data") or {}).get("load_id") \
            or record.get("id", "")
        return {"location": where, "record_id": record.get("id", ""),
                "basis": "committed load %s delivers there %s"
                         % (number, delivered.strftime("%a %d %b"))}
    home = home_base()
    return {"location": home, "record_id": "", "basis": "home base"}


def equipment_type_of(text: str) -> str:
    """The fleet equipment type a listing's words name, or '' when none is recognised."""
    low = " %s " % re.sub(r"[^a-z]+", " ", str(text or "").lower())
    for words, kind in sorted(EQUIPMENT_WORDS, key=lambda pair: len(pair[0]), reverse=True):
        if " %s " % words in low:
            return kind
    return ""


def equipment_fit(required: str, fleet) -> dict:
    """CO-3.3: the load's equipment against the active fleet's equipment types.

    `match` / `mismatch` only when both sides are known. An unrecognised trailer
    word, or a fleet with no active equipment, is `''` with the reason -- never
    a guess in either direction.
    """
    types = sorted({str(u.get("equipment_type") or "") for u in (fleet or [])
                    if u.get("equipment_type")})
    if not str(required or "").strip():
        return {"match": "", "note": "The load names no equipment."}
    if not types:
        return {"match": "", "note": "No active equipment is on Fleet to check against."}
    kind = equipment_type_of(required)
    if not kind:
        return {"match": "", "note": "%r is not an equipment type Dispatch recognises." % required}
    if kind in types:
        return {"match": "match", "note": "The active fleet runs %s." % kind.replace("_", " ")}
    return {"match": "mismatch",
            "note": "The load asks for %s; the active fleet runs %s."
                    % (kind.replace("_", " "), ", ".join(t.replace("_", " ") for t in types))}


def weight_of(card: dict):
    """A numeric weight from the card, or from freeform pieces-and-weight words."""
    try:
        weight = float(card.get("weight_lbs") or 0)
    except (TypeError, ValueError):
        weight = 0.0
    if weight:
        return weight
    from dispatch.listing import _weight

    found = _weight(str(card.get("pieces_weight") or ""))
    return float(found) if found else None


def _rate(card: dict):
    """The card's rate, or None while it is pending. One reading, the engine's."""
    from dispatch import scoring

    return scoring.rate_of(card)


#: The neutral line a card carries while its rate is pending. **Owner ruling,
#: 2026-09-15:** *"holding a load with out a rate will need an astric or blank is
#: not negative."* It is not a warning and does not sit in the warning list.
RATE_PENDING_LINE = "* Rate pending"


def assess(card: dict, *, records=None, fleet=None, today: date | None = None,
           exclude_id: str = "") -> dict:
    """Everything a card should say beside its score. Pure given its inputs.

    Returns `{"distance", "position", "deadhead_miles", "deadhead_basis",
    "equipment", "timing", "warnings", "rate_pending", "rate_line", "missing"}`.
    `warnings` is a list of `{"code", "text"}` in the order a man reading the card
    needs them. A pending rate is not among them: `rate_line` carries the neutral
    "* Rate pending" (Owner ruling 2026-09-15).
    """
    from datetime import timedelta

    from dispatch import booking, capacity, clock, commitment, distance, scoring

    card = dict(card or {})
    records = list(booking._iter(records))
    warnings = []

    # --- miles, with where they came from (CO-3.1) ---
    trip = distance.miles_between(card.get("origin", ""), card.get("destination", ""),
                                  typed=card.get("distance_miles"))
    miles = trip["miles"]

    # --- where the truck starts, and the empty miles to get there (CO-3.2) ---
    pickup_window, delivery_window = booking.windows_of(card)
    pickup_day = booking._as_date(pickup_window)
    position = truck_position(records, before=pickup_day, exclude_id=exclude_id)
    deadhead = None
    deadhead_basis = "unknown: no pickup city"
    if card.get("origin"):
        leg = distance.miles_between(position["location"], card["origin"])
        deadhead = leg["miles"]
        deadhead_basis = ("from %s: %s; miles from the %s"
                          % (position["location"], position["basis"], leg["basis"])
                          if deadhead is not None else
                          "unknown from %s (%s): %s"
                          % (position["location"], position["basis"], leg["note"]))

    # --- equipment (CO-3.3) ---
    fit = equipment_fit(card.get("equipment_required", ""), fleet)

    # --- what the card is missing ---
    rate = _rate(card)
    with_miles = dict(card, distance_miles=miles, weight_lbs=weight_of(card))
    missing = [name for key, name in CARD_FACTS if not with_miles.get(key)]
    # A pending rate is not a warning (Owner ruling 2026-09-15). The card says
    # RATE_PENDING_LINE on its own line, and the rate-dependent check below (the
    # floor over every mile driven) simply does not run without a rate.

    # --- delivery timing: PARKED ---
    # Mike Zachary, 2026-09-15: "this system does not need to track drive times for nay
    # reason. it does not enter into the decision process." The legal-delivery check in
    # dispatch/drive_time.py is kept, not deleted, but nothing on a card or in a warning
    # uses it. The cockpit's planning drive-time line stays (portal/cockpit.py).
    timing = {}

    # --- the day it delivers ---
    delivery_day = booking._as_date(delivery_window)
    for label, day in (("Delivers", delivery_day), ("Picks up", pickup_day)):
        if day is None:
            continue
        if booking.pattern_for(day) == booking.CLOSED:
            warnings.append({"code": "CLOSED_DAY",
                             "text": "%s on %s, a closed day." % (label, day.strftime("%A %d %b"))})
        elif label == "Delivers" and day.weekday() >= 5:
            warnings.append({"code": "WEEKEND_DELIVERY",
                             "text": "Delivers on %s. Check the receiver is open."
                                     % day.strftime("%A %d %b")})

    # --- against committed loads only: Reality, never Possibility ---
    committed = [r for r in records if r.get("id") != exclude_id
                 and commitment.is_committed(r)]
    busy = {}
    for record in committed:
        for day in booking.span_of(record):
            busy.setdefault(day, record)
    own_days = booking.span_of(card)
    for day in own_days:
        if day in busy:
            other = busy[day]
            number = other.get("load_number") or (other.get("card_data") or {}).get("load_id") \
                or other.get("id", "")
            warnings.append({"code": "COLLIDES_WITH_COMMITTED",
                             "text": "Collides with committed load %s on %s."
                                     % (number, day.strftime("%a %d %b"))})
            break

    today = today or clock.home_date()
    occupied = set(busy) | set(own_days)
    if own_days:
        lo, hi = min(own_days) - timedelta(days=2), max(own_days) + timedelta(days=2)
        day = lo
        while day <= hi:
            before, after = day - timedelta(days=1), day + timedelta(days=1)
            if (day not in occupied and day >= today
                    and booking.pattern_for(day) == booking.OPEN
                    and before in occupied and after in occupied
                    and (before in own_days or after in own_days)):
                warnings.append({"code": "STRANDED_GAP_DAY",
                                 "text": "Leaves %s open between two loads."
                                         % day.strftime("%a %d %b")})
            day += timedelta(days=1)

    # --- money over every mile driven ---
    # Mike Zachary, 2026-09-15: "rate floor should include all miles driven including
    # return home." Loaded miles, the empty miles to pickup, and the run home from
    # delivery. A leg nothing can measure is said, never counted as zero silently.
    home = home_base()
    return_leg = (distance.miles_between(card["destination"], home)
                  if card.get("destination") else {"miles": None})
    return_home = return_leg.get("miles")
    if rate is not None and miles:
        total = miles + (deadhead or 0) + (return_home or 0)
        effective = rate / total if total else None
        if effective is not None and effective < scoring._RATE_PER_MILE_FLOOR:
            unmeasured = [name for name, leg in (("to pickup", deadhead), ("home", return_home))
                          if leg is None]
            warnings.append({"code": "BELOW_FLOOR_AFTER_DEADHEAD",
                             "text": "$%.2f a mile over %d miles driven (%d loaded, %d empty to pickup, "
                                     "%d home to %s), below the $%.2f floor.%s"
                                     % (effective, round(total), round(miles), round(deadhead or 0),
                                        round(return_home or 0), home, scoring._RATE_PER_MILE_FLOOR,
                                        (" Miles %s could not be measured." % " and ".join(unmeasured))
                                        if unmeasured else "")})

    # --- weight against what the truck is stated to carry ---
    weight = weight_of(card)
    if weight:
        envelope = capacity.physical_capacity_from_equipment(fleet or [])
        if envelope.configuration_status != "UNCONFIGURED" and envelope.max_weight_lbs > 0:
            if weight > envelope.max_weight_lbs:
                warnings.append({"code": "OVERWEIGHT",
                                 "text": "%s lbs is over the fleet's stated payload of %s lbs."
                                         % (f"{weight:,.0f}", f"{envelope.max_weight_lbs:,.0f}")})
        elif weight > scoring._WEIGHT_LIMIT_LBS:
            warnings.append({"code": "OVERWEIGHT",
                             "text": "%s lbs is over %s lbs. That is a tractor-trailer figure; "
                                     "no payload is stated on Fleet."
                                     % (f"{weight:,.0f}", f"{scoring._WEIGHT_LIMIT_LBS:,}")})

    if fit["match"] == "mismatch":
        warnings.append({"code": "EQUIPMENT_MISMATCH", "text": fit["note"]})

    if missing:
        warnings.append({"code": "MISSING_FACTS",
                         "text": "Missing: %s." % ", ".join(missing)})

    return {
        "distance": trip,
        "position": position,
        "deadhead_miles": deadhead,
        "deadhead_basis": deadhead_basis,
        "return_home_miles": return_home,
        "equipment": fit,
        "timing": {k: (v.isoformat(sep=" ", timespec="minutes") if hasattr(v, "isoformat") else v)
                   for k, v in timing.items()},
        "warnings": warnings,
        "rate_pending": rate is None,
        "rate_line": RATE_PENDING_LINE if rate is None else "",
        "missing": missing,
    }
