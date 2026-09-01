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

from dispatch import load_number as ln

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
    Field("customer", "Customer or broker", "MISSION SOURCE", required=True,
          spoken="Who is the customer?"),
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
    Field("service", "Service type", "LOAD CONTROL",
          hint="Truckload, courier, medical, expedite",
          spoken="What kind of run is it?"),
    Field("rate", "Rate", "LOAD CONTROL", hint="Linehaul, before accessorials",
          spoken="What does it pay?"),

    # --- PICKUP
    Field("pickup_location", "Pickup facility and address", "PICKUP",
          required=True, spoken="Where does it pick up?"),
    Field("pickup_window", "Pickup appointment", "PICKUP", required=True,
          spoken="When is the pickup appointment?"),
    Field("pickup_contact", "Pickup contact", "PICKUP",
          spoken="Who is the contact at the shipper?"),
    Field("pickup_phone", "Pickup phone", "PICKUP",
          spoken="What is the shipper's phone number?"),
    Field("pickup_notes", "Pickup access instructions", "PICKUP",
          hint="Gate, dock, check-in -- what gets the truck in",
          spoken="Any access instructions for the pickup?"),

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
    #: Additional stops, one per line, pipe separated:
    #:     Stop 2: Publix DC Lakeland | 2026-09-02 14:00 | Dock 7 | 863-555-0114
    #: One pickup and one delivery covers most runs; this carries the rest
    #: without a second template for multi-stop work.
    Field("additional_stops", "Additional stops", "DELIVERY",
          hint="One per line: facility | appointment | contact | phone",
          spoken="Are there any stops after that one?"),

    # --- CARGO
    Field("commodity", "Cargo description", "CARGO", required=True,
          spoken="What is the freight?"),
    Field("pallets", "Pallets", "CARGO", spoken="How many pallets?"),
    Field("pieces", "Pieces", "CARGO", spoken="How many pieces?"),
    Field("weight_lbs", "Weight (lbs)", "CARGO", spoken="What does it weigh?"),

    # --- NOTES
    Field("notes", "Notes", "NOTES",
          hint="Anything else that matters on this run",
          spoken="Anything else I should put down?"),
)

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


def parse_stops(raw: str) -> list:
    """Additional stops, one per line, pipe separated.

    A blank field is no extra stops, which is the common case and must not be
    an error.
    """
    stops = []
    for line in str(raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line.split("|")[0]:
            line = line.partition(":")[2].strip()
        parts = [p.strip() for p in line.split("|")]
        stops.append({
            "facility": parts[0] if parts else "",
            "window": parts[1] if len(parts) > 1 else "",
            "poc": parts[2] if len(parts) > 2 else "",
            "phone": parts[3] if len(parts) > 3 else "",
        })
    return stops


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
              load_number: str = "", existing_load_numbers=None) -> dict:
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
    for key in ("pallets", "pieces", "weight_lbs"):
        if number(key) is not None:
            card[key] = number(key)
    if value("rate"):
        card["rate"] = value("rate")

    stops = [{
        "number": 1,
        "label": "STOP 1",
        "facility": value("delivery_location"),
        "window": value("delivery_window"),
        "poc": value("delivery_contact"),
        "phone": value("delivery_phone"),
        "notes": value("delivery_notes"),
    }]
    for i, stop in enumerate(parse_stops(value("additional_stops")), start=2):
        stops.append({"number": i, "label": f"STOP {i}", "notes": "", **stop})

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
    }
    for key, target in (("customer", "broker"), ("customer_poc", "broker_poc"),
                        ("customer_phone", "broker_phone")):
        if value(key):
            record[target] = value(key)
    for key in ("pickup_location", "pickup_window", "pickup_contact",
                "pickup_phone", "pickup_notes", "delivery_location",
                "delivery_window", "delivery_contact", "delivery_phone",
                "delivery_notes", "commodity", "service", "notes"):
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
