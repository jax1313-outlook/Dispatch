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
SOURCE_TEXT = "TEXT"
SOURCE_API = "API"

#: A hand-opened mission. **Spelled to match `models.LOAD_SOURCES`**, which is
#: the vocabulary that actually reaches a load record and the reports built on
#: one: direct, dat, truckstop, broker_call, email, referral, website, other.
#:
#: The two lists never matched before 2026-09-06. `mission.py` copies the card's
#: source onto the load only when it names something `LOAD_SOURCES` recognises,
#: so five of the six values a person could pick -- phone, customer, courier,
#: text, joe -- were **silently dropped**, and the load booked with no source at
#: all. Only `email` happened to appear in both lists.
#:
#: `direct` was already a valid load source. Nothing needed inventing; the two
#: halves needed to agree.
SOURCE_DIRECT = "DIRECT"

INTAKE_SOURCES = (SOURCE_SWEEP, SOURCE_DIRECT, SOURCE_EMAIL, SOURCE_JOE,
                  SOURCE_CUSTOMER, SOURCE_PHONE, SOURCE_COURIER, SOURCE_TEXT,
                  SOURCE_API)

#: **No longer offered on a screen. Mike's analysis, 2026-09-06.**
#:
#: Six options were rendered, validated and stored, and nothing in the program
#: ever branched on one. Mike took the list apart and it did not survive:
#:
#:   - Phone, Email and Text are **methods of communication**, not sources. How
#:     a customer's voice reached him does not change the load.
#:   - JOE is a **capture method** -- dictation instead of typing -- and has no
#:     contact with the outside world other than Mike, so it cannot be a source.
#:   - Courier and medical are **freight types**, not sources. They belong on
#:     the `service` field, which already exists and is empty.
#:
#: What is left is the distinction that matters: **did a machine find this load,
#: or did a customer bring it to me?** And a person sitting at the intake form
#: can only ever be the second one. **A field with one reachable value is a
#: field that should not be asked**, so the form no longer asks and the record
#: sets its own.
#:
#: Kept as a name for callers and for records already stored.
MANUAL_SOURCES = ()

#: Kept so records stored before 2026-09-06 keep resolving. CUSTOMER was what a
#: hand-opened mission used to be called; DIRECT is what it is now, and unlike
#: CUSTOMER it survives into the load record.

#: Kept so older callers and stored records keep resolving. VOICE and MANUAL
#: were the earlier names for what is now JOE and CUSTOMER.
SOURCE_VOICE = SOURCE_JOE
SOURCE_MANUAL = SOURCE_CUSTOMER

#: The operator's sections, in his order. **The one-page layout, 2026-09-15.**
#: Mike marked up a printed Mission Brief -- *"this is the idea trying to get
#: this to one page."* -- and IDENTITY, which the brief used to draw from a list
#: of its own, is now a section of the template like the rest.
SECTIONS = ("IDENTITY", "MISSION SOURCE", "LOAD CONTROL", "PICKUP", "DELIVERY",
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
    #: A fixed list to pick from, or empty for free text. **A field meant to be
    #: counted must be picked from.** "Medical" typed once and "medical route"
    #: the next time are two categories that should be one, and nothing notices
    #: until a report is finally built and shows both.
    choices: tuple = ()
    #: Dispatch fills this in; nobody types it. Shown on the form and the brief
    #: as the value Dispatch assigned, never as a box to write in.
    assigned: bool = False

    def prompt(self) -> str:
        return self.spoken or f"{self.label}?"


#: The kinds of run Level 1 Transport takes. **Mike's list, 2026-09-06.**
#:
#: This is where Courier and Medical belong. They were sitting in the intake
#: source list, where they were a category error -- a courier run is a kind of
#: freight, not a way a load reached the office -- and where nothing could ever
#: report on them.
#:
#: Picked from, never typed. A field meant to be counted has to be, or
#: "Medical" and "medical route" become two categories that should be one.
#: **Manual entry only.** Mike ruled 2026-09-06 that nothing sources this from
#: a load board. The boards do not use these words, and mapping their
#: categories onto this list would build a tidy-looking lie. Leave it alone.
#:
#: **Reduced to two by the one-page layout, 2026-09-15.** Mike: *"drop status
#: type is LTL / Courier"*. Records that already carry one of the earlier twelve
#: keep it exactly as stored; the list only governs what is offered.
SERVICE_TYPES = (
    "LTL",
    "Courier",
)

#: Who holds load control. **A two-choice pick, 2026-09-15.** Mike, asked
#: whether load control is picked from two: *"2) yes either"*. See
#: `dispatch/load_control.py` for the stop-level detail it replaced on the form.
LOAD_CONTROL_CHOICES = lc.HELD_BY


#: The template. Field for field, this is what the Driver Cockpit displays --
#: intake and display agree, or a manually created mission renders with holes a
#: swept one does not have.
#:
#: **The one-page layout: twenty-nine fields, 2026-09-15.** Mike marked up the
#: printed Mission Brief (*"this is the idea trying to get this to one page."*)
#: and found the brief and New Mission are one document (*"I used to wrong
#: document it should have been the New Mission Document but i find the are the
#: same"*). Removed: Status, Intake and Taken by from the brief; the separate
#: "Load number (theirs)" (the number now sits in IDENTITY); "Load control is
#: the", load control phone and email; Shipper at pickup; Stop 1 load control;
#: Cargo items; and separate Pallets and Pieces, merged into one field (*"cargo:
#: 1) Description 2) Pieces / Pallets/ 3) Weight"*).
#:
#: **One card per delivery: thirty-one fields, 2026-09-15.** Consignee and BOL
#: number join the DELIVERY section, because the card is now one delivery and
#: those are the two facts that make one delivery different from the next. Mike:
#: *"each mission which becomes a load card at commit list the delivery ... the
#: customer is the same but each delivery is a different location and a different
#: Bill of Lading. because the consignee is different."*
#:
#: **Nothing stored was deleted or rewritten.** An older record keeps every value
#: it holds; a removed field simply stops being shown.
TEMPLATE: tuple[Field, ...] = (
    # --- IDENTITY: what this mission is called, and what kind of run it is
    #     The load number is not required from the driver. If nobody else
    #     numbered this work, Dispatch numbers it -- see `dispatch/load_number.py`.
    Field("load_number", "Load Number", "IDENTITY",
          hint="Their number exactly as given. Leave blank and Dispatch assigns one",
          spoken="Do they have a load number for it?"),
    # Dispatch's own sequence. Assigned, never typed -- the same number a swept
    # mission gets (`dispatch/mission.py::next_mission_number`).
    Field("mission_number", "Mission Number", "IDENTITY",
          hint="Assigned by Dispatch",
          spoken="Dispatch assigns the mission number. Anything to add?",
          assigned=True),
    Field("service", "Service Type", "IDENTITY",
          hint="What kind of run",
          choices=SERVICE_TYPES,
          spoken="What kind of run is it?"),

    # --- MISSION SOURCE: who the work is for
    # One party, three names depending on who the work came from. A direct
    # customer, the shipper, or a broker -- the record does not need three
    # fields for it, and three fields would only ask which one is current.
    Field("customer", "Customer / Shipper / Broker", "MISSION SOURCE",
          required=True, spoken="Who is the customer, shipper or broker?"),
    Field("customer_poc", "Their contact", "MISSION SOURCE",
          spoken="Who is the contact there?"),
    Field("customer_phone", "Their phone", "MISSION SOURCE",
          spoken="What is their phone number?"),
    # Stored under the key existing records and the Customer Portal already
    # read (`portal/portal_access.py::customer_email`).
    Field("customer_email", "Their email", "MISSION SOURCE",
          spoken="What is their email address?"),

    # --- LOAD CONTROL: who holds it, and what the work pays
    Field("controlled_by", "Load control", "LOAD CONTROL",
          hint="Who holds load control",
          choices=LOAD_CONTROL_CHOICES,
          spoken="Who has load control -- the customer, or Level 1?"),
    Field("rate", "Rate", "LOAD CONTROL", hint="Linehaul, before accessorials",
          spoken="What does it pay?"),
    # Miles sit beside the rate because together they are the economics: without
    # them the engine cannot score the card at all. Added 2026-09-16. The lane
    # table answers for the lanes this truck runs and a mapping provider will
    # answer for the rest; this box is for the lane neither of them knows, so a
    # load he can price himself is never left unranked. **Optional** -- blank is
    # the normal case and is not an error.
    Field("distance_miles", "Loaded miles", "LOAD CONTROL",
          hint="Only if Dispatch cannot work the lane out",
          spoken="Loaded miles, if you know them -- otherwise say skip?"),
    Field("rate_basis", "Rate agreed with", "LOAD CONTROL",
          hint="Posted, or who you negotiated it with",
          spoken="Was the rate posted, or did you negotiate it with somebody?"),
    # The payment arrangement is encoded here, once, when the record is
    # created. It changes the data on the Mission Record and nothing else --
    # the arrival notice, invoice, POD packet and courtesy email run the same
    # sequence on every load. The driver never has to work out which kind of
    # load he is on.
    Field("payment_type", "Payment type", "LOAD CONTROL",
          hint="Broker Invoice, or C.O.D.",
          spoken="Is it billed to the broker, or C.O.D.?"),
    Field("payor", "Paid by", "LOAD CONTROL",
          hint="Who hands over the money on a C.O.D. load",
          spoken="Who pays you?"),
    Field("amount", "Amount", "LOAD CONTROL",
          hint="C.O.D. loads only",
          spoken="How much do you collect?"),

    # --- PICKUP
    Field("pickup_location", "Pickup facility and address", "PICKUP",
          required=True, spoken="Where does the truck load?"),
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
    #
    # **One card per delivery, 2026-09-15.** The card *is* the delivery, so the
    # two facts that make one delivery different from another lead the section:
    # who signs for it, and which bill of lading travels with it. Mike's case:
    # *"the customer is the same but each delivery is a different location and a
    # different Bill of Lading. because the consignee is different. all three
    # signed Bill of Lading is returned to the shipper as POD."*
    Field("consignee", "Consignee", "DELIVERY",
          hint="Who signs for it",
          spoken="Who is the consignee -- who signs for it?"),
    Field("bol_number", "BOL number", "DELIVERY",
          hint="This card's bill of lading",
          spoken="What is the bill of lading number for this one?"),
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
    #: There are no additional stops. One card is one delivery -- see
    #: `dispatch/shipper_group.py`.

    # --- CARGO
    # Stored under `commodity`, the key every existing record and reader uses.
    Field("commodity", "Description", "CARGO", required=True,
          hint="What the freight is",
          spoken="What is the freight?"),
    # One field for the count, in his words: "4 pallets", "20 pieces", or both.
    # Free text on purpose -- a count that has to be a number is a count that
    # cannot say which of the two it is.
    Field("pieces_pallets", "Pieces / Pallets", "CARGO",
          hint="How many, and of what -- pieces, pallets or both",
          spoken="How many pieces or pallets?"),
    Field("weight_lbs", "Weight (lbs, total)", "CARGO",
          spoken="What does it weigh altogether?"),

    # --- NOTES
    Field("notes", "Notes", "NOTES",
          hint="Anything else that matters on this run",
          spoken="Anything else I should put down?"),
)

#: **Stops are gone as an entry concept, 2026-09-15.** `STOP_FIELDS`,
#: `render_stop_block`, `parse_stops` and the ADDITIONAL STOPS section left with
#: them. Mike ruled one card per delivery and said why stops could not carry it:
#:
#:     "rain stops one stop from completing so the driver returns with one load
#:      still onboard. This is why each must stand alone totally. the only
#:      binding item is the shipper. Everything thing else stands alone."
#:
#: **Stored stop data on older records is not deleted and not rewritten.** It is
#: read where it is still read -- the Driver Cockpit renders an older multi-stop
#: record exactly as it is stored -- and it is no longer entered, shown on the
#: brief, or asked for by email.

TEMPLATE_KEYS = tuple(f.key for f in TEMPLATE)
REQUIRED_KEYS = tuple(f.key for f in TEMPLATE if f.required)
#: What a person may type. Everything but what Dispatch assigns.
ENTERED_KEYS = tuple(f.key for f in TEMPLATE if not f.assigned)

#: Kept resolving for callers written against the earlier field names.
_ALIASES = {"broker": "customer", "broker_poc": "customer_poc",
            "broker_phone": "customer_phone", "broker_email": "customer_email"}


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


def pieces_pallets_of(record: dict) -> str:
    """The Pieces / Pallets value, on a record of any age. **Read only.**

    Written since 2026-09-15 as one field. A record written before then carries
    separate `pallets` and `pieces` counts, flat or on its card; they are read
    together under the merged field and never rewritten.
    """
    record = record or {}
    merged = str(record.get("pieces_pallets") or "").strip()
    if merged:
        return merged
    card = record.get("card_data") or {}
    parts = []
    for key in ("pallets", "pieces"):
        value = record.get(key)
        if value in (None, "", []):
            value = card.get(key)
        if value not in (None, "", []):
            parts.append(f"{value} {key}")
    return " / ".join(parts)


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

    # No ADDITIONAL STOPS block. One card is one delivery, so a second delivery
    # for the same shipper is a second template, not a block at the bottom of
    # this one.
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
    inventing a value it could not find. A value written against a field
    Dispatch assigns is not read: the mission number is Dispatch's to give.
    """
    label_to_key = {f.label.lower(): f.key for f in TEMPLATE if not f.assigned}
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


# ------------------------------------------------ another for this shipper ----

#: What a second delivery for the same shipper carries over, and nothing else.
#:
#: **Mike, 2026-09-15:** *"Nothing about it binds them together ... the only
#: binding item is the shipper. Everything thing else stands alone."* So the
#: shipper, how to reach him, how the work is paid for, and the pickup the truck
#: is already going to. The consignee, the BOL, the whole delivery block, the
#: freight and the notes start blank, because those are what make this card a
#: different delivery. The rate starts blank too: *"2 out of three get paid that
#: day"* -- the money is the card's own.
SHIPPER_KEYS = (
    "service",
    "customer", "customer_poc", "customer_phone", "customer_email",
    "controlled_by", "payment_type", "payor", "amount",
    "pickup_location", "pickup_window", "pickup_contact", "pickup_phone",
    "pickup_notes", "pickup_special",
)


def another_delivery(values) -> dict:
    """A blank template carrying only the shipper and the pickup facts.

    `values` is anything that answers `.get(key)` for a template key -- the
    caller resolves each one from the record it came off (`portal.brief`
    already knows where a value can live), so this stays the one place that
    says *which* facts belong to the shipper rather than to the delivery.
    """
    blank = blank_template()
    for key in SHIPPER_KEYS:
        blank[key] = str((values or {}).get(key) or "").strip()
    return blank


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
    # Pieces / Pallets is words ("4 pallets / 20 pieces"); only the total
    # weight is a number.
    for key in ("weight_lbs",):
        raw = str(values.get(key, "")).strip()
        if raw and not raw.replace(",", "").replace(".", "").isdigit():
            problems.append(f"{key} must be a number, got {raw!r}")
    return problems


# ---------------------------------------------------------------- create ----

def to_record(values: dict, *, source: str,
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
    if number("weight_lbs") is not None:
        card["weight_lbs"] = number("weight_lbs")
    if value("rate"):
        card["rate"] = value("rate")
    # Typed miles beat the lane table and are beaten by a live mapping provider
    # (`dispatch/distance.py::miles_between`), which marks them MANUAL and says
    # so on the card. Absent is absent: never a zero, which would read as a
    # measured distance of nothing.
    if number("distance_miles"):
        card["distance_miles"] = number("distance_miles")

    record = {
        "title": f"{value('commodity')} - {value('pickup_location')} "
                 f"to {value('delivery_location')}",
        "card_data": card,
        # The retrieval key. Mission, archive, library, document linkage,
        # communication linkage and COMI all reach the record through it.
        "load_number": assigned["load_number"],
        "load_number_origin": assigned["origin"],
        "intake_source": source,
        # No "taken by". Owner ruling, 2026-09-15: *"meaningless AI thought it
        # was useful. Delete."* An older record that stored one keeps it; nothing
        # writes or shows it.
        #
        # No stop list either. One card is one delivery (2026-09-15), so there is
        # nothing for a stop list to hold that the DELIVERY fields do not. An
        # older record that stored one keeps it exactly as written.
    }
    for key, target in (("customer", "broker"), ("customer_poc", "broker_poc"),
                        ("customer_phone", "broker_phone")):
        if value(key):
            record[target] = value(key)
    for key in ("customer_email", "controlled_by", "pickup_location",
                "pickup_window", "pickup_contact", "pickup_phone",
                "pickup_notes", "pickup_special", "delivery_special",
                "consignee", "bol_number",
                "delivery_location", "delivery_window", "delivery_contact",
                "delivery_phone", "delivery_notes", "commodity",
                "pieces_pallets", "service", "notes", "rate_basis",
                "payment_type", "payor", "amount"):
        if value(key):
            record[key] = value(key)
    return record


def create_mission(values: dict, *, source: str,
                   sandbox_module, mission_module, load_number: str = "") -> dict:
    """Create the Mission Record, numbered the way Dispatch numbers everything.

    Nobody is recorded as having taken it down. Owner ruling, 2026-09-15:
    *"meaningless AI thought it was useful. Delete."*
    """
    stored_records = sandbox_module.get_all()
    # get_all() is keyed by id; the records are the values.
    records = (stored_records.values() if hasattr(stored_records, "values")
               else stored_records)
    existing_numbers = [r.get("load_number") for r in records
                        if isinstance(r, dict)]

    record = to_record(values, source=source,
                       load_number=load_number,
                       existing_load_numbers=existing_numbers)

    mission_number = mission_module.next_mission_number(
        mission_module.assigned_mission_numbers(stored_records))

    entry = sandbox_module.create_entry(
        source_type="dispatch",
        source_id=record["load_number"],
        title=record["title"],
        card_data=record["card_data"],
        summary=f"{source.title()} intake",
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
