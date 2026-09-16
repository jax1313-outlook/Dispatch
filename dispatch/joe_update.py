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
    # One party, whichever name he uses (Mike, 2026-09-06). The separate
    # pickup Shipper field left the template on 2026-09-15.
    "shipper": "customer",
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
    # The label was "Service Type" until 2026-09-16 and that is still how it is
    # said out loud. A shortened label does not change a man's vocabulary.
    "service type": "service",
    # A two-choice pick since 2026-09-15: the Customer, or Level 1. Its phone
    # and email left the template with it.
    "load control": "controlled_by",
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
    # One field since 2026-09-15: "cargo: 1) Description 2) Pieces / Pallets/
    # 3) Weight".
    "pallets": "pieces_pallets",
    "pieces": "pieces_pallets",
    "notes": "notes",
}

#: Words a driver puts in front of the thing he means.
_LEAD = re.compile(
    r"^\s*(joe[,.]?\s+)?(please\s+)?(update|change|set|correct|add|record|make)?\s*",
    re.I)

#: What sits between the field and the value.
_JOIN = re.compile(r"\s*(?:is|=|:|to)\s+", re.I)


#: The word he puts in front of a shared label when he says it out loud. The
#: page has a heading above the field; speech has nothing, so "phone" on its own
#: names three different fields and must not be guessed at.
_SPOKEN_SECTION = {
    "MISSION SOURCE": "customer",
    "PICKUP": "pickup",
    "DELIVERY": "delivery",
}


def _labels() -> dict:
    """The template's labels as names JOE can be addressed by.

    **A label used once is addressable on its own.** Rate, Consignee, BOL,
    Weight, Miles -- say the word and the value.

    **A label used more than once needs its section said first.** When the
    labels were shortened on 2026-09-16 several became deliberately the same
    word in two or three places: Contact, Phone, Facility, Appointment, Access
    and Special instructions are asked under MISSION SOURCE, PICKUP and
    DELIVERY. On the page the heading above them settles which is which. Out
    loud there is no heading, so "delivery phone" is addressable and "phone" is
    not -- which is how a man says it anyway. Writing a delivery phone into the
    pickup because the sentence was ambiguous is exactly what this module exists
    not to do.
    """
    seen = {}
    for field in mt.TEMPLATE:
        seen[field.label.lower()] = seen.get(field.label.lower(), 0) + 1

    names = {}
    for field in mt.TEMPLATE:
        label = field.label.lower()
        if seen[label] == 1:
            names[label] = field.key
            continue
        prefix = _SPOKEN_SECTION.get(field.section)
        if prefix:
            names["%s %s" % (prefix, label)] = field.key
    return names


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
        choices = _choices_for(key)
        if choices:
            # A field meant to be counted is picked from. A value that is not
            # one of the picks is not written down as though it were.
            picked = [c for c in choices if c.lower() == value.lower()]
            if not picked:
                return _unplaced(spoken, "%s is one of: %s." % (
                    _label_for(key), " or ".join(choices)))
            value = picked[0]
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


def _choices_for(key: str) -> tuple:
    for field in mt.TEMPLATE:
        if field.key == key:
            return tuple(field.choices or ())
    return ()


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
