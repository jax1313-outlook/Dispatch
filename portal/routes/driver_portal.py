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

from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from dispatch.connectors import receipt_vision
from dispatch import route_risk as route_risk_model
from dispatch import services as dispatch_svc
from dispatch.models import ALLOWED_EXTENSIONS, IFTA_JURISDICTIONS, MAX_FILE_SIZE
from portal.models import driver_pin_registry as pin_registry
from portal.models import pin_service

driver_portal_bp = Blueprint("driver_portal", __name__)


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

_ACTIVE_LOAD_STATUSES_EXCLUDED = ("archived", "cancelled", "completed")


#: Who a Driver-portal action is recorded against when the portal was opened
#: with a driver PIN, which names no driver (see _driver_login_with_pin_service).
OPEN_DRIVER = "driver-pin"


def _session_driver_id() -> str | None:
    """The signed-in driver: a driver_id, OPEN_DRIVER for a driver-PIN session, or None."""
    return session.get("driver_id") or (OPEN_DRIVER if session.get("driver_open") else None)


@driver_portal_bp.before_request
def _require_driver_login():
    if request.endpoint in ("driver_portal.driver_login", "driver_portal.driver_forgot_pin",
                            "driver_portal.driver_choose_pin"):
        return None
    if not _session_driver_id():
        return redirect(url_for("driver_portal.driver_login"))
    return None


@driver_portal_bp.route("/login", methods=["GET", "POST"])
def driver_login():
    if request.method == "GET":
        return render_template("driver_login.html", error=None, pin_only=pin_service.configured())

    if pin_service.configured():
        return _driver_login_with_pin_service()

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


def _driver_login_with_pin_service():
    """Driver Portal -> Library PIN Service (portal/models/pin_service.py).

    Mike Zachary, 2026-09-13: "it does not matter who is assigned what. as long
    as those 4 characters are entered access is given." A driver PIN names no
    driver, so the session is a driver-PIN session (driver_open): the cockpit
    shows the fleet's active loads rather than one driver's.
    """
    try:
        answer = pin_service.validate(pin_service.DRIVER, request.form.get("pin", ""), request.remote_addr)
    except pin_service.PinServiceUnavailable as exc:
        return render_template("driver_login.html", error=str(exc), pin_only=True), 503
    if not answer:
        return render_template("driver_login.html", error="Denied.", pin_only=True), 401
    return _open_driver_portal()


def _open_driver_portal():
    session.clear()
    session["driver_open"] = True
    session["role"] = "Driver"
    return redirect(url_for("driver_portal.driver_home"))


@driver_portal_bp.route("/choose-pin", methods=["GET", "POST"])
def driver_choose_pin():
    """The PIN window. Mike Zachary, 2026-09-13, in his words:

        1) the PIN window opens 2) Driver enters 4 characters 3) the system
        ask them to repeat the entry. 4) The saved the entry ... No other
        information or verification is needed.
    """
    if not pin_service.configured():
        return redirect(url_for("driver_portal.driver_login"))

    def window(error=None, status=200):
        return render_template("driver_choose_pin.html", error=error,
                               pin_length=pin_service.DRIVER_PIN_LENGTH), status

    if request.method == "GET":
        return window()
    pin, again = request.form.get("pin", ""), request.form.get("pin_again", "")
    if "".join(pin.split()).upper() != "".join(again.split()).upper():
        return window("The two entries are not the same. Try again.", 400)
    try:
        pin_service.add_driver_pin(pin)
    except pin_service.PinRefused as exc:
        return window(str(exc)[:1].upper() + str(exc)[1:] + ".", 400)
    except pin_service.PinServiceUnavailable as exc:
        return window(str(exc), 503)
    return _open_driver_portal()


@driver_portal_bp.route("/logout", methods=["POST"])
def driver_logout():
    session.clear()
    return redirect(url_for("driver_portal.driver_login"))


@driver_portal_bp.route("/forgot-pin", methods=["GET", "POST"])
def driver_forgot_pin():
    if pin_service.configured():
        # Driver PINs live in the Library now; a new one is entered at the PIN window.
        return render_template(
            "driver_forgot_pin.html",
            error="Use Set up a PIN on the sign-in page to enter a new one.",
            success=False,
        ), (200 if request.method == "GET" else 400)

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
    driver_id = _session_driver_id()
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))

    if driver_id == OPEN_DRIVER:
        # A driver PIN names no driver: the fleet's active loads, no one driver's pay.
        driver = {"name": "Driver", "driver_id": None}
    else:
        driver = dispatch_svc.get_driver(driver_id)
    if not driver:
        # Driver record was deleted after the session was established -- fail closed.
        session.clear()
        return redirect(url_for("driver_portal.driver_login"))

    all_loads = dispatch_svc.list_loads(**({} if driver_id == OPEN_DRIVER else {"driver_id": driver_id}))
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
    pay_summary = None if driver_id == OPEN_DRIVER else dispatch_svc.get_driver_pay_summary(driver_id)

    # Truck identity for the fuel scanner. Required by the fuel-receipt
    # ownership chain, and deliberately NOT dependent on there being an active
    # load -- an owner/operator fuels between loads, and the equipment schema
    # has no driver assignment to derive it from, so the driver names it. The
    # active mission's truck is pre-selected when there is one.
    trucks = dispatch_svc.list_equipment(status="active")
    default_equipment_id = (active_card or {}).get("load", {}).get("equipment_id", "")

    return render_template(
        "driver_home.html",
        driver=driver,
        load_cards=load_cards,
        active_card=active_card,
        pay_summary=pay_summary,
        trucks=trucks,
        default_equipment_id=default_equipment_id,
        dispatch_contact_email=dispatch_svc.reviewer_contact_email(),
        broker_contacts=list(broker_contacts_seen.values()),
    )


def _verify_driver_load(load_id: str, driver_id: str):
    """Verify that the given load exists and is assigned to the authenticated driver (IDOR protection).

    A driver-PIN session names no driver, so any active load is its own.
    """
    load = dispatch_svc.get_load(load_id)
    if not load:
        return None
    if driver_id == OPEN_DRIVER:
        return load if load.get("status") not in _ACTIVE_LOAD_STATUSES_EXCLUDED else None
    if load.get("driver_id") != driver_id:
        return None
    return load


def _home():
    return redirect(url_for("driver_portal.driver_home"))


def _tell_driver(message: str, category: str = "error"):
    """Say something back, then return to the cockpit.

    Every write control on this surface is a single tap taken by someone who
    may be standing at a dock or sitting in a cab. A tap that produces a
    silent redirect is indistinguishable from a tap that worked -- which is
    the 70 MPH test failing, not passing. Nothing here is allowed to fail
    quietly: every refusal, every rejected file and every missing field comes
    back as a message the driver can read on the page they land on.
    """
    flash(message, category)
    return _home()


# --- Mission 2: 1-Tap Milestone Progression Controls ---
@driver_portal_bp.route("/loads/<load_id>/milestone", methods=["POST"])
def driver_step_milestone(load_id: str):
    driver_id = _session_driver_id()
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))

    load = _verify_driver_load(load_id, driver_id)
    if not load:
        return redirect(url_for("driver_portal.driver_home"))

    milestone_event = request.form.get("milestone_event", "").strip()
    if not milestone_event:
        return _tell_driver("No milestone was selected.")

    # add_milestone() does NOT raise when the transition gate refuses -- it
    # records the milestone, leaves the status alone, and hands the refusal
    # back on the returned dict under "status_transition_refused" (M1; see
    # dispatch/services.py::add_milestone and the same read in
    # portal/routes/dispatch_api.py::add_milestone, which answers 409).
    # The original driver build wrapped this call in `except Exception: pass`
    # and then discarded the return value, so a refused step looked exactly
    # like a successful one from the cab. ValueError here means the load
    # vanished between the ownership check and the write, not a refusal.
    try:
        result = dispatch_svc.add_milestone(
            load_id,
            event_type=milestone_event,
            source="driver",
            entered_by=f"driver:{driver_id}",
        )
    except ValueError as exc:
        return _tell_driver(str(exc))

    refusal = result.get("status_transition_refused")
    if refusal:
        return _tell_driver(
            f"Recorded, but the load stays in "
            f"{refusal['from_status'].replace('_', ' ')}: {refusal['reason']}",
            "warning",
        )

    return _tell_driver(
        f"{milestone_event.replace('_', ' ').title()} recorded.", "success"
    )


# --- Mission 3: POD Evidence Photo Upload & Dock Exception Timers ---
@driver_portal_bp.route("/loads/<load_id>/pod", methods=["POST"])
def driver_upload_pod(load_id: str):
    driver_id = _session_driver_id()
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))

    load = _verify_driver_load(load_id, driver_id)
    if not load:
        return redirect(url_for("driver_portal.driver_home"))

    pod_file = request.files.get("pod_file")
    if not pod_file or not pod_file.filename:
        return _tell_driver("No photo or file was attached.")

    file_bytes = pod_file.read()
    if not file_bytes:
        return _tell_driver("That file came through empty. Try the photo again.")

    # attach_evidence() refuses a disallowed extension or an oversize file by
    # raising ValueError (dispatch/services.py::_save_upload, ALLOWED_EXTENSIONS
    # and MAX_FILE_SIZE). Unhandled, that is a 500 on a driver's phone with no
    # explanation -- so the message is surfaced instead.
    try:
        dispatch_svc.attach_evidence(
            load_id,
            evidence_type="pod",
            description=f"Signed POD Uploaded by Driver ({driver_id})",
            file_data=file_bytes,
            original_filename=pod_file.filename,
        )
    except ValueError as exc:
        return _tell_driver(str(exc))

    return _tell_driver("POD uploaded.", "success")


@driver_portal_bp.route("/loads/<load_id>/mission-photos", methods=["POST"])
def driver_upload_mission_photos(load_id: str):
    """Load securement and freight condition photos -- customer-facing Mission Visibility
    artifacts (playbook Section 4A; Mike Zachary, 2026-09-13): "A customer cannot see load
    securement. A customer can see evidence of load securement. The evidence is the value."

    The photos join the load's evidence (and so the Mission Visibility View and the final
    mission package), the Mission Record history, and a Customer Alert that travels Joe ->
    Publisher -> COMI -> Email Helper. The M6A check itself stays an internal activity.
    """
    from dispatch.models import CUSTOMER_FACING_PHOTO_TYPES
    from portal import portal_access
    from portal.routes.joe_portal import _mail_connector

    driver_id = _session_driver_id()
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))
    load = _verify_driver_load(load_id, driver_id)
    if not load:
        return redirect(url_for("driver_portal.driver_home"))

    photo_type = request.form.get("photo_type", "securement_photo").strip()
    if photo_type not in CUSTOMER_FACING_PHOTO_TYPES:
        return _tell_driver("Pick securement or freight condition.")
    uploads = [f for f in request.files.getlist("photos") if f and f.filename]
    if not uploads:
        return _tell_driver("No photo was attached.")

    label = CUSTOMER_FACING_PHOTO_TYPES[photo_type]
    added = []
    for upload in uploads:
        data = upload.read()
        if not data:
            return _tell_driver("That photo came through empty. Try again.")
        try:
            evidence = dispatch_svc.attach_evidence(
                load_id, evidence_type=photo_type, description=label, file_data=data,
                original_filename=upload.filename, uploaded_by=f"driver:{driver_id}")
        except ValueError as exc:
            return _tell_driver(str(exc))
        added.append({"evidence_id": evidence["evidence_id"], "evidence_type": photo_type, "label": label})

    alert = portal_access.alert_mission_evidence(load_id, added, mail_connector=_mail_connector,
                                                 url_root=request.url_root)
    told = "The customer was sent a Customer Alert." if alert["sent"] else "No Customer Alert went out; dispatch can see why."
    return _tell_driver(f"{len(added)} {label.lower()}{'s' if len(added) != 1 else ''} added to Mission Visibility. {told}",
                        "success")


@driver_portal_bp.route("/loads/<load_id>/exception", methods=["POST"])
def driver_log_exception(load_id: str):
    driver_id = _session_driver_id()
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
    except ValueError as exc:
        return _tell_driver(str(exc))

    return _tell_driver(
        f"{exception_type.replace('_', ' ').title()} logged. Dispatch can see it.",
        "success",
    )


# --- Mission 4: Vision Fuel Intake & Driver Pay Settlement ---
def _validate_receipt_file(upload):
    """Pre-flight the receipt against the same rules attach_ifta_fuel_evidence()
    will apply, before any record is created.

    The ownership chain requires receipt evidence, so a purchase must never
    exist without its receipt. Attaching is a two-step service flow (create the
    purchase, then attach) -- validating here means the common rejections
    (wrong type, too large, empty) are refused before step one, instead of
    leaving a purchase behind that violates the chain.
    """
    if not upload or not upload.filename:
        return None, "A photo of the receipt is required. Fuel is never logged without one."
    data = upload.read()
    if not data:
        return None, "That file came through empty. Try the photo again."
    if len(data) > MAX_FILE_SIZE:
        return None, f"That file is over the {MAX_FILE_SIZE // (1024 * 1024)} MB limit."
    ext = Path(upload.filename).suffix.lstrip(".").lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None, f"File type not allowed: .{ext}"
    return data, None


@driver_portal_bp.route("/fuel-receipt", methods=["POST"])
def driver_fuel_receipt():
    """Log a fuel purchase into the IFTA ledger from a receipt photo.

    A receipt is logged with its truck, timestamp, jurisdiction and receipt
    evidence. The driver is recorded when the session names one; a driver-PIN
    session names none and asks for none. No Mike Zachary ruling requires
    driver identity on a fuel receipt -- an earlier docstring here quoted one,
    and on 2026-09-13 he said he never made it (DECISION_LOG.md). The Driver
    Portal is a workspace entry control, not identity verification.

    LOAD ASSOCIATION IS OPTIONAL, and that is deliberate. An owner/operator
    fuels between loads; requiring a mission would make Dispatch refuse a real
    operational event. When a load is named it must be one this session may
    act on (the same check the other three routes use). When none is named NO
    ARTIFICIAL LOAD ASSOCIATION IS CREATED.

    This replaces an earlier, stricter reading that required an active load.
    That was over-tight and is recorded as such in the walkthrough report.
    """
    driver_id = _session_driver_id()
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))

    # 1. DRIVER IDENTITY -- from the session, and it must still be a real driver.
    # A driver-PIN session names no driver, and none is asked for: the Driver
    # Portal is a workspace entry control, not identity verification, and the
    # scanner workflow supplies the operational context (Mike Zachary,
    # 2026-09-13). Such a receipt is recorded as entered through a driver PIN.
    if driver_id != OPEN_DRIVER:
        driver = dispatch_svc.get_driver(driver_id)
        if not driver:
            session.clear()
            return redirect(url_for("driver_portal.driver_login"))

    # 2. TRUCK IDENTITY -- required, and it must name real, active equipment.
    equipment_id = request.form.get("equipment_id", "").strip()
    if not equipment_id:
        return _tell_driver("Which truck? A fuel receipt has to name one.")
    equipment = dispatch_svc.get_equipment(equipment_id)
    if not equipment or equipment.get("status") != "active":
        return _tell_driver("That truck is not on the active fleet.")

    # 3. RECEIPT EVIDENCE -- required, validated before anything is written.
    receipt_bytes, problem = _validate_receipt_file(request.files.get("fuel_file"))
    if problem:
        return _tell_driver(problem)

    # Optional load association. Verified when present, never invented.
    load_id = request.form.get("load_id", "").strip()
    if load_id and not _verify_driver_load(load_id, driver_id):
        return _tell_driver("That load is not yours.")

    # A hand-posted form field is not guaranteed to be a number. float() on
    # "abc" is a 500; the driver sees a crash instead of a message.
    def _number(field: str) -> float | None:
        raw = (request.form.get(field) or "").strip()
        if not raw:
            return 0.0
        try:
            value = float(raw)
        except ValueError:
            return None
        return value if value >= 0 else None

    gallons = _number("gallons")
    amount = _number("amount")
    if gallons is None or amount is None:
        return _tell_driver("Gallons and amount must be numbers.")

    jurisdiction = (request.form.get("state") or "").strip().upper()

    extracted = receipt_vision.extract_fuel_receipt(receipt_bytes, request.files["fuel_file"].filename)
    if extracted.get("available"):
        gallons = float(extracted.get("gallons") or gallons)
        amount = float(extracted.get("amount") or amount)
        scanned = receipt_vision.derive_jurisdiction(extracted.get("vendor_address"))
        if scanned:
            jurisdiction = scanned

    if gallons <= 0 and amount <= 0:
        return _tell_driver(
            "Nothing readable on that receipt. Enter the gallons and amount by hand."
        )

    # 4. JURISDICTION -- required and validated. No default. The original build
    # fell back to "FL" whenever the scan could not read a state, silently
    # filing another state's fuel under Florida: an unknown becoming a fact, in
    # a tax record.
    if not jurisdiction:
        return _tell_driver(
            "Could not read the state from that receipt. Enter it by hand."
        )
    if jurisdiction not in IFTA_JURISDICTIONS:
        return _tell_driver(f"{jurisdiction} is not an IFTA jurisdiction.")

    # 5. TIMESTAMP -- recorded explicitly rather than left to a default.
    purchased_on = (request.form.get("date") or "").strip() or _utc_today()

    ownership = f"driver:{driver_id}"
    if load_id:
        ownership += f" load:{load_id}"

    try:
        purchase = dispatch_svc.add_ifta_fuel_purchase(
            jurisdiction=jurisdiction,
            gallons=gallons,
            amount=amount,
            date=purchased_on,
            vehicle_id=equipment_id,
            vendor="Truck Stop (Driver Scanner)",
            notes=ownership,
            extraction_confidence=extracted.get("confidence") if extracted.get("available") else None,
        )
    except ValueError as exc:
        return _tell_driver(str(exc))

    # The receipt completes the chain. If this fails despite the pre-flight,
    # the purchase is removed rather than left standing without its evidence --
    # a fuel row with no receipt is exactly what "never anonymous" forbids.
    try:
        dispatch_svc.attach_ifta_fuel_evidence(
            purchase["purchase_id"],
            file_data=receipt_bytes,
            original_filename=request.files["fuel_file"].filename,
            description=f"Fuel receipt, {equipment.get('unit_number') or equipment_id}",
            uploaded_by=f"driver:{driver_id}",
        )
    except ValueError as exc:
        dispatch_svc.delete_ifta_fuel_purchase(purchase["purchase_id"])
        return _tell_driver(f"Receipt could not be stored, so nothing was logged: {exc}")

    unit = equipment.get("unit_number") or equipment_id
    return _tell_driver(
        f"{gallons:g} gal / ${amount:,.2f} logged in {jurisdiction} for {unit}.", "success"
    )
