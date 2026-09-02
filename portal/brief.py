"""The Mission BRIEF: the whole Mission Record, on one sheet, before the call.

    Show me the whole mission. Show me what is missing. Let me write it in.
    Let me print it.

This is the SAM Brief, rediscovered. In SAM the BRIEF was not the opportunity
-- it was where a human stepped back and evaluated one before committing. The
same tool belongs here, and for the same reason: the Driver Cockpit answers
*how do I run this mission*, and the BRIEF answers *should I run it, and what
do I still need to ask*.

    SWEEP -> Mission Card -> BRIEF -> broker call -> accept or reject

WHAT IT IS NOT
==============

Not a report, not a summary, not an interpretation. It is the Mission Record
rendered for a human to read, and it shows every field the Mission Template
can capture -- which is why it is built from that template rather than from a
second list. A brief with its own field list is a brief that drifts from
intake by the second revision.

**Empty is not a negative. It is empty. Move on.**

An empty field is drawn in pale red and nothing else happens. No score, no
completeness percentage, no required-field logic, no warning, no block. The
colour exists so that a man on the phone to a broker can see at a glance what
is still worth asking about, while he already has somebody on the line. That
is the entire purpose:

    This eliminates getting down to arrival notice and not having a
    phone number.

The system reports. Mike decides.
"""

from __future__ import annotations

from dispatch import load_control as lc, mission_template as mt


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _field(label: str, value, *, hint: str = "", key: str = "") -> dict:
    """One line of the card. `empty` is a fact, never a judgement."""
    shown = _text(value)
    return {"label": label, "value": shown, "empty": not shown,
            "hint": hint, "key": key}


#: Where a value can live besides its own key. The Mission Record grew a card
#: for swept loads, flat fields for intake and a nested block for load control,
#: so one fact can sit in any of three places. These are **keys to look up**,
#: never values -- an earlier version mixed the two and told them apart by
#: asking whether they were strings, which resolved load control to empty on a
#: record that had it, because a resolved value is a string too.
_CARD_KEYS = {
    "customer": ("broker",),
    "customer_phone": ("broker_phone",),
    "load_number": ("load_id",),
    "rate": ("rate",),
    "commodity": ("commodity",),
    "pallets": ("pallets",),
    "pieces": ("pieces",),
    "weight_lbs": ("weight_lbs",),
    "pickup_location": ("origin",),
    "delivery_location": ("destination",),
    "pickup_window": ("pickup_window",),
    "delivery_window": ("delivery_window",),
}

_RECORD_KEYS = {
    "customer": ("customer", "broker"),
    "customer_poc": ("customer_poc", "broker_poc"),
    "customer_phone": ("customer_phone", "broker_phone"),
    "customer_email": ("customer_email", "broker_email"),
}

#: Load control lives in its own block on the record.
_CONTROL_KEYS = ("control_name", "control_role", "control_phone",
                 "control_email", "control_ref")


def _record_value(record: dict, key: str) -> str:
    """What the record holds for this field, wherever it lives.

    Looks in the flat record, then the load-control block, then the card. A
    field shown as empty because the brief looked in one place is worse than
    no brief at all: it sends a man to ask a broker for something he already
    has written down.
    """
    for candidate in _RECORD_KEYS.get(key, (key,)):
        if _text(record.get(candidate)):
            return _text(record.get(candidate))

    if key in _CONTROL_KEYS:
        control = record.get("load_control") or {}
        if _text(control.get(key)):
            return _text(control.get(key))

    card = record.get("card_data") or {}
    for candidate in _CARD_KEYS.get(key, ()):
        if _text(card.get(candidate)):
            return _text(card.get(candidate))

    return ""


def _cargo_line_text(record: dict) -> str:
    """The itemised cargo as the template writes it, from what was stored."""
    lines = []
    for item in record.get("cargo_items") or []:
        if not isinstance(item, dict):
            continue
        parts = [_text(item.get("description"))]
        if item.get("pallets") is not None:
            parts.append(str(item["pallets"]))
        if item.get("weight_each") is not None:
            parts.append(str(item["weight_each"]))
        lines.append(" | ".join(parts))
    return "\n".join(lines)


#: Fields the record carries that the template does not ask for. They belong on
#: the card because the point is the whole record, not the intake form.
EXTRA_FIELDS = {
    "MISSION SOURCE": (("customer_email", "Their email"),),
    "LOAD CONTROL": (("control_email", "Load control email"),),
}


def identity_of(record: dict) -> list:
    """What this mission is called, and where it came from."""
    numbers = record.get("numbers") or {}
    return [
        _field("Load Number", _record_value(record, "load_number")
               or numbers.get("load_number"), key="load_number"),
        _field("Mission Number", record.get("mission_number")),
        _field("Status", record.get("status")),
        _field("Intake", record.get("intake_source")),
        _field("Taken by", record.get("intake_taken_by"), key="intake_taken_by"),
    ]


def sections_of(record: dict) -> list:
    """The whole card, in the operator's six sections plus identity.

    Built from `mission_template.TEMPLATE`, so every field intake can capture
    appears here and the two cannot drift.
    """
    sections = [{"title": "IDENTITY", "fields": identity_of(record),
                 "editable": False}]

    for name in mt.SECTIONS:
        fields = []
        for f in mt.fields_in(name):
            value = _record_value(record, f.key)
            if not value and f.key == "cargo_lines":
                value = _cargo_line_text(record)
            fields.append(_field(f.label, value, hint=f.hint, key=f.key))
        for key, label in EXTRA_FIELDS.get(name, ()):
            fields.append(_field(label, _record_value(record, key), key=key))
        sections.append({"title": name, "fields": fields, "editable": True})

    return sections


def stops_of(record: dict) -> list:
    """Every stop, each with its own authority.

    On a run where load control varies between stops, this is where a man on
    the phone sees that stop 2 answers to somebody else.
    """
    stops = []
    for stop in record.get("stops") or []:
        if not isinstance(stop, dict):
            continue
        control = lc.control_for(stop, record.get("load_control") or {})
        stops.append({
            "label": stop.get("label") or "STOP %s" % stop.get("number", "?"),
            "number": stop.get("number"),
            "fields": [
                _field("Facility", stop.get("facility")),
                _field("Appointment", stop.get("window")),
                _field("Dock contact", stop.get("poc")),
                _field("Dock phone", stop.get("phone")),
                _field("Access instructions", stop.get("notes")),
                _field("SPECIAL INSTRUCTIONS", stop.get("special")),
                _field("Load control", control["name"]),
                _field("Load control is the", control["role_label"]),
                _field("Load control phone", control["phone"]),
                _field("Their reference", control["reference"]),
            ],
        })
    return stops


def cargo_of(record: dict) -> list:
    """The itemised freight, when the load is mixed."""
    return [{"description": item.get("description", ""),
             "pallets": item.get("pallets"),
             "weight_each": item.get("weight_each")}
            for item in (record.get("cargo_items") or [])
            if isinstance(item, dict)]


def arrangement_of(record: dict) -> dict:
    """Where it sits in the van, if he has recorded it."""
    from portal import cockpit

    return cockpit.load_arrangement_for(record)


def card_for(record: dict) -> dict:
    """The complete Mission Card, ready to read, edit or print."""
    sections = sections_of(record)
    stops = stops_of(record)
    # Every highlighted field on the sheet, including the stops. The headline
    # counting fewer than the page shows is the kind of small lie that stops a
    # man trusting the number.
    empty = sum(1 for s in sections for f in s["fields"] if f["empty"])
    empty += sum(1 for stop in stops for f in stop["fields"] if f["empty"])
    return {
        "sections": sections,
        "stops": stops,
        "cargo": cargo_of(record),
        "arrangement": arrangement_of(record),
        # Counted, not scored. It is the number of questions worth asking
        # while somebody is on the phone -- not a mark out of ten, and nothing
        # anywhere reads it to decide whether the mission may proceed.
        "empty_count": empty,
    }


def editable_keys(record: dict) -> list:
    """Which fields EDIT may write. Everything the template can capture.

    Identity is not among them: a load number changed on a brief after the
    number has been quoted to a broker is how a payment goes missing.
    """
    keys = [f.key for f in mt.TEMPLATE]
    for extra in EXTRA_FIELDS.values():
        keys.extend(key for key, _ in extra)
    return keys
