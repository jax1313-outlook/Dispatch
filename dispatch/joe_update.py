"""JOE takes the message. Publisher makes the change.

    Mike -> JOE -> Publisher -> Dispatch -> Mission Record

**JOE does not edit the Mission Record.** He hears what the driver said, works
out which field it belongs to, and hands it over. Publisher performs the update
because Publisher is the production clerk, and Dispatch owns the record. Giving
JOE a pen would quietly make him the owner of mission data, which is the one
thing the authority model does not allow.

    Mike:  "Joe, broker email is sally@xpo.com."

    JOE:   understands  -> field: customer_email, value: sally@xpo.com
           requests     -> Publisher
    JOE:   "Their email updated. 13 fields still have no entry."

This module is the understanding half only. It has no write path of its own and
no import of the store -- see `portal/models/publisher.py:apply_mission_update`
for the half that writes, and `tests/test_joe_update_routing.py` for the test
that fails if a way to write ever appears here.

WHY THIS AND NOT A FORM
=======================

Because the tablet is not always the answer. Sitting in a cab after a broker
call, with a printed brief and handwriting on it, saying four things out loud
beats opening a screen and finding four fields. And if the tablet is broken or
the screen will not load, this is the path that still exists.

Three ways in, any one of which can fail:

    type it into the brief   ·   tell JOE   ·   carry the paper
"""

from __future__ import annotations

import re

from dispatch import mission_template as mt

#: How he actually says a field, mapped to the key it belongs to. Built on top
#: of the template's own labels rather than instead of them: anything the
#: template can capture is addressable, and these are the shortcuts a man uses
#: on the phone.
SPOKEN = {
    "broker": "customer",
    "customer": "customer",
    "shipper": "pickup_shipper",
    "broker email": "customer_email",
    "customer email": "customer_email",
    "their email": "customer_email",
    "email": "customer_email",
    "broker phone": "customer_phone",
    "customer phone": "customer_phone",
    "their phone": "customer_phone",
    "broker contact": "customer_poc",
    "broker poc": "customer_poc",
    "customer contact": "customer_poc",
    "load number": "load_number",
    "rate": "rate",
    "amount": "amount",
    "cod": "cod",
    "payment": "payment_type",
    "service": "service",
    "load control": "control_name",
    "load control phone": "control_phone",
    "load control email": "control_email",
    "pickup": "pickup_location",
    "pickup contact": "pickup_contact",
    "pickup phone": "pickup_phone",
    "pickup appointment": "pickup_window",
    "pickup time": "pickup_window",
    "pickup hours": "pickup_notes",
    "pickup access": "pickup_notes",
    "pickup instructions": "pickup_notes",
    "delivery": "delivery_location",
    "delivery contact": "delivery_contact",
    "delivery phone": "delivery_phone",
    "delivery appointment": "delivery_window",
    "delivery time": "delivery_window",
    "delivery access": "delivery_notes",
    "delivery instructions": "delivery_notes",
    "cargo": "commodity",
    "commodity": "commodity",
    "freight": "commodity",
    "weight": "weight_lbs",
    "pallets": "pallets",
    "pieces": "pieces",
    "notes": "notes",
}

#: Words a driver puts in front of the thing he means.
_LEAD = re.compile(
    r"^\s*(joe[,.]?\s+)?(please\s+)?(update|change|set|correct|add|record|make)?\s*",
    re.I)

#: What sits between the field and the value.
_JOIN = re.compile(r"\s*(?:is|=|:|to)\s+", re.I)


def _labels() -> dict:
    """The template's own labels, lowercased, as addressable names."""
    return {f.label.lower(): f.key for f in mt.TEMPLATE}


def understand(spoken: str) -> dict:
    """What JOE heard, as a field and a value. **Nothing is applied.**

    Longest phrase first, so "broker email" is not read as "broker". A phrase
    JOE cannot place comes back unplaced rather than guessed: writing a
    broker's email into the customer name because the sentence was ambiguous
    is worse than saying "say that again".
    """
    text = _LEAD.sub("", str(spoken or "").strip())
    if not text:
        return _unplaced(spoken, "Nothing to record.")

    names = dict(_labels())
    names.update(SPOKEN)

    lowered = text.lower()
    for phrase in sorted(names, key=len, reverse=True):
        if not lowered.startswith(phrase):
            continue
        remainder = text[len(phrase):]
        value = _JOIN.sub("", remainder, count=1).strip().strip('."')
        if not value:
            return _unplaced(spoken, "I heard the field but no value.")
        key = names[phrase]
        return {
            "understood": True,
            "field": key,
            "label": _label_for(key),
            "value": value,
            "spoken": str(spoken or ""),
            "note": "",
        }

    return _unplaced(spoken, "I could not place that against a field.")


def _unplaced(spoken, note) -> dict:
    return {"understood": False, "field": "", "label": "", "value": "",
            "spoken": str(spoken or ""), "note": note}


def _label_for(key: str) -> str:
    for field in mt.TEMPLATE:
        if field.key == key:
            return field.label
    return key.replace("_", " ").title()


def confirmation(label: str, gaps: int) -> str:
    """What JOE says back once Publisher has made the change.

    The gap count rides along because it is the reason he is doing this at all
    -- he is filling in what a call produced, and how much is left is the next
    thing he wants to know.
    """
    if gaps <= 0:
        return "%s updated. Nothing left with no entry." % label
    return "%s updated. %d field%s still with no entry." % (
        label, gaps, "" if gaps == 1 else "s")
