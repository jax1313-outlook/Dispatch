"""Dispatch Data Engine API routes.

REST endpoints for loads, milestones, evidence, exceptions,
POD packages, and retention archive.
"""

from __future__ import annotations

import csv
import io

from flask import Blueprint, Response, jsonify, render_template, request

from dispatch import notifications, services
from dispatch.models import (
    DRIVER_STATUSES,
    EQUIPMENT_STATUSES,
    EQUIPMENT_TYPES,
    EVIDENCE_TYPES,
    EXCEPTION_STATUSES,
    EXCEPTION_TYPES,
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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


@dispatch_bp.route("/milestones/<milestone_id>", methods=["PATCH"])
def update_milestone(milestone_id):
    from dispatch.models import VALIDATION_STATUSES
    data = request.get_json(silent=True) or {}
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


@dispatch_bp.route("/evidence/<evidence_id>", methods=["PATCH"])
def update_evidence(evidence_id):
    data = request.get_json(silent=True) or {}
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


@dispatch_bp.route("/exceptions/<exception_id>", methods=["PATCH"])
def update_exception(exception_id):
    data = request.get_json(silent=True) or {}
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


# ── Rate Confirmation ────────────────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/rate", methods=["GET"])
def get_rate(load_id):
    rc = services.get_rate_confirmation(load_id)
    if not rc:
        return jsonify({"error": f"No rate confirmation for {load_id}"}), 404
    return jsonify({"status": "ok", "rate_confirmation": rc})


@dispatch_bp.route("/loads/<load_id>/rate", methods=["POST"])
def confirm_rate(load_id):
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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


# ── Settlements ──────────────────────────────────────────────────────

@dispatch_bp.route("/loads/<load_id>/settlement", methods=["GET"])
def get_settlement(load_id):
    stl = services.get_settlement(load_id)
    if not stl:
        return jsonify({"error": f"No settlement for {load_id}"}), 404
    return jsonify({"status": "ok", "settlement": stl})


@dispatch_bp.route("/loads/<load_id>/settlement", methods=["POST"])
def create_settlement(load_id):
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(silent=True) or {}
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
    data = request.get_json(force=True)
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
    data = request.get_json(force=True)
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
    "load_id", "customer", "broker_shipper", "status",
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
    data = request.get_json(force=True)
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
    "pickup_datetime", "delivery_datetime", "equipment", "driver", "notes",
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
    data = request.get_json(force=True)
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
    data = request.get_json(force=True)
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
