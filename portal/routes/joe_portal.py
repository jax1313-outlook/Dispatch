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

from datetime import datetime

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


@joe_bp.route("/joe/update/<path:record_id>", methods=["POST"])
def joe_update(record_id: str):
    """Mike tells JOE. JOE tells Publisher. Publisher changes the record.

        Mike -> JOE -> Publisher -> Dispatch -> Mission Record

    JOE never writes. This route is the handover: it asks JOE what he heard,
    hands that to Publisher, and says back what happened. Giving JOE a write
    path would quietly make him the owner of mission data.
    """
    from dispatch import joe_update as joe
    from portal import brief as brief_view
    from portal.models import publisher

    spoken = str(request.form.get("said") or "").strip()
    said_by = str(request.form.get("by") or "Mike").strip()

    heard = joe.understand(spoken)
    if not heard["understood"]:
        return jsonify({"ok": False, "applied": False,
                        "note": heard["note"], "heard": spoken}), 400

    outcome = publisher.apply_mission_update(
        record_id, heard["field"], heard["value"],
        requested_by=said_by, sandbox_module=sandbox,
        reason="Told to JOE")

    if not outcome.get("ok"):
        return jsonify({"ok": False, "applied": False,
                        "note": outcome.get("note", ""),
                        "heard": spoken}), 400

    record = sandbox.get(record_id) or {}
    record["numbers"] = mission_svc.display_numbers(record)
    gaps = brief_view.card_for(record)["empty_count"]

    return jsonify({
        "ok": True,
        "applied": True,
        "field": heard["field"],
        "label": heard["label"],
        "value": heard["value"],
        "previous": outcome.get("previous", ""),
        "gaps": gaps,
        "note": joe.confirmation(heard["label"], gaps),
    })


@joe_bp.route("/intake")
def mission_intake():
    """Open a mission by hand, on the one Mission Template.

    A broker calling, a courier run phoned in, a shipper emailing direct, a
    text message, an existing customer -- all of them arrive here and all of
    them produce the same Mission Record. There is no courier form and no
    phone-load form: the source is a label on the record, never a different
    kind of mission.
    """
    from dispatch import mission_template as mt

    return render_template(
        "mission_intake.html",
        sections=[(name, mt.fields_in(name)) for name in mt.SECTIONS],
        sources=mt.MANUAL_SOURCES,
        chosen=request.args.get("source") or mt.SOURCE_PHONE,
        problems=[],
        values=mt.blank_template(),
        taken_by="",
    )


@joe_bp.route("/intake", methods=["POST"])
def mission_intake_create():
    """Create the Candidate. Same record SWEEP would have produced."""
    from dispatch import mission_template as mt

    values = {key: str(request.form.get(key) or "").strip()
              for key in mt.TEMPLATE_KEYS}
    source = str(request.form.get("source") or "").strip().upper()
    taken_by = str(request.form.get("taken_by") or "").strip()

    problems = mt.validate(values)
    if not taken_by:
        problems.append("Who took it is required")
    if source not in mt.INTAKE_SOURCES:
        problems.append("Choose how it came in")

    if problems:
        # Everything he typed comes back with it. Losing a call's worth of
        # notes to a validation message is how a screen stops being used.
        return render_template(
            "mission_intake.html",
            sections=[(name, mt.fields_in(name)) for name in mt.SECTIONS],
            sources=mt.MANUAL_SOURCES, chosen=source or mt.SOURCE_PHONE,
            problems=problems, values=values, taken_by=taken_by), 400

    record = mt.create_mission(values, source=source, taken_by=taken_by,
                               sandbox_module=sandbox, mission_module=mission_svc)
    return redirect(url_for("joe_portal.mission_brief", record_id=record["id"]))


@joe_bp.route("/candidates")
def candidate_queue():
    """The workbench: everything in Booking, waiting on a decision.

    Candidates only. A committed mission has left Booking and belongs to
    Dispatch, and a queue that keeps showing it is a queue he stops trusting
    to mean "these need me".
    """
    from dispatch import commitment

    rows = []
    for record in sandbox.get_all().values():
        if not isinstance(record, dict) or commitment.is_committed(record):
            continue
        if record.get("rejected_at"):
            continue
        merged = dict(record)
        merged["numbers"] = mission_svc.display_numbers(merged)
        card = record.get("card_data") or {}
        rows.append({
            "id": record.get("id"),
            "load_number": record.get("load_number") or card.get("load_id") or "",
            "customer": record.get("customer") or card.get("broker") or "",
            "origin": card.get("origin") or record.get("pickup_location") or "",
            "destination": card.get("destination") or record.get("delivery_location") or "",
            "when": record.get("pickup_window") or card.get("pickup_window") or "",
            "rate": record.get("rate") or card.get("rate") or "",
            "source": record.get("intake_source") or card.get("source") or "",
            "gaps": brief_gaps(merged),
        })

    rows.sort(key=lambda r: (r["when"] or "~", r["customer"]))
    return render_template("candidates.html", rows=rows)


def brief_gaps(record: dict) -> int:
    """How many fields have no entry. Counted, never scored."""
    from portal import brief as brief_view

    try:
        return brief_view.card_for(record)["empty_count"]
    except Exception:  # noqa: BLE001 - a count must never take the page down
        return 0


@joe_bp.route("/brief/mission/<path:record_id>/reject", methods=["POST"])
def mission_reject(record_id: str):
    """Leave it. Recorded rather than deleted.

    A candidate turned down is a fact worth keeping: the same broker rings back
    with the same lane, and what he offered last time is the useful thing to
    have. Nothing is removed.
    """
    from datetime import datetime, timezone

    if not sandbox.get(record_id):
        return redirect(url_for("joe_portal.candidate_queue"))

    now = datetime.now(timezone.utc).isoformat()
    data = sandbox._load()
    stored = data.get(record_id) or {}
    stored["rejected_at"] = now
    stored["rejected_reason"] = str(request.form.get("reason") or "").strip()
    stored.setdefault("events", []).append({"action": "rejected", "timestamp": now})
    data[record_id] = stored
    sandbox._save(data)
    return redirect(url_for("joe_portal.candidate_queue"))


@joe_bp.route("/booking")
def booking_board():
    """The forward view of the truck: what is booked, held and still sellable.

    Pattern plus commitments. Nothing about the week is stored -- see
    `dispatch/booking.py` for why a stored day-state would be the second
    calendar the scheduling doctrine forbids.
    """
    from dispatch import booking, scheduling

    # The real Outlook, or nothing. Deliberately not `get_adapter()`: the
    # demonstration adapter derives its entries from the mission records, and
    # on a planning board that would draw invented appointments as real
    # commitments. A board that is honestly empty is usable; one that is
    # quietly wrong is not.
    try:
        calendar = scheduling.OutlookCalendarAdapter().upcoming(
            max(booking.HORIZON_DAYS,
                7 * max(1, min(6, int(request.args.get("weeks") or 2)))))
    except Exception:  # noqa: BLE001 - a quiet calendar must not take the page down
        calendar = {"status": "UNAVAILABLE", "entries": [], "blocker": ""}

    # Two weeks is the operator's booking horizon; four is the same board with
    # the month in view. Same code, different depth -- not a second screen.
    try:
        weeks = max(1, min(6, int(request.args.get("weeks") or 2)))
    except (TypeError, ValueError):
        weeks = 2

    return render_template(
        "booking.html",
        weeks=weeks,
        book=booking.build(sandbox.get_all(), calendar, weeks=weeks),
        calendar_source=calendar.get("source", ""),
        calendar_blocker=calendar.get("blocker", ""),
    )


@joe_bp.route("/brief/mission/<path:record_id>")
def mission_brief(record_id: str):
    """The whole Mission Record on one sheet, before the call.

    Read it, fill in what the broker tells you, print it and take it with you.
    Empty fields are shown in pale red and nothing else happens -- see
    `portal/brief.py` for why that is the entire feature.
    """
    from portal import brief as brief_view

    record = sandbox.get(record_id)
    if not record:
        return redirect(url_for("joe_portal.portal_home"))

    merged = dict(record)
    merged["numbers"] = mission_svc.display_numbers(merged)
    from dispatch import commitment

    return render_template(
        "mission_brief.html",
        record=merged,
        card=brief_view.card_for(merged),
        editing=request.args.get("edit") == "1",
        gate=commitment.describe(merged),
    )


@joe_bp.route("/brief/mission/<path:record_id>/commit", methods=["POST"])
def mission_commit(record_id: str):
    """COMMIT. Booking ends here and Dispatch begins.

    Not a status change. The moment this is pressed, capacity is taken, a
    calendar entry is held, and the mission enters the driver's workflow --
    which is why the brief exists first. Everything necessary to execute is
    supposed to be on the record by now, and the operator is the one who
    decides it is.

    Nothing is created. The record SWEEP found, or that JOE took down by
    voice, is the record that runs.
    """
    from datetime import datetime, timezone

    from dispatch import commitment, scheduling

    record = sandbox.get(record_id)
    if not record:
        return redirect(url_for("joe_portal.portal_home"))

    if commitment.is_committed(record):
        return redirect(url_for("joe_portal.mission_brief", record_id=record_id))

    now = datetime.now(timezone.utc).isoformat()
    data = sandbox._load()
    stored = data.get(record_id) or {}
    stored.update(commitment.commit(stored, when=now))
    if not stored.get("mission_number"):
        stored["mission_number"] = mission_svc.next_mission_number(
            mission_svc.assigned_mission_numbers(data))
    stored.setdefault("events", []).append(
        {"action": "committed", "timestamp": now})

    # Ask the real Outlook to hold the time. Its answer is recorded as given,
    # including "I could not" -- a mission that quietly failed to reach the
    # calendar is how an appointment gets missed, and committing must not
    # depend on whether Outlook happens to be open.
    #
    # The real adapter, never get_adapter(): the demonstration adapter reports
    # ok on an appointment it did not create, which is tolerable on a display
    # and not on the act that takes capacity.
    held = scheduling.on_accept_load(
        dict(stored), scheduling.OutlookCalendarAdapter())
    stored["calendar_hold"] = {
        "held": bool(held.get("held")),
        "note": held.get("note", ""),
        "at": now,
    }

    data[record_id] = stored
    sandbox._save(data)
    return redirect(url_for("joe_portal.mission_brief", record_id=record_id))


@joe_bp.route("/brief/mission/<path:record_id>/save", methods=["POST"])
def mission_brief_save(record_id: str):
    """Write in what the broker just told you.

    Manual enrichment during a call, which is the whole reason the gaps are
    visible. Values are stored exactly as typed and nothing is validated: a
    brief that argues with what a broker just said on the phone is a brief he
    stops using.
    """
    from portal import brief as brief_view

    if not sandbox.get(record_id):
        return redirect(url_for("joe_portal.portal_home"))

    data = sandbox._load()
    stored = data.get(record_id) or {}
    control = dict(stored.get("load_control") or {})

    for key in brief_view.editable_keys(stored):
        if key not in request.form:
            continue
        value = str(request.form.get(key) or "").strip()
        if key.startswith("control_"):
            control[key] = value
        stored[key] = value

    if control:
        stored["load_control"] = control

    # Stop-level edits: a dock phone or a different party holding load control
    # on stop 2 is learned on the same call as everything else.
    stops = brief_view.apply_stop_edits(stored, request.form)
    if stops:
        from dispatch import load_control as lc

        for stop in stops:
            stop["control"] = lc.control_for(stop, control)
        stored["stops"] = stops

    data[record_id] = stored
    sandbox._save(data)

    return redirect(url_for("joe_portal.mission_brief", record_id=record_id))


@joe_bp.route("/portal/mission/<path:record_id>/arrive", methods=["POST"])
def portal_arrive(record_id: str):
    """The documented arrival event, and the notice that comes from it.

    The one outbound act that does not wait for a human -- an arrival notice is
    worth nothing if it is not contemporaneous. The first four are drafted for
    review; after that the template has been read four times and goes on its
    own. See `dispatch/arrival.py`.
    """
    from dispatch import arrival

    record = sandbox.get(record_id)
    if not record:
        return jsonify({"ok": False,
                        "note": "That mission is not on this machine."}), 404

    mode = cockpit.normalise_mode(request.form.get("view"), record)
    stamped = datetime.now()

    data = sandbox._load()
    stored = data.get(record_id) or {}
    stored["arrived_at"] = stamped.isoformat()
    stored["arrived_date"] = stamped.strftime("%Y-%m-%d")
    stored["arrived_time"] = stamped.strftime("%H:%M")
    # GPS as the truck reports it, when the browser offers it. Never invented:
    # a guessed coordinate on arrival evidence is worse than none.
    fix = str(request.form.get("gps") or "").strip()
    if fix:
        stored["%s_gps" % ("delivery" if mode == cockpit.MODE_DELIVERY
                           else "pickup")] = fix

    merged = dict(stored)
    merged["numbers"] = mission_svc.display_numbers(merged)
    notice = cockpit.arrival_notice_for(merged, mode)

    outcome = arrival.deliver(
        merged, notice, records=data, mail=_mail_connector(),
        recipient=_notice_recipient(merged))

    for key in ("arrival_notice_sent_at", "arrival_notice_drafted_at",
                "arrival_notice_error"):
        if outcome.get(key):
            stored[key] = outcome[key]
    # A later success clears an earlier failure. A record carrying both a
    # draft and a stale "nothing was sent" is a record that argues with
    # itself, and the screen believed the older half.
    if outcome.get("ok"):
        stored.pop("arrival_notice_error", None)
    data[record_id] = stored
    sandbox._save(data)

    return jsonify({"ok": bool(outcome.get("ok")),
                    "sent": bool(outcome.get("sent")),
                    "drafted": bool(outcome.get("drafted")),
                    "note": outcome.get("note", ""),
                    "arrived_at": stored["arrived_at"]})


def _mail_connector():
    try:
        from dispatch.connectors import registry

        return registry.mail()
    except Exception:  # noqa: BLE001 - an absent connector is not an error
        return None


def _notice_recipient(record: dict) -> str:
    """Who the arrival notice is addressed to.

    Load control first: on a run where authority varies by stop, the party who
    holds the freight is the party the evidence matters to. Falls back to the
    broker contact, and returns empty rather than guessing -- an arrival notice
    to the wrong company is worse than one nobody received.
    """
    control = (record.get("load_control") or {})
    for candidate in (control.get("control_email"),
                      record.get("customer_email"),
                      record.get("broker_email"),
                      (record.get("card_data") or {}).get("broker_email")):
        value = str(candidate or "").strip()
        if "@" in value:
            return value
    return ""


@joe_bp.route("/portal/mission/<path:record_id>/arrangement", methods=["POST"])
def portal_save_arrangement(record_id: str):
    """Record where the driver put the freight. Six boxes, stored as typed.

    No validation and no interpretation. The values mean stop numbers today
    and could mean COLD, FROZEN, DRY tomorrow -- the driver is the load
    planner and this only remembers what he did.
    """
    record = sandbox.get(record_id)
    if not record:
        return redirect(url_for("joe_portal.portal_home"))

    data = sandbox._load()
    stored = data.get(record_id)
    if stored is not None:
        for number in range(1, cockpit.LOAD_POSITIONS + 1):
            key = f"load_position_{number}"
            stored[key] = str(request.form.get(key) or "").strip()
        sandbox._save(data)

    # Back to the view he was on, at the stop he was looking at. Saving a load
    # chart should not move him.
    return redirect(url_for("joe_portal.portal_mission", record_id=record_id,
                            view=request.form.get("view") or "PICKUP",
                            stop=request.form.get("stop") or None))


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
