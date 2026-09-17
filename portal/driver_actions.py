"""What a driver can do to a load, in one place.

Mike Zachary, 2026-09-14: the two driver screens merge into the Driver Cockpit
(`portal/routes/joe_portal.py`, "DRIVER COCKPIT"); the older Driver Portal home
(`/driver/home`) is parked. Rather than copy the Driver Portal's actions into
the cockpit -- Rule 15, Reuse Before Create -- the actions live here and both
screens call them.

Every function answers (message, category) and never fails quietly: a tap that
produces a silent redirect is indistinguishable from a tap that worked, which is
the 70 MPH test failing. The caller decides where the driver lands.

Categories are the flash categories the screens already use: success, warning,
error.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from dispatch import services as dispatch_svc
from dispatch.connectors import receipt_vision
from dispatch.models import ALLOWED_EXTENSIONS, EXCEPTION_TYPES, IFTA_JURISDICTIONS, MAX_FILE_SIZE

SUCCESS, WARNING, ERROR = "success", "warning", "error"


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def step_milestone(load_id: str, milestone_event: str, actor: str) -> tuple[str, str]:
    """Record one milestone.

    add_milestone() does NOT raise when the transition gate refuses -- it records
    the milestone, leaves the status alone, and hands the refusal back under
    "status_transition_refused" (see dispatch/services.py::add_milestone). An
    earlier driver build swallowed that, so a refused step looked exactly like a
    successful one from the cab. ValueError means the load vanished between the
    ownership check and the write, not a refusal.
    """
    milestone_event = (milestone_event or "").strip()
    if not milestone_event:
        return "No milestone was selected.", ERROR
    try:
        result = dispatch_svc.add_milestone(
            load_id, event_type=milestone_event, source="driver", entered_by=f"driver:{actor}")
    except ValueError as exc:
        return str(exc), ERROR
    refusal = result.get("status_transition_refused")
    if refusal:
        return (f"Recorded, but the load stays in {refusal['from_status'].replace('_', ' ')}: "
                f"{refusal['reason']}"), WARNING
    return f"{milestone_event.replace('_', ' ').title()} recorded.", SUCCESS


def upload_pod(load_id: str, upload, actor: str) -> tuple[str, str]:
    """A POD photo joins the load's evidence.

    attach_evidence() refuses a disallowed extension or an oversize file by
    raising ValueError; unhandled that is a 500 on a driver's tablet with no
    explanation, so the message is surfaced instead.
    """
    if not upload or not upload.filename:
        return "No photo or file was attached.", ERROR
    data = upload.read()
    if not data:
        return "That file came through empty. Try the photo again.", ERROR
    try:
        dispatch_svc.attach_evidence(
            load_id, evidence_type="pod", description=f"Signed POD Uploaded by Driver ({actor})",
            file_data=data, original_filename=upload.filename)
    except ValueError as exc:
        return str(exc), ERROR

    # **Sending the POD is what completes the load.** Owner ruling, 2026-09-16:
    # *"POD sent completes the load and triggers the closing packet."*
    #
    # This used to attach the file and stop. The milestone lived on a different
    # control -- the manual milestone drawer -- so a driver who uploaded his
    # signed POD had, in his own words, sent it, and Dispatch silently
    # disagreed: the load stayed `delivered` and the cockpit went on asking for
    # the POD he had just sent. Found by the regression audit, 2026-09-16.
    #
    # The transition is still gated. Uploading a POD on a load that has not
    # reached `delivered` records the evidence and is refused the advance, said
    # plainly, exactly as any other out-of-order milestone is.
    said, category = step_milestone(load_id, "pod_received", actor)
    if category == ERROR:
        return "POD uploaded, but the load did not advance: %s" % said, WARNING
    if category == WARNING:
        return "POD uploaded. %s" % said, WARNING
    return "POD uploaded. The run is complete.", SUCCESS


def upload_mission_photos(load_id: str, photo_type: str, uploads, actor: str, *,
                          mail_connector, url_root: str) -> tuple[str, str]:
    """Load securement and freight condition photos -- customer-facing Mission Visibility
    artifacts (playbook Section 4A; Mike Zachary, 2026-09-13): "A customer cannot see load
    securement. A customer can see evidence of load securement. The evidence is the value."

    The photos join the load's evidence (and so the Mission Visibility View and the final
    mission package), the Mission Record history, and a Customer Alert that travels Joe ->
    Publisher -> COMI -> Email Helper. The M6A check itself stays an internal activity.
    """
    from dispatch.models import CUSTOMER_FACING_PHOTO_TYPES
    from portal import portal_access

    photo_type = (photo_type or "securement_photo").strip()
    if photo_type not in CUSTOMER_FACING_PHOTO_TYPES:
        return "Pick securement or freight condition.", ERROR
    uploads = [f for f in (uploads or []) if f and f.filename]
    if not uploads:
        return "No photo was attached.", ERROR

    label = CUSTOMER_FACING_PHOTO_TYPES[photo_type]
    added = []
    for upload in uploads:
        data = upload.read()
        if not data:
            return "That photo came through empty. Try again.", ERROR
        try:
            evidence = dispatch_svc.attach_evidence(
                load_id, evidence_type=photo_type, description=label, file_data=data,
                original_filename=upload.filename, uploaded_by=f"driver:{actor}")
        except ValueError as exc:
            return str(exc), ERROR
        added.append({"evidence_id": evidence["evidence_id"], "evidence_type": photo_type, "label": label})

    alert = portal_access.alert_mission_evidence(load_id, added, mail_connector=mail_connector,
                                                 url_root=url_root)
    told = ("The customer was sent a Customer Alert." if alert["sent"]
            else "No Customer Alert went out; dispatch can see why.")
    return (f"{len(added)} {label.lower()}{'s' if len(added) != 1 else ''} added to Mission Visibility. "
            f"{told}"), SUCCESS


def log_exception(load_id: str, exception_type: str, description: str, actor: str) -> tuple[str, str]:
    exception_type = (exception_type or "detention").strip()
    description = (description or "").strip() or f"Dock exception logged by driver ({actor})"
    try:
        dispatch_svc.open_exception(load_id, exception_type=exception_type, severity="medium",
                                    description=description)
    except ValueError as exc:
        return str(exc), ERROR
    return f"{exception_type.replace('_', ' ').title()} logged. Dispatch can see it.", SUCCESS


def exception_choices() -> list[tuple[str, str]]:
    """(value, label) for every exception type Dispatch accepts, detention first."""
    ordered = ["detention"] + [t for t in EXCEPTION_TYPES if t != "detention"]
    return [(t, t.replace("_", " ").title()) for t in ordered]


def validate_receipt_file(upload):
    """Pre-flight the receipt against the same rules attach_ifta_fuel_evidence()
    will apply, before any record is created.

    The ownership chain requires receipt evidence, so a purchase must never exist
    without its receipt. Validating here means the common rejections (wrong type,
    too large, empty) are refused before the purchase is written.
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


def fuel_receipt(form, files, actor: str, *, load_allowed) -> tuple[str, str]:
    """Log a fuel purchase into the IFTA ledger from a receipt photo.

    A receipt is logged with its truck, timestamp, jurisdiction and receipt
    evidence. No Mike Zachary ruling requires driver identity on a fuel receipt
    (DECISION_LOG.md, 2026-09-13); the actor is recorded as the session names it.

    LOAD ASSOCIATION IS OPTIONAL. An owner/operator fuels between loads; when no
    load is named NO ARTIFICIAL LOAD ASSOCIATION IS CREATED. A named load must pass
    the caller's `load_allowed(load_id)` -- the same check its other actions use.
    """
    # TRUCK IDENTITY -- required, and it must name real, active equipment.
    equipment_id = (form.get("equipment_id") or "").strip()
    if not equipment_id:
        return "Which truck? A fuel receipt has to name one.", ERROR
    equipment = dispatch_svc.get_equipment(equipment_id)
    if not equipment or equipment.get("status") != "active":
        return "That truck is not on the active fleet.", ERROR

    # RECEIPT EVIDENCE -- required, validated before anything is written.
    upload = files.get("fuel_file")
    receipt_bytes, problem = validate_receipt_file(upload)
    if problem:
        return problem, ERROR

    # Optional load association. Verified when present, never invented.
    load_id = (form.get("load_id") or "").strip()
    if load_id and not load_allowed(load_id):
        return "That load is not yours.", ERROR

    # A hand-posted form field is not guaranteed to be a number.
    def _number(field: str) -> float | None:
        raw = (form.get(field) or "").strip()
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
        return "Gallons and amount must be numbers.", ERROR

    jurisdiction = (form.get("state") or "").strip().upper()

    extracted = receipt_vision.extract_fuel_receipt(receipt_bytes, upload.filename)
    if extracted.get("available"):
        gallons = float(extracted.get("gallons") or gallons)
        amount = float(extracted.get("amount") or amount)
        scanned = receipt_vision.derive_jurisdiction(extracted.get("vendor_address"))
        if scanned:
            jurisdiction = scanned

    if gallons <= 0 and amount <= 0:
        return "Nothing readable on that receipt. Enter the gallons and amount by hand.", ERROR

    # JURISDICTION -- required and validated. No default: an unknown becoming a
    # fact, in a tax record, is what an earlier "FL" fallback did.
    if not jurisdiction:
        return "Could not read the state from that receipt. Enter it by hand.", ERROR
    if jurisdiction not in IFTA_JURISDICTIONS:
        return f"{jurisdiction} is not an IFTA jurisdiction.", ERROR

    purchased_on = (form.get("date") or "").strip() or _utc_today()

    ownership = f"driver:{actor}"
    if load_id:
        ownership += f" load:{load_id}"

    try:
        purchase = dispatch_svc.add_ifta_fuel_purchase(
            jurisdiction=jurisdiction, gallons=gallons, amount=amount, date=purchased_on,
            vehicle_id=equipment_id, vendor="Truck Stop (Driver Scanner)", notes=ownership,
            extraction_confidence=extracted.get("confidence") if extracted.get("available") else None)
    except ValueError as exc:
        return str(exc), ERROR

    # The receipt completes the chain. If this fails despite the pre-flight, the
    # purchase is removed rather than left standing without its evidence.
    try:
        dispatch_svc.attach_ifta_fuel_evidence(
            purchase["purchase_id"], file_data=receipt_bytes, original_filename=upload.filename,
            description=f"Fuel receipt, {equipment.get('unit_number') or equipment_id}",
            uploaded_by=f"driver:{actor}")
    except ValueError as exc:
        dispatch_svc.delete_ifta_fuel_purchase(purchase["purchase_id"])
        return f"Receipt could not be stored, so nothing was logged: {exc}", ERROR

    unit = equipment.get("unit_number") or equipment_id
    return f"{gallons:g} gal / ${amount:,.2f} logged in {jurisdiction} for {unit}.", SUCCESS
