"""Driver Portal -- Phone Number + PIN authentication for the Driver role
(portal/models/driver_pin_registry.py), separate from both the internal
Authority DISPATCH_PIN login (portal/models/identity.py, session["user_id"])
and the external, token-secured stakeholder portal (portal/routes/
stakeholder.py).

Driver-First Cockpit (Missions 1-4):
  1. Dual-Layer Cockpit (70 MPH Glanceable Active Mission + Rolling 7-Day Horizon)
  2. 1-Tap Milestone Progression Controls, Native Dialers & Map Navigation
  3. Camera POD / Evidence Capture & 1-Tap Dock Detention Timers
  4. Vision Fuel Intake Scan & Driver Pay Settlement Glance
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from cin_lite.agents import receipt_vision
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
    driver_id = session.get("driver_id")
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))

    driver = dispatch_svc.get_driver(driver_id)
    if not driver:
        # Driver record was deleted after the session was established -- fail closed.
        session.clear()
        return redirect(url_for("driver_portal.driver_login"))

    all_loads = dispatch_svc.list_loads(driver_id=driver_id)
    active_loads = [l for l in all_loads if l["status"] not in _ACTIVE_LOAD_STATUSES_EXCLUDED]

    load_cards = []
    broker_contacts_seen: dict[str, dict] = {}
    for load in active_loads:
        comi = dispatch_svc.get_comi_status(load["load_id"])
        contacts = dispatch_svc.get_load_contacts(load["load_id"])
        broker_contact = contacts["broker_contact"]
        if broker_contact and broker_contact.get("broker_id") not in broker_contacts_seen:
            broker_contacts_seen[broker_contact["broker_id"]] = broker_contact
        load_cards.append({
            "load": load,
            "comi_status": comi["status"] if comi["exists"] else "No communications drafted yet",
            "route_risk": route_risk_model.get_route_risk(load["load_id"]),
            "broker_contact": broker_contact,
            "mission_visibility": dispatch_svc.get_mission_visibility(load["load_id"]),
            "publisher_status": dispatch_svc.get_publisher_status(load["load_id"]),
        })

    # Mission 1: Dual-Layer Cockpit - Primary Active Load vs Rolling Week Horizon
    active_card = load_cards[0] if load_cards else None

    # Pay Summary for Mission 4 Driver Settlement Glance
    pay_summary = dispatch_svc.get_driver_pay_summary(driver_id)

    return render_template(
        "driver_home.html",
        driver=driver,
        load_cards=load_cards,
        active_card=active_card,
        pay_summary=pay_summary,
        dispatch_contact_email=dispatch_svc.reviewer_contact_email(),
        broker_contacts=list(broker_contacts_seen.values()),
    )


def _verify_driver_load(load_id: str, driver_id: str):
    """Verify that the given load exists and is assigned to the authenticated driver (IDOR protection)."""
    load = dispatch_svc.get_load(load_id)
    if not load or load.get("driver_id") != driver_id:
        return None
    return load


# --- Mission 2: 1-Tap Milestone Progression Controls ---
@driver_portal_bp.route("/loads/<load_id>/milestone", methods=["POST"])
def driver_step_milestone(load_id: str):
    driver_id = session.get("driver_id")
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))

    load = _verify_driver_load(load_id, driver_id)
    if not load:
        return redirect(url_for("driver_portal.driver_home"))

    milestone_event = request.form.get("milestone_event", "").strip()
    if milestone_event:
        try:
            dispatch_svc.add_milestone(
                load_id,
                event_type=milestone_event,
                source="driver",
                entered_by=f"driver:{driver_id}",
            )
        except Exception:
            pass  # Fail gracefully if gate refuses transition

    return redirect(url_for("driver_portal.driver_home"))


# --- Mission 3: POD Evidence Photo Upload & Dock Exception Timers ---
@driver_portal_bp.route("/loads/<load_id>/pod", methods=["POST"])
def driver_upload_pod(load_id: str):
    driver_id = session.get("driver_id")
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))

    load = _verify_driver_load(load_id, driver_id)
    if not load:
        return redirect(url_for("driver_portal.driver_home"))

    pod_file = request.files.get("pod_file")
    if pod_file and pod_file.filename:
        file_bytes = pod_file.read()
        if file_bytes:
            dispatch_svc.attach_evidence(
                load_id,
                evidence_type="pod",
                description=f"Signed POD Uploaded by Driver ({driver_id})",
                file_data=file_bytes,
                original_filename=pod_file.filename,
            )

    return redirect(url_for("driver_portal.driver_home"))


@driver_portal_bp.route("/loads/<load_id>/exception", methods=["POST"])
def driver_log_exception(load_id: str):
    driver_id = session.get("driver_id")
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))

    load = _verify_driver_load(load_id, driver_id)
    if not load:
        return redirect(url_for("driver_portal.driver_home"))

    exception_type = request.form.get("exception_type", "detention").strip()
    description = request.form.get("description", f"Dock exception logged by driver ({driver_id})").strip()

    try:
        dispatch_svc.open_exception(
            load_id,
            exception_type=exception_type,
            severity="medium",
            description=description,
        )
    except Exception:
        pass

    return redirect(url_for("driver_portal.driver_home"))


# --- Mission 4: Vision Fuel Intake & Driver Pay Settlement ---
@driver_portal_bp.route("/fuel-receipt", methods=["POST"])
def driver_fuel_receipt():
    driver_id = session.get("driver_id")
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))

    fuel_file = request.files.get("fuel_file")
    gallons_val = request.form.get("gallons")
    amount_val = request.form.get("amount")
    state_val = request.form.get("state", "FL").upper()

    gallons = float(gallons_val) if gallons_val else 0.0
    amount = float(amount_val) if amount_val else 0.0

    if fuel_file and fuel_file.filename:
        file_bytes = fuel_file.read()
        if file_bytes:
            extracted = receipt_vision.extract_fuel_receipt(file_bytes, fuel_file.filename)
            if extracted.get("available"):
                gallons = float(extracted.get("gallons") or gallons)
                amount = float(extracted.get("amount") or amount)
                jur = receipt_vision.derive_jurisdiction(extracted.get("vendor_address"))
                if jur:
                    state_val = jur

    if gallons > 0 or amount > 0:
        dispatch_svc.add_ifta_fuel_purchase(
            jurisdiction=state_val,
            gallons=gallons,
            amount=amount,
            vendor="Truck Stop (Driver Scanner)",
            notes=f"driver:{driver_id}",
        )

    return redirect(url_for("driver_portal.driver_home"))
