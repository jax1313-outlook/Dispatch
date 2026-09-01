"""The Mission Template: one shape, whatever brings a load in.

    ONE MISSION TEMPLATE
    MULTIPLE INTAKE METHODS
    ONE MISSION RECORD
    ONE WORKFLOW

A load found by SWEEP, emailed in on a template, or read to JOE at a truck stop
produces the same record, numbered the same way, working the same way.

The temptation with manual entry is always a lighter path -- a quicker form,
fewer fields, "it is only a phone load". What that produces is two kinds of
load, two sets of rules, and a Mission Record that means different things
depending on how it arrived. This module exists to make the short path and the
long path the same path.

Two methods, both landing here:

    Email:  "Joe email me a Mission Template."
            driver completes -> Ops@l1truck.com -> Email Helper -> COMI
            -> Scheduler -> Mission Record -> Load Number

    Voice:  "Joe open a Mission Template."
            JOE takes it down as clerk -> COMI -> Scheduler
            -> Mission Record -> Load Number

**JOE is a clerk here and commits nothing.** It reads the template, takes the
answers and hands them over. Dispatch creates the record and Dispatch assigns
the number, exactly as it does for a mission SWEEP found.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Where a completed template is sent, and the subject token COMI watches for.
INTAKE_MAILBOX = "Ops@l1truck.com"
INTAKE_SUBJECT_TOKEN = "[DISPATCH MISSION INTAKE]"

#: How a mission arrived. Recorded on the record, because "who told us about
#: this load" is a real question later and guessing at it is not possible.
SOURCE_SWEEP = "SWEEP"
SOURCE_EMAIL = "EMAIL"
SOURCE_VOICE = "VOICE"
SOURCE_MANUAL = "MANUAL"
INTAKE_SOURCES = (SOURCE_SWEEP, SOURCE_EMAIL, SOURCE_VOICE, SOURCE_MANUAL)


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    required: bool = False
    hint: str = ""
    #: What JOE says when taking this field down by voice. A template read aloud
    #: badly is a template nobody finishes.
    spoken: str = ""

    def prompt(self) -> str:
        return self.spoken or f"{self.label}?"


#: The template. Field for field, this is what the Driver Cockpit displays --
#: intake and display agree, or a manually created mission renders with holes
#: that a swept one does not have.
TEMPLATE: tuple[Field, ...] = (
    # --- who the load is for
    Field("broker", "Broker", required=True,
          spoken="Who is the broker?"),
    Field("load_number", "Load number (theirs)", required=True,
          hint="The broker's number, exactly as they gave it",
          spoken="What is their load number?"),
    Field("broker_poc", "Broker contact",
          spoken="Who is the contact at the broker?"),
    Field("broker_phone", "Broker phone",
          spoken="What is their phone number?"),
    Field("rate", "Rate", hint="Linehaul, before accessorials",
          spoken="What does it pay?"),

    # --- where it loads
    Field("pickup_location", "Pickup facility and address", required=True,
          spoken="Where does it pick up?"),
    Field("pickup_window", "Pickup appointment", required=True,
          spoken="When is the pickup appointment?"),
    Field("pickup_contact", "Pickup contact",
          spoken="Who is the contact at the shipper?"),
    Field("pickup_phone", "Pickup phone",
          spoken="What is the shipper's phone number?"),
    Field("pickup_notes", "Pickup access instructions",
          hint="Gate, dock, check-in -- what gets the truck in",
          spoken="Any access instructions for the pickup?"),

    # --- where it goes
    Field("delivery_location", "Delivery facility and address", required=True,
          spoken="Where does it deliver?"),
    Field("delivery_window", "Delivery appointment", required=True,
          spoken="When is the delivery appointment?"),
    Field("delivery_contact", "Delivery contact",
          spoken="Who is the contact at the receiver?"),
    Field("delivery_phone", "Delivery phone",
          spoken="What is the receiver's phone number?"),
    Field("delivery_notes", "Delivery access instructions",
          spoken="Any access instructions for the delivery?"),

    # --- what is on the truck
    Field("commodity", "Cargo description", required=True,
          spoken="What is the freight?"),
    Field("pallets", "Pallets", spoken="How many pallets?"),
    Field("pieces", "Pieces", spoken="How many pieces?"),
    Field("weight_lbs", "Weight (lbs)", spoken="What does it weigh?"),
)

TEMPLATE_KEYS = tuple(f.key for f in TEMPLATE)
REQUIRED_KEYS = tuple(f.key for f in TEMPLATE if f.required)


class TemplateError(ValueError):
    """The template could not be turned into a mission, and says why."""


# ---------------------------------------------------------------- render ----

def blank_template() -> dict:
    return {f.key: "" for f in TEMPLATE}


def render_email(values: dict | None = None) -> str:
    """The template as a driver receives and returns it.

    Plain text on purpose. It is filled in on a phone, in a cab, sometimes with
    one thumb, and a form that needs a browser is a form that waits until he is
    home.
    """
    values = values or {}
    lines = [
        INTAKE_SUBJECT_TOKEN,
        "",
        "Fill in what you have and send this back to " + INTAKE_MAILBOX + ".",
        "Leave anything you do not know blank -- do not guess.",
        "",
    ]
    for field in TEMPLATE:
        mark = " *" if field.required else ""
        lines.append(f"{field.label}{mark}: {values.get(field.key, '')}")
        if field.hint:
            lines.append(f"    ({field.hint})")
    lines += ["", "* required", ""]
    return "\n".join(lines)


def voice_script() -> list:
    """What JOE asks, in order, when taking a load down by voice."""
    return [{"key": f.key, "prompt": f.prompt(), "required": f.required}
            for f in TEMPLATE]


# ----------------------------------------------------------------- parse ----

def parse_email(body: str) -> dict:
    """Read a returned template back into values.

    Tolerant of what a phone does to an email -- reply markers, wrapping,
    stray blank lines -- and deliberately not tolerant of inventing a value it
    could not find.
    """
    label_to_key = {f.label.lower(): f.key for f in TEMPLATE}
    values = blank_template()
    for raw in (body or "").splitlines():
        line = raw.strip().lstrip(">").strip()
        if not line or ":" not in line:
            continue
        label, _, value = line.partition(":")
        key = label_to_key.get(label.strip().rstrip("*").strip().lower())
        if key and not values[key]:
            values[key] = value.strip()
    return values


# -------------------------------------------------------------- validate ----

def validate(values: dict) -> list:
    """Every problem, not the first. Returns a list of plain-language reasons."""
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

def to_record(values: dict, *, source: str, taken_by: str = "") -> dict:
    """Turn a completed template into the record shape the cockpit reads.

    The broker's load number is carried across **exactly as given**. Dispatch
    assigns the mission number separately, which is what keeps a phoned-in load
    the same object as a swept one.
    """
    if source not in INTAKE_SOURCES:
        raise TemplateError(f"Unknown intake source {source!r}")
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

    card = {
        "load_id": value("load_number"),
        "origin": value("pickup_location"),
        "destination": value("delivery_location"),
        "broker": value("broker"),
        "broker_phone": value("broker_phone"),
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

    record = {
        "title": f"{value('commodity')} - {value('pickup_location')} to {value('delivery_location')}",
        "card_data": card,
        "intake_source": source,
        "intake_taken_by": taken_by,
    }
    for key in ("broker", "broker_poc", "broker_phone",
                "pickup_location", "pickup_window", "pickup_contact",
                "pickup_phone", "pickup_notes",
                "delivery_location", "delivery_window", "delivery_contact",
                "delivery_phone", "delivery_notes", "commodity"):
        if value(key):
            record[key] = value(key)
    return record


def create_mission(values: dict, *, source: str, taken_by: str,
                   sandbox_module, mission_module) -> dict:
    """Create the Mission Record, numbered the way Dispatch numbers everything.

    `taken_by` is required and is a person: JOE may read a template and write
    down the answers, but a mission arrives on somebody's word and the record
    says whose. It is the same reason an override carries a reason.
    """
    if not str(taken_by or "").strip():
        raise TemplateError(
            "Manual intake requires who took it. A mission arrives on "
            "somebody's word, and the record has to say whose.")

    record = to_record(values, source=source, taken_by=taken_by)
    existing = mission_module.assigned_mission_numbers(sandbox_module.get_all())
    mission_number = mission_module.next_mission_number(existing)

    entry = sandbox_module.create_entry(
        source_type="dispatch",
        source_id=record["card_data"]["load_id"] or f"MANUAL-{mission_number}",
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
