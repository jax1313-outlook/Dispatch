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

PARKED 2026-09-14. Mike Zachary: the two driver screens merge into the Driver
Cockpit (portal/routes/joe_portal.py); this home screen is parked, not deleted.
A driver sign-in now lands in the Driver Cockpit. /driver/home still renders, and
its action routes stay, because they and the cockpit call the same actions in
portal/driver_actions.py.
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from dispatch import route_risk as route_risk_model
from dispatch import services as dispatch_svc
from portal import driver_actions
from portal.models import driver_pin_registry as pin_registry
from portal.models import pin_service

driver_portal_bp = Blueprint("driver_portal", __name__)


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
    return redirect(_cockpit())


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


def _cockpit() -> str:
    """Where a driver lands: **his calendar** (Mike Zachary, 2026-09-16).

    It used to be `joe_portal.portal_home` -- Operations' front page, reached by
    a driver PIN. He found it while planning the end-to-end test:

        *"when you sign in to the driver screen through a pin code you are taken
        directly there. You don't get to see a map. Excuse me, A calendar? All
        you see is a blank screen."*

    **The Driver Portal is a separate workspace from Operations.** Operations
    creates and commits work; the driver executes it. So the driver's front door
    is his own, and it is the calendar rather than a cockpit, because on a
    Sunday evening the question is not *what am I doing today* -- it is *what is
    Monday, and where are my gaps*. A cockpit cannot answer that and a blank
    screen answers nothing.
    """
    return url_for("driver_portal.driver_calendar")


def _open_driver_portal():
    session.clear()
    session["driver_open"] = True
    session["role"] = "Driver"
    return redirect(_cockpit())


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
# The actions themselves live in portal/driver_actions.py, shared with the
# Driver Cockpit. These routes keep the parked screen working.
@driver_portal_bp.route("/loads/<load_id>/milestone", methods=["POST"])
def driver_step_milestone(load_id: str):
    driver_id = _session_driver_id()
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))
    if not _verify_driver_load(load_id, driver_id):
        return redirect(url_for("driver_portal.driver_home"))
    return _tell_driver(*driver_actions.step_milestone(
        load_id, request.form.get("milestone_event", ""), driver_id))


# --- Mission 3: POD Evidence Photo Upload & Dock Exception Timers ---
@driver_portal_bp.route("/loads/<load_id>/pod", methods=["POST"])
def driver_upload_pod(load_id: str):
    driver_id = _session_driver_id()
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))
    if not _verify_driver_load(load_id, driver_id):
        return redirect(url_for("driver_portal.driver_home"))
    return _tell_driver(*driver_actions.upload_pod(load_id, request.files.get("pod_file"), driver_id))


@driver_portal_bp.route("/loads/<load_id>/mission-photos", methods=["POST"])
def driver_upload_mission_photos(load_id: str):
    """Load securement and freight condition photos -- customer-facing Mission
    Visibility artifacts (playbook Section 4A). See driver_actions.upload_mission_photos."""
    from portal.routes.joe_portal import _mail_connector

    driver_id = _session_driver_id()
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))
    if not _verify_driver_load(load_id, driver_id):
        return redirect(url_for("driver_portal.driver_home"))
    return _tell_driver(*driver_actions.upload_mission_photos(
        load_id, request.form.get("photo_type", "securement_photo"), request.files.getlist("photos"),
        driver_id, mail_connector=_mail_connector, url_root=request.url_root))


@driver_portal_bp.route("/loads/<load_id>/exception", methods=["POST"])
def driver_log_exception(load_id: str):
    driver_id = _session_driver_id()
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))
    if not _verify_driver_load(load_id, driver_id):
        return redirect(url_for("driver_portal.driver_home"))
    return _tell_driver(*driver_actions.log_exception(
        load_id, request.form.get("exception_type", "detention"),
        request.form.get("description", f"Dock exception logged by driver ({driver_id})"), driver_id))


# --- Mission 4: Vision Fuel Intake & Driver Pay Settlement ---
@driver_portal_bp.route("/fuel-receipt", methods=["POST"])
def driver_fuel_receipt():
    """Log a fuel purchase into the IFTA ledger from a receipt photo.

    See driver_actions.fuel_receipt. A session that names a driver must still name
    a real one; a driver-PIN session names none and asks for none (Mike Zachary,
    2026-09-13). Load association stays optional and is never invented.
    """
    driver_id = _session_driver_id()
    if not driver_id:
        return redirect(url_for("driver_portal.driver_login"))
    if driver_id != OPEN_DRIVER and not dispatch_svc.get_driver(driver_id):
        session.clear()
        return redirect(url_for("driver_portal.driver_login"))
    return _tell_driver(*driver_actions.fuel_receipt(
        request.form, request.files, driver_id,
        load_allowed=lambda load_id: bool(_verify_driver_load(load_id, driver_id))))


# ------------------------------------------------------- the driver's door ----

@driver_portal_bp.route("/calendar")
def driver_calendar():
    """**The driver's landing page. Owner ruling, 2026-09-16.**

        Driver PIN -> Driver Calendar -> Select Day -> Driver Cockpit -> Work

    *"The calendar is the driver's landing page. Not the Driver Cockpit. Not a
    blank screen. Not a mission card."*

    **A month, not a week.** He is the driver and the owner: *"The need is not
    simply: What am I doing today? The need is: Where are my gaps? What capacity
    is available? Where am I overcommitted? What opportunities exist?"* A month
    answers those; a week answers the first one only.

    **Looking is not acting.** He can open Monday through Sunday, this month or
    any month, and nothing happens. No day is reserved, no status moves, no
    calendar entry is written. *"The system must never turn a glance into a
    commitment."*

    **One calendar, one source of truth, multiple views.** The capacity behind
    this grid is `dispatch.booking.month_of` -- the same calculation the Booking
    board reads. Two presentations, one set of facts, so they cannot disagree
    about a Tuesday.
    """
    from datetime import date as _date

    from dispatch import booking, clock
    from portal.models import sandbox

    today = clock.home_date()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
        _date(year, month, 1)
    except (TypeError, ValueError):
        year, month = today.year, today.month

    grid = booking.month_of(year, month, sandbox._load(), today=today)
    return render_template("driver_calendar.html", grid=grid, today=today,
                           states=booking.LABELS)


@driver_portal_bp.route("/day/<day>")
def driver_day(day: str):
    """What the truck is doing on one day, behind the square he tapped.

    Committed freight first, then candidates -- marked, and never counted as
    capacity, because until COMMIT the day is still sellable to somebody else.
    A day with nothing on it says so; that is a gap, and a gap is information.

    **Still viewing.** Reaching a load from here opens its cockpit to be read.
    Nothing here starts a mission.
    """
    from datetime import datetime as _datetime

    from dispatch import booking, clock
    from portal.models import sandbox

    try:
        when = _datetime.strptime(day, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return redirect(url_for("driver_portal.driver_calendar"))

    return render_template(
        "driver_day.html", day=when, today=clock.home_date(),
        loads=booking.loads_on(when, sandbox._load()))
