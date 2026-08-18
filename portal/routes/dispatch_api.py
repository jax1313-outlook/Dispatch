"""Dispatch Data Engine API routes.

REST endpoints for loads, milestones, evidence, exceptions,
POD packages, and retention archive.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from flask import Blueprint, Response, jsonify, render_template, request, send_file

from dispatch import notifications, services
from dispatch.models import (
    ALLOWED_EXTENSIONS,
    BROKER_STATUSES,
    DETENTION_LOCATIONS,
    DETENTION_STATUSES,
    DRIVER_STATUSES,
    EQUIPMENT_STATUSES,
    EQUIPMENT_TYPES,
    EVIDENCE_TYPES,
    EXCEPTION_STATUSES,
    EXCEPTION_TYPES,
    IFTA_JURISDICTIONS,
    LOAD_SOURCES,
    MAX_FILE_SIZE,
    SEVERITY_LEVELS,
    ACTIVITY_TYPES,
    EXPENSE_CATEGORIES,
    LICENSE_CLASSES,
    LOAD_STATUSES,
    MILESTONE_SOURCES,
    MILESTONE_TYPES,
    PAYMENT_METHODS,
    RATE_TYPES,
    SETTLEMENT_STATUSES,
)

dispatch_bp = Blueprint("dispatch_api", __name__)


def _json_body(force: bool = False) -> dict:
    """Safely read a JSON request body as a dict.

    ``request.get_json(silent=True) or {}`` (and the ``force=True`` variant
    used elsewhere in this file) only substitutes {} when parsing *fails* --
    a syntactically valid but non-object body (a list, string, or number) is
    truthy/non-None and passes through unchanged, and the first
    ``data.get(...)`` call on it raises an unhandled AttributeError -> 500.
    This normalizes any non-dict result (including None) to {} the same way
    a missing/invalid body already is. ``force=True`` preserves the original
    call sites' behavior of parsing the body as JSON regardless of the
    request's Content-Type header.
    """
    data = request.get_json(force=force, silent=True)
    return data if isinstance(data, dict) else {}


def _get_page_params():
    raw_page = request.args.get("page")
    if raw_page is None:
        return None, None
    try:
        page = int(raw_page)
    except (ValueError, TypeError):
        return None, None
    raw_pp = request.args.get("per_page")
    per_page = int(raw_pp) if raw_pp else None
    return page, per_page


def _paginated_response(result, collection_key):
    if isinstance(result, dict) and "items" in result:
        return jsonify({
            "status": "ok",
            collection_key: result["items"],
            "count": len(result["items"]),
            "total": result["total"],
            "page": result["page"],
            "per_page": result["per_page"],
            "pages": result["pages"],
        })
    return jsonify({
        "status": "ok",
        collection_key: result,
        "count": len(result),
    })


# ── Loads ─────────────────────────────────────────────────────────────

@dispatch_bp.route("/loads", methods=["GET"])
def list_loads():
    status = request.args.get("status")
    if status and status not in LOAD_STATUSES:
        return jsonify({"error": f"Invalid status: {status}"}), 400
    customer = request.args.get("customer")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    page, per_page = _get_page_params()
    loads = services.list_loads(
        status=status, customer=customer,
        date_from=date_from, date_to=date_to,
        page=page, per_page=per_page,
    )
    return _paginated_response(loads, "loads")


@dispatch_bp.route("/loads", methods=["POST"])
def create_load():
    data = _json_body()
    customer = data.get("customer", "")
    if not customer:
        return jsonify({"error": "customer is required"}), 400
    try:
        load = services.create_load(
            customer=customer,
            broker_shipper=data.get("broker_shipper", ""),
            pickup_location=data.get("pickup_location", ""),
            delivery_location=data.get("delivery_location", ""),
            pickup_datetime=data.get("pickup_datetime", ""),
            delivery_datetime=data.get("delivery_datetime", ""),
            equipment=data.get("equipment", ""),
            driver=data.get("driver", ""),
            driver_id=data.get("driver_id", ""),
            equipment_id=data.get("equipment_id", ""),
            source=data.get("source", ""),
            notes=data.get("notes", ""),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"status": "ok", "load": load}), 201


@dispatch_bp.route("/loads/<load_id>", methods=["GET"])
def get_load(load_id):
    load = services.get_load(load_id)
    if not load:
        return jsonify({"error": f"Load {load_id} not found"}), 404
    return jsonify({"status": "ok", "load": load})


@dispatch_bp.route("/loads/<load_id>", methods=["PATCH"])
def update_load(load_id):
    data = _json_body()
    data.pop("load_id", None)
    if "status" in data and data["status"] not in LOAD_STATUSES:
        return jsonify({"error": f"Invalid status: {data['status']}"}), 400
    try:
        result = services.update_load(load_id, **data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not result:
        return jsonify({"error": f"Load {load_id} not found"}), 404
    return jsonify({"status": "ok", "load": result})


@dispatch_bp.route("/loads/<load_id>", methods=["DELETE"])
def delete_load(load_id):
    try:
        deleted = services.delete_load(load_id)
    except ValueError as e:
        msg = str(e)
        status = 404 if "not found" in msg.lower() else 400
        return jsonify({"error": msg}), status
    if not deleted:
        return jsonify({"error": f"Load {load_id} not found"}), 404
    return jsonify({"status": "ok", "deleted": True})


@dispatch_bp.route("/loads/<load_id>/duplicate", methods=["POST"])
def duplicate_load(load_id):
    try:
        load = services.duplicate_load(load_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"status": "ok", "load": load}), 201


@dispatch_bp.route("/loads/<load_id>/bundle", methods=["GET"])
def load_bundle(load_id):
    bundle = services.get_load_bundle(load_id)
    if not bundle:
        return jsonify({"error": f"Load {load_id} not found"}), 404
    return jsonify({"status": "ok", **bundle})


# ── Load Source Stats ────────────────────────────────────────────────

@dispatch_bp.route("/loads/source-stats", methods=["GET"])
def load_source_stats():
    return jsonify(services.get_load_source_stats())


# ── Stalled Loads ─────────────────────────────────────────────────────

@dispatch_bp.route("/charts", methods=["GET"])
def chart_data():
    data = services.get_chart_data()
    return jsonify(data)


@dispatch_bp.route("/loads/stalled", methods=["GET"])
def stalled_loads():
    stalled = services.check_stalled_loads()
    return jsonify({"status": "ok", "loads": stalled, "count": len(stalled)})


@dispatch_bp.route("/loads/stalled/notify", methods=["POST"])
def notify_stalled():
    notified = services.notify_stalled_loads()
    return jsonify({
        "status": "ok", "notified": len(notified),
        "loads": [{"load_id": l["load_id"], "customer": l.get("customer", ""),
                    "hours_in_status": l.get("hours_in_status", 0)}
                   for l in notified],
    })


# ── Visibility ────────────────────────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/visibility", methods=["GET"])
def get_visibility(load_id):
    vis = services.get_visibility(load_id)
    if not vis:
        return jsonify({"error": f"No visibility record for {load_id}"}), 404
    return jsonify({"status": "ok", "visibility": vis})


@dispatch_bp.route("/loads/<load_id>/visibility", methods=["PATCH"])
def update_visibility(load_id):
    data = _json_body()
    customer_note = data.get("customer_note")
    internal_note = data.get("internal_note")
    try:
        vis = services.update_visibility_notes(
            load_id,
            customer_note=customer_note,
            internal_note=internal_note,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    if not vis:
        return jsonify({"error": f"No visibility record for {load_id}"}), 404
    return jsonify({"status": "ok", "visibility": vis})


# ── Milestones ────────────────────────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/milestones", methods=["GET"])
def list_milestones(load_id):
    milestones = services.get_timeline(load_id)
    return jsonify({
        "status": "ok", "load_id": load_id,
        "milestones": milestones, "count": len(milestones),
    })


@dispatch_bp.route("/loads/<load_id>/milestones", methods=["POST"])
def add_milestone(load_id):
    data = _json_body()
    event_type = data.get("event_type", "")
    if not event_type:
        return jsonify({"error": "event_type is required"}), 400
    if event_type not in MILESTONE_TYPES:
        return jsonify({"error": f"Invalid event_type: {event_type}"}), 400
    source = data.get("source", "dispatcher")
    if source not in MILESTONE_SOURCES:
        return jsonify({"error": f"Invalid source: {source}"}), 400
    try:
        ms = services.add_milestone(
            load_id=load_id,
            event_type=event_type,
            location=data.get("location", ""),
            source=source,
            note=data.get("note", ""),
            entered_by=data.get("entered_by", ""),
            event_time=data.get("event_time", ""),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"status": "ok", "milestone": ms}), 201


@dispatch_bp.route("/milestones/<milestone_id>", methods=["PATCH"])
def update_milestone(milestone_id):
    from dispatch.models import VALIDATION_STATUSES
    data = _json_body()
    validation_status = data.get("validation_status")
    if validation_status and validation_status not in VALIDATION_STATUSES:
        return jsonify({
            "error": f"Invalid validation_status: {validation_status}",
        }), 400
    try:
        ms = services.validate_milestone(milestone_id, validation_status) if validation_status else None
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not ms:
        return jsonify({"error": f"Milestone not found: {milestone_id}"}), 404
    return jsonify({"status": "ok", "milestone": ms})


# ── Evidence ──────────────────────────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/evidence", methods=["GET"])
def list_evidence(load_id):
    items = services.list_evidence(load_id)
    return jsonify({
        "status": "ok", "load_id": load_id,
        "evidence": items, "count": len(items),
    })


@dispatch_bp.route("/loads/<load_id>/evidence", methods=["POST"])
def attach_evidence(load_id):
    uploaded_file = request.files.get("file")
    if uploaded_file and uploaded_file.filename:
        ev_type = request.form.get("evidence_type", "document")
        if ev_type not in EVIDENCE_TYPES:
            return jsonify({"error": f"Invalid evidence_type: {ev_type}"}), 400
        filename = uploaded_file.filename
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({"error": f"File type not allowed: .{ext}"}), 400
        file_data = uploaded_file.read()
        if len(file_data) > MAX_FILE_SIZE:
            return jsonify({"error": f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit"}), 400
        try:
            ev = services.attach_evidence(
                load_id=load_id,
                evidence_type=ev_type,
                description=request.form.get("description", ""),
                related_milestone_id=request.form.get("related_milestone_id") or None,
                uploaded_by=request.form.get("uploaded_by", ""),
                file_data=file_data,
                original_filename=filename,
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        return jsonify({"status": "ok", "evidence": ev}), 201

    data = _json_body()
    ev_type = data.get("evidence_type", "document")
    if ev_type not in EVIDENCE_TYPES:
        return jsonify({"error": f"Invalid evidence_type: {ev_type}"}), 400
    try:
        ev = services.attach_evidence(
            load_id=load_id,
            evidence_type=ev_type,
            description=data.get("description", ""),
            file_path=data.get("file_path"),
            related_milestone_id=data.get("related_milestone_id"),
            uploaded_by=data.get("uploaded_by", ""),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"status": "ok", "evidence": ev}), 201


@dispatch_bp.route("/evidence/<evidence_id>/download", methods=["GET"])
def download_evidence(evidence_id):
    result = services.get_evidence_file(evidence_id)
    if not result:
        return jsonify({"error": "File not found"}), 404
    file_path, download_name = result
    return send_file(file_path, download_name=download_name, as_attachment=True)


@dispatch_bp.route("/evidence/<evidence_id>", methods=["PATCH"])
def update_evidence(evidence_id):
    data = _json_body()
    data.pop("evidence_id", None)
    if "evidence_type" in data and data["evidence_type"] not in EVIDENCE_TYPES:
        return jsonify({"error": f"Invalid evidence_type: {data['evidence_type']}"}), 400
    result = services.update_evidence(evidence_id, **data)
    if not result:
        return jsonify({"error": f"Evidence {evidence_id} not found"}), 404
    return jsonify({"status": "ok", "evidence": result})


@dispatch_bp.route("/evidence/<evidence_id>", methods=["DELETE"])
def delete_evidence(evidence_id):
    if not services.delete_evidence(evidence_id):
        return jsonify({"error": f"Evidence {evidence_id} not found"}), 404
    return jsonify({"status": "ok"})


# ── Exceptions ────────────────────────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/exceptions", methods=["GET"])
def list_exceptions(load_id):
    status = request.args.get("status")
    if status and status not in EXCEPTION_STATUSES:
        return jsonify({"error": f"Invalid status: {status}"}), 400
    items = services.list_exceptions(load_id=load_id, status=status)
    return jsonify({
        "status": "ok", "load_id": load_id,
        "exceptions": items, "count": len(items),
    })


@dispatch_bp.route("/loads/<load_id>/exceptions", methods=["POST"])
def open_exception(load_id):
    data = _json_body()
    exc_type = data.get("exception_type", "other")
    if exc_type not in EXCEPTION_TYPES:
        return jsonify({"error": f"Invalid exception_type: {exc_type}"}), 400
    severity = data.get("severity", "medium")
    if severity not in SEVERITY_LEVELS:
        return jsonify({"error": f"Invalid severity: {severity}"}), 400
    try:
        exc = services.open_exception(
            load_id=load_id,
            exception_type=exc_type,
            severity=severity,
            description=data.get("description", ""),
            related_milestone_id=data.get("related_milestone_id"),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"status": "ok", "exception": exc}), 201


@dispatch_bp.route("/exceptions/<exception_id>/resolve", methods=["POST"])
def resolve_exception(exception_id):
    data = _json_body()
    result = services.resolve_exception(
        exception_id=exception_id,
        resolution_note=data.get("resolution_note", ""),
    )
    if not result:
        return jsonify({"error": f"Exception {exception_id} not found"}), 404
    return jsonify({"status": "ok", "exception": result})


@dispatch_bp.route("/exceptions/<exception_id>", methods=["PATCH"])
def update_exception(exception_id):
    data = _json_body()
    data.pop("exception_id", None)
    if "exception_type" in data and data["exception_type"] not in EXCEPTION_TYPES:
        return jsonify({"error": f"Invalid exception_type: {data['exception_type']}"}), 400
    if "severity" in data and data["severity"] not in SEVERITY_LEVELS:
        return jsonify({"error": f"Invalid severity: {data['severity']}"}), 400
    result = services.update_exception(exception_id, **data)
    if not result:
        return jsonify({"error": f"Exception {exception_id} not found"}), 404
    return jsonify({"status": "ok", "exception": result})


# ── Global Exceptions ────────────────────────────────────────────

@dispatch_bp.route("/exceptions", methods=["GET"])
def list_all_exceptions():
    status = request.args.get("status")
    if status and status not in EXCEPTION_STATUSES:
        return jsonify({"error": f"Invalid status: {status}"}), 400
    severity = request.args.get("severity")
    if severity and severity not in SEVERITY_LEVELS:
        return jsonify({"error": f"Invalid severity: {severity}"}), 400
    exc_type = request.args.get("exception_type")
    if exc_type and exc_type not in EXCEPTION_TYPES:
        return jsonify({"error": f"Invalid exception_type: {exc_type}"}), 400
    page, per_page = _get_page_params()
    items = services.list_exceptions(status=status, page=page, per_page=per_page)
    if isinstance(items, dict) and "items" in items:
        if severity:
            items["items"] = [e for e in items["items"] if e.get("severity") == severity]
        if exc_type:
            items["items"] = [e for e in items["items"] if e.get("exception_type") == exc_type]
        items["count"] = len(items["items"])
    else:
        if severity:
            items = [e for e in items if e.get("severity") == severity]
        if exc_type:
            items = [e for e in items if e.get("exception_type") == exc_type]
    return _paginated_response(items, "exceptions")


# ── POD Packages ──────────────────────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/pod", methods=["GET"])
def list_pods(load_id):
    pods = services.list_pods(load_id)
    return jsonify({
        "status": "ok", "load_id": load_id,
        "pods": pods, "count": len(pods),
    })


@dispatch_bp.route("/loads/<load_id>/pod", methods=["POST"])
def generate_pod(load_id):
    data = _json_body()
    try:
        pod = services.generate_pod(
            load_id=load_id,
            recipient=data.get("recipient", ""),
            notes=data.get("notes", ""),
            evidence_ids=data.get("evidence_ids"),
        )
    except ValueError as e:
        msg = str(e)
        status = 404 if "not found" in msg.lower() else 409
        return jsonify({"error": msg}), status
    return jsonify({"status": "ok", "pod": pod}), 201


# ── Retention Archive ─────────────────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/archive", methods=["POST"])
def archive_load(load_id):
    try:
        ret = services.archive_load(load_id)
    except ValueError as e:
        status = 404 if "not found" in str(e).lower() else 409
        return jsonify({"error": str(e)}), status

    # D10: "Archive Takes Custody" -- if this load has a Completion Packet with an Email
    # Cluster already stored on it (see submit_email_package below), record that this
    # (existing, human-triggered) archive action took custody of it. Does not change
    # when/whether archiving happens -- purely a cross-reference on the packet.
    from portal.models import completion_packet
    packet = completion_packet.get_packet(load_id)
    if packet and packet.get("status") == "CLUSTERED":
        completion_packet.mark_archived(load_id, ret["archive_id"])

    return jsonify({"status": "ok", "retention": ret}), 201


@dispatch_bp.route("/retention", methods=["GET"])
def list_retentions():
    items = services.list_retentions()
    return jsonify({"status": "ok", "archives": items, "count": len(items)})


# ── Completion Packet / End Load ───────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/completion-packet", methods=["GET"])
def get_completion_packet(load_id):
    from portal.models import completion_packet
    packet = completion_packet.get_packet(load_id)
    if not packet:
        return jsonify({"error": "No completion packet for this load"}), 404
    return jsonify({"status": "ok", "packet": packet})


@dispatch_bp.route("/loads/<load_id>/end-load", methods=["POST"])
def end_load(load_id):
    """Deterministic End Load trigger: assemble the closeout packet from existing load
    artifacts and route it to Publisher as a PENDING action awaiting human review. Never
    sends anything -- Publisher's existing DRAFT/READY/APPROVED gate is the human review step.
    """
    from portal.models import completion_packet, publisher

    existing = completion_packet.get_packet(load_id)
    if existing:
        return jsonify({"status": "ok", "packet": existing, "already_ended": True})

    try:
        packet_data = services.build_completion_packet(load_id)
    except ValueError as e:
        status = 404 if "not found" in str(e).lower() else 409
        return jsonify({"error": str(e)}), status

    packet = completion_packet.create_packet(
        load_id=load_id,
        closeout_data=packet_data,
        available=packet_data["available"],
        missing=packet_data["missing"],
    )
    action = publisher.create_action(
        action_type="Completion Packet Ready",
        sandbox_id=f"LOAD-{load_id}",
        trigger_reason=f"End Load triggered for {load_id}",
        available_data=packet_data["available"],
        missing_data=packet_data["missing"],
    )
    packet = completion_packet.mark_routed(load_id, action["id"])

    return jsonify({"status": "ok", "packet": packet, "publisher_action": action}), 201


# ── Email Helper (review package) ──────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/email-package", methods=["GET"])
def get_email_package(load_id):
    from portal.models import email_helper
    package = email_helper.get_package(load_id)
    if not package:
        return jsonify({"error": "No email package for this load"}), 404
    return jsonify({"status": "ok", "package": package})


@dispatch_bp.route("/loads/<load_id>/email-package/draft", methods=["POST"])
def draft_email_package(load_id):
    """Draft the broker/customer completion emails from the load's Completion Packet.
    Requires End Load to have already run -- there's nothing to draft from otherwise.
    """
    from portal.models import completion_packet, email_helper

    packet = completion_packet.get_packet(load_id)
    if not packet:
        return jsonify({"error": "Run End Load before drafting the email package"}), 409

    closeout = packet["closeout_data"]
    package = email_helper.create_draft(
        load_id=load_id,
        load=closeout["load"],
        broker_contact=closeout.get("broker_contact"),
        pod_id=(closeout["pods"][0]["pod_id"] if closeout.get("pods") else None),
        invoice_number=(closeout["settlement"]["invoice_number"] if closeout.get("settlement") else None),
        closeout_data=closeout,
    )
    return jsonify({"status": "ok", "package": package}), 201


@dispatch_bp.route("/loads/<load_id>/email-package", methods=["PATCH"])
def update_email_package(load_id):
    from portal.models import email_helper
    data = request.get_json(silent=True) or {}
    try:
        package = email_helper.update_draft(load_id, **data)
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    return jsonify({"status": "ok", "package": package})


@dispatch_bp.route("/loads/<load_id>/email-package/submit", methods=["POST"])
def submit_email_package(load_id):
    from portal.models import completion_packet, email_helper
    data = request.get_json(silent=True) or {}
    submitted_by = data.get("submitted_by")
    try:
        package = email_helper.submit_package(load_id, submitted_by)
    except email_helper.EmailHelperSubmitError as e:
        return jsonify({"error": str(e)}), 403
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 409

    # D10: "Email Sent -> Render Email to Business Document -> ... -> Store With
    # Completion Package." Only clusters a real, already-submitted package -- never
    # renders a package that's still in DRAFT/REVIEWED.
    if package["status"] == "SUBMITTED" and completion_packet.get_packet(load_id):
        completion_packet.create_email_cluster(load_id, package)

    return jsonify({"status": "ok", "package": package})


@dispatch_bp.route("/retention/<load_id>", methods=["GET"])
def get_retention(load_id):
    ret = services.get_retention(load_id)
    if not ret:
        return jsonify({"error": f"No retention record for {load_id}"}), 404
    return jsonify({"status": "ok", "retention": ret})


# ── Rate Confirmation ────────────────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/rate", methods=["GET"])
def get_rate(load_id):
    rc = services.get_rate_confirmation(load_id)
    if not rc:
        return jsonify({"error": f"No rate confirmation for {load_id}"}), 404
    return jsonify({"status": "ok", "rate_confirmation": rc})


@dispatch_bp.route("/loads/<load_id>/rate", methods=["POST"])
def confirm_rate(load_id):
    data = _json_body()
    rate_amount = data.get("rate_amount")
    if rate_amount is None:
        return jsonify({"error": "rate_amount is required"}), 400
    try:
        rate_amount = float(rate_amount)
    except (ValueError, TypeError):
        return jsonify({"error": "rate_amount must be a number"}), 400
    rate_type = data.get("rate_type", "flat")
    if rate_type not in RATE_TYPES:
        return jsonify({"error": f"Invalid rate_type: {rate_type}"}), 400
    distance = 0.0
    if data.get("distance_miles") is not None:
        try:
            distance = float(data["distance_miles"])
        except (ValueError, TypeError):
            return jsonify({"error": "distance_miles must be a number"}), 400
    try:
        rc = services.confirm_rate(
            load_id=load_id,
            rate_amount=rate_amount,
            rate_type=rate_type,
            distance_miles=distance,
            confirmed_by=data.get("confirmed_by", ""),
            notes=data.get("notes", ""),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"status": "ok", "rate_confirmation": rc}), 201


# ── Expenses ─────────────────────────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/expenses", methods=["GET"])
def list_expenses(load_id):
    items = services.list_expenses(load_id)
    return jsonify({
        "status": "ok", "load_id": load_id,
        "expenses": items, "count": len(items),
    })


@dispatch_bp.route("/loads/<load_id>/expenses", methods=["POST"])
def add_expense(load_id):
    data = _json_body()
    amount = data.get("amount")
    if amount is None:
        return jsonify({"error": "amount is required"}), 400
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({"error": "amount must be a number"}), 400
    category = data.get("category", "other")
    if category not in EXPENSE_CATEGORIES:
        return jsonify({"error": f"Invalid category: {category}"}), 400
    try:
        exp = services.add_expense(
            load_id=load_id,
            category=category,
            description=data.get("description", ""),
            amount=amount,
            receipt_evidence_id=data.get("receipt_evidence_id"),
            notes=data.get("notes", ""),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"status": "ok", "expense": exp}), 201


@dispatch_bp.route("/expenses/<expense_id>", methods=["PATCH"])
def update_expense(expense_id):
    data = _json_body()
    data.pop("expense_id", None)
    if "category" in data and data["category"] not in EXPENSE_CATEGORIES:
        return jsonify({"error": f"Invalid category: {data['category']}"}), 400
    if "amount" in data:
        try:
            data["amount"] = float(data["amount"])
        except (ValueError, TypeError):
            return jsonify({"error": "amount must be a number"}), 400
    result = services.update_expense(expense_id, **data)
    if not result:
        return jsonify({"error": f"Expense {expense_id} not found"}), 404
    return jsonify({"status": "ok", "expense": result})


@dispatch_bp.route("/expenses/<expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    if not services.delete_expense(expense_id):
        return jsonify({"error": f"Expense {expense_id} not found"}), 404
    return jsonify({"status": "ok"})


# ── Financials Summary ───────────────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/financials", methods=["GET"])
def get_financials(load_id):
    result = services.get_financials(load_id)
    if not result:
        return jsonify({"error": f"Load {load_id} not found"}), 404
    return jsonify({"status": "ok", **result})


# ── Fuel Cost Estimator ──────────────────────────────────────────────

@dispatch_bp.route("/fuel-estimate", methods=["GET", "POST"])
def fuel_estimate():
    if request.method == "POST":
        data = _json_body()
    else:
        data = {}
        for k in ("distance_miles", "mpg", "fuel_price"):
            v = request.args.get(k)
            if v:
                try:
                    data[k] = float(v)
                except (ValueError, TypeError):
                    return jsonify({"error": f"{k} must be a number"}), 400
        load_id = request.args.get("load_id", "")
        if load_id:
            data["load_id"] = load_id

    result = services.estimate_fuel_cost(
        distance_miles=float(data.get("distance_miles", 0)),
        mpg=float(data.get("mpg", 0)),
        fuel_price=float(data.get("fuel_price", 0)),
        load_id=data.get("load_id", ""),
    )
    return jsonify({"status": "ok", **result})


@dispatch_bp.route("/fuel-defaults", methods=["GET"])
def fuel_defaults():
    return jsonify({
        "status": "ok",
        "avg_fuel_price": services.get_avg_fuel_price(),
        "fleet_mpg": services.get_fleet_mpg(),
    })


# ── Settlements ──────────────────────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/settlement", methods=["GET"])
def get_settlement(load_id):
    stl = services.get_settlement(load_id)
    if not stl:
        return jsonify({"error": f"No settlement for {load_id}"}), 404
    return jsonify({"status": "ok", "settlement": stl})


@dispatch_bp.route("/loads/<load_id>/settlement", methods=["POST"])
def create_settlement(load_id):
    data = _json_body()
    try:
        stl = services.create_settlement(
            load_id=load_id,
            due_date=data.get("due_date", ""),
            notes=data.get("notes", ""),
        )
    except ValueError as e:
        msg = str(e)
        status = 404 if "not found" in msg.lower() else 409
        return jsonify({"error": msg}), status
    return jsonify({"status": "ok", "settlement": stl}), 201


@dispatch_bp.route("/loads/<load_id>/settlement", methods=["PATCH"])
def update_settlement(load_id):
    data = _json_body()
    data.pop("load_id", None)
    if "payment_status" in data and data["payment_status"] not in SETTLEMENT_STATUSES:
        return jsonify({"error": f"Invalid payment_status: {data['payment_status']}"}), 400
    if "payment_method" in data and data["payment_method"] and data["payment_method"] not in PAYMENT_METHODS:
        return jsonify({"error": f"Invalid payment_method: {data['payment_method']}"}), 400
    for field in ("invoice_amount", "payment_amount", "factoring_fee"):
        if field in data:
            try:
                data[field] = float(data[field])
            except (ValueError, TypeError):
                return jsonify({"error": f"{field} must be a number"}), 400
    result = services.update_settlement(load_id, **data)
    if not result:
        return jsonify({"error": f"No settlement for {load_id}"}), 404
    return jsonify({"status": "ok", "settlement": result})


@dispatch_bp.route("/loads/<load_id>/payment", methods=["POST"])
def record_payment(load_id):
    data = _json_body()
    payment_amount = data.get("payment_amount")
    if payment_amount is None:
        return jsonify({"error": "payment_amount is required"}), 400
    try:
        payment_amount = float(payment_amount)
    except (ValueError, TypeError):
        return jsonify({"error": "payment_amount must be a number"}), 400
    payment_method = data.get("payment_method", "ach")
    if payment_method not in PAYMENT_METHODS:
        return jsonify({"error": f"Invalid payment_method: {payment_method}"}), 400
    factoring_fee = 0.0
    if data.get("factoring_fee") is not None:
        try:
            factoring_fee = float(data["factoring_fee"])
        except (ValueError, TypeError):
            return jsonify({"error": "factoring_fee must be a number"}), 400
    result = services.record_payment(
        load_id=load_id,
        payment_amount=payment_amount,
        payment_method=payment_method,
        factoring_fee=factoring_fee,
        notes=data.get("notes", ""),
    )
    if not result:
        return jsonify({"error": f"No settlement for {load_id}"}), 404
    return jsonify({"status": "ok", "settlement": result})


@dispatch_bp.route("/loads/<load_id>/settlement/dispute", methods=["POST"])
def dispute_settlement(load_id):
    data = _json_body()
    try:
        result = services.dispute_settlement(
            load_id=load_id,
            reason=data.get("reason", ""),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not result:
        return jsonify({"error": f"No settlement for {load_id}"}), 404
    return jsonify({"status": "ok", "settlement": result})


@dispatch_bp.route("/loads/<load_id>/settlement/write-off", methods=["POST"])
def write_off_settlement(load_id):
    data = _json_body()
    try:
        result = services.write_off_settlement(
            load_id=load_id,
            reason=data.get("reason", ""),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not result:
        return jsonify({"error": f"No settlement for {load_id}"}), 404
    return jsonify({"status": "ok", "settlement": result})


@dispatch_bp.route("/settlements", methods=["GET"])
def list_settlements():
    status = request.args.get("payment_status")
    if status and status not in SETTLEMENT_STATUSES:
        return jsonify({"error": f"Invalid payment_status: {status}"}), 400
    page, per_page = _get_page_params()
    items = services.list_settlements(
        payment_status=status,
        customer=request.args.get("customer") or None,
        date_from=request.args.get("date_from") or None,
        date_to=request.args.get("date_to") or None,
        invoice_number=request.args.get("invoice") or None,
        page=page, per_page=per_page,
    )
    return _paginated_response(items, "settlements")


# ── Financial Dashboard ──────────────────────────────────────────────

@dispatch_bp.route("/dashboard/financials", methods=["GET"])
def financial_dashboard():
    dashboard = services.get_financial_dashboard()
    return jsonify({"status": "ok", **dashboard})


# ── Aging Check ─────────────────────────────────────────────────────

@dispatch_bp.route("/settlements/aging", methods=["POST"])
def run_aging_check():
    newly_overdue = services.check_overdue_settlements()
    return jsonify({
        "status": "ok",
        "newly_overdue": newly_overdue,
        "count": len(newly_overdue),
    })


# ── Drivers ─────────────────────────────────────────────────────────

@dispatch_bp.route("/drivers", methods=["GET"])
def list_drivers():
    status = request.args.get("status")
    if status and status not in DRIVER_STATUSES:
        return jsonify({"error": f"Invalid status: {status}"}), 400
    name = request.args.get("name")
    page, per_page = _get_page_params()
    drivers = services.list_drivers(status=status, name=name, page=page, per_page=per_page)
    return _paginated_response(drivers, "drivers")


@dispatch_bp.route("/drivers", methods=["POST"])
def create_driver():
    data = _json_body()
    name = data.get("name", "")
    if not name:
        return jsonify({"error": "name is required"}), 400
    license_class = data.get("license_class", "")
    if license_class and license_class not in LICENSE_CLASSES:
        return jsonify({"error": f"Invalid license_class: {license_class}"}), 400
    drv = services.create_driver(
        name=name,
        license_number=data.get("license_number", ""),
        license_class=license_class,
        phone=data.get("phone", ""),
        email=data.get("email", ""),
        hire_date=data.get("hire_date", ""),
        notes=data.get("notes", ""),
    )
    return jsonify({"status": "ok", "driver": drv}), 201


@dispatch_bp.route("/drivers/<driver_id>", methods=["GET"])
def get_driver(driver_id):
    drv = services.get_driver(driver_id)
    if not drv:
        return jsonify({"error": f"Driver {driver_id} not found"}), 404
    return jsonify({"status": "ok", "driver": drv})


@dispatch_bp.route("/drivers/<driver_id>", methods=["PATCH"])
def update_driver(driver_id):
    data = _json_body()
    data.pop("driver_id", None)
    if "status" in data and data["status"] not in DRIVER_STATUSES:
        return jsonify({"error": f"Invalid status: {data['status']}"}), 400
    if "license_class" in data and data["license_class"] and data["license_class"] not in LICENSE_CLASSES:
        return jsonify({"error": f"Invalid license_class: {data['license_class']}"}), 400
    result = services.update_driver(driver_id, **data)
    if not result:
        return jsonify({"error": f"Driver {driver_id} not found"}), 404
    return jsonify({"status": "ok", "driver": result})


@dispatch_bp.route("/drivers/<driver_id>", methods=["DELETE"])
def delete_driver_route(driver_id):
    if not services.delete_driver(driver_id):
        return jsonify({"error": f"Driver {driver_id} not found"}), 404
    return jsonify({"status": "ok"})


# ── Equipment ───────────────────────────────────────────────────────

@dispatch_bp.route("/equipment", methods=["GET"])
def list_equipment():
    status = request.args.get("status")
    if status and status not in EQUIPMENT_STATUSES:
        return jsonify({"error": f"Invalid status: {status}"}), 400
    eq_type = request.args.get("equipment_type")
    if eq_type and eq_type not in EQUIPMENT_TYPES:
        return jsonify({"error": f"Invalid equipment_type: {eq_type}"}), 400
    unit_number = request.args.get("unit_number")
    page, per_page = _get_page_params()
    items = services.list_equipment(
        status=status, equipment_type=eq_type, unit_number=unit_number,
        page=page, per_page=per_page,
    )
    return _paginated_response(items, "equipment")


@dispatch_bp.route("/equipment", methods=["POST"])
def create_equipment():
    data = _json_body()
    unit_number = data.get("unit_number", "")
    if not unit_number:
        return jsonify({"error": "unit_number is required"}), 400
    eq_type = data.get("equipment_type", "dry_van")
    if eq_type not in EQUIPMENT_TYPES:
        return jsonify({"error": f"Invalid equipment_type: {eq_type}"}), 400
    eqp = services.create_equipment(
        unit_number=unit_number,
        equipment_type=eq_type,
        make=data.get("make", ""),
        model=data.get("model", ""),
        year=data.get("year", ""),
        vin=data.get("vin", ""),
        license_plate=data.get("license_plate", ""),
        notes=data.get("notes", ""),
    )
    return jsonify({"status": "ok", "equipment": eqp}), 201


@dispatch_bp.route("/equipment/<equipment_id>", methods=["GET"])
def get_equipment(equipment_id):
    eqp = services.get_equipment(equipment_id)
    if not eqp:
        return jsonify({"error": f"Equipment {equipment_id} not found"}), 404
    return jsonify({"status": "ok", "equipment": eqp})


@dispatch_bp.route("/equipment/<equipment_id>", methods=["PATCH"])
def update_equipment(equipment_id):
    data = _json_body()
    data.pop("equipment_id", None)
    if "status" in data and data["status"] not in EQUIPMENT_STATUSES:
        return jsonify({"error": f"Invalid status: {data['status']}"}), 400
    if "equipment_type" in data and data["equipment_type"] not in EQUIPMENT_TYPES:
        return jsonify({"error": f"Invalid equipment_type: {data['equipment_type']}"}), 400
    result = services.update_equipment(equipment_id, **data)
    if not result:
        return jsonify({"error": f"Equipment {equipment_id} not found"}), 404
    return jsonify({"status": "ok", "equipment": result})


@dispatch_bp.route("/equipment/<equipment_id>", methods=["DELETE"])
def delete_equipment_route(equipment_id):
    if not services.delete_equipment(equipment_id):
        return jsonify({"error": f"Equipment {equipment_id} not found"}), 404
    return jsonify({"status": "ok"})


# ── Fleet Assignment ────────────────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/assign-driver", methods=["POST"])
def assign_driver(load_id):
    data = _json_body()
    driver_id = data.get("driver_id", "")
    if not driver_id:
        return jsonify({"error": "driver_id is required"}), 400
    try:
        result = services.assign_driver(load_id, driver_id)
    except ValueError as e:
        msg = str(e)
        status = 404 if "not found" in msg.lower() else 400
        return jsonify({"error": msg}), status
    return jsonify({"status": "ok", "load": result})


@dispatch_bp.route("/loads/<load_id>/unassign-driver", methods=["POST"])
def unassign_driver(load_id):
    try:
        result = services.unassign_driver(load_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"status": "ok", "load": result})


@dispatch_bp.route("/loads/<load_id>/assign-equipment", methods=["POST"])
def assign_equipment(load_id):
    data = _json_body()
    equipment_id = data.get("equipment_id", "")
    if not equipment_id:
        return jsonify({"error": "equipment_id is required"}), 400
    try:
        result = services.assign_equipment(load_id, equipment_id)
    except ValueError as e:
        msg = str(e)
        status = 404 if "not found" in msg.lower() else 400
        return jsonify({"error": msg}), status
    return jsonify({"status": "ok", "load": result})


@dispatch_bp.route("/loads/<load_id>/unassign-equipment", methods=["POST"])
def unassign_equipment(load_id):
    try:
        result = services.unassign_equipment(load_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"status": "ok", "load": result})


# ── Fleet Summary ───────────────────────────────────────────────────

@dispatch_bp.route("/fleet/summary", methods=["GET"])
def fleet_summary():
    summary = services.get_fleet_summary()
    return jsonify({"status": "ok", **summary})


# ── Decision (email action clicks) ──────────────────────────────────

@dispatch_bp.route("/decision/<load_id>/<action>")
def dispatch_decision(load_id, action):
    token = request.args.get("token", "")

    if action not in notifications.DISPATCH_ACTIONS:
        return render_template(
            "dispatch_decision.html",
            success=False,
            error=f"Unknown action: {action}",
            load_id=load_id,
        ), 400

    if not notifications.verify_token(load_id, action, token):
        return render_template(
            "dispatch_decision.html",
            success=False,
            error="Invalid or expired token.",
            load_id=load_id,
        ), 403

    load = services.get_load(load_id)
    if not load:
        return render_template(
            "dispatch_decision.html",
            success=False,
            error="Load not found.",
            load_id=load_id,
        ), 404

    label, _ = notifications.DISPATCH_ACTIONS[action]

    if action == "escalate":
        services.open_exception(
            load_id=load_id,
            exception_type="other",
            severity="high",
            description="Escalated via email action by reviewer",
        )
    elif action == "flag_review":
        services.open_exception(
            load_id=load_id,
            exception_type="other",
            severity="medium",
            description="Flagged for review via email action by reviewer",
        )

    services.add_milestone(
        load_id=load_id,
        event_type="checkpoint",
        source="email",
        note=f"Email decision: {label}",
        entered_by="reviewer",
    )

    return render_template(
        "dispatch_decision.html",
        success=True,
        load_id=load_id,
        action_label=label,
        load=load,
    )


# ── Batch Status Update ──────────────────────────────────────────────


@dispatch_bp.route("/loads/batch-status", methods=["POST"])
def batch_status_update():
    data = _json_body(force=True)
    load_ids = data.get("load_ids", [])
    status = data.get("status", "")
    if not load_ids or not isinstance(load_ids, list):
        return jsonify({"error": "load_ids list is required"}), 400
    if not status:
        return jsonify({"error": "status is required"}), 400
    updated = 0
    errors = []
    for lid in load_ids:
        try:
            result = services.update_load(lid, status=status)
            if result:
                updated += 1
            else:
                errors.append(f"{lid}: not found")
        except ValueError as exc:
            errors.append(f"{lid}: {exc}")
    return jsonify({"updated": updated, "errors": errors})


# ── Batch Invoice Creation ───────────────────────────────────────────


@dispatch_bp.route("/settlements/batch-create", methods=["POST"])
def batch_create_settlements():
    data = _json_body(force=True)
    load_ids = data.get("load_ids", [])
    due_date = data.get("due_date", "")
    if not load_ids or not isinstance(load_ids, list):
        return jsonify({"error": "load_ids list is required"}), 400
    created = 0
    errors = []
    for lid in load_ids:
        try:
            services.create_settlement(load_id=lid, due_date=due_date)
            created += 1
        except ValueError as exc:
            errors.append(f"{lid}: {exc}")
    return jsonify({"status": "ok", "created": created, "errors": errors})


# ── CSV Export ───────────────────────────────────────────────────────

_LOAD_CSV_COLUMNS = [
    "load_id", "customer", "broker_shipper", "status", "source",
    "pickup_location", "delivery_location",
    "pickup_datetime", "delivery_datetime",
    "equipment", "driver", "notes", "created_at", "updated_at",
]

_SETTLEMENT_CSV_COLUMNS = [
    "invoice_number", "load_id", "invoice_amount", "payment_status",
    "invoice_date", "due_date", "payment_amount", "payment_date",
    "payment_method", "notes",
]


def _to_csv(rows: list[dict], columns: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in columns})
    return buf.getvalue()


@dispatch_bp.route("/loads/export.csv", methods=["GET"])
def export_loads_csv():
    loads = services.list_loads(
        status=request.args.get("status") or None,
        customer=request.args.get("customer") or None,
        date_from=request.args.get("date_from") or None,
        date_to=request.args.get("date_to") or None,
    )
    csv_data = _to_csv(loads, _LOAD_CSV_COLUMNS)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=loads.csv"},
    )


@dispatch_bp.route("/settlements/export.csv", methods=["GET"])
def export_settlements_csv():
    settlements = services.list_settlements(
        payment_status=request.args.get("status") or None,
        customer=request.args.get("customer") or None,
        date_from=request.args.get("date_from") or None,
        date_to=request.args.get("date_to") or None,
        invoice_number=request.args.get("invoice") or None,
    )
    for stl in settlements:
        load = services.get_load(stl["load_id"])
        stl["customer"] = load["customer"] if load else ""
    csv_data = _to_csv(settlements, ["customer"] + _SETTLEMENT_CSV_COLUMNS)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=settlements.csv"},
    )


# ── Activities ───────────────────────────────────────────────────────


@dispatch_bp.route("/loads/<load_id>/activities", methods=["GET"])
def list_activities(load_id):
    load = services.get_load(load_id)
    if not load:
        return jsonify({"error": "Load not found"}), 404
    activity_type = request.args.get("type")
    if activity_type and activity_type not in ACTIVITY_TYPES:
        return jsonify({"error": f"Invalid type. Must be one of {ACTIVITY_TYPES}"}), 400
    items = services.list_activities(load_id, activity_type=activity_type)
    return jsonify(items)


@dispatch_bp.route("/loads/<load_id>/activities", methods=["POST"])
def add_activity(load_id):
    data = _json_body(force=True)
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400
    activity_type = data.get("activity_type", "comment")
    if activity_type not in ACTIVITY_TYPES:
        return jsonify({"error": f"Invalid activity_type. Must be one of {ACTIVITY_TYPES}"}), 400
    try:
        result = services.add_activity(
            load_id=load_id,
            message=message,
            activity_type=activity_type,
            author=data.get("author", ""),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(result), 201


@dispatch_bp.route("/activities/<activity_id>", methods=["DELETE"])
def delete_activity(activity_id):
    if services.delete_activity(activity_id):
        return jsonify({"ok": True})
    return jsonify({"error": "Activity not found"}), 404


# ── Global Search ────────────────────────────────────────────────────

@dispatch_bp.route("/search", methods=["GET"])
def global_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q parameter is required"}), 400
    if len(q) < 2:
        return jsonify({"error": "Search query must be at least 2 characters"}), 400
    results = services.global_search(q)
    total = sum(len(v) for v in results.values())
    return jsonify({"status": "ok", "query": q, "total": total, **results})


# ── CSV Import ───────────────────────────────────────────────────────

_IMPORT_REQUIRED = {"customer"}
_IMPORT_FIELDS = {
    "customer", "broker_shipper", "pickup_location", "delivery_location",
    "pickup_datetime", "delivery_datetime", "equipment", "driver", "source", "notes",
}


@dispatch_bp.route("/loads/import", methods=["POST"])
def import_loads_csv():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "file is required"}), 400

    try:
        text = f.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify({"error": "File must be UTF-8 encoded CSV"}), 400

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return jsonify({"error": "CSV file is empty or has no headers"}), 400

    headers = {h.strip().lower() for h in reader.fieldnames}
    missing = _IMPORT_REQUIRED - headers
    if missing:
        return jsonify({"error": f"Missing required columns: {', '.join(sorted(missing))}"}), 400

    created = 0
    errors = []
    for i, row in enumerate(reader, start=2):
        cleaned = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        customer = cleaned.get("customer", "")
        if not customer:
            errors.append(f"Row {i}: customer is required")
            continue
        kwargs = {k: cleaned[k] for k in _IMPORT_FIELDS & set(cleaned) if cleaned[k]}
        try:
            services.create_load(**kwargs)
            created += 1
        except ValueError as exc:
            errors.append(f"Row {i}: {exc}")

    return jsonify({"status": "ok", "created": created, "errors": errors})


# ── Lane Templates ──────────────────────────────────────────────────


@dispatch_bp.route("/lane-templates", methods=["GET"])
def list_lane_templates():
    return jsonify(services.list_lane_templates())


@dispatch_bp.route("/lane-templates", methods=["POST"])
def create_lane_template():
    data = _json_body(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    try:
        tpl = services.create_lane_template(
            name=name,
            customer=data.get("customer", ""),
            broker_shipper=data.get("broker_shipper", ""),
            pickup_location=data.get("pickup_location", ""),
            delivery_location=data.get("delivery_location", ""),
            equipment=data.get("equipment", ""),
            notes=data.get("notes", ""),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(tpl), 201


@dispatch_bp.route("/lane-templates/<template_id>", methods=["GET"])
def get_lane_template(template_id):
    tpl = services.get_lane_template(template_id)
    if not tpl:
        return jsonify({"error": "not found"}), 404
    return jsonify(tpl)


@dispatch_bp.route("/lane-templates/<template_id>", methods=["PATCH"])
def update_lane_template(template_id):
    data = _json_body(force=True)
    data.pop("template_id", None)
    tpl = services.update_lane_template(template_id, **data)
    if not tpl:
        return jsonify({"error": "not found"}), 404
    return jsonify(tpl)


@dispatch_bp.route("/lane-templates/<template_id>", methods=["DELETE"])
def delete_lane_template(template_id):
    ok = services.delete_lane_template(template_id)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "deleted"})


@dispatch_bp.route("/lane-templates/<template_id>/create-load", methods=["POST"])
def create_load_from_template(template_id):
    load = services.create_load_from_template(template_id)
    if not load:
        return jsonify({"error": "template not found"}), 404
    return jsonify(load), 201


# ── Broker Scorecard ────────────────────────────────────────────────


@dispatch_bp.route("/brokers", methods=["GET"])
def broker_scorecards():
    return jsonify(services.get_broker_scorecards())


@dispatch_bp.route("/brokers/<path:broker_name>", methods=["GET"])
def broker_detail(broker_name):
    detail = services.get_broker_detail(broker_name)
    if not detail["loads"]:
        return jsonify({"error": "no loads found for broker"}), 404
    return jsonify(detail)


# ── Load Calendar ───────────────────────────────────────────────────


@dispatch_bp.route("/calendar", methods=["GET"])
def load_calendar_api():
    from datetime import date
    today = date.today()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
    except (ValueError, TypeError):
        year, month = today.year, today.month
    data = services.get_load_calendar(year, month)
    return jsonify(data)


# ── Detention Tracking ─────────────────────────────────────────────


@dispatch_bp.route("/loads/<load_id>/detentions", methods=["GET"])
def list_detentions(load_id):
    detentions = services.list_detentions(load_id=load_id)
    return jsonify({"status": "ok", "detentions": detentions, "count": len(detentions)})


@dispatch_bp.route("/loads/<load_id>/detentions", methods=["POST"])
def start_detention(load_id):
    data = _json_body()
    location_type = data.get("location_type", "pickup")
    if location_type not in DETENTION_LOCATIONS:
        return jsonify({"error": f"Invalid location_type: {location_type}"}), 400
    try:
        det = services.start_detention(
            load_id=load_id,
            location_type=location_type,
            free_hours=float(data.get("free_hours", 2.0)),
            hourly_rate=float(data.get("hourly_rate", 75.0)),
            notes=data.get("notes", ""),
            started_at=data.get("started_at", ""),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(det), 201


@dispatch_bp.route("/detentions/<detention_id>", methods=["PATCH"])
def update_detention(detention_id):
    data = _json_body()
    data.pop("detention_id", None)
    result = services.update_detention(detention_id, **data)
    if not result:
        return jsonify({"error": "detention not found"}), 404
    return jsonify(result)


@dispatch_bp.route("/detentions/<detention_id>/stop", methods=["POST"])
def stop_detention(detention_id):
    data = _json_body()
    ended_at = data.get("ended_at", "")
    if ended_at:
        # A malformed (but non-empty) ended_at would otherwise be silently
        # swallowed by DetentionEvent.total_hours() -> 0.0 hours -> no
        # expense created at all, with no error surfaced anywhere. Reject
        # it here instead of losing real detention revenue silently.
        try:
            datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return jsonify({"error": f"ended_at is not a valid ISO timestamp: {ended_at!r}"}), 400
    try:
        result = services.stop_detention(
            detention_id,
            ended_at=ended_at,
            create_expense=data.get("create_expense", True),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not result:
        return jsonify({"error": "detention not found"}), 404
    return jsonify(result)


@dispatch_bp.route("/detentions/<detention_id>", methods=["DELETE"])
def delete_detention(detention_id):
    ok = services.delete_detention(detention_id)
    if not ok:
        return jsonify({"error": "detention not found"}), 404
    return jsonify({"status": "ok"})


@dispatch_bp.route("/detentions/summary", methods=["GET"])
def detention_summary():
    return jsonify(services.get_detention_summary())


# ── IFTA Trip Legs ─────────────────────────────────────────────────


@dispatch_bp.route("/ifta/trip-legs", methods=["GET"])
def list_ifta_trip_legs():
    kwargs = {}
    for key in ("date_from", "date_to", "jurisdiction", "vehicle_id", "load_id"):
        val = request.args.get(key)
        if val:
            kwargs[key] = val
    return jsonify(services.list_ifta_trip_legs(**kwargs))


@dispatch_bp.route("/ifta/trip-legs", methods=["POST"])
def add_ifta_trip_leg():
    data = _json_body(force=True)
    try:
        result = services.add_ifta_trip_leg(
            jurisdiction=data.get("jurisdiction", ""),
            miles=float(data.get("miles", 0)),
            date=data.get("date", ""),
            vehicle_id=data.get("vehicle_id", ""),
            load_id=data.get("load_id", ""),
            notes=data.get("notes", ""),
        )
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result), 201


@dispatch_bp.route("/ifta/trip-legs/<leg_id>", methods=["PATCH"])
def update_ifta_trip_leg(leg_id):
    data = _json_body(force=True)
    data.pop("leg_id", None)
    try:
        result = services.update_ifta_trip_leg(leg_id, **data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@dispatch_bp.route("/ifta/trip-legs/<leg_id>", methods=["DELETE"])
def delete_ifta_trip_leg(leg_id):
    ok = services.delete_ifta_trip_leg(leg_id)
    if not ok:
        return jsonify({"error": "trip leg not found"}), 404
    return jsonify({"status": "ok"})


# ── IFTA Fuel Purchases ───────────────────────────────────────────


@dispatch_bp.route("/ifta/fuel-purchases", methods=["GET"])
def list_ifta_fuel_purchases():
    kwargs = {}
    for key in ("date_from", "date_to", "jurisdiction", "vehicle_id"):
        val = request.args.get(key)
        if val:
            kwargs[key] = val
    return jsonify(services.list_ifta_fuel_purchases(**kwargs))


@dispatch_bp.route("/ifta/fuel-purchases", methods=["POST"])
def add_ifta_fuel_purchase():
    data = _json_body(force=True)
    raw_confidence = data.get("extraction_confidence")
    try:
        result = services.add_ifta_fuel_purchase(
            jurisdiction=data.get("jurisdiction", ""),
            gallons=float(data.get("gallons", 0)),
            amount=float(data.get("amount", 0)),
            date=data.get("date", ""),
            vehicle_id=data.get("vehicle_id", ""),
            vendor=data.get("vendor", ""),
            notes=data.get("notes", ""),
            extraction_confidence=float(raw_confidence) if raw_confidence is not None else None,
        )
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result), 201


@dispatch_bp.route("/ifta/fuel-purchases/extract-receipt", methods=["POST"])
def extract_ifta_fuel_receipt():
    """Pre-fill lookup only -- creates no fuel purchase, no evidence row.
    Always returns 200 with either extracted fields or an
    available:false reason; the one genuine client error is no file at
    all."""
    from cin_lite.agents import receipt_vision

    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "No file provided"}), 400
    file_data = uploaded_file.read()
    if len(file_data) > MAX_FILE_SIZE:
        return jsonify({"error": f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit"}), 400

    result = receipt_vision.extract_fuel_receipt(file_data, uploaded_file.filename)
    if result.get("available") and result.get("vendor_address"):
        result["jurisdiction"] = receipt_vision.derive_jurisdiction(result["vendor_address"])
    return jsonify(result)


@dispatch_bp.route("/ifta/fuel-purchases/<purchase_id>", methods=["PATCH"])
def update_ifta_fuel_purchase(purchase_id):
    data = _json_body(force=True)
    data.pop("purchase_id", None)
    try:
        result = services.update_ifta_fuel_purchase(purchase_id, **data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@dispatch_bp.route("/ifta/fuel-purchases/<purchase_id>", methods=["DELETE"])
def delete_ifta_fuel_purchase(purchase_id):
    ok = services.delete_ifta_fuel_purchase(purchase_id)
    if not ok:
        return jsonify({"error": "fuel purchase not found"}), 404
    return jsonify({"status": "ok"})


# ── IFTA Fuel Purchase Evidence (Phase 5) ──────────────────────────
# Two-step, mirroring /loads/<load_id>/evidence: the purchase must
# already exist before a receipt can be attached to it.


@dispatch_bp.route("/ifta/fuel-purchases/<purchase_id>/evidence", methods=["GET"])
def list_ifta_fuel_evidence(purchase_id):
    items = services.list_ifta_fuel_evidence(purchase_id)
    return jsonify({"status": "ok", "purchase_id": purchase_id, "evidence": items, "count": len(items)})


@dispatch_bp.route("/ifta/fuel-purchases/<purchase_id>/evidence", methods=["POST"])
def attach_ifta_fuel_evidence(purchase_id):
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "No file provided"}), 400
    filename = uploaded_file.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"File type not allowed: .{ext}"}), 400
    file_data = uploaded_file.read()
    if len(file_data) > MAX_FILE_SIZE:
        return jsonify({"error": f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit"}), 400
    try:
        ev = services.attach_ifta_fuel_evidence(
            purchase_id=purchase_id,
            file_data=file_data,
            original_filename=filename,
            description=request.form.get("description", ""),
            uploaded_by=request.form.get("uploaded_by", ""),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"status": "ok", "evidence": ev}), 201


@dispatch_bp.route("/ifta/fuel-evidence/<evidence_id>/download", methods=["GET"])
def download_ifta_fuel_evidence(evidence_id):
    result = services.get_ifta_fuel_evidence_file(evidence_id)
    if not result:
        return jsonify({"error": "File not found"}), 404
    file_path, download_name = result
    return send_file(file_path, download_name=download_name, as_attachment=True)


# ── IFTA Quarterly Report ─────────────────────────────────────────


@dispatch_bp.route("/ifta/report", methods=["GET"])
def ifta_quarterly_report():
    try:
        year = int(request.args.get("year", 0))
        quarter = int(request.args.get("quarter", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "year and quarter must be integers"}), 400
    if not year or not quarter:
        return jsonify({"error": "year and quarter are required"}), 400
    vehicle_id = request.args.get("vehicle_id", "")
    try:
        report = services.get_ifta_quarterly_report(year, quarter, vehicle_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(report)


@dispatch_bp.route("/ifta/monthly-report", methods=["GET"])
def ifta_monthly_report():
    try:
        year = int(request.args.get("year", 0))
        month = int(request.args.get("month", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "year and month must be integers"}), 400
    if not year or not month:
        return jsonify({"error": "year and month are required"}), 400
    vehicle_id = request.args.get("vehicle_id", "")
    try:
        report = services.get_ifta_monthly_report(year, month, vehicle_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(report)


@dispatch_bp.route("/ifta/export-csv", methods=["GET"])
def ifta_export_csv():
    from flask import Response

    try:
        year = int(request.args.get("year", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "year must be an integer"}), 400

    vehicle_id = request.args.get("vehicle_id", "")
    period_type = request.args.get("type", "quarter")

    try:
        if period_type == "month":
            month = int(request.args.get("month", 0))
            if not year or not month:
                return jsonify({"error": "year and month are required"}), 400
            report = services.get_ifta_monthly_report(year, month, vehicle_id)
            filename = f"ifta_{year}_{month:02d}.csv"
        else:
            quarter = int(request.args.get("quarter", 0))
            if not year or not quarter:
                return jsonify({"error": "year and quarter are required"}), 400
            report = services.get_ifta_quarterly_report(year, quarter, vehicle_id)
            filename = f"ifta_{year}_Q{quarter}.csv"
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    csv_data = services.export_ifta_csv(report)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── IFTA Report Approvals (Phase 4 finalization gate) ────────────────


@dispatch_bp.route("/ifta/report-approvals", methods=["GET", "POST"])
def ifta_report_approvals():
    if request.method == "GET":
        return jsonify({"status": "ok", "approvals": services.list_ifta_report_approvals()})

    data = _json_body()
    try:
        year = int(data.get("year", 0))
        quarter = int(data.get("quarter", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "year and quarter must be integers"}), 400
    if not year or not quarter:
        return jsonify({"error": "year and quarter are required"}), 400
    vehicle_id = data.get("vehicle_id", "")

    try:
        approval = services.submit_ifta_quarter_for_approval(year, quarter, vehicle_id)
    except services.AlreadySubmittedError as exc:
        return jsonify({"error": str(exc)}), 409
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(approval), 201


@dispatch_bp.route("/ifta/report-approvals/<approval_id>", methods=["GET"])
def ifta_report_approval_detail(approval_id):
    approval = services.get_ifta_report_approval(approval_id)
    if approval is None:
        return jsonify({"error": f"No such IFTA report approval: {approval_id}"}), 404
    return jsonify(approval)


@dispatch_bp.route("/ifta/report-approvals/<approval_id>/exceptions", methods=["GET"])
def ifta_report_approval_exceptions(approval_id):
    approval = services.get_ifta_report_approval(approval_id)
    if approval is None:
        return jsonify({"error": f"No such IFTA report approval: {approval_id}"}), 404
    exceptions = services.list_ifta_exceptions(approval_id)
    return jsonify({"status": "ok", "approval_id": approval_id, "exceptions": exceptions, "count": len(exceptions)})


@dispatch_bp.route("/ifta/report-approvals/<approval_id>/approve", methods=["GET"])
def ifta_report_approval_approve(approval_id):
    token = request.args.get("token", "")
    try:
        approval = services.approve_ifta_quarter(approval_id, token)
    except services.InvalidApprovalTokenError as exc:
        return render_template(
            "ifta_approval_decision.html", success=False, error=str(exc),
            approval_id=approval_id,
        ), 403
    except ValueError as exc:
        return render_template(
            "ifta_approval_decision.html", success=False, error=str(exc),
            approval_id=approval_id,
        ), 404
    return render_template(
        "ifta_approval_decision.html", success=True, approval=approval,
    )


# ── Broker Contact Directory ─────────────────────────────────────────


@dispatch_bp.route("/broker-contacts", methods=["GET"])
def list_broker_contacts():
    kwargs = {}
    status = request.args.get("status")
    if status:
        kwargs["status"] = status
    search = request.args.get("search")
    if search:
        kwargs["search"] = search
    return jsonify(services.list_broker_contacts(**kwargs))


@dispatch_bp.route("/broker-contacts", methods=["POST"])
def add_broker_contact():
    data = _json_body(force=True)
    try:
        result = services.add_broker_contact(
            company_name=data.get("company_name", ""),
            contact_name=data.get("contact_name", ""),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            mc_number=data.get("mc_number", ""),
            dot_number=data.get("dot_number", ""),
            address=data.get("address", ""),
            payment_terms=data.get("payment_terms", ""),
            notes=data.get("notes", ""),
            status=data.get("status", "active"),
        )
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result), 201


@dispatch_bp.route("/broker-contacts/<broker_id>", methods=["GET"])
def get_broker_contact(broker_id):
    broker = services.get_broker_contact_with_stats(broker_id)
    if not broker:
        return jsonify({"error": "broker not found"}), 404
    return jsonify(broker)


@dispatch_bp.route("/broker-contacts/<broker_id>", methods=["PUT"])
def update_broker_contact(broker_id):
    data = _json_body(force=True)
    try:
        result = services.update_broker_contact(broker_id, data)
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    if not result:
        return jsonify({"error": "broker not found"}), 404
    return jsonify(result)


@dispatch_bp.route("/broker-contacts/<broker_id>", methods=["DELETE"])
def delete_broker_contact(broker_id):
    ok = services.delete_broker_contact(broker_id)
    if not ok:
        return jsonify({"error": "broker not found"}), 404
    return jsonify({"status": "ok"})


# ── Load Profitability Ranking ───────────────────────────────────────


@dispatch_bp.route("/profitability", methods=["GET"])
def load_profitability():
    sort_by = request.args.get("sort_by", "profit")
    sort_order = request.args.get("sort_order", "desc")
    date_from = request.args.get("date_from") or None
    date_to = request.args.get("date_to") or None
    status = request.args.get("status") or None
    try:
        result = services.get_load_profitability(
            sort_by=sort_by, sort_order=sort_order,
            date_from=date_from, date_to=date_to, status=status,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


# ── Driver Pay ───────────────────────────────────────────────────────


@dispatch_bp.route("/driver-pay", methods=["GET"])
def list_driver_pay():
    from dispatch import services as svc
    entries = svc.list_driver_pay(
        driver_id=request.args.get("driver_id") or None,
        load_id=request.args.get("load_id") or None,
        status=request.args.get("status") or None,
        pay_period=request.args.get("pay_period") or None,
    )
    return jsonify(entries)


@dispatch_bp.route("/driver-pay", methods=["POST"])
def create_driver_pay():
    from dispatch import services as svc
    data = _json_body(force=True)
    driver_id = data.get("driver_id", "")
    pay_type = data.get("pay_type", "per_mile")
    if not driver_id:
        return jsonify({"error": "driver_id is required"}), 400
    try:
        result = svc.add_driver_pay(
            driver_id=driver_id,
            pay_type=pay_type,
            amount=float(data.get("amount", 0)),
            load_id=data.get("load_id", ""),
            description=data.get("description", ""),
            rate=float(data.get("rate", 0)),
            miles=float(data.get("miles", 0)),
            hours=float(data.get("hours", 0)),
            percentage=float(data.get("percentage", 0)),
            pay_period=data.get("pay_period", ""),
            notes=data.get("notes", ""),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result), 201


@dispatch_bp.route("/driver-pay/<pay_id>", methods=["GET"])
def get_driver_pay(pay_id):
    from dispatch import services as svc
    entry = svc.get_driver_pay_entry(pay_id)
    if not entry:
        return jsonify({"error": "not found"}), 404
    return jsonify(entry)


@dispatch_bp.route("/driver-pay/<pay_id>", methods=["PATCH"])
def update_driver_pay(pay_id):
    from dispatch import services as svc
    data = _json_body(force=True)
    data.pop("pay_id", None)
    try:
        result = svc.update_driver_pay(pay_id, **data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not result:
        return jsonify({"error": "not found"}), 404
    return jsonify(result)


@dispatch_bp.route("/driver-pay/<pay_id>", methods=["DELETE"])
def delete_driver_pay(pay_id):
    from dispatch import services as svc
    if svc.delete_driver_pay(pay_id):
        return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


@dispatch_bp.route("/driver-pay/summary/<driver_id>", methods=["GET"])
def driver_pay_summary(driver_id):
    from dispatch import services as svc
    summary = svc.get_driver_pay_summary(
        driver_id,
        pay_period=request.args.get("pay_period") or None,
    )
    return jsonify(summary)


@dispatch_bp.route("/driver-pay/approve", methods=["POST"])
def approve_driver_pay():
    from dispatch import services as svc
    data = _json_body(force=True)
    pay_ids = data.get("pay_ids", [])
    if not pay_ids:
        return jsonify({"error": "pay_ids required"}), 400
    count = svc.approve_driver_pay(pay_ids)
    return jsonify({"approved": count})


@dispatch_bp.route("/driver-pay/mark-paid", methods=["POST"])
def mark_driver_pay_paid():
    from dispatch import services as svc
    data = _json_body(force=True)
    pay_ids = data.get("pay_ids", [])
    if not pay_ids:
        return jsonify({"error": "pay_ids required"}), 400
    count = svc.mark_driver_pay_paid(
        pay_ids, paid_date=data.get("paid_date", "")
    )
    return jsonify({"paid": count})


# ── Maintenance Schedules ────────────────────────────────────────────


@dispatch_bp.route("/maintenance", methods=["GET"])
def list_maintenance():
    from dispatch import services as svc
    entries = svc.list_maintenance_schedules(
        equipment_id=request.args.get("equipment_id") or None,
        status=request.args.get("status") or None,
    )
    return jsonify(entries)


@dispatch_bp.route("/maintenance", methods=["POST"])
def create_maintenance():
    from dispatch import services as svc
    data = _json_body(force=True)
    equipment_id = data.get("equipment_id", "")
    if not equipment_id:
        return jsonify({"error": "equipment_id is required"}), 400
    try:
        result = svc.add_maintenance_schedule(
            equipment_id=equipment_id,
            service_type=data.get("service_type", "other"),
            description=data.get("description", ""),
            interval_miles=float(data.get("interval_miles", 0)),
            interval_days=int(data.get("interval_days", 0)),
            next_due_date=data.get("next_due_date", ""),
            next_due_miles=float(data.get("next_due_miles", 0)),
            cost_estimate=float(data.get("cost_estimate", 0)),
            vendor=data.get("vendor", ""),
            notes=data.get("notes", ""),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result), 201


@dispatch_bp.route("/maintenance/<schedule_id>", methods=["GET"])
def get_maintenance(schedule_id):
    from dispatch import services as svc
    entry = svc.get_maintenance_schedule(schedule_id)
    if not entry:
        return jsonify({"error": "not found"}), 404
    return jsonify(entry)


@dispatch_bp.route("/maintenance/<schedule_id>", methods=["PATCH"])
def update_maintenance(schedule_id):
    from dispatch import services as svc
    data = _json_body(force=True)
    try:
        result = svc.update_maintenance_schedule(schedule_id, **data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not result:
        return jsonify({"error": "not found"}), 404
    return jsonify(result)


@dispatch_bp.route("/maintenance/<schedule_id>", methods=["DELETE"])
def delete_maintenance(schedule_id):
    from dispatch import services as svc
    if svc.delete_maintenance_schedule(schedule_id):
        return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


@dispatch_bp.route("/maintenance/<schedule_id>/complete", methods=["POST"])
def complete_maintenance(schedule_id):
    from dispatch import services as svc
    data = _json_body(force=True)
    result = svc.complete_maintenance(
        schedule_id,
        service_date=data.get("service_date", ""),
        service_miles=float(data.get("service_miles", 0)),
    )
    if not result:
        return jsonify({"error": "not found"}), 404
    return jsonify(result)


@dispatch_bp.route("/maintenance/upcoming", methods=["GET"])
def upcoming_maintenance():
    from dispatch import services as svc
    days = int(request.args.get("days", 7))
    entries = svc.get_upcoming_maintenance(days_ahead=days)
    return jsonify(entries)


@dispatch_bp.route("/maintenance/overdue", methods=["GET"])
def overdue_maintenance():
    from dispatch import services as svc
    entries = svc.get_overdue_maintenance()
    return jsonify(entries)


@dispatch_bp.route("/maintenance/check-alerts", methods=["POST"])
def check_maintenance_alerts():
    from dispatch import services as svc
    result = svc.check_maintenance_alerts()
    return jsonify(result)


# ── Compliance Document Tracker ──────────────────────────────────────


@dispatch_bp.route("/compliance", methods=["GET"])
def list_compliance_documents():
    from dispatch import services as svc
    filters = {}
    for key in ("entity_type", "entity_id", "doc_type", "status"):
        val = request.args.get(key)
        if val:
            filters[key] = val
    docs = svc.list_compliance_documents(**filters)
    return jsonify(docs)


@dispatch_bp.route("/compliance", methods=["POST"])
def add_compliance_document():
    from dispatch import services as svc
    data = request.json or {}
    try:
        doc = svc.add_compliance_document(
            doc_type=data.get("doc_type", "other"),
            title=data.get("title", ""),
            entity_type=data.get("entity_type", "company"),
            entity_id=data.get("entity_id", ""),
            issuing_authority=data.get("issuing_authority", ""),
            doc_number=data.get("doc_number", ""),
            issue_date=data.get("issue_date", ""),
            expiry_date=data.get("expiry_date", ""),
            alert_days=int(data.get("alert_days", 30)),
            notes=data.get("notes", ""),
        )
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(doc), 201


@dispatch_bp.route("/compliance/<doc_id>", methods=["GET"])
def get_compliance_document(doc_id):
    from dispatch import services as svc
    doc = svc.get_compliance_document(doc_id)
    if not doc:
        return jsonify({"error": "not found"}), 404
    return jsonify(doc)


@dispatch_bp.route("/compliance/<doc_id>", methods=["PATCH"])
def update_compliance_document(doc_id):
    from dispatch import services as svc
    data = request.json or {}
    try:
        if "alert_days" in data:
            data["alert_days"] = int(data["alert_days"])
        doc = svc.update_compliance_document(doc_id, **data)
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(doc)


@dispatch_bp.route("/compliance/<doc_id>", methods=["DELETE"])
def delete_compliance_document(doc_id):
    from dispatch import services as svc
    if svc.delete_compliance_document(doc_id):
        return jsonify({"status": "deleted"})
    return jsonify({"error": "not found"}), 404


@dispatch_bp.route("/compliance/expiring", methods=["GET"])
def expiring_compliance_documents():
    from dispatch import services as svc
    days = int(request.args.get("days", 30))
    docs = svc.get_expiring_compliance_documents(days_ahead=days)
    return jsonify(docs)


@dispatch_bp.route("/compliance/check-alerts", methods=["POST"])
def check_compliance_alerts():
    from dispatch import services as svc
    result = svc.check_compliance_alerts()
    return jsonify(result)


# ── Email Template Preview ───────────────────────────────────────────


@dispatch_bp.route("/email-preview", methods=["GET"])
def email_preview_list():
    from dispatch.notifications import EMAIL_TEMPLATES
    return jsonify(EMAIL_TEMPLATES)


@dispatch_bp.route("/email-preview/<template_key>", methods=["GET"])
def email_preview(template_key):
    from dispatch.notifications import preview_notification
    result = preview_notification(template_key)
    if not result:
        return jsonify({"error": "unknown template"}), 404
    if request.args.get("raw") == "1":
        return result["html"], 200, {"Content-Type": "text/html"}
    return jsonify(result)
