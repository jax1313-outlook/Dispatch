"""A Mission Record, in the names the Owner's templates ask for.

His registry and the Mission Template do not use the same words, and they do not
have to. `{{pickup_appointment}}` against `pickup_window`, `{{cargo_description}}`
against `commodity`, `{{weight}}` against `weight_lbs`. This module is the one
place the two vocabularies meet, so neither has to bend to the other.

**Nothing is invented.** A fact the record does not hold is simply absent from
the result, and `template_fill` then leaves the placeholder standing -- rule 7.
An empty string here would fill the document with a blank that looks answered.

**Money is absent on purpose.** Mike, 2026-09-16: *"these are accounting issues
not mission issues. not the concern of this program ... All money issues are
deferred to accounting software."* So no invoice number, no invoice date, no
payment terms, no due date, no remit-to. They stay visible on the document and
the accounting software answers them. The rate and the C.O.D. amount are here
because they are facts of the mission the Owner agreed on the call, not
accounting's arithmetic.

**Names this module does not produce are not failures.** *"the variations
between documents and field names must be allowed. not 2 companies are the
same."* A customer's template may ask for anything.
"""

from __future__ import annotations

import re

#: A stored window: "2026-09-16 09:00", or just the date.
_WINDOW = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}))?")

#: A template's "is it in the packet" placeholder, and the checklist line the
#: driver ticks for it (`portal/cockpit.py::PICKUP_ARTIFACTS` /
#: `DELIVERY_ARTIFACTS`). **A tick means "I have it in hand"** -- the Owner's
#: ruling of 2026-09-05 -- so these report what he said he holds, not what a
#: machine guessed from a folder listing.
#:
#: **One placeholder, one line, one tick.** Nothing here maps two placeholders
#: onto the same tick: answering two questions from one answer invents the
#: second.
#:
#: **The three photo names are the Owner's, and they are the same words in the
#: cockpit, the Mission Record, the registry and here** (PUBLISHER HARDENING
#: RULING, 2026-09-16): *"Publisher, Cockpit, Mission Record, and Placeholder
#: Registry must use the same three names."*
#:
#:     PICKUP     Photos - Loaded Vehicle    -> loaded_vehicle_photos_attached
#:     EN ROUTE   Photos - Mid-Route Secure. -> securement_photos_attached
#:     DELIVERY   Photos - Final Condition   -> final_condition_photos_attached
ATTACHED_FROM_CHECKLIST = {
    "pod_attached": "Proof Of Delivery Document",
    "signed_bol_attached": "Bill of Lading (BOL)",
    "invoice_attached": "Invoice To Broker",
    "loaded_vehicle_photos_attached": "Photos - Loaded Vehicle",
    "securement_photos_attached": "Photos - Mid-Route Securement",
    "final_condition_photos_attached": "Photos - Final Condition",
}

#: **Struck. PUBLISHER TEST RULING - REVISION 3, 2026-09-16.** A template still
#: asking for one of these needs revising; nothing will ever answer it.
#:
#: `receiver_title` -- *"Receiver title has no operational value. Titles are
#: generally not collected in freight operations ... not required for delivery
#: proof, claims defense, payment readiness, archive retention."*
#:
#: `pickup_on_time_status` -- *"Derived interpretation. Dispatch already stores
#: Pickup appointment, ARRIVE event, Timeline, Detention records,
#: Communications. The underlying facts remain authoritative. No calculated 'on
#: time' field required."*
#:
#: *"Do not collect. Do not store. Do not display. Do not create placeholders."*
#:
#: `freight_condition_photos_attached` -- struck by the **PUBLISHER HARDENING
#: RULING**, same day, from the cockpit, the templates, the registry, the
#: Publisher mappings and the tests: *"Not a separate operational event. Creates
#: duplicate evidence concepts. Does not represent a distinct workflow
#: milestone."* The loaded vehicle photographed at the shipper already carries
#: what the freight looked like.
REMOVED_FIELDS = frozenset({
    "receiver_title",
    "pickup_on_time_status",
    "freight_condition_photos_attached",
})

#: **Real, and already preserved inside the controlling document. REVISION 3.**
#:
#: *"KEEP AS EVIDENCE ONLY ... The signed POD remains the authoritative source.
#: Publisher should not create separate Mission Record ownership for these
#: fields. The POD image/PDF already preserves printed receiver name and
#: receiver signature. No duplicate tracking field is required. When delivery
#: proof is needed: Retrieve POD."*
#:
#: **The distinction from `REMOVED_FIELDS` is the remedy, and it matters.** A
#: removed field means fix the template. One of these means the answer exists --
#: go and get the POD. Reporting them in one list would send a man to delete
#: something he actually needs.
EVIDENCE_IN_POD = frozenset({"receiver_name", "receiver_signature"})

#: Everything Publisher will never fill, for whichever of the two reasons.
NEVER_FILLED = REMOVED_FIELDS | EVIDENCE_IN_POD

#: What a ticked and an unticked line print as.
HELD = "Yes"
NOT_HELD = "No"


def _split_window(window: str) -> tuple:
    """`(date, time)` from a stored window, either part empty when unwritten."""
    match = _WINDOW.match(str(window or ""))
    if not match:
        return "", ""
    return match.group(1), match.group(2) or ""


def _first(*candidates) -> str:
    for value in candidates:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _maps_link(coords: str) -> str:
    """A fix the driver's tablet recorded, as a link a customer can open.

    Only from coordinates Dispatch actually stored when he pressed ARRIVE. A
    link built from the facility address instead would look like evidence the
    truck was there and be nothing of the kind.
    """
    fix = str(coords or "").strip()
    if not fix:
        return ""
    return "https://www.google.com/maps/search/?api=1&query=%s" % fix.replace(" ", "")


def _attachment_values(record: dict) -> dict:
    """The "is it in the packet" lines, from the driver's own checklist.

    **Silent until he has worked the list.** If `artifacts_held` was never
    written, nobody has said what is in hand, and printing "No" against every
    line would be a document asserting an absence nobody checked. The
    placeholders stay visible instead, which is rule 7.
    """
    if "artifacts_held" not in record:
        return {}
    held = {str(a).strip().lower() for a in (record.get("artifacts_held") or [])}
    return {placeholder: (HELD if line.lower() in held else NOT_HELD)
            for placeholder, line in ATTACHED_FROM_CHECKLIST.items()}


def values_for(record: dict, *, today: str = "", driver_name: str = "",
               delivered: bool = False) -> dict:
    """The placeholder values this Mission Record can answer for.

    Only keys with a real value are returned. `today` is the date the document
    is being produced on, for `{{date}}`; `driver_name` is who ran the load;
    `delivered` is whether the Delivered milestone has been recorded. All three
    are passed in rather than read from a clock, a settings file or the
    database, so this stays pure and a rehearsal produces the same document
    twice.

    **`delivered` is a parameter because the milestone is not on this record.**
    It goes to the load row through `dispatch.services.add_milestone`; the
    sandbox record never learns of it. An earlier version of this module read a
    `delivered_at` field that **nothing has ever written**, so `{{delivery_status}}`
    would have stayed blank on every real run while looking wired -- found by
    walking a load end to end through the routes on 2026-09-16, not by reading
    the code. The caller holds the load row; the caller answers.
    """
    record = dict(record or {})
    card = dict(record.get("card_data") or {})

    def fact(*keys) -> str:
        return _first(*[record.get(k) for k in keys],
                      *[card.get(k) for k in keys])

    pickup_window = fact("pickup_window")
    delivery_window = fact("delivery_window")
    pickup_date, pickup_time = _split_window(pickup_window)
    delivery_date, delivery_time = _split_window(delivery_window)

    # The number the customer quotes back. Mike, 2026-09-16: *"why would system
    # generate a load number when the BOL one is clearly provided ... this is
    # how this company actually list load numbers: Tallahassee-1487."*
    # `load_number.assign` already keeps a supplied number exactly as given and
    # only generates when nobody numbered the work, so the record's own number
    # is the right answer to both placeholders.
    load_number = fact("load_number")

    values = {
        "load_number": load_number,
        "customer_load_number": _first(card.get("load_id"), load_number),
        "date": str(today or "").strip(),
        "customer": fact("customer", "broker"),
        "billing_contact": fact("customer_poc", "broker_poc"),
        "billing_email": fact("customer_email", "broker_email"),
        "consignee": fact("consignee"),
        "bol_number": fact("bol_number"),
        "pickup_location": fact("pickup_location", "origin"),
        "pickup_appointment": pickup_window,
        "pickup_date": pickup_date,
        "pickup_time": pickup_time,
        "delivery_location": fact("delivery_location", "destination"),
        "delivery_appointment": delivery_window,
        "delivery_date": delivery_date,
        "delivery_time": delivery_time,
        "cargo_description": fact("commodity"),
        "pieces_pallets": fact("pieces_pallets"),
        "weight": fact("weight_lbs"),
        # Facts of the mission, agreed on the call -- not accounting's working.
        "rate": fact("rate"),
        "amount": fact("amount"),
        "delivery_notes": fact("delivery_notes"),
        "pickup_notes": fact("pickup_notes"),
        # Who ran it. The same man prepares the packet, so one answer serves
        # both -- and neither is invented here: the caller supplies it.
        "driver_name": str(driver_name or "").strip(),
        "prepared_by": str(driver_name or "").strip(),
        # Where the tablet said the truck was when he pressed ARRIVE. Only the
        # pickup fix: `{{gps_location_link}}` is asked on the Pickup
        # Confirmation and nowhere else, and answering it with a delivery fix on
        # some future template would be quietly wrong.
        "gps_location_link": _maps_link(record.get("pickup_gps")),
        # Delivered when the milestone says so, not when a folder looked full.
        "delivery_status": "Delivered" if delivered else "",
        "pod_status": ("Received" if "proof of delivery document" in
                       {str(a).strip().lower()
                        for a in (record.get("artifacts_held") or [])} else ""),
    }
    values.update(_attachment_values(record))
    return {key: value for key, value in values.items() if value}
