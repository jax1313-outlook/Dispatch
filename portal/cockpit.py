"""Driver Cockpit presentation logic.

Pure functions over a Mission Record. No Flask, no store, no I/O -- the screen
is a view of the record, and a view that reaches for data of its own is a second
record wearing a template.

The design this serves is recorded in `Driver_Cockpit_Design_Notes_2026-08-31`:
one screen, three modes, the layout static and only the contents, the emphasis,
the checklist and the live actions changing with the mode.
"""

from __future__ import annotations

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
MODES = (
    {"key": MODE_PICKUP, "label": "PICKUP"},
    {"key": MODE_IN_TRANSIT, "label": "CURRENT"},
    {"key": MODE_DELIVERY, "label": "DELIVERY"},
)

MODE_LABELS = {m["key"]: m["label"] for m in MODES}

#: `dispatch.mission` speaks the same three words, so the mapping is direct.
_BACKEND_VIEW = {
    MODE_PICKUP: "PICKUP",
    MODE_IN_TRANSIT: "CURRENT",
    MODE_DELIVERY: "DELIVERY",
}


def normalise_mode(requested: str | None) -> str:
    """Accept a mode, or fall back to IN TRANSIT.

    Also accepts `IN_TRANSIT`, so a link written while that label was in use
    still opens rather than silently landing somewhere else.
    """
    key = str(requested or "").upper().replace(" ", "_").replace("-", "_")
    if key == "IN_TRANSIT":
        return MODE_IN_TRANSIT  # a link written while the label was IN TRANSIT
    return key if key in MODE_LABELS else MODE_IN_TRANSIT


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


def stops_for(record: dict) -> dict:
    """Where the driver is in the sequence, when there is a sequence."""
    try:
        total = int(record.get("stop_total") or 1)
    except (TypeError, ValueError):
        total = 1
    try:
        number = int(record.get("stop_number") or 1)
    except (TypeError, ValueError):
        number = 1
    number = max(1, min(number, total))
    return {
        "number": number,
        "total": total,
        "label": f"STOP {number} OF {total}",
        "has_next": number < total,
        "has_previous": number > 1,
        "next_sub": (f"Advance to stop {number + 1}" if number < total
                     else "Last stop on this run"),
        "previous_sub": (f"Back to stop {number - 1}" if number > 1
                         else "First stop on this run"),
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
    return items


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
        from dispatch.connectors import registry  # noqa: F401
    except Exception:
        return "UNCONFIGURED"
    return "UNCONFIGURED"


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
            "note": ("Packet preparation is UNCONFIGURED in this build. Nothing has "
                     "been prepared, drafted or sent."
                     if sendable != "CONFIGURED" else
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
        "opening": "Truck arrived on site.",
        "fields": [
            {"key": "Date", "value": record.get("arrived_date") or ""},
            {"key": "Time", "value": record.get("arrived_time") or ""},
            {"key": "GPS", "value": record.get(f"{end}_gps") or ""},
            {"key": "Facility", "value": ends[end]["place"]},
            {"key": "Load Number", "value": (record.get("numbers") or {}).get("load_label") or ""},
            {"key": "Description", "value": cargo_for(record)["description"]},
        ],
        "follows_intro": ("The following documents will be provided upon completion "
                          f"of {phase.lower()} activities:"),
        "follows": ARRIVAL_NOTICE_FOLLOWS[phase],
        "bcc": ARRIVAL_NOTICE_BCC,
        "sent": bool(record.get("arrived_at")),
        "transmission": transmission_status(),
    }


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
            else f"{len(occupied)} positions occupied · capacity UNCONFIGURED"
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

def drawers_for(record: dict, mode: str, route_risk: str = "") -> list:
    """One drawer per data point, opening from the side its control lives on."""
    ends = ends_for(record)
    cargo = cargo_for(record)
    broker = broker_for(record)
    status = document_status(record, mode)

    def rows(*pairs):
        return [{"key": k, "value": v} for k, v in pairs]

    return [
        {"key": "pickup", "side": "left", "title": "Pickup details",
         "rows": rows(("Facility", ends["pickup"]["place"]),
                      ("Appointment", ends["pickup"]["window"]),
                      ("Contact", _first(record, "pickup_contact", default="—")),
                      ("Phone", _first(record, "pickup_phone", default="—")),
                      ("Instructions", _first(record, "pickup_notes", default="—")))},

        {"key": "delivery", "side": "left", "title": "Delivery details",
         "rows": rows(("Facility", ends["delivery"]["place"]),
                      ("Appointment", ends["delivery"]["window"]),
                      ("Contact", _first(record, "delivery_contact", default="—")),
                      ("Phone", _first(record, "delivery_phone", default="—")),
                      ("Instructions", _first(record, "delivery_notes", default="—")))},

        {"key": "route", "side": "right", "title": "Route notes & corridor risk",
         "rows": rows(("Corridor risk", route_risk or "None reported"),
                      ("Route notes", _first(record, "route_notes", default="—")))},

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


def cockpit_context(record: dict, mode: str, route_risk: str = "") -> dict:
    """Everything the template needs, and nothing it has to look up itself."""
    return {
        "modes": MODES,
        "requested_view": mode,
        "mode_label": MODE_LABELS[mode],
        "emphasis": emphasis_for(mode),
        "ends": ends_for(record),
        "cargo": cargo_for(record),
        "broker": broker_for(record),
        "stops": stops_for(record),
        "doc_status": document_status(record, mode),
        "completion": completion_effect(record, mode),
        "arrive": arrive_for(record, mode),
        "arrival_notice": arrival_notice_for(record, mode),
        "load_diagram": load_diagram_for(record),
        "facility_map": facility_map_for(record, mode),
        "drawers": drawers_for(record, mode, route_risk),
    }
