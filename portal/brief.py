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

ONE PAGE, 2026-09-15
====================

Mike marked up a printout of this sheet -- *"this is the idea trying to get
this to one page."* -- and found it is the same document as New Mission. The
brief is now exactly the Mission Template's fields in its seven
sections, IDENTITY included. Status, Intake and Taken by are gone from it, and
so is every field the template dropped. **An older record keeps every value it
stored; a removed field is simply not shown.**

Later the same day (Owner rulings, 2026-09-15): Load Arrangement is gone from it,
and so are stops. **One card is one delivery.** The sheet has no ADDITIONAL STOPS
section and no stop boxes to edit; what it carries in the corner instead is the
group label -- "1 of 3" -- from `dispatch/shipper_group.py`. Stop data an older
record stored is left exactly as it is.
"""

from __future__ import annotations

from dispatch import mission_template as mt


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _field(label: str, value, *, hint: str = "", key: str = "",
           choices: tuple = (), locked: bool = False) -> dict:
    """One line of the card. `empty` is a fact, never a judgement.

    `locked` fields are never written from the brief: the load number once it
    has been quoted, and anything Dispatch assigns.
    """
    shown = _text(value)
    return {"label": label, "value": shown, "empty": not shown,
            "hint": hint, "key": key, "choices": list(choices or ()),
            "locked": locked}


#: Where a value can live besides its own key. The Mission Record grew a card
#: for swept loads and flat fields for intake, so one fact can sit in more than
#: one place. These are **keys to look up**, never values -- an earlier version
#: mixed the two and told them apart by asking whether they were strings, which
#: resolved a field to empty on a record that had it, because a resolved value
#: is a string too.
_CARD_KEYS = {
    "customer": ("broker",),
    "customer_phone": ("broker_phone",),
    # Where a pasted listing or offer email files the address it read. The
    # Customer Portal already reads it there (`portal_access.customer_email`).
    "customer_email": ("broker_email",),
    "load_number": ("load_id",),
    "rate": ("rate",),
    # Typed miles, for the lane neither the provider nor the table answers for
    # (2026-09-16). Here so miles that came in on a capture show on the sheet;
    # the brief does not score, and saving one does not score either.
    "distance_miles": ("distance_miles",),
    "commodity": ("commodity",),
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


def _record_value(record: dict, key: str) -> str:
    """What the record holds for this field, wherever it lives.

    Looks in the flat record, then the card. A field shown as empty because the
    brief looked in one place is worse than no brief at all: it sends a man to
    ask a broker for something he already has written down.
    """
    if key == "pieces_pallets":
        return mt.pieces_pallets_of(record)

    for candidate in _RECORD_KEYS.get(key, (key,)):
        if _text(record.get(candidate)):
            return _text(record.get(candidate))

    card = record.get("card_data") or {}
    for candidate in _CARD_KEYS.get(key, ()):
        if _text(card.get(candidate)):
            return _text(card.get(candidate))

    return ""


#: Never written from the brief. A load number changed after it has been quoted
#: to a broker is how a payment goes missing; a mission number is Dispatch's.
LOCKED_KEYS = ("load_number",) + tuple(f.key for f in mt.TEMPLATE if f.assigned)


def _value_for(record: dict, key: str) -> str:
    value = _record_value(record, key)
    if not value and key == "load_number":
        value = _text((record.get("numbers") or {}).get("load_number"))
    return value


def value_of(record: dict, key: str) -> str:
    """What the record holds for one template field, wherever it lives.

    The public name for what the sheet already does on every line. A caller that
    wants one fact off a Mission Record -- the customer's name to put on a
    button, say -- asks here rather than guessing which of two places it sits in.
    """
    return _value_for(record, key)


def sections_of(record: dict) -> list:
    """The whole card: the Mission Template's sections, IDENTITY first.

    Built from `mission_template.TEMPLATE`, so every field intake can capture
    appears here, nothing else does, and the two cannot drift.
    """
    sections = []
    for name in mt.SECTIONS:
        fields = [_field(f.label, _value_for(record, f.key), hint=f.hint,
                         key=f.key, choices=f.choices,
                         locked=f.key in LOCKED_KEYS)
                  for f in mt.fields_in(name)]
        sections.append({"title": name, "fields": fields, "editable": True})
    return sections


def card_for(record: dict) -> dict:
    """The complete Mission Card, ready to read, edit or print.

    No stops. **One card is one delivery** (Owner ruling, 2026-09-15), so the
    sheet is the Mission Template's sections and nothing beside them. A second
    delivery for the same shipper is a second card, labelled "2 of 3" in the
    corner by `dispatch/shipper_group.py`.
    """
    sections = sections_of(record)
    # Every highlighted field on the sheet. The headline counting fewer than the
    # page shows is the kind of small lie that stops a man trusting the number.
    empty = sum(1 for s in sections for f in s["fields"] if f["empty"])
    return {
        "sections": sections,
        # No Load Arrangement. Owner ruling, 2026-09-15: *"good idea but delete
        # now. for small operation not really useful."* Stored values are kept.
        # Counted, not scored. It is the number of questions worth asking
        # while somebody is on the phone -- not a mark out of ten, and nothing
        # anywhere reads it to decide whether the mission may proceed.
        "empty_count": empty,
    }


def another_delivery_values(record: dict) -> dict:
    """A fresh New Mission form for the same shipper, and nothing else carried.

    `mission_template.SHIPPER_KEYS` says *which* facts belong to the shipper
    rather than to the delivery; this resolves each one off the record wherever
    it happens to live, which is already this module's job. Consignee, BOL, the
    delivery block, the freight, the rate and the notes come back blank: they
    are what makes the next card a different delivery.
    """
    return mt.another_delivery({key: _value_for(record, key)
                                for key in mt.SHIPPER_KEYS})


def editable_keys(record: dict) -> list:
    """Which fields EDIT may write. Everything a person enters on the template.

    What Dispatch assigns is not among them -- a mission number is Dispatch's
    to give. The load number stays writable by a posted form, as it always was,
    but the brief never draws it as a box (`LOCKED_KEYS`).
    """
    return list(mt.ENTERED_KEYS)
