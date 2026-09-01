"""The Mission Template: one shape, whatever brings the work in.

    ONE MISSION TEMPLATE
    MULTIPLE INTAKE METHODS
    ONE MISSION RECORD
    ONE WORKFLOW

Dispatch used to assume missions came from SWEEP. That assumption is no longer
valid. Work arrives from SWEEP, from email, from JOE taking it down by voice,
from a customer direct, from a phone call, from courier and medical routes, and
in time from an API.

**The Mission Record does not care where the work originated.** There is no
courier template, no medical template, no truckload template and no specialty
template. There is one template, and different people and systems populate it.

The temptation with manual entry is always a lighter path -- a shorter form,
fewer fields, "it is only a phone load". What that produces is two kinds of
load, two sets of rules, and a Mission Record that means different things
depending on how it arrived. This module exists to make the short path and the
long path the same path.

The number comes first
----------------------

JOE assigns the Load Number **before** the template is filled in, not after.
That is what lets the number be the email subject, and lets COMI recognise the
reply as mission intake rather than as one more message from a broker.

    Email:  "Joe email me a Mission Template."
            JOE assigns L1-XXXX -> emails template, subject L1-XXXX
            -> driver completes and replies, subject intact
            -> Email Helper -> COMI -> Mission Intake -> Scheduler
            -> Mission Record -> Calendar Entry -> normal workflow

    Voice:  "Joe open a Mission Template."
            JOE assigns L1-XXXX -> walks the template field by field
            -> COMI -> Scheduler -> Mission Record -> Calendar Entry
            -> normal workflow

**JOE is a clerk here and commits nothing.** It issues a number, reads the
template, takes the answers down and hands them over. The Mission Record is
authoritative and this module populates it -- it does not invent a second
mission structure alongside it.
"""

from __future__ import annotations

from dataclasses import dataclass

from dispatch import load_control as lc, load_number as ln

#: Where a completed template is sent. The subject is the Load Number itself --
#: see `dispatch.load_number.is_mission_intake` for the rule COMI applies.
INTAKE_MAILBOX = "Ops@l1truck.com"

#: Every way work reaches Dispatch. The Mission Record is the same object for
#: all of them; only this label differs, and it differs on purpose because
#: "where did this come from" is a real question later.
SOURCE_SWEEP = "SWEEP"
SOURCE_EMAIL = "EMAIL"
SOURCE_JOE = "JOE"
SOURCE_CUSTOMER = "CUSTOMER"
SOURCE_PHONE = "PHONE"
SOURCE_COURIER = "COURIER"
SOURCE_API = "API"
INTAKE_SOURCES = (SOURCE_SWEEP, SOURCE_EMAIL, SOURCE_JOE, SOURCE_CUSTOMER,
                  SOURCE_PHONE, SOURCE_COURIER, SOURCE_API)

#: Kept so older callers and stored records keep resolving. VOICE and MANUAL
#: were the earlier names for what is now JOE and CUSTOMER.
SOURCE_VOICE = SOURCE_JOE
SOURCE_MANUAL = SOURCE_CUSTOMER

#: The operator's six sections, in his order.
SECTIONS = ("MISSION SOURCE", "LOAD CONTROL", "PICKUP", "DELIVERY",
            "CARGO", "NOTES")


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    section: str
    required: bool = False
    hint: str = ""
    #: What JOE says when taking this field down by voice. A template read
    #: aloud badly is a template nobody finishes.
    spoken: str = ""

    def prompt(self) -> str:
        return self.spoken or f"{self.label}?"


#: The template. Field for field, this is what the Driver Cockpit displays --
#: intake and display agree, or a manually created mission renders with holes a
#: swept one does not have.
TEMPLATE: tuple[Field, ...] = (
    # --- MISSION SOURCE: who the work is for and who took it
    # One party, three names depending on who the work came from. A direct
    # customer, the shipper, or a broker -- the record does not need three
    # fields for it, and three fields would only ask which one is current.
    Field("customer", "Customer / Shipper / Broker", "MISSION SOURCE",
          required=True, spoken="Who is the customer, shipper or broker?"),
    Field("customer_poc", "Their contact", "MISSION SOURCE",
          spoken="Who is the contact there?"),
    Field("customer_phone", "Their phone", "MISSION SOURCE",
          spoken="What is their phone number?"),

    # --- LOAD CONTROL: the number, and what the work pays
    #     Not required from the driver. If nobody else numbered this work,
    #     Dispatch numbers it -- see `dispatch/load_number.py`.
    Field("load_number", "Load number (theirs)", "LOAD CONTROL",
          hint="Their number exactly as given. Leave blank and Dispatch assigns one",
          spoken="Do they have a load number for it?"),
    # Who to call when something is wrong with the freight. Not necessarily
    # the broker -- see dispatch/load_control.py. This is the run's default;
    # any stop can name somebody else, and on a real run one usually does.
    Field("control_name", "Load control", "LOAD CONTROL",
          hint="Who to call on issues or damage, if it is the same for the whole run",
          spoken="Who has load control -- who do you call if there is a problem?"),
    Field("control_role", "Load control is the", "LOAD CONTROL",
          hint="Broker, shipper, customer or consignee",
          spoken="Are they the broker, the shipper, or the customer?"),
    Field("control_phone", "Load control phone", "LOAD CONTROL",
          spoken="What is their number?"),
    Field("service", "Service type", "LOAD CONTROL",
          hint="Truckload, courier, medical, expedite",
          spoken="What kind of run is it?"),
    Field("rate", "Rate", "LOAD CONTROL", hint="Linehaul, before accessorials",
          spoken="What does it pay?"),
    Field("rate_basis", "Rate agreed with", "LOAD CONTROL",
          hint="Posted, or who you negotiated it with",
          spoken="Was the rate posted, or did you negotiate it with somebody?"),
    # A load paid at the dock is a load you can drive away from unpaid. The
    # difference between "invoice it" and "collect a check" is not a billing
    # note -- it is an action at the delivery, and the checklist has to say so.
    # C.O.D. is its own field rather than a phrase inside payment terms.
    # Whether the driver leaves the dock with money is too consequential to
    # depend on somebody having written "check" instead of "cheque".
    Field("cod", "C.O.D.", "LOAD CONTROL",
          hint="Amount to collect at delivery. Blank if it is not a C.O.D. load",
          spoken="Is this a C.O.D. load -- do you collect at delivery?"),
    Field("payment_terms", "Payment", "LOAD CONTROL",
          hint="Invoice, or collected on delivery -- say who pays and how",
          spoken="How does this one pay -- invoiced, or do you collect at delivery?"),
    Field("pod_required", "POD required", "LOAD CONTROL",
          hint="What this customer accepts as proof of delivery",
          spoken="What do they want back as proof of delivery?"),

    # --- PICKUP
    Field("pickup_location", "Pickup facility and address", "PICKUP",
          required=True, spoken="Where does the truck load?"),
    # The shipper is a party; the pickup is a place. On an interline or
    # linehaul move they are not the same -- the freight can be shipped by a
    # hospital in Minnesota and collected from a partner's dock in Georgia.
    # Collapsing the two puts the shipper's city in the address field, which
    # is a thousand miles of wrong turn.
    Field("pickup_shipper", "Shipper", "PICKUP",
          hint="Whose freight it is, if not the facility you load at",
          spoken="Who is the shipper, if it is not where you are loading?"),
    Field("pickup_window", "Pickup appointment", "PICKUP", required=True,
          spoken="When is the pickup appointment?"),
    Field("pickup_contact", "Pickup contact", "PICKUP",
          spoken="Who is the contact at the shipper?"),
    Field("pickup_phone", "Pickup phone", "PICKUP",
          spoken="What is the shipper's phone number?"),
    Field("pickup_notes", "Pickup access instructions", "PICKUP",
          hint="Gate, dock, check-in -- what gets the truck in",
          spoken="Any access instructions for the pickup?"),
    # Distinct from access instructions on purpose. Access is how you get in
    # on a normal day; a special instruction changes the plan -- a security
    # hold, a single permitted gate, an escort. Buried among routine notes it
    # gets read at the gate instead of before leaving.
    Field("pickup_special", "Pickup SPECIAL INSTRUCTIONS", "PICKUP",
          hint="Anything that changes the plan: security holds, gate restrictions, escorts",
          spoken="Anything special about getting in there -- security, gate restrictions?"),

    # --- DELIVERY
    Field("delivery_location", "Delivery facility and address", "DELIVERY",
          required=True, spoken="Where does it deliver?"),
    Field("delivery_window", "Delivery appointment", "DELIVERY", required=True,
          spoken="When is the delivery appointment?"),
    Field("delivery_contact", "Delivery contact", "DELIVERY",
          spoken="Who is the contact at the receiver?"),
    Field("delivery_phone", "Delivery phone", "DELIVERY",
          spoken="What is the receiver's phone number?"),
    Field("delivery_notes", "Delivery access instructions", "DELIVERY",
          spoken="Any access instructions for the delivery?"),
    Field("delivery_special", "Delivery SPECIAL INSTRUCTIONS", "DELIVERY",
          hint="Anything that changes the plan at this end",
          spoken="Anything special at the delivery end?"),
    #: Additional stops are captured as repeating STOP blocks rather than as
    #: fields here -- see STOP_FIELDS. A pipe-separated line could not carry
    #: load control legibly, and load control is the field a driver reads at a
    #: dock with damaged freight.
    Field("delivery_control_name", "Stop 1 load control", "DELIVERY",
          hint="Only if it differs from the run's load control",
          spoken="Is load control for this stop the same as the run?"),

    # --- CARGO
    Field("commodity", "Cargo description", "CARGO", required=True,
          hint="What it is overall. Itemise below if it is a mixed load",
          spoken="What is the freight?"),
    # A mixed load is normal, and one commodity field cannot hold two
    # commodities at two weights. Itemising is what lets the totals be
    # computed rather than done in the driver's head at a scale.
    Field("cargo_lines", "Cargo items", "CARGO",
          hint="One per line: description | pallets | weight each (lbs)",
          spoken="Break it down for me -- what is on each pallet?"),
    Field("pallets", "Pallets (total)", "CARGO",
          hint="Leave blank to total the items above",
          spoken="How many pallets altogether?"),
    Field("pieces", "Pieces", "CARGO", spoken="How many pieces?"),
    Field("weight_lbs", "Weight (lbs, total)", "CARGO",
          hint="Leave blank to total the items above",
          spoken="What does it weigh altogether?"),

    # --- NOTES
    Field("notes", "Notes", "NOTES",
          hint="Anything else that matters on this run",
          spoken="Anything else I should put down?"),
)

#: A stop, captured as a repeating block. Every delivery on the run carries
#: these, and load control is among them because it is a stop-level fact: one
#: broker's run can still have the shipper holding authority on stop 2.
STOP_FIELDS: tuple[Field, ...] = (
    Field("facility", "Facility", "STOP", required=True,
          spoken="Where does this one go?"),
    Field("window", "Appointment", "STOP", required=True,
          spoken="When is the appointment?"),
    Field("poc", "Dock contact", "STOP", spoken="Who is the contact at the dock?"),
    Field("phone", "Dock phone", "STOP", spoken="What is the dock number?"),
    Field("notes", "Access instructions", "STOP",
          spoken="Any access instructions?"),
    Field("special", "SPECIAL INSTRUCTIONS", "STOP",
          hint="Anything that changes the plan at this stop",
          spoken="Anything special about this stop?"),
    Field("control_name", "Load control", "STOP",
          hint="Who to call on issues or damage for this stop",
          spoken="Who has load control on this stop?"),
    Field("control_role", "Load control is the", "STOP",
          hint="Broker, shipper, customer or consignee",
          spoken="Are they the broker, the shipper, or the customer?"),
    Field("control_phone", "Load control phone", "STOP",
          spoken="What is their number?"),
    Field("control_ref", "Their reference", "STOP",
          hint="Their load or order number for this stop",
          spoken="Do they have a reference number for this stop?"),
)

STOP_KEYS = tuple(f.key for f in STOP_FIELDS)

TEMPLATE_KEYS = tuple(f.key for f in TEMPLATE)
REQUIRED_KEYS = tuple(f.key for f in TEMPLATE if f.required)

#: Kept resolving for callers written against the earlier field names.
_ALIASES = {"broker": "customer", "broker_poc": "customer_poc",
            "broker_phone": "customer_phone"}


class TemplateError(ValueError):
    """The template could not be turned into a mission, and says why."""


def fields_in(section: str) -> tuple:
    return tuple(f for f in TEMPLATE if f.section == section)


def _resolve(values: dict) -> dict:
    """Accept the old field names as well as the current ones."""
    out = dict(values or {})
    for old, new in _ALIASES.items():
        if out.get(old) and not out.get(new):
            out[new] = out[old]
    return out


# ---------------------------------------------------------------- number ----

def open_template(*, existing_load_numbers=None, supplied: str = "") -> dict:
    """Start an intake. The number is issued **now**, before anything is filled.

    This is the order the doctrine requires: JOE hands out the Load Number when
    the driver asks for a template, so the number can be the email subject and
    COMI can recognise the reply.
    """
    assigned = ln.assign(supplied, existing=existing_load_numbers)
    return {
        "load_number": assigned["load_number"],
        "origin": assigned["origin"],
        "subject": assigned["load_number"],
        "mailbox": INTAKE_MAILBOX,
        "values": blank_template(),
    }


# ---------------------------------------------------------------- render ----

def blank_template() -> dict:
    return {f.key: "" for f in TEMPLATE}


def render_email(values: dict | None = None, *, load_number: str = "") -> str:
    """The template as a driver receives and returns it.

    Plain text on purpose. It is filled in on a phone, in a cab, sometimes with
    one thumb, and a form that needs a browser is a form that waits until he is
    home.
    """
    values = _resolve(values or {})
    lines = []
    if load_number:
        lines += [f"LOAD NUMBER: {load_number}",
                  "Keep this subject line when you reply.", ""]
    lines += [f"Fill in what you have and send this back to {INTAKE_MAILBOX}.",
              "Leave anything you do not know blank -- do not guess.", ""]

    for section in SECTIONS:
        section_fields = fields_in(section)
        if not section_fields:
            continue
        lines += [section, "-" * len(section)]
        for field in section_fields:
            mark = " *" if field.required else ""
            lines.append(f"{field.label}{mark}: {values.get(field.key, '')}")
            if field.hint:
                lines.append(f"    ({field.hint})")
        lines.append("")

    # Additional stops, if the run has any. Blocks rather than a packed line:
    # load control has to be readable at a dock, not decoded.
    lines += ["ADDITIONAL STOPS", "-" * len("ADDITIONAL STOPS"),
              "Copy the block below for each further stop. No extra stops? "
              "Delete it.", "", render_stop_block(2), ""]
    lines += ["* required", ""]
    return "\n".join(lines)


def voice_script() -> list:
    """What JOE asks, in order, when taking work down by voice."""
    return [{"key": f.key, "prompt": f.prompt(), "required": f.required,
             "section": f.section} for f in TEMPLATE]


# ----------------------------------------------------------------- parse ----

def parse_email(body: str) -> dict:
    """Read a returned template back into values.

    Tolerant of what a phone does to an email -- reply markers, wrapping, stray
    blank lines, the section rules -- and deliberately not tolerant of
    inventing a value it could not find.
    """
    label_to_key = {f.label.lower(): f.key for f in TEMPLATE}
    values = blank_template()
    for raw in (body or "").splitlines():
        line = raw.strip().lstrip(">").strip()
        if not line or ":" not in line or set(line) <= {"-"}:
            continue
        label, _, value = line.partition(":")
        key = label_to_key.get(label.strip().rstrip("*").strip().lower())
        if key and not values[key]:
            values[key] = value.strip()
    return values


def render_stop_block(number: int, values: dict | None = None) -> str:
    """One stop, as a labelled block rather than a packed line.

    The pipe-separated line this replaced could not carry load control
    legibly, and load control is the field a driver reads standing at a dock
    with damaged freight. Length is worth paying for there.
    """
    values = values or {}
    lines = [f"STOP {number}", "-" * len(f"STOP {number}")]
    for field in STOP_FIELDS:
        mark = " *" if field.required else ""
        lines.append(f"  {field.label}{mark}: {values.get(field.key, '')}")
        if field.hint:
            lines.append(f"      ({field.hint})")
    return "\n".join(lines)


def parse_stops(body: str) -> list:
    """Every STOP block in a returned template, in order.

    No blocks is one delivery, which is the common case and is not an error.
    """
    label_to_key = {f.label.lower(): f.key for f in STOP_FIELDS}
    stops, current = [], None

    for raw in (body or "").splitlines():
        line = raw.strip().lstrip(">").strip()
        if not line or set(line) <= {"-"}:
            continue

        head = line.rstrip(":").strip().upper()
        if head.startswith("STOP ") and head[5:].strip().isdigit():
            if current is not None:
                stops.append(current)
            current = {"number": int(head[5:].strip())}
            continue

        if current is None or ":" not in line:
            continue
        label, _, value = line.partition(":")
        key = label_to_key.get(label.strip().rstrip("*").strip().lower())
        if key and not current.get(key):
            current[key] = value.strip()

    if current is not None:
        stops.append(current)

    return [stop for stop in stops
            if any(stop.get(k) for k in STOP_KEYS)]


def parse_cargo(raw: str) -> list:
    """Cargo items, one per line: description | pallets | weight each.

    A mixed load is the normal case, not an exception -- one pallet of
    equipment and two of supplies at different weights is one load with three
    positions on the trailer and two descriptions on the paperwork.
    """
    items = []
    for line in str(raw or "").splitlines():
        line = line.strip().lstrip(">").strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]

        def whole(text):
            text = "".join(c for c in str(text) if c.isdigit())
            return int(text) if text else None

        items.append({
            "description": parts[0] if parts else "",
            "pallets": whole(parts[1]) if len(parts) > 1 else None,
            "weight_each": whole(parts[2]) if len(parts) > 2 else None,
        })
    return [i for i in items if i["description"]]


def cargo_totals(items: list) -> dict:
    """Pallets and weight across the items. Partial data totals what it has.

    Returns None rather than 0 for a total nothing was recorded for: zero
    pounds is a claim about the freight, and an absent weight is not.
    """
    pallets = [i["pallets"] for i in items or [] if i.get("pallets")]
    weights = [(i["pallets"] or 1) * i["weight_each"]
               for i in items or [] if i.get("weight_each")]
    return {
        "pallets": sum(pallets) if pallets else None,
        "weight_lbs": sum(weights) if weights else None,
    }


# -------------------------------------------------------------- validate ----

def validate(values: dict) -> list:
    """Every problem, not the first. Returns a list of plain-language reasons.

    The Load Number is **not** among them. Work that nobody else numbered is
    still work, and Dispatch numbers it -- refusing the load would be inventing
    a rule the doctrine does not have.
    """
    values = _resolve(values)
    problems = []
    for field in TEMPLATE:
        if field.required and not str(values.get(field.key, "")).strip():
            problems.append(f"{field.label} is required")
    for key in ("pallets", "pieces", "weight_lbs"):
        raw = str(values.get(key, "")).strip()
        if raw and not raw.replace(",", "").replace(".", "").isdigit():
            problems.append(f"{key} must be a number, got {raw!r}")
    return problems


# ---------------------------------------------------------------- create ----

def to_record(values: dict, *, source: str, taken_by: str = "",
              load_number: str = "", existing_load_numbers=None,
              extra_stops=None) -> dict:
    """Turn a completed template into the Mission Record shape.

    Populates the fields existing Mission Records already use. It does not
    define a second mission structure -- the Mission Record remains
    authoritative and this fills it in.
    """
    if source not in INTAKE_SOURCES:
        raise TemplateError(f"Unknown intake source {source!r}")
    values = _resolve(values)
    problems = validate(values)
    if problems:
        raise TemplateError("Template incomplete:\n  - " + "\n  - ".join(problems))

    def value(key):
        return str(values.get(key, "")).strip()

    def number(key):
        raw = value(key).replace(",", "")
        try:
            return int(float(raw)) if raw else None
        except ValueError:
            return None

    # The number the mission is retrieved by. Supplied if anyone gave us one,
    # ours if not, and never absent.
    assigned = ln.assign(load_number or value("load_number"),
                         existing=existing_load_numbers)

    card = {
        # The broker's own reference stays the broker's -- empty when they
        # never gave one, because our number in that field is how a payment
        # goes missing.
        "load_id": assigned["supplied"],
        "origin": value("pickup_location"),
        "destination": value("delivery_location"),
        "broker": value("customer"),
        "broker_phone": value("customer_phone"),
        "commodity": value("commodity"),
        "pickup_window": value("pickup_window"),
        "delivery_window": value("delivery_window"),
        "source": source.lower(),
    }
    # Itemised cargo becomes the load plan the diagram and the stop-by-stop
    # cargo view already read; totals fall back to the items when the driver
    # did not also state them, so he is never asked for arithmetic he has
    # already given us the parts for.
    items = parse_cargo(value("cargo_lines"))
    totals = cargo_totals(items)
    for key in ("pallets", "pieces", "weight_lbs"):
        if number(key) is not None:
            card[key] = number(key)
        elif totals.get(key) is not None:
            card[key] = totals[key]
    if value("rate"):
        card["rate"] = value("rate")

    # The run's default point of authority. Any stop may name somebody else,
    # and on a real run one usually does.
    mission_control = {
        "control_name": value("control_name"),
        "control_role": lc.normalise_role(value("control_role")),
        "control_phone": value("control_phone"),
    }

    stops = [{
        "number": 1,
        "label": "STOP 1",
        "facility": value("delivery_location"),
        "window": value("delivery_window"),
        "poc": value("delivery_contact"),
        "phone": value("delivery_phone"),
        "notes": value("delivery_notes"),
        "special": value("delivery_special"),
        "control_name": value("delivery_control_name"),
        "control_role": "",
        "control_phone": "",
        "control_ref": assigned["supplied"],
    }]
    for stop in extra_stops or []:
        number = int(stop.get("number") or len(stops) + 1)
        stops.append({
            "number": number,
            "label": f"STOP {number}",
            **{key: str(stop.get(key) or "").strip() for key in STOP_KEYS},
        })

    # Resolved once, here, so every reader sees the same answer rather than
    # each working out inheritance for itself.
    for stop in stops:
        stop["control"] = lc.control_for(stop, mission_control)

    record = {
        "title": f"{value('commodity')} - {value('pickup_location')} "
                 f"to {value('delivery_location')}",
        "card_data": card,
        # The retrieval key. Mission, archive, library, document linkage,
        # communication linkage and COMI all reach the record through it.
        "load_number": assigned["load_number"],
        "load_number_origin": assigned["origin"],
        "intake_source": source,
        "intake_taken_by": taken_by,
        "stops": stops,
        "stop_total": len(stops),
        "stop_number": 1,
        "load_control": mission_control,
        "cargo_items": items,
        "load_plan": [{"position": n, "description": item["description"],
                       "stop": "Stop 1"}
                      for n, item in enumerate(
                          [i for i in items for _ in range(i.get("pallets") or 1)],
                          start=1)],
        # When a run carries more than one point of authority the stop card has
        # to name it. That reverses the one-broker-one-place rule deliberately:
        # that rule was written for a run with one broker and fails the run
        # where stop 2 answers to somebody else.
        "load_control_varies": lc.differs_across(stops, mission_control),
    }
    for key, target in (("customer", "broker"), ("customer_poc", "broker_poc"),
                        ("customer_phone", "broker_phone")):
        if value(key):
            record[target] = value(key)
    for key in ("pickup_location", "pickup_shipper", "pickup_window",
                "pickup_contact", "pickup_phone", "pickup_notes",
                "pickup_special", "delivery_special", "delivery_location",
                "delivery_window", "delivery_contact", "delivery_phone",
                "delivery_notes", "commodity", "service", "notes",
                "rate_basis", "payment_terms", "pod_required", "cod"):
        if value(key):
            record[key] = value(key)
    return record


def create_mission(values: dict, *, source: str, taken_by: str,
                   sandbox_module, mission_module, load_number: str = "") -> dict:
    """Create the Mission Record, numbered the way Dispatch numbers everything.

    `taken_by` is required and is a person: JOE may read a template and write
    down the answers, but a mission arrives on somebody's word and the record
    says whose. It is the same reason an override carries a reason.
    """
    if not str(taken_by or "").strip():
        raise TemplateError(
            "Manual intake requires who took it. A mission arrives on "
            "somebody's word, and the record has to say whose.")

    stored_records = sandbox_module.get_all()
    # get_all() is keyed by id; the records are the values.
    records = (stored_records.values() if hasattr(stored_records, "values")
               else stored_records)
    existing_numbers = [r.get("load_number") for r in records
                        if isinstance(r, dict)]

    record = to_record(values, source=source, taken_by=taken_by,
                       load_number=load_number,
                       existing_load_numbers=existing_numbers)

    mission_number = mission_module.next_mission_number(
        mission_module.assigned_mission_numbers(stored_records))

    entry = sandbox_module.create_entry(
        source_type="dispatch",
        source_id=record["load_number"],
        title=record["title"],
        card_data=record["card_data"],
        summary=f"Taken by {taken_by} via {source.title()} intake",
    )

    stored = sandbox_module.get(entry["id"]) or entry
    for key, val in record.items():
        if key not in ("card_data", "title"):
            stored[key] = val
    stored["mission_number"] = mission_number
    data = sandbox_module._load()
    data[stored["id"]] = stored
    sandbox_module._save(data)
    return stored
