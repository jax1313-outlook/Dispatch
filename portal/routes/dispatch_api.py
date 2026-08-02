"""Dispatch Data Engine API routes.

REST endpoints for loads, milestones, evidence, exceptions,
POD packages, and retention archive.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from dispatch import notifications, services
from dispatch.models import (
    EVIDENCE_TYPES,
    EXCEPTION_STATUSES,
    EXCEPTION_TYPES,
    LOAD_STATUSES,
    MILESTONE_SOURCES,
    MILESTONE_TYPES,
    SEVERITY_LEVELS,
)

dispatch_bp = Blueprint("dispatch_api", __name__)


# ── Loads ─────────────────────────────────────────────────────────────

@dispatch_bp.route("/loads", methods=["GET"])
def list_loads():
    status = request.args.get("status")
    if status and status not in LOAD_STATUSES:
        return jsonify({"error": f"Invalid status: {status}"}), 400
    loads = services.list_loads(status=status)
    return jsonify({"status": "ok", "loads": loads, "count": len(loads)})


@dispatch_bp.route("/loads", methods=["POST"])
def create_load():
    data = request.get_json(silent=True) or {}
    customer = data.get("customer", "")
    if not customer:
        return jsonify({"error": "customer is required"}), 400
    load = services.create_load(
        customer=customer,
        broker_shipper=data.get("broker_shipper", ""),
        pickup_location=data.get("pickup_location", ""),
        delivery_location=data.get("delivery_location", ""),
        pickup_datetime=data.get("pickup_datetime", ""),
        delivery_datetime=data.get("delivery_datetime", ""),
        equipment=data.get("equipment", ""),
        driver=data.get("driver", ""),
        notes=data.get("notes", ""),
    )
    return jsonify({"status": "ok", "load": load}), 201


@dispatch_bp.route("/loads/<load_id>", methods=["GET"])
def get_load(load_id):
    load = services.get_load(load_id)
    if not load:
        return jsonify({"error": f"Load {load_id} not found"}), 404
    return jsonify({"status": "ok", "load": load})


@dispatch_bp.route("/loads/<load_id>", methods=["PATCH"])
def update_load(load_id):
    data = request.get_json(silent=True) or {}
    if "status" in data and data["status"] not in LOAD_STATUSES:
        return jsonify({"error": f"Invalid status: {data['status']}"}), 400
    result = services.update_load(load_id, **data)
    if not result:
        return jsonify({"error": f"Load {load_id} not found"}), 404
    return jsonify({"status": "ok", "load": result})


@dispatch_bp.route("/loads/<load_id>/bundle", methods=["GET"])
def load_bundle(load_id):
    bundle = services.get_load_bundle(load_id)
    if not bundle:
        return jsonify({"error": f"Load {load_id} not found"}), 404
    return jsonify({"status": "ok", **bundle})


# ── Visibility ────────────────────────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/visibility", methods=["GET"])
def get_visibility(load_id):
    vis = services.get_visibility(load_id)
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
    result = services.resolve_exception(
        exception_id=exception_id,
        resolution_note=data.get("resolution_note", ""),
    )
    if not result:
        return jsonify({"error": f"Exception {exception_id} not found"}), 404
    return jsonify({"status": "ok", "exception": result})


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
    data = request.get_json(silent=True) or {}
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
    return jsonify({"status": "ok", "retention": ret}), 201


@dispatch_bp.route("/retention", methods=["GET"])
def list_retentions():
    items = services.list_retentions()
    return jsonify({"status": "ok", "archives": items, "count": len(items)})


@dispatch_bp.route("/retention/<load_id>", methods=["GET"])
def get_retention(load_id):
    ret = services.get_retention(load_id)
    if not ret:
        return jsonify({"error": f"No retention record for {load_id}"}), 404
    return jsonify({"status": "ok", "retention": ret})


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

    return render_template(
        "dispatch_decision.html",
        success=True,
        load_id=load_id,
        action_label=label,
        load=load,
    )
