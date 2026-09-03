"""The Dispatch API Joe works through. Phase 1: the Dispatch Workstation.

    Dispatch is one of Joe's workstations.

Joe is a delegated operational co-driver whose intelligence is rented. Nothing
here is AI: these are the endpoints a brain calls to read a mission, report a
status, and -- after reading it back -- change one.

PLATFORM AGNOSTIC BY CONSTRUCTION
=================================

Joe is an operational **role**, not a feature of whatever brain is rented. One
stack is certified first, and this contract is written so that being first does
not make it the definition:

  - No endpoint, parameter or field names a vendor.
  - Identity arrives as a bearer token and a driver name, which any caller can
    present -- a connector today, a phone app or a different brain later.
  - The channel an instruction arrived through is *recorded data*, not a code
    path, so adding one is a new constant and not a new branch.

The OpenAPI document generated from this is an artifact of the first
certification. The contract is the thing; the connector is one adapter to it.

AUTHORITY
=========

Every call carries the driver whose authority it acts on, and every call is
logged against that name. Class 2 actions -- persistent record changes and
outbound communications -- require `confirmed: true`, which a caller may only
set after reading the change back to the driver. Class 3 is refused here and
belongs to the man, not the machine.
"""

from __future__ import annotations

import os
from functools import wraps

from flask import Blueprint, jsonify, request

from dispatch import audit, joe_authority as authority, mission as mission_svc
from portal.models import sandbox

joe_api = Blueprint("joe_api", __name__)

#: The shared secret a caller presents. Set it in the environment; when it is
#: unset the API refuses everything rather than running open, because an
#: unauthenticated write path into the Mission Record is worse than no API.
TOKEN_VAR = "DISPATCH_JOE_TOKEN"


def _configured_token() -> str:
    return str(os.environ.get(TOKEN_VAR) or "").strip()


def _presented_token() -> str:
    header = str(request.headers.get("Authorization") or "").strip()
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return str(request.headers.get("X-Dispatch-Token") or "").strip()


def _driver() -> str:
    """Whose authority this call carries.

    Required on every call. An action with nobody's name on it is an action
    nobody authorised, and the doctrine has exactly one hard wall.
    """
    body = request.get_json(silent=True) or {}
    return str(request.headers.get("X-Driver")
               or body.get("driver")
               or request.args.get("driver") or "").strip()


def _channel() -> str:
    body = request.get_json(silent=True) or {}
    return str(request.headers.get("X-Channel")
               or body.get("channel")
               or audit.CHANNEL_API).strip().upper()


def authenticated(view):
    """Refuse anything that cannot say who it is acting for."""

    @wraps(view)
    def guard(*args, **kwargs):
        token = _configured_token()
        if not token:
            return jsonify({
                "ok": False,
                "note": "This Dispatch node is not accepting Joe calls yet.",
            }), 503
        if _presented_token() != token:
            return jsonify({"ok": False, "note": "Not authorised."}), 401
        if not _driver():
            return jsonify({
                "ok": False,
                "note": "Every action carries somebody's authority. I need whose.",
            }), 400
        return view(*args, **kwargs)

    return guard


def _confirmed() -> bool:
    body = request.get_json(silent=True) or {}
    return bool(body.get("confirmed") is True)


def _mission(mission_id: str):
    """A mission by its Load Number or its record id.

    Load Number first: it is the retrieval key the whole system is built on,
    and it is what a driver says out loud.
    """
    record = sandbox.get(mission_id)
    if record:
        return record
    for candidate in sandbox.get_all().values():
        if not isinstance(candidate, dict):
            continue
        if str(candidate.get("load_number") or "").strip() == mission_id:
            return candidate
    return None


# ---------------------------------------------------------------- Class 1 ---

@joe_api.route("/api/joe/mission-status", methods=["GET"])
@authenticated
def mission_status():
    """What the truck is doing. Class 1: answered and reported."""
    from dispatch import commitment
    from portal import cockpit

    mission_id = str(request.args.get("mission") or "").strip()
    record = _mission(mission_id) if mission_id else _current_mission()

    if not record:
        audit.record(action="mission-status", driver=_driver(),
                     channel=_channel(), result=audit.RESULT_FAILURE,
                     note="no mission found")
        return jsonify({"ok": False, "note": "No mission on this node."}), 404

    merged = dict(record)
    merged["numbers"] = mission_svc.display_numbers(merged)
    stops = cockpit.stops_for(merged)

    audit.record(action="mission-status", driver=_driver(),
                 channel=_channel(), mission_id=record.get("id", ""),
                 result=audit.RESULT_SUCCESS)

    return jsonify({
        "ok": True,
        "mission": {
            "load_number": merged.get("load_number", ""),
            "mission_number": merged.get("mission_number"),
            "state": commitment.state_of(merged),
            "phase": commitment.phase_of(merged),
            "status": merged.get("status", ""),
            "customer": merged.get("broker") or merged.get("customer", ""),
            "pickup": merged.get("pickup_location", ""),
            "pickup_window": merged.get("pickup_window", ""),
            "delivery": merged.get("delivery_location", ""),
            "delivery_window": merged.get("delivery_window", ""),
            "stop": stops["label"],
            "arrived_at": merged.get("arrived_at", ""),
        },
    })


def _current_mission():
    """The committed mission the truck is on, if there is one."""
    from dispatch import commitment

    committed = [r for r in sandbox.get_all().values()
                 if isinstance(r, dict) and commitment.is_committed(r)]
    if not committed:
        return None
    return sorted(committed, key=lambda r: commitment.committed_at(r))[-1]


@joe_api.route("/api/joe/driver-status", methods=["POST"])
@authenticated
def driver_status():
    """The driver saying where he is. Class 1: recorded and reported back.

    The status vocabulary is locked: ON TIME, DELAYED, AT RISK. A word outside
    it is refused rather than stored, because a status that means whatever the
    sender felt like is not a status.
    """
    body = request.get_json(silent=True) or {}
    status = str(body.get("status") or "").strip().upper()
    mission_id = str(body.get("mission") or "").strip()
    note = str(body.get("note") or "").strip()

    if status not in authority.STATUS_VOCABULARY:
        return jsonify({
            "ok": False,
            "note": "Status is ON TIME, DELAYED or AT RISK.",
        }), 400

    record = _mission(mission_id) if mission_id else _current_mission()
    if not record:
        return jsonify({"ok": False, "note": "No mission on this node."}), 404

    data = sandbox._load()
    stored = data.get(record["id"]) or {}
    previous = stored.get("driver_status", "")
    stored["driver_status"] = status
    stored["driver_status_note"] = note
    data[record["id"]] = stored
    sandbox._save(data)

    audit.record(action="driver-status", driver=_driver(), channel=_channel(),
                 mission_id=record["id"], field="driver_status",
                 old_value=previous, new_value=status, intent=note,
                 result=audit.RESULT_SUCCESS)

    return jsonify({"ok": True, "status": status,
                    "report": authority.report(["DRIVER STATUS RECORDED: " + status])})


@joe_api.route("/api/joe/facility-intel/<path:facility_id>", methods=["GET"])
@authenticated
def facility_intel(facility_id: str):
    """What is known about getting into a facility. Class 1.

    Reports only what the record holds. Nothing about a gate is inferred: a
    guessed access instruction is how a truck ends up at the wrong door.
    """
    wanted = str(facility_id or "").strip().lower()
    found = []
    for record in sandbox.get_all().values():
        if not isinstance(record, dict):
            continue
        for end in ("pickup", "delivery"):
            place = str(record.get("%s_location" % end) or "")
            if wanted and wanted in place.lower():
                found.append({
                    "facility": place,
                    "end": end,
                    "contact": record.get("%s_contact" % end, ""),
                    "phone": record.get("%s_phone" % end, ""),
                    "access": record.get("%s_notes" % end, ""),
                    "special": record.get("%s_special" % end, ""),
                    "load_number": record.get("load_number", ""),
                })

    audit.record(action="facility-intel", driver=_driver(), channel=_channel(),
                 intent=facility_id,
                 result=audit.RESULT_SUCCESS if found else audit.RESULT_PARTIAL,
                 note="%d record(s)" % len(found))

    return jsonify({"ok": True, "facility": facility_id, "known": found,
                    "note": "" if found else "Nothing on record for that one."})


@joe_api.route("/api/joe/schedule-fit", methods=["GET"])
@authenticated
def schedule_fit():
    """Whether a day has room. Class 1: reports the board, decides nothing.

    It answers what the business model says about a day and what is already
    on it. Whether to take the load is Class 3 and belongs to the driver.
    """
    from datetime import date

    from dispatch import booking, scheduling

    try:
        calendar = scheduling.OutlookCalendarAdapter().upcoming(
            booking.HORIZON_DAYS)
    except Exception:  # noqa: BLE001 - a quiet calendar must not fail the call
        calendar = {"status": "UNAVAILABLE", "entries": []}

    book = booking.build(sandbox.get_all(), calendar)
    wanted = str(request.args.get("date") or "").strip()

    days = book["board"]
    if wanted:
        days = [d for d in days if d["iso"] == wanted]

    audit.record(action="schedule-fit", driver=_driver(), channel=_channel(),
                 intent=wanted, result=audit.RESULT_SUCCESS)

    return jsonify({
        "ok": True,
        "unsold_days": book["unsold_count"],
        "sellable_days": book["sellable_count"],
        "booked_days": book["booked_count"],
        "depth": book["depth"]["line"],
        "calendar": book["calendar_status"],
        "days": [{
            "date": d["iso"], "state": d["state"], "planned": d["planned"],
            "loads": len(d["loads"]), "candidates": len(d["candidates"]),
            "appointments": len(d["appointments"]),
        } for d in days],
    })


# ---------------------------------------------------------------- Class 2 ---

@joe_api.route("/api/joe/mission-record/<path:mission_id>", methods=["PATCH"])
@authenticated
def mission_record_update(mission_id: str):
    """Correct a field. Class 2: read back first, then change.

        Joe, update broker email to sally@xpo.com
        -> Broker email has no entry. Set to sally@xpo.com. Confirm?
        -> Confirm
        -> MISSION RECORD UPDATED.

    Without `confirmed: true` this returns the read-back and changes nothing.
    The read-back is not politeness: a phone number heard wrongly and written
    silently is a corrupted record nobody knows is corrupted.

    Publisher performs the change. Joe never writes to the Mission Record --
    see `dispatch/joe_update.py`.
    """
    from dispatch import joe_update as joe
    from portal.models import publisher

    body = request.get_json(silent=True) or {}
    record = _mission(mission_id)
    if not record:
        return jsonify({"ok": False, "note": "That mission is not on this node."}), 404

    field = str(body.get("field") or "").strip()
    value = str(body.get("value") or "").strip()

    # A spoken sentence is accepted as well as a field and a value, so the same
    # endpoint serves "broker email is sally@xpo.com" and a structured call.
    if not field and body.get("said"):
        heard = joe.understand(body["said"])
        if not heard["understood"]:
            return jsonify({"ok": False, "note": heard["note"]}), 400
        field, value = heard["field"], heard["value"]

    if not field or not value:
        return jsonify({"ok": False, "note": "I need a field and a value."}), 400

    label = joe._label_for(field)
    current = (record.get("load_control") or {}).get(field) \
        if field.startswith("control_") else record.get(field, "")

    if not _confirmed():
        audit.record(action="mission-record-update", driver=_driver(),
                     channel=_channel(), mission_id=record["id"], field=field,
                     old_value=current, new_value=value,
                     result=audit.RESULT_PARTIAL, note="read back, awaiting confirm")
        return jsonify({
            "ok": True,
            "applied": False,
            "needs_confirmation": True,
            "read_back": authority.read_back(field_label=label,
                                             current=current, proposed=value),
            "field": field, "old_value": current, "new_value": value,
        })

    outcome = publisher.apply_mission_update(
        record["id"], field, value, requested_by=_driver(),
        sandbox_module=sandbox, reason="Joe, confirmed")

    audit.record(action="mission-record-update", driver=_driver(),
                 channel=_channel(), mission_id=record["id"], field=field,
                 old_value=outcome.get("previous", current), new_value=value,
                 result=(audit.RESULT_SUCCESS if outcome.get("applied")
                         else audit.RESULT_FAILURE),
                 note=outcome.get("note", ""))

    if not outcome.get("applied"):
        return jsonify({"ok": False, "applied": False,
                        "note": outcome.get("note", "")}), 400

    return jsonify({
        "ok": True, "applied": True, "field": field,
        "old_value": outcome.get("previous", ""), "new_value": value,
        "report": authority.report(["MISSION RECORD UPDATED"]),
    })


@joe_api.route("/api/joe/send-notice", methods=["POST"])
@authenticated
def send_notice():
    """Send an operational notice. Class 2: read back, then send.

    Outbound communication under Level 1 Transport's name. Without
    `confirmed: true` it returns what would be sent and sends nothing.

    Reports part by part. A notice that reached the broker but did not reach
    the office is not a success and is not a failure -- it is exactly what
    happened, and the driver is told so.
    """
    from dispatch import arrival
    from dispatch.connectors import registry

    body = request.get_json(silent=True) or {}
    mission_id = str(body.get("mission") or "").strip()
    record = _mission(mission_id)
    if not record:
        return jsonify({"ok": False, "note": "That mission is not on this node."}), 404

    to = str(body.get("to") or "").strip()
    subject = str(body.get("subject") or "").strip()
    message = str(body.get("message") or "").strip()

    if not (to and subject and message):
        return jsonify({"ok": False,
                        "note": "I need a recipient, a subject and a message."}), 400

    if not _confirmed():
        audit.record(action="send-notice", driver=_driver(), channel=_channel(),
                     mission_id=record["id"], new_value=to,
                     result=audit.RESULT_PARTIAL, note="read back, awaiting confirm")
        return jsonify({
            "ok": True, "sent": False, "needs_confirmation": True,
            "read_back": "To %s. Subject: %s. Confirm?" % (to, subject),
            "to": to, "subject": subject, "message": message,
        })

    mail = registry.mail()
    if mail is None:
        audit.record(action="send-notice", driver=_driver(), channel=_channel(),
                     mission_id=record["id"], result=audit.RESULT_FAILURE,
                     note="no mail connector")
        return jsonify({"ok": False, "sent": False,
                        "report": authority.report(["EMAIL NOT SENT",
                                                    "NOTHING WAS CHANGED"])}), 503

    result = mail.send(to, subject, message, bcc=arrival.NOTICE_BCC)
    sent = bool(result.get("sent"))

    audit.record(action="send-notice", driver=_driver(), channel=_channel(),
                 mission_id=record["id"], new_value=to,
                 result=audit.RESULT_SUCCESS if sent else audit.RESULT_FAILURE,
                 note=result.get("blocker", ""))

    parts = ["EMAIL SENT TO %s" % to.upper()] if sent else \
        ["EMAIL NOT SENT", "NOTHING WAS CHANGED"]
    return jsonify({"ok": sent, "sent": sent,
                    "report": authority.report(parts)}), (200 if sent else 502)


# ---------------------------------------------------------------- Class 3 ---

@joe_api.route("/api/joe/commit/<path:mission_id>", methods=["POST"])
@authenticated
def commit_is_reserved(mission_id: str):
    """Committing a load is the driver's decision. Joe does the staff work.

    Present so that a caller asking for it gets a clear answer rather than a
    404 that looks like a bug. It is not missing; it is reserved.
    """
    audit.record(action="commit-load", driver=_driver(), channel=_channel(),
                 mission_id=mission_id, result=audit.RESULT_FAILURE,
                 note="Class 3 - reserved to human command")
    return jsonify(authority.held(
        "commit-load",
        "Everything necessary to execute has to exist, and whether it does is "
        "your call. The brief shows what is still open.")), 403


# ------------------------------------------------------------------ audit ---

@joe_api.route("/api/joe/audit", methods=["GET"])
@authenticated
def audit_trail():
    """What Joe has done, on whose authority. Read only."""
    mission_id = str(request.args.get("mission") or "").strip()
    return jsonify({"ok": True,
                    "entries": audit.entries(mission_id=mission_id, limit=200)})
