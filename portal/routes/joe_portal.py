"""JOE Presentation Layer routes.

The Driver Portal, evolved. One Mission Record, three deterministic views, a
Sweep Control area, and a JOE line along the bottom.

    Portal owns display and interaction.
    Dispatch owns workflow.
    The Mission Record owns mission data.
    JOE owns communication.

Nothing in this module decides anything. It assembles a record, filters it by
phase, and renders. Every action a driver presses POSTs to Dispatch's existing
API, which owns the workflow and the consequences.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from dispatch import mission as mission_svc
from dispatch import scheduling, sweep
from portal import cockpit
from portal.models import sandbox

joe_bp = Blueprint("joe_portal", __name__)


# What a driver can record at each end of the run. Labels are what he reads;
# milestones are what Dispatch stores.
PHASE_ACTIONS = {
    "PICKUP": [
        ("On my way", "en_route_pickup"),
        ("Arrived", "arrived_pickup"),
        ("Loaded", "loaded"),
        ("Rolling", "departed_pickup"),
    ],
    "DELIVERY": [
        ("Arrived", "arrived_delivery"),
        ("Delivered", "delivered"),
        ("POD sent", "pod_received"),
    ],
}


def _actions_for(mode: str):
    return PHASE_ACTIONS.get(str(mode).upper(), [])


def _next_action(record: dict, phase: str) -> str:
    """The one thing to do next, in words, not a status code.

    A driver asking "what now" wants a verb, not an enum.
    """
    status = str(record.get("status") or "").lower()
    if not mission_svc.is_mission(record):
        return "Decide: accept or pass"
    return {
        "created": "Start toward pickup",
        "dispatched": "Start toward pickup",
        "en_route_pickup": "Arrive and check in",
        "at_pickup": "Get loaded",
        "picked_up": "Roll to delivery",
        "in_transit": "Roll to delivery",
        "at_delivery": "Get unloaded",
        "delivered": "Send the POD",
        "completed": "Nothing — this one is closed",
    }.get(status, "Check the load")


def _route_risk(record: dict) -> str:
    """Route Risk, carried on the record since acquisition."""
    for field in ("route_risk", "hos_risk"):
        value = record.get(field)
        if value and str(value).lower() not in ("unknown", "none", ""):
            return str(value)
    return ""


def _facility_intel(record: dict, phase: str) -> str:
    """Facility intelligence for the end of the run being looked at."""
    card = record.get("card_data") or {}
    text = card.get("location_intelligence") or ""
    if not text:
        intel = record.get("intelligence") or {}
        for module in intel.values():
            if isinstance(module, dict) and module.get("summary"):
                text = module["summary"]
                break
    return str(text or "")


def _bundle_for(record_id: str) -> dict:
    """The operational facets, if this record has been accepted."""
    from dispatch import services as dispatch_svc

    try:
        return dispatch_svc.get_load_bundle(record_id) or {}
    except Exception:  # noqa: BLE001 - an unaccepted record simply has none
        return {}


@joe_bp.route("/portal")
def portal_home():
    """Straight to the mission being worked, or to the sweep if there is none."""
    records = sandbox.get_all()
    missions = [r for r in records.values() if mission_svc.is_mission(r)]
    active = [r for r in missions
              if str(r.get("status", "")).lower() not in ("completed", "archived")]
    chosen = (active or missions)
    if chosen:
        newest = sorted(chosen, key=lambda r: r.get("accepted_at", ""))[-1]
        # Carry the requested mode through the redirect. Without this a link or
        # bookmark to /portal?view=DELIVERY silently lands in CURRENT -- the
        # driver presses a saved shortcut and gets a different screen than the
        # one he saved, with nothing to tell him why.
        return redirect(url_for("joe_portal.portal_mission",
                                record_id=newest["id"],
                                view=cockpit.normalise_mode(request.args.get("view"), newest),
                                stop=request.args.get("stop")))
    return render_template(
        "joe_portal.html",
        record={"id": "", "title": "No mission accepted",
                "numbers": mission_svc.display_numbers({}),
                "purpose": mission_svc.PURPOSE_OPPORTUNITY,
                "card_data": {}},
        view={"phase": "PICKUP", "milestones": [], "evidence": [],
              "exceptions": [], "detentions": [], "pods": []},
        views={"PICKUP": {"milestones": [], "evidence": []},
               "DELIVERY": {"milestones": [], "evidence": []}},
        sweep=sweep.status(),
        joe={"status": "Ask JOE anything. It answers; it does not decide."},
        next_action="Run a sweep, then accept a load",
        route_risk="", facility_intel="",
        actions_for=_actions_for,
        # The empty state honours the requested mode too. Hard-coding it here
        # meant a link to ?view=DELIVERY landed in CURRENT whenever no mission
        # was accepted -- the screen quietly disagreeing with the URL that
        # opened it, which is the same defect as the dropped redirect above.
        **cockpit.cockpit_context(
            {"id": "", "title": "No mission accepted",
             "numbers": mission_svc.display_numbers({}), "card_data": {}},
            cockpit.normalise_mode(request.args.get("view"))),
    )


@joe_bp.route("/portal/mission/<path:record_id>")
def portal_mission(record_id: str):
    """One Mission Record, one of three views over it."""
    record = sandbox.get(record_id)
    if not record:
        return redirect(url_for("joe_portal.portal_home"))

    mode = cockpit.normalise_mode(request.args.get("view"), record)
    requested = cockpit.backend_view(mode)
    try:
        stop_number = int(request.args.get("stop") or 0) or None
    except (TypeError, ValueError):
        stop_number = None

    # ONE read. The filter works over what is already assembled - that is the
    # property that keeps three views from becoming three records.
    merged = mission_svc.merge_record(record, _bundle_for(record_id))
    phase = mission_svc.resolve_view(merged, requested)
    view = mission_svc.filter_bundle(merged, phase)
    # Each phase panel shows ITS OWN facets, not only the resolved one.
    # Without this the DELIVERY timeline stayed empty until the record's
    # status had already moved to the delivery side - which is exactly when a
    # driver stops needing to look at it.
    #
    # Still one store read. filter_bundle() is pure over the bundle already in
    # hand, so two phases cost no second query and create no second record.
    views = {
        "PICKUP": mission_svc.filter_bundle(merged, "PICKUP"),
        "DELIVERY": mission_svc.filter_bundle(merged, "DELIVERY"),
    }

    risk = _route_risk(record)
    return render_template(
        "joe_portal.html",
        record=merged,
        view=view,
        views=views,
        sweep=sweep.status(),
        joe={"status": "Ask JOE anything. It answers; it does not decide."},
        next_action=_next_action(merged, phase),
        route_risk=risk,
        facility_intel=_facility_intel(record, phase),
        actions_for=_actions_for,
        **cockpit.cockpit_context(merged, mode, risk, stop_number),
    )


@joe_bp.route("/portal/prototype")
def portal_prototype():
    """Mike's original Planning Mode dashboard, served as it arrived.

    Kept reachable so the two can be compared at a URL rather than by
    hunting through Edge's temp folder - which is where it was found, and
    which Windows clears without asking.

    Served exactly as supplied, including its three CDN references. It will
    look wrong with no signal, and that is the point: it is the evidence for
    why the portal vendors them.
    """
    from flask import send_from_directory
    from pathlib import Path

    folder = Path(__file__).resolve().parent.parent / "prototype"
    return send_from_directory(
        folder, "L1_Transport_Planning_Intelligence_Dashboard.html")


# ---- Sweep Control -----------------------------------------------------

@joe_bp.route("/api/sweep/start", methods=["POST"])
def sweep_start():
    return jsonify(sweep.start())


@joe_bp.route("/api/sweep/schedule", methods=["POST"])
def sweep_schedule():
    body = request.get_json(silent=True) or {}
    return jsonify(sweep.set_schedule(
        timer_enabled=bool(body.get("timer_enabled")),
        daily_at=str(body.get("daily_at") or ""),
    ))


@joe_bp.route("/api/sweep/status", methods=["GET"])
def sweep_status():
    return jsonify(sweep.status())


# ---- Calendar boundary -------------------------------------------------

@joe_bp.route("/api/calendar/probe", methods=["GET"])
def calendar_probe():
    """What the calendar connection actually is, said plainly."""
    return jsonify(scheduling.get_adapter().probe())


@joe_bp.route("/api/calendar/upcoming", methods=["GET"])
def calendar_upcoming():
    return jsonify(scheduling.get_adapter().upcoming())
