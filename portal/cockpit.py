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
        "next_sub": (f"Advance to stop {number + 1}" if number < total
                     else "Last stop on this run"),
    }


# ---------------------------------------------------------- document status --

#: Recovered from the operator's notes. **Not yet approved as policy** -- the
#: final pickup and delivery lists are an operating-procedure decision he has
#: said he needs to think through, and inventing the rest would be exactly the
#: fabrication the doctrine forbids. What is here is what he named.
PICKUP_ARTIFACTS = (
    "Proof of Pickup (POP)",
    "Bill of Lading (BOL)",
    "Packing List",
    "Load Diagram",
    "Photos",
)

#: The delivery list has NOT been reconstructed. This is deliberately short and
#: is marked provisional on screen rather than padded out to look finished.
DELIVERY_ARTIFACTS = (
    "Proof of Delivery (POD)",
    "Signed POD",
    "Photos",
)

STATUS_READY = "READY"
STATUS_COMPLETE = "COMPLETE"


def _artifact_list(mode: str) -> tuple:
    return DELIVERY_ARTIFACTS if mode == MODE_DELIVERY else PICKUP_ARTIFACTS


def _held(record: dict) -> set:
    held = record.get("artifacts_held") or []
    return {str(a).strip().lower() for a in held}


def document_checklist(record: dict, mode: str) -> list:
    held = _held(record)
    return [{"label": name, "done": name.lower() in held}
            for name in _artifact_list(mode)]


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

    **The operator's rule:** the final green check on the delivery checklist
    activates the automatic email of the final document packet to the broker.

    That is not the system deciding to send. The driver completing a checklist
    *is* the authorising act, and it is the one place in this screen where a
    human action reaches outside the truck -- so it is stated on the drawer in
    plain words *before* the last box is ticked, not discovered afterwards.

    What this function will not do is claim a send. Transmission is not wired in
    this build. A screen that reports "sent to broker" when nothing left the
    machine is the precise failure the no-fabrication rule exists to prevent,
    and it is worse here than usual: the driver would drive away believing the
    broker had his paperwork.
    """
    status = document_status(record, mode)
    sendable = transmission_status()

    if mode != MODE_DELIVERY:
        return {
            "arms_send": False,
            "consequence": "Completing this checklist records pickup readiness.",
            "transmission": sendable,
            "note": "",
        }

    if status["complete"]:
        return {
            "arms_send": True,
            "consequence": "Delivery complete. The final document packet goes to the broker.",
            "transmission": sendable,
            "note": ("Transmission is UNCONFIGURED in this build, so the packet is "
                     "prepared and held. Nothing has been sent."
                     if sendable != "CONFIGURED" else
                     "The packet has been prepared for sending."),
        }

    return {
        "arms_send": False,
        "consequence": ("The last check sends the final document packet to the broker."),
        "transmission": sendable,
        "note": "Nothing is sent until every item is checked.",
    }


# ----------------------------------------------------------------- actions --

def arrive_for(record: dict, mode: str) -> dict:
    """The mission transition event, not a status button.

    It stamps date, time and position, and it is what starts packet creation,
    review and send. Its meaning changes with the mode; its position does not.
    """
    if mode == MODE_DELIVERY:
        return {"available": True, "phase": "DELIVERY",
                "sub": "Stamp arrival · start delivery packet"}
    if mode == MODE_PICKUP:
        return {"available": True, "phase": "PICKUP",
                "sub": "Stamp arrival · start pickup packet"}
    return {"available": False, "phase": "IN_TRANSIT",
            "sub": "Available at pickup or delivery"}


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
                      ("Load diagram", _first(record, "load_diagram", default="Not yet produced")))},

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
        "facility_map": facility_map_for(record, mode),
        "drawers": drawers_for(record, mode, route_risk),
    }
