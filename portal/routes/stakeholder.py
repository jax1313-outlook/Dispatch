"""External stakeholder portal -- read-only. Token links, and the Customer Portal.

The Customer Portal (/portal/login, /portal/mission) opens the Mission
Visibility View of one mission with its Mission Visibility Key, the customer
load number; see the section below the blueprint. Everything that follows describes the token links, which keep
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

# ── Customer Portal: the Mission Visibility Key ──────────────────────────────
#
# Doctrine: DISPATCH_OPERATIONAL_INTELLIGENCE_PLAYBOOK_v1.md, Section 4A (Mike
# Zachary, 2026-09-13). "The customer is getting a curated window into their
# mission." The Customer Load Number is a Mission Visibility Key -- not a
# username, account, company login or organizational credential -- and it is
# mission-scoped: it opens the Mission Visibility View of the one mission whose
# Mission Record carries that load number, and nothing else. The Library PIN
# Service says whether the key is good; the Mission Record says which mission.
# The token links above keep working for recipients who have no key.


def _normalize_key(value) -> str:
    """How a key is compared: spaces removed, letters upper-cased (as the Library does)."""
    return "".join(str(value or "").split()).upper()


def _mission_for_key(key: str, customer: str | None) -> dict | None:
    """The one committed Mission Record this key opens, or None.

    The record's load number must equal the key, and its customer must be the
    customer the Library holds the key for. Returns the record id and, when
    Dispatch has opened the load, its load_id.
    """
    from dispatch import commitment
    from portal import brief
    from portal.models import sandbox

    wanted = _normalize_key(key)
    for record_id, record in sandbox.get_all().items():
        record = dict(record, id=record.get("id") or record_id)
        if (not wanted or _normalize_key(brief._record_value(record, "load_number")) != wanted
                or not commitment.is_committed(record) or record.get("data_origin") == "SIMULATED"
                or pin_service.customer_key(brief._record_value(record, "customer")) != pin_service.customer_key(customer)):
            continue
        load_id = next((candidate for candidate in (record.get("engine_load_id"), record["id"])
                        if candidate and services.get_load(candidate)), None)
        return {"record_id": record["id"], "load_id": load_id}
    return None


def _session_mission() -> dict | None:
    return session.get("mission")


def _may_view(load_id: str, token: str) -> bool:
    if token and notifications.verify_stakeholder_token(load_id, token):
        return True
    mission = _session_mission()
    return bool(mission and mission.get("load_id") and mission["load_id"] == load_id)


@stakeholder_bp.route("/login", methods=["GET", "POST"])
def customer_login():
    if not pin_service.configured():
        return render_template("customer_login.html",
                               error="Customer sign-in is not set up on this server yet."), 503
    if request.method == "GET":
        return render_template("customer_login.html", error=None)
    key = request.form.get("pin", "")
    try:
        answer = pin_service.validate(pin_service.CUSTOMER, key, request.remote_addr)
    except pin_service.PinServiceUnavailable as exc:
        return render_template("customer_login.html", error=str(exc)), 503
    if not answer:
        return render_template("customer_login.html", error="Denied."), 401
    mission = _mission_for_key(key, answer.get("subject_ref") or answer.get("display_name"))
    session.clear()
    session["mission"] = mission or {"record_id": None, "load_id": None}
    session["customer_name"] = answer["display_name"]
    session["role"] = answer["role"]
    return redirect(url_for("stakeholder.customer_mission"))


@stakeholder_bp.route("/logout", methods=["POST"])
def customer_logout():
    session.clear()
    return redirect(url_for("stakeholder.customer_login"))


@stakeholder_bp.route("/loads")
def customer_loads():
    """Kept for links already sent: the key's mission, not a list."""
    return redirect(url_for("stakeholder.customer_mission"))


@stakeholder_bp.route("/mission")
def customer_mission():
    """The Mission Visibility View of the key's one mission."""
    from portal import brief
    from portal.models import sandbox

    mission = _session_mission()
    if not mission:
        return redirect(url_for("stakeholder.customer_login"))
    if mission.get("load_id"):
        view = services.build_stakeholder_view(mission["load_id"])
        if view:
            return render_template("stakeholder_view.html", error=None, signed_in=True, **view)
    record = sandbox.get(mission["record_id"]) if mission.get("record_id") else None
    summary = None
    if record:
        summary = {
            "load_number": brief._record_value(record, "load_number"),
            "status": "committed",
            "pickup_location": brief._record_value(record, "pickup_location"),
            "pickup_window": brief._record_value(record, "pickup_window"),
            "delivery_location": brief._record_value(record, "delivery_location"),
            "delivery_window": brief._record_value(record, "delivery_window"),
        }
    return render_template("customer_mission.html", customer_name=session.get("customer_name"), mission=summary)


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
