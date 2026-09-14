"""External stakeholder portal -- read-only. Token links, and the Customer Portal.

The Customer Portal (/portal/login, /portal/loads) signs a customer in through
the Library PIN Service with one of their load numbers; see the section below
the blueprint. Everything that follows describes the token links, which keep
working for a recipient with no PIN.

Broker/shipper/customer view of a single load (D11: Manufacturer -> Shipper
-> Broker -> Level 1 Transport is a genuine disclosure chain, not a set of
synonyms -- see dispatch/services.py::build_stakeholder_view() for exactly
what is and is not shared with these parties).

    GET /portal/loads/<load_id>?token=<hmac_token>

The token is produced by dispatch.notifications.make_stakeholder_token() and
must be generated from inside the (PIN-gated) portal -- see the "Stakeholder
Link" control on the load detail page. This route itself carries no session
requirement; it is exempted from the DISPATCH_PIN gate in portal/app.py the
same way the existing decision-email action links are, because it must work
for a recipient with no portal login of their own.

Distinct from the INTERNAL, PIN-gated read-only load view added for Load
Search (portal/routes/pages.py::search_load_detail, `/search/loads/<id>`,
portal/templates/load_readonly_detail.html) -- that page is for Dispatch's
own staff to look a load up without risk of editing it; this one is for an
external party with no Dispatch login at all.

    GET /portal/loads/<load_id>/evidence/<evidence_id>?token=<hmac_token>

Token-scoped evidence file download -- the fast-follow flagged (but
deliberately not built) in build_stakeholder_view()'s docstring. Same
verify_stakeholder_token() check as the view route above, PLUS a mandatory
IDOR check: the evidence record's own load_id must equal the load_id in the
URL. A stakeholder token is scoped to exactly one load; without this check
anyone holding a valid token for load A could enumerate evidence_ids and
pull evidence that belongs to a completely different load B. Any failure
of that check -- evidence not found, or found but scoped to a different
load -- returns a flat 404, never a 403, so the response never confirms or
denies whether a given evidence_id exists (just under a different load).
"""

from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request, send_file, session, url_for

from dispatch import notifications, services, store
from portal.models import pin_service

stakeholder_bp = Blueprint("stakeholder", __name__)

# ── Customer Portal -> Library PIN Service ───────────────────────────────────
#
# A customer signs in with one of their load numbers (portal/models/
# pin_service.py). The answer names the customer, and the session sees every
# load recorded for that customer and nothing else: security within one
# customer does not matter, but one customer seeing another's work does
# (Mike Zachary, 2026-09-13). A load belongs to the customer when its
# `customer` field matches the identity's subject_ref, or its display name
# when no subject_ref was given -- ignoring case and spacing, never partially.
# The token links above keep working for recipients who have no PIN.


def _customer() -> str:
    return session.get("customer") or ""


def _belongs_to_session_customer(load: dict | None) -> bool:
    customer = _customer()
    return bool(customer and load and pin_service.customer_key(load.get("customer")) == customer)


def _may_view(load_id: str, token: str) -> bool:
    if token and notifications.verify_stakeholder_token(load_id, token):
        return True
    return _belongs_to_session_customer(services.get_load(load_id)) if _customer() else False


@stakeholder_bp.route("/login", methods=["GET", "POST"])
def customer_login():
    if not pin_service.configured():
        return render_template("customer_login.html",
                               error="Customer sign-in is not set up on this server yet."), 503
    if request.method == "GET":
        return render_template("customer_login.html", error=None)
    try:
        answer = pin_service.validate(pin_service.CUSTOMER, request.form.get("pin", ""), request.remote_addr)
    except pin_service.PinServiceUnavailable as exc:
        return render_template("customer_login.html", error=str(exc)), 503
    customer = pin_service.customer_key((answer or {}).get("subject_ref") or (answer or {}).get("display_name"))
    if not answer or not customer:
        return render_template("customer_login.html", error="Denied."), 401
    session.clear()
    session["customer"] = customer
    session["customer_name"] = answer["display_name"]
    session["role"] = answer["role"]
    return redirect(url_for("stakeholder.customer_loads"))


@stakeholder_bp.route("/logout", methods=["POST"])
def customer_logout():
    session.clear()
    return redirect(url_for("stakeholder.customer_login"))


@stakeholder_bp.route("/loads")
def customer_loads():
    if not _customer():
        return redirect(url_for("stakeholder.customer_login"))
    loads = [dict(load, linked=True) for load in services.list_loads(include_rehearsal=False)
             if _belongs_to_session_customer(load)]
    return render_template("customer_loads.html", customer_name=session.get("customer_name"),
                           loads=loads + _committed_missions(exclude={l["load_id"] for l in loads}))


def _committed_missions(exclude: set) -> list[dict]:
    """Committed loads for this customer that Dispatch has not opened as a load yet.

    COMMIT is when the customer is given the portal, which can be before the
    load exists in the dispatch tables. Only the fields a customer is shown
    anywhere else are carried: load number, status, pickup and delivery.
    """
    from dispatch import commitment
    from portal import brief
    from portal.models import sandbox

    rows = []
    for record_id, record in sandbox.get_all().items():
        record = dict(record, id=record.get("id") or record_id)
        if (not commitment.is_committed(record) or record.get("data_origin") == "SIMULATED"
                or pin_service.customer_key(brief._record_value(record, "customer")) != _customer()
                or {record["id"], record.get("engine_load_id")} & exclude):
            continue
        rows.append({
            "load_id": brief._record_value(record, "load_number") or record["id"],
            "status": "committed",
            "pickup_location": brief._record_value(record, "pickup_location"),
            "pickup_datetime": brief._record_value(record, "pickup_window"),
            "delivery_location": brief._record_value(record, "delivery_location"),
            "delivery_datetime": brief._record_value(record, "delivery_window"),
            "linked": False,
        })
    return rows


@stakeholder_bp.route("/loads/<load_id>")
def stakeholder_view(load_id: str):
    token = request.args.get("token", "")
    as_json = request.args.get("format") == "json"

    if not _may_view(load_id, token):
        error = "Invalid or expired link."
        if as_json:
            return jsonify({"error": error}), 403
        return render_template(
            "stakeholder_view.html",
            error=error,
            load_id=load_id,
        ), 403

    view = services.build_stakeholder_view(load_id)
    if not view:
        error = "Load not found."
        if as_json:
            return jsonify({"error": error}), 404
        return render_template(
            "stakeholder_view.html",
            error=error,
            load_id=load_id,
        ), 404

    if as_json:
        return jsonify(view)
    return render_template("stakeholder_view.html", error=None, **view)


@stakeholder_bp.route("/loads/<load_id>/evidence/<evidence_id>")
def stakeholder_evidence_download(load_id: str, evidence_id: str):
    token = request.args.get("token", "")

    if not _may_view(load_id, token):
        return jsonify({"error": "Invalid or expired link."}), 403

    # IDOR check: an evidence_id that exists but belongs to a different
    # load must 404 exactly the same as an evidence_id that doesn't exist
    # at all -- never reveal which case it is.
    evidence = store.get_evidence(evidence_id)
    if not evidence or evidence.get("load_id") != load_id:
        return jsonify({"error": "Evidence not found."}), 404

    result = services.get_evidence_file(evidence_id)
    if not result:
        return jsonify({"error": "Evidence not found."}), 404

    file_path, download_name = result
    return send_file(file_path, download_name=download_name, as_attachment=True)
