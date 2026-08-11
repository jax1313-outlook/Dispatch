"""JSON API routes — card actions, publisher, inquiry, conflicts, library, archive, intelligence."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from portal import helpers
from portal.models import sandbox, publisher, conflict
from portal.models import library as lib_model
from portal.models import archive as arc_model
from portal.models import intelligence as intel_model

api_bp = Blueprint("api", __name__)


@api_bp.route("/action", methods=["POST"])
def card_action():
    """Update sandbox status: interested, pursue, pass, watch."""
    data = request.get_json(force=True)
    sandbox_id = data.get("sandbox_id")
    action = data.get("action", "").upper()

    if not sandbox_id:
        return jsonify({"error": "sandbox_id required"}), 400

    entry = sandbox.get(sandbox_id)
    if not entry:
        return jsonify({"error": "Sandbox entry not found"}), 404

    status_map = {
        "INTERESTED": "INTERESTED",
        "PURSUE": "PURSUE",
        "PASS": "PASS",
        "WATCH": "WATCH",
        "BOOK": "BOOKED",
    }

    new_status = status_map.get(action)
    if not new_status:
        return jsonify({"error": f"Invalid action: {action}"}), 400

    if action == "BOOK":
        if entry.get("engine_load_id"):
            return jsonify({"error": "Load already booked", "engine_load_id": entry["engine_load_id"]}), 409
        if entry.get("source_type") != "dispatch":
            return jsonify({"error": "Only dispatch entries can be booked"}), 400

        booking_conflicts = conflict.check_booking_conflicts(entry["card_data"], sandbox_id)

        from dispatch import services as dispatch_svc
        cd = entry["card_data"]
        engine_load = dispatch_svc.create_load(
            customer=cd.get("broker", cd.get("broker_shipper", entry.get("title", ""))),
            broker_shipper=cd.get("broker", ""),
            pickup_location=cd.get("origin", ""),
            delivery_location=cd.get("destination", ""),
            pickup_datetime=_extract_window_start(cd.get("pickup_window", "")),
            delivery_datetime=_extract_window_start(cd.get("delivery_window", "")),
            equipment=cd.get("equipment_required", ""),
            notes=_build_booking_notes(cd, entry),
        )
        _auto_rate_confirm(dispatch_svc, engine_load["load_id"], cd)
        sandbox.link_engine_load(sandbox_id, engine_load["load_id"])
        updated = sandbox.update_status(sandbox_id, "BOOKED",
                                        note=f"Booked as engine load {engine_load['load_id']}")
        resp = {"status": "ok", "entry": updated, "engine_load": engine_load}
        if booking_conflicts:
            resp["warnings"] = [c["explanation"] for c in booking_conflicts]
        return jsonify(resp)

    updated = sandbox.update_status(sandbox_id, new_status)

    if action == "PURSUE":
        available = lib_model.get_available_company_assets()
        missing = lib_model.get_missing_company_assets()
        publisher.create_action(
            action_type="Broker Packet Required",
            sandbox_id=sandbox_id,
            trigger_reason=f"User selected PURSUE for {entry.get('title', sandbox_id)}",
            available_data=available,
            missing_data=missing,
        )

    if action == "PASS":
        arc_model.archive_from_sandbox(entry)
        sandbox.add_note(
            entry["id"],
            f"Archived — status PASS at {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        )

    return jsonify({"status": "ok", "entry": updated})


@api_bp.route("/publisher/create", methods=["POST"])
def create_publisher_action():
    data = request.get_json(force=True)
    sandbox_id = data.get("sandbox_id")
    action_type = data.get("action_type")

    if not sandbox_id or not action_type:
        return jsonify({"error": "sandbox_id and action_type required"}), 400

    entry = sandbox.get(sandbox_id)
    if not entry:
        return jsonify({"error": "Sandbox entry not found"}), 404

    available = lib_model.get_available_company_assets()
    missing = lib_model.get_missing_company_assets()

    action = publisher.create_action(
        action_type=action_type,
        sandbox_id=sandbox_id,
        trigger_reason=f"Manual trigger for {entry.get('title', sandbox_id)}",
        available_data=available,
        missing_data=missing,
    )
    sandbox.update_status(sandbox_id, "PUBLISHER_REQUIRED")
    return jsonify({"status": "ok", "action": action})


@api_bp.route("/publisher/update", methods=["POST"])
def update_publisher_action():
    data = request.get_json(force=True)
    action_id = data.get("action_id")
    new_status = data.get("status")
    approved_by = data.get("approved_by")

    if not action_id or not new_status:
        return jsonify({"error": "action_id and status required"}), 400

    try:
        action = publisher.update_action_status(action_id, new_status, approved_by=approved_by)
        if new_status == "ARCHIVED":
            arc_model.archive_publisher_action(action)
        return jsonify({"status": "ok", "action": action})
    except (KeyError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@api_bp.route("/inquiry/create", methods=["POST"])
def create_inquiry():
    data = request.get_json(force=True)
    sandbox_id = data.get("sandbox_id")

    if not sandbox_id:
        return jsonify({"error": "sandbox_id required"}), 400

    entry = sandbox.get(sandbox_id)
    if not entry:
        return jsonify({"error": "Sandbox entry not found"}), 404

    card = entry["card_data"]
    score = entry.get("score")
    threshold = int(os.environ.get("PORTAL_INQUIRY_THRESHOLD", "90"))

    if card.get("hard_stop"):
        return jsonify({"status": "BLOCKED_HARD_STOP", "reason": "Hard stop active on this load."})

    broker_email = card.get("broker_email")
    if not broker_email:
        return jsonify({"status": "BLOCKED_MISSING_EMAIL", "reason": "No broker email available."})

    if score is not None and score < threshold:
        return jsonify({
            "status": "NOT_READY",
            "reason": f"Score {score} is below the inquiry threshold ({threshold}).",
        })

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    draft = {
        "subject": helpers.INQUIRY_TEMPLATE_SUBJECT,
        "to": broker_email,
        "body": helpers.INQUIRY_TEMPLATE_BODY,
        "status": "DRAFT_CREATED",
        "mode": "HUMAN_REVIEW",
        "created_at": now,
    }

    sandbox.set_inquiry_draft(sandbox_id, draft)
    sandbox.update_status(sandbox_id, "INQUIRY_DRAFTED")

    if entry.get("source_type") == "dispatch" and card.get("broker"):
        intel_model.create_record(
            intel_type="broker",
            subject=card["broker"],
            content=f"Inquiry drafted for load {entry.get('source_id', '')}",
            source=f"auto-contact:{sandbox_id}",
        )

    return jsonify({"status": "DRAFT_CREATED", "draft": draft})


@api_bp.route("/inquiry/mark-sent", methods=["POST"])
def mark_inquiry_sent():
    data = request.get_json(force=True)
    sandbox_id = data.get("sandbox_id")

    if not sandbox_id:
        return jsonify({"error": "sandbox_id required"}), 400

    entry = sandbox.get(sandbox_id)
    if not entry or not entry.get("inquiry_draft"):
        return jsonify({"error": "No inquiry draft found"}), 404

    entry["inquiry_draft"]["status"] = "SENT_MANUAL"
    sandbox.set_inquiry_draft(sandbox_id, entry["inquiry_draft"])
    sandbox.update_status(sandbox_id, "INQUIRY_SENT_MANUAL")

    return jsonify({"status": "ok"})


@api_bp.route("/conflict/resolve", methods=["POST"])
def resolve_conflict():
    data = request.get_json(force=True)
    notice_id = data.get("notice_id")

    if not notice_id:
        return jsonify({"error": "notice_id required"}), 400

    resolution_note = data.get("resolution_note", "")
    try:
        notice = conflict.resolve_notice(notice_id, resolution_note=resolution_note)
        return jsonify({"status": "ok", "notice": notice})
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404


# ---- Library API ----

@api_bp.route("/library/add", methods=["POST"])
def library_add():
    data = request.get_json(force=True)
    section = data.get("section")
    name = data.get("name")
    if not section or not name:
        return jsonify({"error": "section and name required"}), 400
    try:
        record = lib_model.add_record(
            section=section,
            name=name,
            content=data.get("content", ""),
            metadata=data.get("metadata"),
            submitted_by=data.get("submitted_by", "human"),
        )
        return jsonify({"status": "ok", "record": record})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@api_bp.route("/library/review", methods=["POST"])
def library_review():
    """Promote or reject a machine-submitted (pending_review) Library candidate.

    No caller in Dispatch submits a machine candidate yet (see library.py module docstring),
    so this route has no live traffic today -- it exists so review_candidate() is reachable
    once a future automated nomination path (e.g. a Publisher content worker) is wired up.
    """
    data = request.get_json(force=True)
    record_id = data.get("record_id")
    approve = data.get("approve")
    reviewed_by = data.get("reviewed_by")
    if not record_id or approve is None:
        return jsonify({"error": "record_id and approve required"}), 400
    try:
        record = lib_model.review_candidate(record_id, approve=bool(approve), reviewed_by=reviewed_by)
        return jsonify({"status": "ok", "record": record})
    except (KeyError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@api_bp.route("/library/update", methods=["POST"])
def library_update():
    data = request.get_json(force=True)
    record_id = data.get("record_id")
    if not record_id:
        return jsonify({"error": "record_id required"}), 400
    try:
        record = lib_model.update_record(
            record_id=record_id,
            name=data.get("name"),
            content=data.get("content"),
            metadata=data.get("metadata"),
        )
        return jsonify({"status": "ok", "record": record})
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404


@api_bp.route("/library/delete", methods=["POST"])
def library_delete():
    data = request.get_json(force=True)
    record_id = data.get("record_id")
    if not record_id:
        return jsonify({"error": "record_id required"}), 400
    try:
        record = lib_model.delete_record(record_id)
        return jsonify({"status": "ok", "record": record})
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404


# ---- Archive API ----

@api_bp.route("/archive/create", methods=["POST"])
def archive_create():
    data = request.get_json(force=True)
    sandbox_id = data.get("sandbox_id")
    if not sandbox_id:
        return jsonify({"error": "sandbox_id required"}), 400
    entry = sandbox.get(sandbox_id)
    if not entry:
        return jsonify({"error": "Sandbox entry not found"}), 404
    record = arc_model.archive_from_sandbox(entry)
    return jsonify({"status": "ok", "record": record})


# ---- Intelligence API ----

@api_bp.route("/intelligence/add", methods=["POST"])
def intelligence_add():
    data = request.get_json(force=True)
    intel_type = data.get("intel_type")
    subject = data.get("subject")
    if not intel_type or not subject:
        return jsonify({"error": "intel_type and subject required"}), 400
    try:
        record = intel_model.create_record(
            intel_type=intel_type,
            subject=subject,
            content=data.get("content", ""),
            source=data.get("source", ""),
            metadata=data.get("metadata"),
        )
        return jsonify({"status": "ok", "record": record})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@api_bp.route("/intelligence/update", methods=["POST"])
def intelligence_update():
    data = request.get_json(force=True)
    record_id = data.get("record_id")
    if not record_id:
        return jsonify({"error": "record_id required"}), 400
    try:
        record = intel_model.update_record(
            record_id=record_id,
            content=data.get("content"),
            metadata=data.get("metadata"),
        )
        return jsonify({"status": "ok", "record": record})
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404


# ---- Engine Sync API ----

@api_bp.route("/sync-engine", methods=["POST"])
def sync_engine_status():
    """Sync engine load statuses back to linked sandbox entries."""
    from dispatch import services as dispatch_svc

    all_entries = sandbox.get_all()
    synced = []
    for sid, entry in all_entries.items():
        engine_load_id = entry.get("engine_load_id")
        if not engine_load_id:
            continue
        load = dispatch_svc.get_load(engine_load_id)
        if not load:
            continue
        current_engine_status = entry.get("card_data", {}).get("engine_status")
        if current_engine_status != load["status"]:
            sandbox.update_engine_status(sid, load["status"])
            synced.append({"sandbox_id": sid, "engine_status": load["status"]})
    return jsonify({"status": "ok", "synced": synced, "count": len(synced)})


# ---- Helpers ----

def _extract_window_start(window: str) -> str:
    """Extract start datetime from a window like '2026-07-30 06:00 - 10:00'."""
    if not window:
        return ""
    parts = window.split(" - ")
    return parts[0].strip()


def _auto_rate_confirm(dispatch_svc, load_id: str, cd: dict) -> None:
    """Create a RateConfirmation from opportunity card data when booking a load."""
    rate = cd.get("rate")
    if not rate:
        return
    try:
        rate_amount = float(rate)
    except (TypeError, ValueError):
        return
    distance = 0.0
    if cd.get("distance_miles"):
        try:
            distance = float(cd["distance_miles"])
        except (TypeError, ValueError):
            pass
    dispatch_svc.confirm_rate(
        load_id=load_id,
        rate_amount=rate_amount,
        rate_type="flat",
        distance_miles=distance,
        confirmed_by="booking-auto",
        notes=f"Auto-confirmed from load board opportunity (RPM: ${cd.get('rpm', 'N/A')})",
    )


def _build_booking_notes(cd: dict, entry: dict) -> str:
    """Build engine load notes from card data."""
    parts = []
    source_id = entry.get("source_id", "")
    if source_id:
        parts.append(f"Booked from load board: {source_id}")
    if cd.get("rate"):
        parts.append(f"Rate: ${cd['rate']}")
    if cd.get("rpm"):
        parts.append(f"RPM: ${cd['rpm']}")
    if cd.get("distance_miles"):
        parts.append(f"Distance: {cd['distance_miles']} mi")
    if cd.get("weight_lbs"):
        parts.append(f"Weight: {cd['weight_lbs']} lbs")
    if cd.get("detention_history"):
        parts.append(f"Detention: {cd['detention_history']}")
    return " | ".join(parts)
