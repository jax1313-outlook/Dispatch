"""Driver Portal -- Phone Number + PIN authentication for the Driver role
(portal/models/driver_pin_registry.py), separate from both the internal
Authority DISPATCH_PIN login (portal/models/identity.py, session["user_id"])
and the external, token-secured stakeholder portal (portal/routes/
stakeholder.py). A driver session is its own namespace, session["driver_id"],
so a driver's session can never reach an Authority-only route (nothing
outside this blueprint checks session["driver_id"]) and an Authority's
session can never satisfy this blueprint's own gate (nothing here checks
session["user_id"]).

Deliberately small, per the "no enterprise identity management, no complex
role frameworks" instruction: one dashboard, three lookups (COMI status,
Route Risk, dispatch/broker contact info), plus the two auth actions a
driver actually needs self-service (log in, recover a forgotten PIN). No
driver-facing editing of loads, email drafts, or anything else -- Driver-
First Doctrine's cognitive-load-reduction principle means this surface
answers "what do I need to know right now," not "here is an admin panel."

Issuing, resetting, deactivating, or deleting a PIN Card is NOT done here
-- that's Mike-only, via the Library page and its API endpoints
(portal/routes/api.py), behind the normal Authority PIN gate. Mike remains
final authority: nothing in this blueprint can create Driver Portal access,
only use it.
"""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, session, url_for

from dispatch import route_risk as route_risk_model
from dispatch import services as dispatch_svc
from portal.models import driver_pin_registry as pin_registry

driver_portal_bp = Blueprint("driver_portal", __name__)

_ACTIVE_LOAD_STATUSES_EXCLUDED = ("archived", "cancelled", "completed")


@driver_portal_bp.before_request
def _require_driver_login():
    if request.endpoint in ("driver_portal.driver_login", "driver_portal.driver_forgot_pin"):
        return None
    if not session.get("driver_id"):
        return redirect(url_for("driver_portal.driver_login"))
    return None


@driver_portal_bp.route("/login", methods=["GET", "POST"])
def driver_login():
    if request.method == "GET":
        return render_template("driver_login.html", error=None)

    phone = request.form.get("phone", "")
    pin = request.form.get("pin", "")
    record = pin_registry.verify_login(phone, pin)
    if not record:
        return render_template(
            "driver_login.html",
            error="Incorrect phone number or PIN, or the account is temporarily locked.",
        ), 401

    session.clear()
    session["driver_id"] = record["driver_id"]
    return redirect(url_for("driver_portal.driver_home"))


@driver_portal_bp.route("/logout", methods=["POST"])
def driver_logout():
    session.clear()
    return redirect(url_for("driver_portal.driver_login"))


@driver_portal_bp.route("/forgot-pin", methods=["GET", "POST"])
def driver_forgot_pin():
    if request.method == "GET":
        return render_template("driver_forgot_pin.html", error=None, success=False)

    phone = request.form.get("phone", "")
    recovery_word = request.form.get("recovery_word", "")
    new_pin = request.form.get("new_pin", "")

    try:
        record = pin_registry.reset_pin_with_recovery_word(phone, recovery_word, new_pin)
    except pin_registry.DriverPinError as exc:
        return render_template("driver_forgot_pin.html", error=str(exc), success=False), 400

    if not record:
        return render_template(
            "driver_forgot_pin.html",
            error="Phone number or recovery word not recognized, or the account is inactive.",
            success=False,
        ), 401

    return render_template("driver_forgot_pin.html", error=None, success=True)


@driver_portal_bp.route("/home")
def driver_home():
    driver_id = session["driver_id"]
    driver = dispatch_svc.get_driver(driver_id)
    if not driver:
        # Driver record was deleted after the session was established -- fail closed.
        session.clear()
        return redirect(url_for("driver_portal.driver_login"))

    all_loads = dispatch_svc.list_loads(driver_id=driver_id)
    active_loads = [l for l in all_loads if l["status"] not in _ACTIVE_LOAD_STATUSES_EXCLUDED]

    load_cards = []
    for load in active_loads:
        comi = dispatch_svc.get_comi_status(load["load_id"])
        broker_contact = None
        if load.get("broker_shipper"):
            matches = dispatch_svc.list_broker_contacts(search=load["broker_shipper"])
            broker_contact = matches[0] if matches else None
        load_cards.append({
            "load": load,
            "comi_status": comi["status"] if comi["exists"] else "No communications drafted yet",
            "route_risk": route_risk_model.get_route_risk(load["load_id"]),
            "broker_contact": broker_contact,
        })

    return render_template(
        "driver_home.html",
        driver=driver,
        load_cards=load_cards,
        dispatch_contact_email=dispatch_svc.reviewer_contact_email(),
    )
