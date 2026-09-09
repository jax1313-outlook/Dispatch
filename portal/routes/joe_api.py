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

import hmac
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
        # Constant-time. A plain `!=` leaks length and shared prefix through
        # timing, and csrf.py two files away already compares correctly for a
        # less sensitive value. Owner Priority 3, 2026-09-07.
        if not hmac.compare_digest(_presented_token(), token):
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

@joe_api.route("/api/joe/mission-template", methods=["GET"])
@authenticated
def mission_template():
    """**The form itself.** What JOE asks, in what order, in whose words.

    Owner ruling, 2026-09-08: *"build B, publish the template from Dispatch."*
    Class 3 -- an endpoint beyond the six the governing document names -- and
    ruled rather than assumed.

    WHY IT EXISTS. JOE had its own list of eleven fields with eleven questions I
    wrote. The Mission Card has **thirty-three fields, each already carrying the
    question to ask** -- `Field.spoken`, whose own comment says *"a template read
    aloud badly is a template nobody finishes."* Two lists that must agree will
    eventually disagree, and the copy was already wrong: it had no load number,
    which the card has had all along.

    The Owner put it plainly: *"How does Joe not know the fields in this
    document?"* It does now, and it asks rather than remembering.

    **This is a read of a definition, not of operational truth.** No load, no
    driver, no record of any kind passes through here -- it is the shape of the
    form, which is the same on an empty node as on a busy one. Class 1 to serve.

    The Company Library is deliberately not the source. A printed mission brief
    is a *rendering* of the form; learning fields from it would drift the first
    time the form changed and the print did not.
    """
    from dispatch import mission_template as mt
    from dispatch import opportunity

    onto = opportunity.ONTO_MISSION_CARD
    for_card = {card_field: contract_field
                for contract_field, card_field in onto.items()}

    fields = [{
        "key": field.key,
        "label": field.label,
        "section": field.section,
        "required": bool(field.required),
        "hint": field.hint,
        # The question, in the words the form already chose. JOE says this.
        "spoken": field.spoken,
        "choices": list(field.choices or ()),
        # Which contract field this one feeds, or "" when it is for the card
        # alone. JOE needs both: it asks for everything and sends what fits.
        "opportunity_field": for_card.get(field.key, ""),
    } for field in mt.TEMPLATE]

    audit.record(action="mission-template", driver=_driver(),
                 channel=_channel(), result=audit.RESULT_SUCCESS,
                 note="published %d fields" % len(fields))

    return jsonify({
        "ok": True,
        "fields": fields,
        "sections": list(dict.fromkeys(f["section"] for f in fields)),
        "opportunity": {
            "fields": list(opportunity.FIELDS),
            "required": list(opportunity.REQUIRED),
            "dictation_order": list(opportunity.dictation_order()),
        },
    }), 200


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
#
# There is no commit endpoint, and its absence is the enforcement.
#
# An earlier version had one that returned 403 and logged the attempt. The
# argument for it was that a connector asking to commit should get a clear
# refusal rather than a 404 that looks like a bug. The argument against it won:
# Section 8 specifies six Phase 1 endpoints, a door with a lock is still a door
# where doctrine says there should be none, and a provider's convenience is not
# a reason to widen the contract.
#
# Class 3 actions -- committing or accepting a load, signing, spending beyond
# policy, reopening a locked plan, changing doctrine -- are reserved to human
# command. Joe does the staff work and presents it. The Brief shows what is
# still open and the operator presses COMMIT himself.
#
# `dispatch/joe_authority.py` still classifies them, so anything routed through
# the authority model is held rather than run. Nothing here can perform one
# because nothing here accepts one.
#
# ------------------------------------------------------------------ audit ---
#
# There is no audit-read endpoint either. Section 8 item 3 requires an
# append-only audit log, which `dispatch/audit.py` is. It does not require a
# way to read it back over the API, and Phase 1 needs none: the log is a local
# file on the node that writes it.


# --------------------------------------------------------- opportunity capture

@joe_api.route("/api/joe/opportunity", methods=["POST"])
@authenticated
def opportunity_capture():
    """Log a board listing the Owner just read. **The seventh contract.**

    OPP-CAPTURE v1.0 §2. **Class 1 — no read-back, no `confirmed` flag.** It is
    internal and reversible, touches no Mission Record and no outside party, and
    §1 is explicit that *speed is the point: capture in seconds, move to the next
    listing.* Requiring a confirmation here would be confirmation that does not
    match consequence, which is the whole of Section 3.

    **Sparse capture is valid capture.** Board, lane and rate are required and
    nothing else is — *"a capture with gaps beats a listing lost to the next
    screen."*

    **No board automation exists in this path.** The input is what the Owner
    dictated. Nothing here reads a board, and nothing here may be taught to.
    """
    from dispatch import opportunity

    payload = request.get_json(silent=True) or {}
    driver = _driver()
    channel = _channel()

    try:
        record = opportunity.capture(payload, driver=driver, channel=channel)
    except opportunity.OpportunityError as refusal:
        # Honest Reporting Rule: say what is missing, log the refusal, and do
        # not half-store a capture that was never valid.
        audit.record(action="opportunity-capture", driver=driver,
                     channel=channel, result=audit.RESULT_FAILURE,
                     note=str(refusal))
        return jsonify({"ok": False, "note": str(refusal)}), 400

    verdict = record.get("verdict", "NEW")
    audit.record(
        action="opportunity-capture", driver=driver, channel=channel,
        mission_id=record["opportunity_id"],
        intent="%s %s to %s" % (record.get("source_board", ""),
                                record.get("origin", ""),
                                record.get("destination", "")),
        new_value=str(record.get("rate") or ""),
        result=audit.RESULT_SUCCESS,
        note=("merged into existing capture; filled %s"
              % (", ".join(record.get("filled") or []) or "nothing")
              if verdict == "MERGED" else
              "flagged %s of %s" % (opportunity.FLAG_POSSIBLE_DUPLICATE,
                                    record.get("possible_duplicate_of", ""))
              if verdict == "AMBIGUOUS" else "captured")
        + (" (captured_via %r not recognised, recorded as CHAT)"
           % record["unrecognised_channel"] if record.get("unrecognised_channel") else ""))

    # The card, at capture time. Mike's ruling of 2026-09-09: it exists the
    # moment he stops speaking, not later when a screen assembles one.
    #
    # After the capture is stored and audited, never before. A card is a view of
    # a capture that already happened, and the contract's own record is the
    # thing that must survive. If making the card fails, the capture stands and
    # the failure is reported rather than swallowed -- the Honest Reporting Rule
    # is why the response carries `carded` instead of quietly implying one.
    carded = False
    card_note = ""
    try:
        from portal.models import opportunity_card

        opportunity_card.from_capture(record)
        carded = True
    except Exception as exc:  # noqa: BLE001 - a card must never lose a capture
        card_note = f"capture stored; card not created ({exc})"
        audit.record(action="opportunity-card", driver=driver, channel=channel,
                     mission_id=record["opportunity_id"],
                     result=audit.RESULT_FAILURE, note=card_note)

    return jsonify({
        "ok": True,
        "verdict": verdict,
        "opportunity_id": record["opportunity_id"],
        "carded": carded,
        "card_note": card_note,
        "echo": opportunity.echo(record),
        "flag": record.get("flag", ""),
        "possible_duplicate_of": record.get("possible_duplicate_of", ""),
        "filled": record.get("filled", []),
        "opportunity": {k: record.get(k) for k in (
            "source_board", "origin", "destination", "rate", "pieces_weight",
            "equipment", "pickup_date", "delivery_date", "contact", "notes",
            "captured_via", "captured_by", "captured_at", "state", "origins")},
    }), 201 if verdict != "MERGED" else 200
