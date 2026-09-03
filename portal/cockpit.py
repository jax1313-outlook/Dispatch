"""Driver Cockpit presentation logic.

Pure functions over a Mission Record. No Flask, no store, no I/O -- the screen
is a view of the record, and a view that reaches for data of its own is a second
record wearing a template.

The design this serves is recorded in `Driver_Cockpit_Design_Notes_2026-08-31`:
one screen, three modes, the layout static and only the contents, the emphasis,
the checklist and the live actions changing with the mode.
"""

from __future__ import annotations

#: JOE's words for system conditions. Nothing that names a subsystem reaches
#: the glass; the driver is talking to JOE, not to a mail transport.
from dispatch import load_control as lc
from portal import joe_voice

# ---------------------------------------------------------------- modes ----

#: The driver's three situations, in the driver's own words.
#:
#: These replaced CURRENT / PICKUP / DELIVERY. "Current" is a software state;
#: a driver is going to a pickup, moving freight, or making a delivery. The
#: operator hesitated over CURRENT for days and stopped hesitating the moment
#: IN TRANSIT was said out loud.
MODE_PICKUP = "PICKUP"
MODE_IN_TRANSIT = "CURRENT"
MODE_DELIVERY = "DELIVERY"

#: Reverted to CURRENT on the operator's instruction. He preferred IN TRANSIT --
#: it is how a driver speaks -- but raised the right objection when the change
#: turned out to touch more than a label: CURRENT is a *resolver*, meaning
#: "whichever phase this record is actually in", while IN TRANSIT reads as a
#: third phase of its own. Changing a word is cheap; changing the state model is
#: not, and it is not worth doing on a first draft to gain a nicer noun.
#:
#: The label is one string. It costs nothing to switch back once the phase
#: question is settled on purpose rather than as a side effect.
#: Two controls. CURRENT was dropped on the operator's instruction: a driver is
#: going to a pickup or making a delivery, and a third button for "whichever of
#: those you are already in" is a button that answers a question he did not ask.
#:
#: It survives as the *default* rather than as a control -- opening the cockpit
#: with no mode chosen still resolves to the phase the record is actually in.
MODES = (
    {"key": MODE_PICKUP, "label": "PICKUP"},
    {"key": MODE_DELIVERY, "label": "DELIVERY"},
)

MODE_LABELS = {m["key"]: m["label"] for m in MODES}
MODE_LABELS[MODE_IN_TRANSIT] = "CURRENT"   # still addressable by URL

#: `dispatch.mission` speaks the same three words, so the mapping is direct.
_BACKEND_VIEW = {
    MODE_PICKUP: "PICKUP",
    MODE_IN_TRANSIT: "CURRENT",
    MODE_DELIVERY: "DELIVERY",
}


def normalise_mode(requested: str | None, record: dict | None = None) -> str:
    """Accept a mode, or resolve the one the record is actually in.

    With no mode asked for, the phase decides: before the freight is loaded he
    is going to a pickup, after it he is making a delivery. CURRENT and
    IN_TRANSIT still resolve, so older links open where they used to.
    """
    key = str(requested or "").upper().replace(" ", "_").replace("-", "_")
    if key in (MODE_PICKUP, MODE_DELIVERY):
        return key
    if key in ("CURRENT", "IN_TRANSIT"):
        return default_mode(record)
    return default_mode(record)


#: Statuses before the freight is on the truck. After them, the next thing that
#: matters is where it has to be.
_PICKUP_STATUSES = {"", "open", "created", "dispatched", "en_route_pickup", "at_pickup"}


def default_mode(record: dict | None = None) -> str:
    """The phase the record is in, which is what CURRENT used to answer."""
    status = str((record or {}).get("status") or "").strip().lower()
    return MODE_PICKUP if status in _PICKUP_STATUSES else MODE_DELIVERY


def backend_view(mode: str) -> str:
    return _BACKEND_VIEW.get(mode, "CURRENT")


# ------------------------------------------------------------- emphasis ----

def emphasis_for(mode: str) -> dict:
    """Which end of the run is bright, and which is merely present.

    Nothing is hidden. A driver who cannot see where the mission started has
    lost his orientation, not just a panel -- so the non-active end stays
    readable and simply stops competing.
    """
    if mode == MODE_PICKUP:
        return {"pickup": "bright", "delivery": "subdued"}
    if mode == MODE_DELIVERY:
        return {"pickup": "subdued", "delivery": "bright"}
    return {"pickup": "neutral", "delivery": "neutral"}


# ------------------------------------------------------------ the record ----

def _first(record: dict, *keys, default: str = "—") -> str:
    card = record.get("card_data") or {}
    for key in keys:
        value = record.get(key) or card.get(key)
        if value not in (None, "", []):
            return str(value)
    return default


def ends_for(record: dict) -> dict:
    return {
        "pickup": {
            "place": _first(record, "pickup_location", "origin"),
            "window": _first(record, "pickup_window", "pickup_appointment"),
        },
        "delivery": {
            "place": _first(record, "delivery_location", "destination"),
            "window": _first(record, "delivery_window", "delivery_appointment"),
        },
    }


def cargo_for(record: dict) -> dict:
    """Description, then the three facts a driver keeps in the back of his mind."""
    card = record.get("card_data") or {}
    parts = []
    for key, unit in (("pallets", "pallets"), ("pieces", "pieces"), ("weight_lbs", "lbs")):
        value = record.get(key) or card.get(key)
        if value not in (None, "", []):
            parts.append(f"{value} {unit}")
    return {
        "description": _first(record, "commodity", "cargo", default="Not stated"),
        "brackets": " · ".join(parts) if parts else "no cargo detail recorded",
    }


def broker_for(record: dict) -> dict:
    return {
        "name": _first(record, "broker", "broker_name", default=""),
        "reference": (record.get("numbers") or {}).get("load_label") or "—",
        "phone": _first(record, "broker_phone", default=""),
    }


def stop_list(record: dict) -> list:
    """Every stop on the run, each with its own delivery information.

    A multi-stop run is not one delivery seen three times. Each stop has its own
    facility, its own appointment, its own contact and its own freight, and the
    screen has to switch between them without the driver losing the mission.
    """
    raw = record.get("stops") or []
    stops = []
    for i, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict):
            continue
        stops.append({
            "number": entry.get("number") or i,
            "label": entry.get("label") or f"STOP {entry.get('number') or i}",
            "facility": entry.get("facility") or entry.get("address") or "",
            "window": entry.get("window") or "",
            "poc": entry.get("poc") or "",
            "phone": entry.get("phone") or "",
            "notes": entry.get("notes") or "",
            "gps": entry.get("gps") or "",
            # Who holds authority for this stop, carried through rather than
            # normalised away. Dropping these here silently fell back to the
            # run's default, which showed the broker on the stop that answers
            # to the shipper -- the precise failure this data exists to stop.
            "control_name": entry.get("control_name") or "",
            "control_role": entry.get("control_role") or "",
            "control_phone": entry.get("control_phone") or "",
            "control_ref": entry.get("control_ref") or "",
            "special": entry.get("special") or "",
        })
    return stops


def stops_for(record: dict, selected: int | None = None) -> dict:
    """Where the driver is in the run, and which stop the screen is showing."""
    listed = stop_list(record)
    if listed:
        total = len(listed)
    else:
        try:
            total = int(record.get("stop_total") or 1)
        except (TypeError, ValueError):
            total = 1

    if selected is None:
        try:
            selected = int(record.get("stop_number") or 1)
        except (TypeError, ValueError):
            selected = 1
    try:
        selected = int(selected)
    except (TypeError, ValueError):
        selected = 1
    number = max(1, min(selected, total))

    return {
        "number": number,
        "total": total,
        "label": f"STOP {number} OF {total}",
        "list": listed,
        "selectable": total > 1,
        "has_next": number < total,
        "has_previous": number > 1,
        "next_sub": (f"Advance to stop {number + 1}" if number < total
                     else "Last stop on this run"),
        "previous_sub": (f"Back to stop {number - 1}" if number > 1
                         else "First stop on this run"),
    }


def selected_stop(record: dict, number: int) -> dict:
    """The stop being shown, or an empty shape when the run has no stop list."""
    for stop in stop_list(record):
        if int(stop["number"]) == int(number):
            return stop
    return {}


# -------------------------------------------------- mission-level sections --

def cargo_by_stop(record: dict) -> dict:
    """Truck-wide cargo, summarised by the stop it comes off at.

    Not the current stop's cargo -- the whole truck. A driver planning an unload
    needs to know what else is aboard and whose it is, and a summary that shows
    only the stop he is standing at hides the freight behind it.
    """
    plan = record.get("load_plan") or []
    by_stop: dict = {}
    for entry in plan:
        if not isinstance(entry, dict):
            continue
        stop = entry.get("stop") or "Unassigned"
        row = by_stop.setdefault(stop, {"stop": stop, "description": "", "pallets": 0})
        row["pallets"] += 1
        if not row["description"]:
            row["description"] = entry.get("description") or ""

    card = record.get("card_data") or {}
    totals = []
    for key, unit in (("pallets", "pallets"), ("pieces", "pieces"), ("weight_lbs", "lbs")):
        value = record.get(key) or card.get(key)
        if value not in (None, "", []):
            totals.append(f"{value} {unit}")

    return {
        "rows": list(by_stop.values()),
        "summary": cargo_for(record)["description"],
        "total": " · ".join(totals) if totals else "no cargo detail recorded",
        "has_rows": bool(by_stop),
    }


def _drive_time(miles) -> str:
    """Planning drive time from distance. Stated as planning, not as a promise."""
    try:
        hours = float(miles) / 50.0
    except (TypeError, ValueError):
        return ""
    whole = int(hours)
    minutes = int(round((hours - whole) * 60))
    if minutes == 60:
        whole, minutes = whole + 1, 0
    return f"{whole}h {minutes:02d}m" if whole else f"{minutes}m"


def end_detail(record: dict, end: str, stop_number: int | None = None) -> dict:
    """What a driver needs to get from where he is to this end, and get in.

    **The filter is travel.** Not everything known about the stop -- what is
    needed to reach it and be admitted: where it is, when he is due, how far and
    how long, who to ring, and what the gate expects. LOAD NUMBER leads and is
    bold because it is the broker's number, the one on the paperwork and the one
    he is asked for at the guard shack.

    Access instructions count as travel. "Dock 4 after 06:00" is not dock work,
    it is whether the trip succeeds on arrival.
    """
    ends = ends_for(record)
    card = record.get("card_data") or {}
    plan = record.get("load_plan") or []
    number = stops_for(record, stop_number)["number"]
    stop = selected_stop(record, number) if end == "delivery" else {}

    if end == "delivery":
        stop_label = f"Stop {number}"
        items = [e.get("description") or "" for e in plan
                 if isinstance(e, dict) and e.get("stop") == stop_label]
    else:
        items = [e.get("description") or "" for e in plan if isinstance(e, dict)]

    seen, unique = set(), []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)

    # Distance describes the lane, so it belongs to the far end of it. Showing
    # it against the pickup would imply Dispatch knows where the truck is now,
    # and it does not.
    miles = card.get("distance_miles") or record.get("distance_miles")
    distance = f"{miles} mi" if (end == "delivery" and miles) else ""
    drive = _drive_time(miles) if (end == "delivery" and miles) else ""

    # A selected stop overrides the lane's end: on a multi-stop run the
    # "destination" is whichever stop the driver is looking at, not the last one.
    return {
        "load_number": (record.get("numbers") or {}).get("load_label") or "—",
        "stop_label": stop.get("label", ""),
        "address": stop.get("facility") or ends[end]["place"],
        "appointment": stop.get("window") or ends[end]["window"],
        "distance": distance,
        "drive_time": drive,
        "poc": stop.get("poc") or _first(record, f"{end}_poc", f"{end}_contact", default="—"),
        "phone": stop.get("phone") or _first(record, f"{end}_phone", default="—"),
        # No shared fallback. `location_intelligence` is one load-level field,
        # and using it for both ends puts the pickup's dock note under the
        # delivery address -- which is how a driver ends up at the wrong door
        # with paperwork that says he is right.
        "instructions": stop.get("notes") or _first(record, f"{end}_notes",
                                                    f"{end}_instructions", default="—"),
        "items": unique or ["—"],
        # Who to call when something is wrong with the freight on THIS stop.
        #
        # This deliberately reverses the rule that broker identity lives in one
        # place only. That rule was written for a run with one broker and holds
        # for one -- it fails the run the operator described: one broker, two
        # stops, and the shipper holding authority on the second. Standing at a
        # dock with damaged freight, the party named here is the party he rings,
        # and the cost of it being the wrong one is not a tidier screen.
        # Distinct from access instructions, and shown apart from them. A
        # security hold or a single permitted gate is not a note about the
        # door -- it changes when the driver has to leave, and it has to be
        # read before the trip rather than at the gate.
        "special": (stop.get("special")
                    or _first(record, f"{end}_special", default="")),
        "control": lc.control_for(stop, record.get("load_control") or {}),
        "control_varies": bool(record.get("load_control_varies")),
    }


# ---------------------------------------------------------- document status --

#: The checklists, as specified by the operator on 31 August 2026.
#:
#: The Arrival Notice leads both and is already satisfied when the driver opens
#: the drawer, because Dispatch generated and sent it when he pressed ARRIVE.
#: Everything below it is something he has to come back with.
#:
#: The Load Diagram is deliberately NOT here. It is a mission-execution item he
#: works *from*, not an artifact he collects -- see `load_diagram_for`.
ARRIVAL_NOTICE = "Arrival Notice"

PICKUP_ARTIFACTS = (
    ARRIVAL_NOTICE,
    "Packing List",
    "Bill of Lading (BOL)",
    "Photos - Load Securement",
)

#: The delivery list. **Fixed, for every mission.**
#:
#: An earlier version derived it from a per-customer POD requirement so that a
#: direct-pay run would not be asked for an invoice to a broker. The operator
#: reversed that, and was right twice over.
#:
#: Right on the freight: XPO is still in the transaction chain on a Mayo C.O.D.
#: run. Mayo hands over the check, and XPO still receives the normal POD packet
#: so they can reconcile the load on their side. The invoice was never wrong.
#:
#: Right on the architecture, which matters more:
#:
#:     KISS is a survivability doctrine.
#:
#: A checklist that branches per customer is a branch to be remembered, tested,
#: debugged and explained years from now, in a one-truck business with no
#: maintenance budget. The strongest decisions in Dispatch have all removed
#: special cases rather than added them -- one Mission Record instead of record
#: types, modes as views instead of screens, C.O.D. as a field instead of a
#: process.
#:
#: The data changes. The workflow does not.
DELIVERY_ARTIFACTS = (
    ARRIVAL_NOTICE,
    "Proof Of Delivery Document",
    "Packing List (if included)",
    "Photos - Condition / Delivery",
    "Invoice To Broker",
)


#: What each notice promises will follow. Reproduced from the operator's
#: templates rather than summarised: this text goes to a broker.
ARRIVAL_NOTICE_FOLLOWS = {
    "PICKUP": ("Bill of Lading (BOL)", "Packing List",
               "Load Diagram", "Load Securement Photos"),
    "DELIVERY": ("Signed POD / Signed BOL", "Packing List (if included)",
                 "Delivery Photos", "Invoice"),
}

#: Every arrival notice is blind-copied here, so the office holds the evidence
#: whether or not the broker acknowledges it.
ARRIVAL_NOTICE_BCC = "Ops@l1truck.com"

STATUS_READY = "READY"
STATUS_COMPLETE = "COMPLETE"


def _artifact_list(mode: str) -> tuple:
    return DELIVERY_ARTIFACTS if mode == MODE_DELIVERY else PICKUP_ARTIFACTS


def _held(record: dict) -> set:
    held = record.get("artifacts_held") or []
    return {str(a).strip().lower() for a in held}


def document_checklist(record: dict, mode: str) -> list:
    """What the driver must come back with, and what Dispatch already has.

    The Arrival Notice is ticked by pressing ARRIVE rather than by collecting
    anything -- Dispatch generated it and sent it. Showing it unticked would ask
    him to go and find a document that is already in the broker's inbox.
    """
    held = _held(record)
    arrived = bool(record.get("arrived_at"))
    items = []
    for name in _artifact_list(mode):
        if name == ARRIVAL_NOTICE:
            items.append({"label": name, "done": arrived,
                          "note": "Dispatch generated and auto-sent"})
        else:
            items.append({"label": name, "done": name.lower() in held, "note": ""})

    # The one thing that differs operationally on a C.O.D. load: do not pull
    # away from the dock without the check. Not a workflow and not a branch --
    # a reminder, on the list he is already reading.
    #
    # Everything else stays identical, because the Mission Template already
    # encoded the payment arrangement when it created the record. The data
    # changes; the workflow does not.
    if mode == MODE_DELIVERY:
        cod = cod_for(record)
        if cod["is_cod"]:
            items.append({"label": cod["label"], "done": cod["collected"],
                          "note": cod["note"]})
    return items


def cod_for(record: dict) -> dict:
    """Whether the driver collects at this delivery, and what the line says.

    C.O.D. is a field on the Mission Record, not a kind of mission. A record
    carrying `payment_type: C.O.D.` produces one extra line; a record without
    it produces none. Nothing downstream behaves differently either way --
    the arrival notice, the invoice, the POD packet and the courtesy email all
    run exactly as they do for every other load, because on a C.O.D. run the
    broker is still in the transaction chain and still reconciles his side.
    """
    payment_type = str(record.get("payment_type") or "").strip()
    legacy = str(record.get("cod") or "").strip()
    is_cod = payment_type.upper().replace(".", "") == "COD" or bool(legacy)

    if not is_cod:
        return {"is_cod": False, "label": "", "note": "", "collected": False,
                "payor": "", "amount": "", "balance_due": ""}

    payor = str(record.get("payor") or "").strip() or legacy
    amount = str(record.get("amount") or "").strip()
    collected = bool(record.get("payment_collected_at"))

    label = "C.O.D. Collected"
    if payor:
        label += f" - {payor}"
    if amount:
        label += f" - {amount}"

    return {
        "is_cod": True,
        "label": label,
        "note": "Do not leave the dock without it.",
        "collected": collected,
        "payor": payor,
        "amount": amount,
        # Zero once collected. The record shows the balance; nothing else in
        # the closeout sequence reads it.
        "balance_due": ("0.00" if collected else amount),
    }


def document_status(record: dict, mode: str) -> dict:
    """READY or COMPLETE. Two states, because the question has two answers.

    Not pending, not holding, not in progress. Those are administrative words
    for an operational question: do I have what I need, and am I done?
    """
    items = document_checklist(record, mode)
    complete = bool(items) and all(i["done"] for i in items)
    phase = "DELIVERY" if mode == MODE_DELIVERY else "PICKUP"
    state = STATUS_COMPLETE if complete else STATUS_READY
    return {"phase": phase, "state": state, "complete": complete,
            "label": f"{phase} - {state}"}


# ------------------------------------------------- what completing sets off --

def transmission_status() -> str:
    """Whether Dispatch can actually send anything from this build.

    Reported rather than assumed. The connector boundary lives on `main`; this
    branch has no `dispatch.connectors` at all, so nothing here can send and
    saying otherwise on a driver's screen would be a lie he acts on.
    """
    try:
        from dispatch.connectors import registry
    except Exception:  # noqa: BLE001 - an absent connector is not an error
        return "UNCONFIGURED"
    try:
        return registry.mail_status()
    except Exception:  # noqa: BLE001
        return "UNAVAILABLE"


def completion_effect(record: dict, mode: str) -> dict:
    """What ticking the last box actually sets in motion.

    **The operator's rule, corrected 31 August 2026.** The final checklist item
    does **not** send anything. It triggers:

        Publisher packet creation -> JOE review -> Outlook draft creation

    **Human review and Outlook send remain required.** The driver completing the
    checklist prepares the packet; a person still reads it and a person still
    presses send.

    An earlier version of this said the last check "sends the final document
    packet to the broker". That overstated it in the direction that matters: it
    told the driver an outbound act had been authorised by ticking a box, when
    what he actually authorised was preparation. The distinction is the whole
    authority model -- Dispatch performs operational work, a human commits.

    Nothing here claims a send, and nothing here claims a draft exists when the
    machinery to make one is not wired.
    """
    status = document_status(record, mode)
    sendable = transmission_status()

    if mode != MODE_DELIVERY:
        return {
            "prepares_packet": False,
            "consequence": "Completing this checklist records pickup readiness.",
            "chain": "",
            "transmission": sendable,
            "note": "",
        }

    chain = "Publisher packet -> JOE review -> Outlook draft. You review and send."

    if status["complete"]:
        return {
            "prepares_packet": True,
            "consequence": ("Delivery complete. The final document packet is prepared "
                            "for review and sending."),
            "chain": chain,
            "transmission": sendable,
            # Truthful, and in his language. Nothing was prepared -- but the
            # line says what happens instead, because a driver told only that
            # something failed has been handed a problem to solve.
            "note": ("I can't put the packet together myself yet. Hold your "
                     "paperwork -- the office assembles it."
                     if not joe_voice.can_send(sendable) else
                     "Review the draft in Outlook, then send it yourself."),
        }

    return {
        "prepares_packet": False,
        "consequence": ("The last check prepares the final document packet for "
                        "review and sending."),
        "chain": chain,
        "transmission": sendable,
        "note": "Nothing is prepared until every item is checked.",
    }


# ----------------------------------------------------------------- actions --

def arrive_for(record: dict, mode: str) -> dict:
    """The mission transition event, and the one action that sends by itself.

    **Workflow 1, and it is auto-send.** Pressing ARRIVE captures date, time,
    GPS, facility, load number, description, broker, broker POC and facility
    POC; Publisher writes the Arrival Notice; COMI routes it; it **sends**,
    blind-copied to the office.

    That is deliberate and it is not the same act as the delivery packet. An
    arrival notice is *evidence that the truck was on site at a time* -- it is
    only worth anything if it leaves immediately, because its whole value is
    being contemporaneous. A packet that closes out a load is a different thing
    and a human sends that one. See `completion_effect`.
    """
    phase = "DELIVERY" if mode == MODE_DELIVERY else "PICKUP"
    if mode == MODE_IN_TRANSIT:
        return {"available": False, "phase": "CURRENT", "auto_sends": False,
                "sub": "Available at pickup or delivery",
                "bcc": "", "follows": ()}
    return {
        "available": True,
        "phase": phase,
        "auto_sends": True,
        "sub": f"Stamps time and GPS. Sends the {phase.lower()} arrival notice.",
        "bcc": ARRIVAL_NOTICE_BCC,
        "follows": ARRIVAL_NOTICE_FOLLOWS[phase],
    }


#: Placeholders that are honest on a screen and dishonest in a document. The
#: cockpit shows "—" or "Not stated" so a driver can see the field exists and is
#: unanswered. A broker reading the same words in a notice sees an answer.
_SCREEN_PLACEHOLDERS = {"—", "-", "Not stated", "Unknown", "None"}


def _blank_if_placeholder(value: str) -> str:
    return "" if str(value).strip() in _SCREEN_PLACEHOLDERS else str(value)


def _contact(record: dict, *keys) -> str:
    """A name and a number if both are known, whichever exists if only one.

    Empty when neither is recorded. A contact line reading "Unknown" on a notice
    to a broker is worse than a blank -- it looks like the field was answered.
    """
    parts = []
    for key in keys:
        value = record.get(key)
        if value not in (None, "", []) and str(value) not in parts:
            parts.append(str(value))
    return " · ".join(parts)


def arrival_notice_for(record: dict, mode: str) -> dict:
    """What the notice will say, so the driver can see it before it goes.

    Fields left empty are left empty. A notice that invents a facility name is
    worse than one that admits it does not have it -- this text reaches a broker
    under Level 1 Transport's name.
    """
    phase = "DELIVERY" if mode == MODE_DELIVERY else "PICKUP"
    ends = ends_for(record)
    end = "delivery" if mode == MODE_DELIVERY else "pickup"
    return {
        "phase": phase,
        "title": f"{phase} ARRIVAL NOTICE",
        # SAFELY, on the operator's instruction. The notice is the first thing
        # a customer sees from Level 1 Transport on this load, and a truck
        # arriving safely is the thing they actually wanted to know.
        "opening": "Truck arrived on site SAFELY.",
        # The operator's capture list, in his order. Broker and the two points of
        # contact matter to the reader: a notice that proves a truck arrived is
        # only useful to somebody who can act on it, and the facility contact is
        # who the broker rings when he wants it confirmed from the other end.
        "fields": [
            {"key": "Date", "value": record.get("arrived_date") or ""},
            {"key": "Time", "value": record.get("arrived_time") or ""},
            {"key": "GPS", "value": record.get(f"{end}_gps") or ""},
            {"key": "Facility", "value": _blank_if_placeholder(ends[end]["place"])},
            {"key": "Load Number", "value": (record.get("numbers") or {}).get("load_label") or ""},
            {"key": "Description",
             "value": _blank_if_placeholder(cargo_for(record)["description"])},
            {"key": "Broker", "value": broker_for(record)["name"]},
            {"key": "Broker POC", "value": _contact(record, "broker_poc", "broker_contact",
                                                    "broker_phone")},
            {"key": "Facility POC", "value": _contact(record, f"{end}_poc",
                                                      f"{end}_contact", f"{end}_phone")},
        ],
        "follows_intro": ("The following documents will be provided upon completion "
                          f"of {phase.lower()} activities:"),
        "follows": ARRIVAL_NOTICE_FOLLOWS[phase],
        "bcc": ARRIVAL_NOTICE_BCC,
        "sent": bool(record.get("arrived_at")),
        # What the driver reads about delivery of this notice. The precise
        # system condition stays available to engineering under `transmission`;
        # `delivery` is what reaches the glass, in his language and with what
        # happens next attached. See `portal/joe_voice.py`.
        "transmission": transmission_status(),
        # Whether it ACTUALLY went, not whether the connector could. Those are
        # different facts and only one of them is safe to put on a screen: a
        # working mail connector says nothing about whether this notice left,
        # and "sent" is a claim the driver acts on.
        "delivery": _notice_delivery(record),
    }


#: Cargo positions in the van. Six, because that is what the truck has.
LOAD_POSITIONS = 6


def load_arrangement_for(record: dict) -> dict:
    """Where the driver put the freight. Recorded, never computed.

        Grab and go, not hunt and seek.

    This is the Penske load chart, which exists for one reason: to tell the
    driver where freight physically sits so he is not opening doors and
    digging at stop four in the rain. Route order and load order are related
    and are not the same thing -- on a three-stop run the first stop loads
    last, so the route reads 1, 2, 3 while the van reads 3, 2, 1 from the
    bulkhead out.

    **The driver is the load planner. Dispatch only remembers the
    arrangement.** No optimiser, no weight balancing, no automatic placement,
    no stop-sequencing engine -- those are maintenance, and the man who loads
    the truck already knows where the freight goes. Values are free-form and
    stored exactly as typed: they mean stop numbers today and could mean COLD,
    FROZEN, DRY tomorrow without this code caring.

    Laid out the way he faces it: rear doors nearest, bulkhead deepest.
    """
    positions = []
    for number in range(1, LOAD_POSITIONS + 1):
        value = str(record.get(f"load_position_{number}") or "").strip()
        positions.append({"position": number, "value": value,
                          "empty": not value})

    occupied = [p for p in positions if p["value"]]
    return {
        "positions": positions,
        # Two across, three deep. The physical shape of the van, so a glance
        # maps to the doors rather than to a list.
        "rows": [positions[i:i + 2] for i in range(0, LOAD_POSITIONS, 2)],
        "near_label": "REAR DOORS",
        "far_label": "BULKHEAD",
        "recorded": bool(occupied),
        "occupied_count": len(occupied),
        "empty_count": LOAD_POSITIONS - len(occupied),
        "summary": (f"{len(occupied)} of {LOAD_POSITIONS} positions loaded"
                    if occupied else "Not recorded"),
    }


def _notice_delivery(record: dict) -> dict:
    """What the driver reads about this notice reaching the broker.

    Four states, and they are genuinely different:

        sent        Outlook accepted it and the record says when.
        drafted     Prepared and waiting in Drafts. During the vetting period
                    this is success, not failure -- the first four notices are
                    read before any go out on their own.
        not yet     He has not pressed ARRIVE. Nothing failed.
        could not   He pressed it and nothing was produced.

    The drafted state was missing, so a notice that had been prepared exactly
    as intended read as "I couldn't send the arrival notice myself" -- telling
    him something had gone wrong while it sat in his Drafts waiting for him.
    """
    from dispatch import arrival

    if record.get("arrival_notice_sent_at"):
        return {"sent": True, "line": "Arrival notice sent.", "instead": ""}

    if record.get("arrival_notice_drafted_at"):
        left = arrival.vetting_remaining(_all_records())
        tail = ("" if not left else
                " %d more to check before it goes on its own." % left)
        return {
            "sent": False,
            "drafted": True,
            "line": "Arrival notice is in your Drafts.",
            "instead": "Read it, then send it." + tail,
        }

    if not record.get("arrived_at"):
        return {"sent": False, "line": "Arrival notice goes out when you press ARRIVE.",
                "instead": ""}

    # Arrived, and nothing was produced. Treated as not sent, always: the
    # absence of proof is the only safe reading, because a driver who believes
    # the broker has his arrival evidence does not chase it.
    return {
        "sent": False,
        "line": "I couldn't send the arrival notice myself.",
        "instead": ("Dispatch has your arrival on record with the time. "
                    "It goes out from the office."),
    }


def _all_records():
    """Every record, for counting notices. Never fatal to a screen."""
    try:
        from portal.models import sandbox

        return sandbox.get_all()
    except Exception:  # noqa: BLE001
        return {}


def load_diagram_for(record: dict) -> dict:
    """Where the freight sits, in what order it comes off, and what is still free.

    **Ruled by the operator: the Load Diagram is not a checklist item.** It is
    something the driver works *from* while loading and unloading, not something
    he collects and hands over. On a multi-stop run it decides whether stop
    three is reachable without unloading stop four onto the dock.

    **Empty positions are shown, and they are not decoration.** An empty space is
    operational capacity -- it is the answer to "can I take another two pallets
    on the way back", which is a question asked at a truck stop with a phone in
    one hand. A diagram that draws only what is loaded answers half of it.

    Capacity is reported, never assumed. The van has not been bought, so the
    position count is frequently unknown, and an invented six would put a number
    under a decision about real freight.
    """
    plan = record.get("load_plan") or []
    total = record.get("pallet_positions")
    try:
        total = int(total) if total not in (None, "", []) else None
    except (TypeError, ValueError):
        total = None

    occupied = []
    for entry in plan:
        if not isinstance(entry, dict):
            continue
        occupied.append({
            "position": entry.get("position") or "?",
            "stop": entry.get("stop") or "",
            "description": entry.get("description") or "",
        })

    positions = []
    if total:
        taken = {str(o["position"]) for o in occupied}
        for n in range(1, total + 1):
            match = next((o for o in occupied if str(o["position"]) == str(n)), None)
            positions.append(match or {"position": n, "stop": "", "description": "",
                                       "empty": True})
        for slot in positions:
            slot.setdefault("empty", False)

    empty_count = (total - len(occupied)) if total is not None else None

    return {
        "available": bool(plan or record.get("load_position")),
        "position": record.get("load_position") or "Not recorded",
        "positions": positions,
        "occupied_count": len(occupied),
        "total": total,
        "empty_count": empty_count,
        "capacity_line": (
            f"{len(occupied)} of {total} positions occupied · {empty_count} available"
            if total is not None
            # Still refuses to invent a total -- it just says so in his words.
            # "Capacity not recorded" is a fact about the truck; the other
            # phrasing was a fact about a config file.
            else f"{len(occupied)} positions occupied · total capacity not recorded"
        ),
        "sub": ("Cargo arrangement and unload order" if plan
                else "No diagram produced yet"),
    }


def facility_map_for(record: dict, mode: str) -> dict:
    """A button that opens Google, not a map rebuilt inside Dispatch.

    No target in transit: the driver is using the truck's navigation, and a
    facility map is for the place he has not reached yet.
    """
    if mode == MODE_IN_TRANSIT:
        return {"available": False, "target": "",
                "sub": "Use truck navigation in transit"}
    ends = ends_for(record)
    end = "delivery" if mode == MODE_DELIVERY else "pickup"
    coords = record.get(f"{end}_gps") or ""
    place = ends[end]["place"]
    target = coords or place
    return {
        "available": target not in ("", "—"),
        "target": target,
        "sub": (f"Satellite · {place}" if target not in ("", "—")
                else "No address or coordinates recorded"),
    }


# ----------------------------------------------------------------- drawers --

def drawers_for(record: dict, mode: str, route_risk: str = "",
                stop_number: int | None = None) -> list:
    """One drawer per data point, opening from the side its control lives on."""
    ends = ends_for(record)
    cargo = cargo_for(record)
    broker = broker_for(record)
    status = document_status(record, mode)

    def rows(*pairs):
        return [{"key": k, "value": v} for k, v in pairs]

    return [
        # Execution information, not presentation. The load number leads and is
        # large because many facilities use it as the access code -- load
        # number, pickup number, reference number -- and it is what the gate
        # asks for before anything else.
        {"key": "pickup", "side": "left", "title": "Pickup details",
         "detail": end_detail(record, "pickup", stop_number)},

        # Follows the selected stop, and says which one so there is no doubt
        # about whose dock the driver is reading.
        {"key": "delivery", "side": "left", "title": "Delivery details",
         "detail": end_detail(record, "delivery", stop_number)},

        {"key": "route", "side": "right", "title": "Route notes & corridor risk",
         "rows": rows(("Corridor risk", route_risk or "None reported"),
                      ("Route notes", _first(record, "route_notes", default="—")))},

        # No broker here. Broker identity belongs in one place, or a driver
        # reading a cargo drawer has to work out which of two names is current.
        {"key": "cargo", "side": "left", "title": "Cargo",
         "rows": rows(("Commodity", cargo["description"]),
                      ("Detail", cargo["brackets"]),
                      ("Load position", load_diagram_for(record)["position"]))},

        # Worked from, not collected. Left side: it belongs to the freight.
        {"key": "loaddiagram", "side": "left", "title": "Load diagram",
         "diagram": load_diagram_for(record)},

        # What ARRIVE will send, visible before it is pressed.
        {"key": "arrival", "side": "right", "title": "Arrival notice",
         "notice": arrival_notice_for(record, mode)},

        {"key": "broker", "side": "left", "title": "Broker",
         "rows": rows(("Broker", broker["name"] or "—"),
                      ("Their load number", broker["reference"]),
                      ("Phone", broker["phone"] or "—"))},

        # Sticky: worked from while walking a dock with the tablet in hand, so
        # a stray touch on the scrim must not shut it mid-count.
        {"key": "documents", "side": "right", "sticky": True,
         "title": f"{status['phase']} document checklist",
         "checklist": document_checklist(record, mode),
         "status": status["state"],
         "effect": completion_effect(record, mode)},
    ]


def cockpit_context(record: dict, mode: str, route_risk: str = "",
                    stop_number: int | None = None) -> dict:
    """Everything the template needs, and nothing it has to look up itself."""
    return {
        "modes": MODES,
        "requested_view": mode,
        "mode_label": MODE_LABELS[mode],
        "emphasis": emphasis_for(mode),
        "ends": ends_for(record),
        "cargo": cargo_for(record),
        "cargo_by_stop": cargo_by_stop(record),
        "arrangement": load_arrangement_for(record),
        "pickup_detail": end_detail(record, "pickup", stop_number),
        "delivery_detail": end_detail(record, "delivery", stop_number),
        "broker": broker_for(record),
        "stops": stops_for(record, stop_number),
        "doc_status": document_status(record, mode),
        "completion": completion_effect(record, mode),
        "arrive": arrive_for(record, mode),
        "arrival_notice": arrival_notice_for(record, mode),
        "load_diagram": load_diagram_for(record),
        "facility_map": facility_map_for(record, mode),
        "drawers": drawers_for(record, mode, route_risk, stop_number),
    }
