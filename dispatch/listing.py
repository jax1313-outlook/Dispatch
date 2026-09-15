"""Pasted load listings and broker offer emails, read into a card.

CO-2, 2026-09-14. The Owner's must-have: *"A rapid way to capture load
information for later decision making."* Dictation is one way in. The other is
the one his hands already do at a board or in a mailbox: select the listing,
copy it, paste it.

WHAT THIS IS, AND WHAT IT IS NOT
================================

**It reads text a person pasted.** It never fetches a page, never logs into a
board, never reads an inbox. D1: *"only API / MCP connected boards will be
swept."* No scraping or session tooling of any kind -- the input here is the
clipboard, and the clipboard is his.

**It is not written for any one board.** No board's layout, column order or
abbreviation code is known to it. It looks for the shapes every freight listing
shares -- a labelled field ("Rate: $1,850"), a city and state ("Jacksonville,
FL"), a dollar figure, a mileage, a weight, a date -- so a board Level 1 signs
up for next year needs no change here.

**Deterministic and pure.** Same text, same answer, no clock, no network, no
database. Dates stay as the words that were pasted; they are read as dates at
capture, on the home terminal's day, the same way a dictated date is
(`portal/models/opportunity_card.resolve_windows`).

**Nothing is invented.** A fact the text does not carry comes back absent, and
`missing` names it, so the card shows the gap instead of a guess. The load
number in particular is only ever taken from a labelled field: D8 -- *"Mission
number is listed on load board by customer and transfer to opportunity card.
should there be no number or blank space the number will be generated at the
moment of Commit by Publisher."* A number this module guessed would be neither.

Returns the capture contract's own fields (`dispatch.opportunity.FIELDS`) plus
`card_extras` -- facts the card carries that the contract has no field for
(miles, a numeric weight, the customer's load number, a phone, an email).
"""

from __future__ import annotations

import re

#: US and Canadian region codes. A "City, XX" only counts as a place when XX is
#: one of these, which is what stops "Partners, OK" style text being a lane.
REGIONS = frozenset("""
AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT
NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR
AB BC MB NB NL NS NT NU ON PE QC SK YT
""".split())

#: Labels a listing or an offer email uses, by the fact they introduce. Matched
#: against the text before a colon or a tab, case-insensitively, whole label
#: only. Generic freight words -- no board's private vocabulary.
LABELS = {
    "origin": ("origin", "from", "origin city", "pickup city", "pick up city",
               "pickup location", "pick up location", "load at", "shipper location",
               "ship from"),
    "destination": ("destination", "dest", "to", "destination city", "delivery city",
                    "delivery location", "deliver to", "consignee location", "ship to",
                    "drop location"),
    "pickup": ("pickup", "pick up", "pu"),
    "delivery": ("delivery", "deliver", "drop", "del"),
    "pickup_date": ("pickup date", "pick up date", "pu date", "ship date", "ready date",
                    "load date", "available", "pickup time", "pickup appointment",
                    "pick up appointment"),
    "delivery_date": ("delivery date", "del date", "drop date", "deliver by", "due date",
                      "delivery time", "delivery appointment", "must deliver"),
    "rate": ("rate", "pay", "price", "linehaul", "line haul", "all in", "offer",
             "rate offered", "total rate", "total pay", "flat rate"),
    "miles": ("miles", "mileage", "distance", "trip miles", "loaded miles", "total miles"),
    "weight": ("weight", "wt", "gross weight", "total weight"),
    "equipment": ("equipment", "equip", "trailer", "trailer type", "truck type",
                  "equipment type", "vehicle"),
    "contact": ("contact", "broker", "company", "posted by", "customer", "shipper",
                "carrier rep", "rep", "agent"),
    "phone": ("phone", "tel", "telephone", "call", "phone number", "contact phone"),
    "email": ("email", "e-mail", "contact email"),
    "load_number": ("load #", "load number", "load no", "load id", "reference",
                    "reference #", "reference number", "ref", "ref #", "order #",
                    "order number", "pro #", "po #", "po number"),
    "commodity": ("commodity", "product", "freight", "cargo", "description"),
    "pieces": ("pallets", "pieces", "pcs", "skids", "count", "qty", "quantity"),
    "notes": ("notes", "comments", "instructions", "requirements", "special instructions"),
}

_LABEL_TO_FACT = {label: fact for fact, labels in LABELS.items() for label in labels}

_CITY_STATE = re.compile(
    r"([A-Z][A-Za-z.'\-]*(?:[ ][A-Z][A-Za-z.'\-]*){0,3}),\s*([A-Z]{2})\b(?:\s+(\d{5}))?")
_DOLLARS = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{2}))?(?!\s*(?:/\s*mi|per\s*mi))",
                      re.I)
_PER_MILE = re.compile(r"\$?\s?(\d+(?:\.\d{1,2})?)\s*(?:/\s*mi(?:le)?\b|per\s*mile|rpm\b)", re.I)
_MILES = re.compile(r"(?<![$\d.])(\d{1,3}(?:,\d{3})+|\d+)\s*(?:mi|miles)\b(?!\s*/)", re.I)
_WEIGHT = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k)?\s*(?:lbs?|pounds)\b", re.I)
_PHONE = re.compile(r"\(?\b\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}\b")
_EMAIL = re.compile(r"\b[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+\b")
_DATE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2})?"
    r"|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?(?:\s+\d{1,2}:\d{2}(?:\s*[ap]m)?)?"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}"
    r"(?:st|nd|rd|th)?(?:,?\s+\d{4})?(?:\s+\d{1,2}:\d{2}(?:\s*[ap]m)?)?",
    re.I)
_PIECES = re.compile(r"\b(\d+)\s*(pallets?|skids?|pieces|pcs|cases|crates)\b", re.I)

#: The plain-language names of what a card needs, in the order a card reads.
WANTED = (
    ("origin", "pickup city"),
    ("destination", "delivery city"),
    ("rate", "rate"),
    ("pickup_date", "pickup date"),
    ("delivery_date", "delivery date"),
    ("equipment", "equipment"),
    ("weight_lbs", "weight"),
    ("distance_miles", "miles"),
    ("contact", "customer"),
)

#: The capture fields a card leads with (`opportunity.KEY_FACTS`). Reported when
#: not read, so the card shows the gap. **No longer required** -- Owner rulings,
#: 2026-09-15: a listing without a rate or a city is still logged. Only a paste
#: nothing could be read from is refused (`nothing_read`).
KEY_FACTS = ("origin", "destination", "rate")


def nothing_read(fields: dict) -> bool:
    """Whether a read found no freight fact the capture contract carries."""
    from dispatch import opportunity

    return not opportunity.has_freight_fact(fields or {})


def _number(text: str):
    cleaned = str(text or "").replace(",", "").replace("$", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _place(text: str) -> str:
    """"City, ST" out of a value, or the value itself when it holds no such shape."""
    match = _CITY_STATE.search(text or "")
    if match:
        return f"{match.group(1).strip()}, {match.group(2)}" if match.group(2) in REGIONS \
            else text.strip()
    return str(text or "").strip()


def _places(text: str) -> list:
    return [(m.start(), f"{m.group(1).strip()}, {m.group(2)}")
            for m in _CITY_STATE.finditer(text or "") if m.group(2) in REGIONS]


def _equipment(text: str) -> str:
    """A trailer type named in the text, using the words capture already knows."""
    from dispatch.opportunity import _EQUIPMENT

    low = str(text or "").lower()
    for kind in sorted(_EQUIPMENT, key=len, reverse=True):
        match = re.search(r"\b%s\b" % re.escape(kind), low)
        if match:
            return text[match.start():match.end()].strip()
    return ""


def _weight(text: str):
    match = _WEIGHT.search(text or "")
    if not match:
        return None
    value = _number(match.group(1))
    if value is None:
        return None
    return int(value * 1000) if match.group(2) else int(value)


def _labelled(text: str) -> dict:
    """Every `Label: value` line whose label is a freight word, first one wins."""
    found: dict = {}
    for raw in str(text or "").splitlines():
        line = raw.strip().lstrip(">").strip()
        if not line:
            continue
        match = re.match(r"^([A-Za-z][A-Za-z #./\-]{0,30}?)\s*(?::|\t)\s*(.*)$", line)
        if not match:
            continue
        label = re.sub(r"\s+", " ", match.group(1).strip().lower()).rstrip(".")
        fact = _LABEL_TO_FACT.get(label)
        value = match.group(2).strip()
        # "From:" and "To:" head every email. They name a lane only when what
        # follows is a place, never when it is a person or an address.
        if label in ("from", "to") and not _places(value):
            continue
        if fact and value and fact not in found:
            found[fact] = value
    return found


def parse_listing(text: str) -> dict:
    """Read pasted listing text. Returns fields, card extras and what is missing.

    `{"fields": {...}, "card_extras": {...}, "missing": [...],
      "key_missing": [...], "nothing_read": bool, "pasted": "..."}`
    """
    pasted = str(text or "")
    labelled = _labelled(pasted)
    fields: dict = {}
    extras: dict = {}

    # --- the lane --------------------------------------------------------
    for fact in ("pickup", "delivery"):
        value = labelled.get(fact, "")
        if not value:
            continue
        # "Pickup: Jacksonville, FL 09/15 08:00" carries a place and a date.
        places = _places(value)
        date = _DATE.search(value)
        target = "origin" if fact == "pickup" else "destination"
        if places:
            labelled.setdefault(target, places[0][1])
        if date:
            labelled.setdefault(f"{fact}_date", date.group(0))
        if not places and not date:
            labelled.setdefault(target, value)

    if labelled.get("origin"):
        fields["origin"] = _place(labelled["origin"])
    if labelled.get("destination"):
        fields["destination"] = _place(labelled["destination"])

    if not fields.get("origin") or not fields.get("destination"):
        taken = {fields.get("origin"), fields.get("destination")}
        spare = [p for _, p in _places(pasted) if p not in taken]
        for key in ("origin", "destination"):
            if not fields.get(key) and spare:
                fields[key] = spare.pop(0)

    if not fields.get("origin") or not fields.get("destination"):
        # "Jacksonville to Atlanta" on a line of its own, with no states.
        for raw in pasted.splitlines():
            line = raw.strip()
            if ":" in line or len(line) > 60:
                continue
            lane = re.match(r"^(.+?)\s+(?:to|->|=>|→)\s+(.+)$", line, re.I)
            if lane:
                fields.setdefault("origin", lane.group(1).strip(" ,.-"))
                fields.setdefault("destination", lane.group(2).strip(" ,.-"))
                break

    # --- money -----------------------------------------------------------
    per_mile = _PER_MILE.search(labelled.get("rate", "")) or _PER_MILE.search(pasted)
    if per_mile:
        extras["rpm"] = float(per_mile.group(1))
    rate = None
    if labelled.get("rate"):
        # A labelled "Rate: $2.50/mi" is a per-mile figure, not the load's pay.
        if not _PER_MILE.search(labelled["rate"]):
            money = _DOLLARS.search(labelled["rate"])
            rate = _number(money.group(0)) if money else _number(labelled["rate"].split()[0])
    if rate is None:
        for money in _DOLLARS.finditer(pasted):
            value = _number(money.group(0))
            if value is not None and value >= 100:
                rate = value
                break
    if rate is not None:
        fields["rate"] = rate

    # --- miles, weight, pieces, equipment --------------------------------
    miles = None
    if labelled.get("miles"):
        miles = _number(re.sub(r"[^\d,.]", "", labelled["miles"].split()[0]))
    if miles is None:
        match = _MILES.search(pasted)
        miles = _number(match.group(1)) if match else None
    if miles:
        extras["distance_miles"] = miles

    weight = _weight(labelled.get("weight", "")) if labelled.get("weight") else None
    if weight is None and labelled.get("weight"):
        weight = int(_number(re.sub(r"[^\d,.]", "", labelled["weight"])) or 0) or None
    if weight is None:
        weight = _weight(pasted)
    if weight:
        extras["weight_lbs"] = weight

    pieces = labelled.get("pieces", "")
    if not pieces:
        match = _PIECES.search(pasted)
        pieces = match.group(0) if match else ""
    weight_words = f"{weight:,} lbs" if weight else ""
    pieces_weight = ", ".join(p for p in (pieces, weight_words) if p)
    if pieces_weight:
        fields["pieces_weight"] = pieces_weight

    equipment = labelled.get("equipment", "") or _equipment(pasted)
    if equipment:
        fields["equipment"] = equipment

    # --- dates, left as the words that were pasted -----------------------
    if labelled.get("pickup_date"):
        fields["pickup_date"] = labelled["pickup_date"]
    if labelled.get("delivery_date"):
        fields["delivery_date"] = labelled["delivery_date"]
    if not fields.get("pickup_date") or not fields.get("delivery_date"):
        used = {fields.get("pickup_date"), fields.get("delivery_date")}
        spare = [m.group(0) for m in _DATE.finditer(pasted) if m.group(0) not in used]
        for key in ("pickup_date", "delivery_date"):
            if not fields.get(key) and spare:
                fields[key] = spare.pop(0)

    # --- who, and their number -------------------------------------------
    if labelled.get("contact"):
        fields["contact"] = labelled["contact"]
    phone = _PHONE.search(labelled.get("phone", "")) or _PHONE.search(pasted)
    if phone:
        extras["broker_phone"] = phone.group(0)
    email = _EMAIL.search(labelled.get("email", "")) or _EMAIL.search(pasted)
    if email:
        extras["broker_email"] = email.group(0)
    if labelled.get("load_number"):
        extras["load_id"] = labelled["load_number"]
    if labelled.get("commodity"):
        extras["commodity"] = labelled["commodity"]
    if labelled.get("notes"):
        fields["notes"] = labelled["notes"]

    return _report(fields, extras, pasted)


def parse_offer_email(text: str) -> dict:
    """A broker's offer email, pasted. Template labels first, then listing shapes.

    A reply on the Mission Template (`mission_template.render_email`) carries
    the template's own labels, and `mission_template.parse_email` and
    `parse_stops` already read those -- so they are asked first and their
    answers win. Whatever the email says in its own words fills the gaps
    through `parse_listing`. Nothing reads a mailbox: the text is pasted.
    """
    from dispatch import mission_template as mt

    values = mt.parse_email(text)
    stops = mt.parse_stops(text)

    fields: dict = {}
    extras: dict = {}
    onto = {
        "pickup_location": "origin", "delivery_location": "destination",
        "pickup_window": "pickup_date", "delivery_window": "delivery_date",
        "customer": "contact", "notes": "notes",
    }
    for key, target in onto.items():
        if values.get(key):
            fields[target] = values[key]
    if values.get("rate"):
        rate = _number(values["rate"].split()[0])
        if rate is not None:
            fields["rate"] = rate
    if values.get("customer_poc") and fields.get("contact"):
        fields["contact"] = f"{fields['contact']} ({values['customer_poc']})"
    if values.get("customer_phone"):
        extras["broker_phone"] = values["customer_phone"]
    if values.get("load_number"):
        extras["load_id"] = values["load_number"]
    if values.get("commodity"):
        extras["commodity"] = values["commodity"]
    if values.get("weight_lbs"):
        weight = _number(values["weight_lbs"])
        if weight:
            extras["weight_lbs"] = int(weight)
    count = " ".join(p for p in (
        f"{values['pallets']} pallets" if values.get("pallets") else "",
        f"{values['pieces']} pieces" if values.get("pieces") else "") if p)
    if count:
        fields["pieces_weight"] = count
    extra_notes = []
    if values.get("service"):
        extra_notes.append(f"Service: {values['service']}")
    for stop in stops:
        extra_notes.append("Stop %s: %s %s" % (stop.get("number"), stop.get("facility", ""),
                                               stop.get("window", "")))
    if extra_notes:
        fields["notes"] = " | ".join(
            ([fields["notes"]] if fields.get("notes") else []) + extra_notes)

    listing = parse_listing(text)
    for key, value in listing["fields"].items():
        fields.setdefault(key, value)
    for key, value in listing["card_extras"].items():
        extras.setdefault(key, value)
    # The template names Dispatch's own intake mailbox; that is not the customer.
    if str(extras.get("broker_email", "")).lower() == mt.INTAKE_MAILBOX.lower():
        extras.pop("broker_email")
    return _report(fields, extras, str(text or ""))


def _report(fields: dict, extras: dict, pasted: str) -> dict:
    combined = dict(fields, **extras)
    missing = [name for key, name in WANTED if not combined.get(key)]
    return {
        "fields": {k: v for k, v in fields.items() if v not in ("", None)},
        "card_extras": {k: v for k, v in extras.items() if v not in ("", None)},
        "missing": missing,
        # Reported, never refused for: a card shows these gaps.
        "key_missing": [k for k in KEY_FACTS if fields.get(k) in (None, "")],
        "nothing_read": nothing_read(fields),
        "pasted": pasted,
    }
