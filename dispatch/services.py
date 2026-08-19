"""Dispatch Data Engine service functions.

Business logic for the full load lifecycle: create -> dispatch -> pickup
-> transit -> deliver -> POD -> archive.
"""

from __future__ import annotations

from pathlib import Path

from dispatch.models import (
    BROKER_STATUSES,
    EXCEPTION_STATUSES,
    IFTA_JURISDICTIONS,
    LOAD_SOURCES,
    LOAD_STATUSES,
    BrokerContact,
    DetentionEvent,
    Driver,
    Equipment,
    EvidenceItem,
    ExceptionNotice,
    Expense,
    IFTAException,
    IFTAFuelEvidence,
    IFTAFuelPurchase,
    IFTAReportApproval,
    IFTATripLeg,
    Load,
    LoadVisibilityRecord,
    MilestoneEvent,
    PODPackage,
    RateConfirmation,
    RetentionArchive,
    Settlement,
    _utc_now,
)
from dispatch import notifications, store

import sys


def _notify_safe(send) -> None:
    """Run a notifications.notify_* call without letting an SMTP failure
    turn an already-completed write into a false failure response.

    Every notify_* call site here runs strictly after the DB write it's
    reporting on has already committed. An SMTP timeout/auth failure raised
    from smtplib (cin_lite/email_delivery.py's transport, reused by
    dispatch/notifications.py) is not the caller's problem to see as a 500 --
    the load *was* archived/delivered/invoiced; only the notification email
    failed. Log and continue rather than propagate.
    """
    try:
        send()
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any transport failure, not just SMTP
        print(f"[dispatch.notifications] notify failed, continuing: {exc}", file=sys.stderr)


_MILESTONE_TO_STATUS = {
    "dispatched": "dispatched",
    "en_route_pickup": "en_route_pickup",
    "arrived_pickup": "at_pickup",
    "loaded": "picked_up",
    "departed_pickup": "in_transit",
    "in_transit": "in_transit",
    "checkpoint": None,
    "arrived_delivery": "at_delivery",
    "delivered": "delivered",
    "pod_received": "delivered",
    "completed": "completed",
}

_VALID_TRANSITIONS: dict[str, set[str]] = {
    "created": {"dispatched", "cancelled"},
    "dispatched": {"en_route_pickup", "cancelled"},
    "en_route_pickup": {"at_pickup", "cancelled"},
    "at_pickup": {"picked_up", "cancelled"},
    "picked_up": {"in_transit"},
    "in_transit": {"at_delivery"},
    "at_delivery": {"delivered"},
    "delivered": {"completed", "archived"},
    "completed": {"archived"},
    "archived": set(),
    "cancelled": {"archived"},
}


def validate_status_transition(current: str, target: str) -> None:
    if current == target:
        return
    allowed = _VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        allowed_list = ", ".join(sorted(allowed)) if allowed else "none"
        raise ValueError(
            f"Invalid status transition: {current} -> {target}. "
            f"Allowed from {current}: {allowed_list}"
        )


_MILESTONE_NEXT = {
    "dispatched": "en_route_pickup",
    "en_route_pickup": "arrived_pickup",
    "arrived_pickup": "loaded",
    "loaded": "departed_pickup",
    "departed_pickup": "in_transit",
    "in_transit": "arrived_delivery",
    "checkpoint": None,
    "arrived_delivery": "delivered",
    "delivered": "pod_received",
    "pod_received": "completed",
    "completed": None,
}


def create_load(
    customer: str,
    broker_shipper: str = "",
    pickup_location: str = "",
    delivery_location: str = "",
    pickup_datetime: str = "",
    delivery_datetime: str = "",
    equipment: str = "",
    driver: str = "",
    driver_id: str = "",
    equipment_id: str = "",
    source: str = "",
    notes: str = "",
) -> dict:
    if driver_id:
        _validate_driver_assignment(driver_id)
    if equipment_id:
        _validate_equipment_assignment(equipment_id)

    load = Load(
        customer=customer,
        broker_shipper=broker_shipper,
        pickup_location=pickup_location,
        delivery_location=delivery_location,
        pickup_datetime=pickup_datetime,
        delivery_datetime=delivery_datetime,
        equipment=equipment,
        driver=driver,
        driver_id=driver_id,
        equipment_id=equipment_id,
        source=source,
        notes=notes,
    )
    result = store.create_load(load)
    vis = LoadVisibilityRecord(
        load_id=load.load_id,
        current_status="created",
        next_expected_milestone="dispatched",
    )
    store.upsert_visibility(vis)
    return result


def get_load(load_id: str) -> dict | None:
    return store.get_load(load_id)


def list_loads(
    status: str | None = None,
    customer: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    driver_id: str | None = None,
    *,
    page: int | None = None,
    per_page: int | None = None,
) -> list[dict] | dict:
    return store.list_loads(
        status=status, customer=customer,
        date_from=date_from, date_to=date_to, driver_id=driver_id,
        page=page, per_page=per_page,
    )


def update_load(load_id: str, **fields) -> dict | None:
    if "driver_id" in fields and fields["driver_id"]:
        _validate_driver_assignment(fields["driver_id"])
    if "equipment_id" in fields and fields["equipment_id"]:
        _validate_equipment_assignment(fields["equipment_id"])
    if "source" in fields and fields["source"]:
        if fields["source"] not in LOAD_SOURCES:
            raise ValueError(f"Invalid source: {fields['source']}")
    old_status = None
    if "status" in fields:
        current = store.get_load(load_id)
        if current:
            old_status = current["status"]
            validate_status_transition(old_status, fields["status"])
    result = store.update_load(load_id, **fields)
    if result and old_status and "status" in fields:
        from dispatch.models import LoadActivity
        store.create_activity(LoadActivity(
            load_id=load_id,
            activity_type="status_change",
            message=f"Status changed from {old_status} to {fields['status']}",
            source="system",
        ))
    return result


_DELETABLE_STATUSES = {"created", "cancelled"}


def delete_load(load_id: str) -> bool:
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")
    if load["status"] not in _DELETABLE_STATUSES:
        raise ValueError(
            f"Cannot delete load in status '{load['status']}'. "
            f"Only loads in {sorted(_DELETABLE_STATUSES)} can be deleted."
        )
    return store.delete_load(load_id)


def assign_driver(load_id: str, driver_id: str) -> dict | None:
    """Assign an active driver to a load."""
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")
    _validate_driver_assignment(driver_id)
    drv = store.get_driver(driver_id)
    store.update_load(load_id, driver_id=driver_id, driver=drv["name"])
    _try_auto_dispatch(load_id)
    return store.get_load(load_id)


def unassign_driver(load_id: str) -> dict | None:
    """Remove driver assignment from a load."""
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")
    return store.update_load(load_id, driver_id="", driver="")


def assign_equipment(load_id: str, equipment_id: str) -> dict | None:
    """Assign active equipment to a load."""
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")
    _validate_equipment_assignment(equipment_id)
    eqp = store.get_equipment(equipment_id)
    label = f"{eqp['unit_number']} ({eqp['equipment_type']})"
    store.update_load(load_id, equipment_id=equipment_id, equipment=label)
    _try_auto_dispatch(load_id)
    return store.get_load(load_id)


def unassign_equipment(load_id: str) -> dict | None:
    """Remove equipment assignment from a load."""
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")
    return store.update_load(load_id, equipment_id="", equipment="")


def _validate_driver_assignment(driver_id: str) -> None:
    drv = store.get_driver(driver_id)
    if not drv:
        raise ValueError(f"Driver not found: {driver_id}")
    if drv["status"] != "active":
        raise ValueError(f"Driver {driver_id} is not active (status: {drv['status']})")


def _validate_equipment_assignment(equipment_id: str) -> None:
    eqp = store.get_equipment(equipment_id)
    if not eqp:
        raise ValueError(f"Equipment not found: {equipment_id}")
    if eqp["status"] != "active":
        raise ValueError(f"Equipment {equipment_id} is not active (status: {eqp['status']})")


def _try_auto_dispatch(load_id: str) -> None:
    load = store.get_load(load_id)
    if not load or load["status"] != "created":
        return
    if not load.get("driver_id") or not load.get("equipment_id"):
        return
    store.update_load(load_id, status="dispatched")
    ms = MilestoneEvent(
        load_id=load_id,
        event_type="dispatched",
        source="system",
        note="Auto-dispatched: driver and equipment assigned",
        event_time=_utc_now(),
    )
    store.create_milestone(ms)
    vis = LoadVisibilityRecord(
        load_id=load_id,
        current_status="dispatched",
        last_milestone="dispatched",
        next_expected_milestone="en_route_pickup",
    )
    store.upsert_visibility(vis)
    updated = store.get_load(load_id)
    if updated:
        _notify_safe(lambda: notifications.notify_dispatched(updated))


def record_route_risk_event(
    load_id: str,
    condition_summary: str,
    consequence_level: int = 1,
    estimated_delay_minutes: int = 0,
    source_type: str = "manual_entry",
    source_label: str = "Internal Dispatcher Entry",
    affected_area: str = "",
    affected_corridor: str = "",
    delivery_commitment_status: str = "achievable",
    has_map_visual: bool = True,
) -> dict:
    from dispatch import route_risk
    return route_risk.record_route_risk_event(
        load_id=load_id,
        condition_summary=condition_summary,
        consequence_level=consequence_level,
        estimated_delay_minutes=estimated_delay_minutes,
        source_type=source_type,
        source_label=source_label,
        affected_area=affected_area,
        affected_corridor=affected_corridor,
        delivery_commitment_status=delivery_commitment_status,
        has_map_visual=has_map_visual,
    )


def get_route_risk(load_id: str) -> dict:
    from dispatch import route_risk
    return route_risk.get_route_risk(load_id)


def get_visibility(load_id: str) -> dict | None:
    return store.get_visibility(load_id)


def get_mission_visibility(load_id: str) -> dict:
    """Unified, externally-safe visibility snapshot for a load.

    Wraps store.get_visibility() and deliberately EXCLUDES internal_note
    (internal-only content -- matches the precedent set by
    build_stakeholder_view(), which also withholds internal_note from
    external-facing payloads). Always returns the same dict shape, even
    when no visibility record exists yet, so callers never need a
    None-check before accessing fields.
    """
    visibility = store.get_visibility(load_id)
    if not visibility:
        return {
            "current_status": None,
            "last_milestone": None,
            "next_expected_milestone": None,
            "customer_note": "",
            "updated_at": None,
        }
    return {
        "current_status": visibility.get("current_status"),
        "last_milestone": visibility.get("last_milestone"),
        "next_expected_milestone": visibility.get("next_expected_milestone"),
        "customer_note": visibility.get("customer_note", ""),
        "updated_at": visibility.get("updated_at"),
    }


def add_milestone(
    load_id: str,
    event_type: str,
    location: str = "",
    source: str = "dispatcher",
    note: str = "",
    entered_by: str = "",
    event_time: str = "",
) -> dict:
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")

    ms = MilestoneEvent(
        load_id=load_id,
        event_type=event_type,
        location=location,
        source=source,
        note=note,
        entered_by=entered_by,
        event_time=event_time or _utc_now(),
    )
    result = store.create_milestone(ms)

    new_status = _MILESTONE_TO_STATUS.get(event_type)
    if new_status and new_status in LOAD_STATUSES:
        store.update_load(load_id, status=new_status)

    has_open = bool(store.list_exceptions(load_id=load_id, status="open"))

    vis = LoadVisibilityRecord(
        load_id=load_id,
        current_status=new_status or load["status"],
        last_milestone=event_type,
        next_expected_milestone=_MILESTONE_NEXT.get(event_type),
        exception_flag=has_open,
    )
    store.upsert_visibility(vis)

    if event_type == "delivered":
        updated_load = store.get_load(load_id) or load
        _notify_safe(lambda: notifications.notify_delivered(updated_load, result))

    return result


def get_timeline(load_id: str) -> list[dict]:
    return store.list_milestones(load_id)


def validate_milestone(milestone_id: str, validation_status: str) -> dict | None:
    from dispatch.models import VALIDATION_STATUSES
    if validation_status not in VALIDATION_STATUSES:
        raise ValueError(
            f"Invalid validation_status: {validation_status!r}. "
            f"Must be one of {VALIDATION_STATUSES}"
        )
    return store.update_milestone(milestone_id, validation_status=validation_status)


def update_visibility_notes(
    load_id: str,
    customer_note: str | None = None,
    internal_note: str | None = None,
) -> dict | None:
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")
    fields: dict[str, str] = {}
    if customer_note is not None:
        fields["customer_note"] = customer_note
    if internal_note is not None:
        fields["internal_note"] = internal_note
    if not fields:
        return store.get_visibility(load_id)
    return store.update_visibility_notes(load_id, **fields)


def _get_upload_dir() -> Path:
    import os
    upload_dir = os.environ.get("PORTAL_UPLOAD_DIR")
    if upload_dir:
        p = Path(upload_dir)
    else:
        memory_root = os.environ.get("DISPATCH_MEMORY_ROOT")
        if memory_root:
            p = Path(memory_root) / "Evidence"
        else:
            portal_data = os.environ.get("PORTAL_DATA_DIR")
            if portal_data:
                p = Path(portal_data) / "uploads"
            else:
                ops_root = os.environ.get("DISPATCH_OPERATIONS_ROOT")
                if ops_root:
                    p = Path(ops_root) / "Current Workspace" / "PortalData" / "uploads"
                else:
                    p = Path(__file__).resolve().parent.parent / "portal" / "data" / "uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _save_upload(evidence_id: str, filename: str, data: bytes) -> Path:
    from dispatch.models import ALLOWED_EXTENSIONS, MAX_FILE_SIZE
    if len(data) > MAX_FILE_SIZE:
        raise ValueError(f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit")
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type not allowed: .{ext}")
    safe_name = f"{evidence_id}.{ext}"
    dest = _get_upload_dir() / safe_name
    dest.write_bytes(data)
    return dest


def attach_evidence(
    load_id: str,
    evidence_type: str = "document",
    description: str = "",
    file_path: str | None = None,
    related_milestone_id: str | None = None,
    uploaded_by: str = "",
    file_data: bytes | None = None,
    original_filename: str = "",
) -> dict:
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")

    ev = EvidenceItem(
        load_id=load_id,
        evidence_type=evidence_type,
        description=description,
        file_path=file_path,
        related_milestone_id=related_milestone_id,
        uploaded_by=uploaded_by,
        original_filename=original_filename,
    )
    if file_data:
        ev.compute_checksum(file_data)
        ev.file_size = len(file_data)
        import mimetypes
        ev.mime_type = mimetypes.guess_type(original_filename or "file.pdf")[0] or "application/octet-stream"
        saved = _save_upload(ev.evidence_id, original_filename or "file.pdf", file_data)
        ev.file_path = str(saved)
    return store.create_evidence(ev)


def get_evidence_file(evidence_id: str) -> tuple[Path, str] | None:
    ev = store.get_evidence(evidence_id)
    if not ev or not ev.get("file_path"):
        return None
    p = Path(ev["file_path"])
    if not p.is_file():
        return None
    return p, ev.get("original_filename") or p.name


def list_evidence(load_id: str) -> list[dict]:
    return store.list_evidence(load_id)


def update_evidence(evidence_id: str, **fields) -> dict | None:
    return store.update_evidence(evidence_id, **fields)


def delete_evidence(evidence_id: str) -> bool:
    ev = store.get_evidence(evidence_id)
    if ev and ev.get("file_path"):
        p = Path(ev["file_path"])
        if p.is_file():
            p.unlink()
    return store.delete_evidence(evidence_id)


def open_exception(
    load_id: str,
    exception_type: str = "other",
    severity: str = "medium",
    description: str = "",
    related_milestone_id: str | None = None,
) -> dict:
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")

    exc = ExceptionNotice(
        load_id=load_id,
        exception_type=exception_type,
        severity=severity,
        description=description,
        related_milestone_id=related_milestone_id,
    )
    result = store.create_exception(exc)

    vis = store.get_visibility(load_id)
    if vis:
        updated = LoadVisibilityRecord(
            load_id=load_id,
            current_status=vis["current_status"],
            last_milestone=vis.get("last_milestone"),
            next_expected_milestone=vis.get("next_expected_milestone"),
            exception_flag=True,
            customer_note=vis.get("customer_note", ""),
            internal_note=vis.get("internal_note", ""),
        )
        store.upsert_visibility(updated)

    if severity in ("high", "critical"):
        _notify_safe(lambda: notifications.notify_exception(load, result))

    return result


def resolve_exception(
    exception_id: str,
    resolution_note: str = "",
) -> dict | None:
    exc = store.update_exception(
        exception_id,
        status="resolved",
        resolution_note=resolution_note,
        resolved_at=_utc_now(),
    )
    if not exc:
        return None

    load_id = exc["load_id"]
    open_remaining = store.list_exceptions(load_id=load_id, status="open")
    vis = store.get_visibility(load_id)
    if vis:
        updated = LoadVisibilityRecord(
            load_id=load_id,
            current_status=vis["current_status"],
            last_milestone=vis.get("last_milestone"),
            next_expected_milestone=vis.get("next_expected_milestone"),
            exception_flag=bool(open_remaining),
            customer_note=vis.get("customer_note", ""),
            internal_note=vis.get("internal_note", ""),
        )
        store.upsert_visibility(updated)

    return exc


def list_exceptions(
    load_id: str | None = None,
    status: str | None = None,
    *,
    page: int | None = None,
    per_page: int | None = None,
) -> list[dict] | dict:
    return store.list_exceptions(
        load_id=load_id, status=status, page=page, per_page=per_page,
    )


def update_exception(exception_id: str, **fields) -> dict | None:
    return store.update_exception(exception_id, **fields)


_POD_ELIGIBLE_STATUSES = {"delivered", "completed", "archived"}


def generate_pod(
    load_id: str,
    recipient: str = "",
    notes: str = "",
    evidence_ids: list[str] | None = None,
    require_delivered: bool = True,
) -> dict:
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")

    if require_delivered and load["status"] not in _POD_ELIGIBLE_STATUSES:
        raise ValueError(
            f"Load must be delivered before generating POD (current: {load['status']})"
        )

    if evidence_ids is None:
        all_ev = store.list_evidence(load_id)
        evidence_ids = [e["evidence_id"] for e in all_ev]

    pod = PODPackage(
        load_id=load_id,
        evidence_ids=evidence_ids,
        recipient=recipient,
        notes=notes,
        status="complete",
    )
    result = store.create_pod(pod)

    milestones = store.list_milestones(load_id)
    has_pod_milestone = any(m["event_type"] == "pod_received" for m in milestones)
    if not has_pod_milestone:
        add_milestone(
            load_id=load_id,
            event_type="pod_received",
            source="system",
            note=f"POD generated: {pod.pod_id}",
        )

    _notify_safe(lambda: notifications.notify_pod_generated(load, result))

    return result


def get_pod(pod_id: str) -> dict | None:
    return store.get_pod(pod_id)


def list_pods(load_id: str) -> list[dict]:
    return store.list_pods(load_id)


def get_comi_status(load_id: str) -> dict:
    """Shared COMI (Freight Closeout Communications) status lookup, so every
    surface -- Driver Portal, Stakeholder Portal, Operations Feed, and any
    future consumer -- reads the same DRAFT/REVIEWED/SUBMITTED signal from
    portal.models.email_helper instead of re-deriving it independently."""
    from portal.models import email_helper

    pkg = email_helper.get_package(load_id)
    if not pkg:
        return {"exists": False, "status": None}
    return {"exists": True, "status": pkg["status"]}


def evaluate_comi_routing(
    load_id: str,
    trigger_type: str,
    consequence_level: int = 1,
    source_refs: dict | None = None,
    custom_notes: dict | None = None,
) -> dict:
    """COMI routing helper evaluating triggers and recipient role visibility."""
    from dispatch import comi_routing
    return comi_routing.evaluate_comi_routing(
        load_id=load_id,
        trigger_type=trigger_type,
        consequence_level=consequence_level,
        source_refs=source_refs,
        custom_notes=custom_notes,
    )


def sanitize_payload_for_role(payload: dict, role: str) -> dict:
    """Role-based payload sanitization ensuring internal-only information is excluded for external recipients."""
    from dispatch import comi_routing
    return comi_routing.sanitize_payload_for_role(payload, role)


def archive_load(load_id: str) -> dict:
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")

    existing = store.get_retention_by_load(load_id)
    if existing:
        raise ValueError(f"Load {load_id} is already archived")

    validate_status_transition(load["status"], "archived")

    all_ev = store.list_evidence(load_id)
    evidence_ids = [e["evidence_id"] for e in all_ev]

    pods = store.list_pods(load_id)
    pod_id = pods[0]["pod_id"] if pods else None

    financials = get_financials(load_id)
    fin_summary = financials["summary"] if financials else {}
    settlement = store.get_settlement(load_id)
    if settlement:
        fin_summary["settlement_status"] = settlement["payment_status"]
        fin_summary["invoice_number"] = settlement["invoice_number"]

    archive_loc = f"retention/{load_id}"

    ret = RetentionArchive(
        load_id=load_id,
        final_status=load["status"],
        pod_package_id=pod_id,
        evidence_index=evidence_ids,
        financial_summary=fin_summary,
        archive_location=archive_loc,
    )
    result = store.create_retention(ret)

    store.update_load(load_id, status="archived")
    vis = store.get_visibility(load_id)
    if vis:
        updated = LoadVisibilityRecord(
            load_id=load_id,
            current_status="archived",
            last_milestone=vis.get("last_milestone"),
            exception_flag=bool(vis.get("exception_flag")),
        )
        store.upsert_visibility(updated)

    _notify_safe(lambda: notifications.notify_archived(load, result))

    return result


def get_retention(load_id: str) -> dict | None:
    return store.get_retention_by_load(load_id)


def list_retentions() -> list[dict]:
    return store.list_retentions()


_CLOSEOUT_ELIGIBLE_STATUSES = {"delivered", "completed"}


def build_completion_packet(load_id: str) -> dict:
    """Assemble the End Load closeout bundle from artifacts that already exist for this load.

    Pulls together rate confirmation, POD, settlement/invoice, evidence, and broker contact --
    generates nothing new. Callers use `available`/`missing` to know what's ready to route
    toward Publisher/Email Helper and what still needs to be gathered first.
    """
    bundle = get_load_bundle(load_id)
    if not bundle:
        raise ValueError(f"Load not found: {load_id}")

    load = bundle["load"]
    if load["status"] not in _CLOSEOUT_ELIGIBLE_STATUSES:
        raise ValueError(
            f"Load must be delivered or completed before End Load (current: {load['status']})"
        )

    broker_contact = None
    if load.get("broker_shipper"):
        matches = store.list_broker_contacts(search=load["broker_shipper"])
        broker_contact = matches[0] if matches else None

    rate_confirmation = bundle["financials"]["rate_confirmation"] if bundle["financials"] else None
    financial_summary = bundle["financials"]["summary"] if bundle["financials"] else None

    available: list[str] = []
    missing: list[str] = []
    for label, present in (
        ("Rate Confirmation", bool(rate_confirmation)),
        ("POD", bool(bundle["pods"])),
        ("Invoice / Settlement", bool(bundle["settlement"])),
        ("Broker Contact", bool(broker_contact)),
        ("Evidence", bool(bundle["evidence"])),
    ):
        (available if present else missing).append(label)

    return {
        "load_id": load_id,
        "load": load,
        "rate_confirmation": rate_confirmation,
        "financial_summary": financial_summary,
        "settlement": bundle["settlement"],
        "pods": bundle["pods"],
        "evidence": bundle["evidence"],
        "broker_contact": broker_contact,
        "available": available,
        "missing": missing,
    }


def confirm_rate(
    load_id: str,
    rate_amount: float,
    rate_type: str = "flat",
    distance_miles: float = 0.0,
    confirmed_by: str = "",
    notes: str = "",
) -> dict:
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")

    existing = store.get_rate_confirmation(load_id)
    if existing:
        return store.update_rate_confirmation(
            load_id,
            rate_amount=rate_amount,
            rate_type=rate_type,
            distance_miles=distance_miles,
            confirmed_by=confirmed_by,
            notes=notes,
        )

    rc = RateConfirmation(
        load_id=load_id,
        rate_amount=rate_amount,
        rate_type=rate_type,
        distance_miles=distance_miles,
        confirmed_by=confirmed_by,
        notes=notes,
    )
    return store.create_rate_confirmation(rc)


def get_rate_confirmation(load_id: str) -> dict | None:
    return store.get_rate_confirmation(load_id)


def add_expense(
    load_id: str,
    category: str = "other",
    description: str = "",
    amount: float = 0.0,
    receipt_evidence_id: str | None = None,
    notes: str = "",
) -> dict:
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")

    exp = Expense(
        load_id=load_id,
        category=category,
        description=description,
        amount=amount,
        receipt_evidence_id=receipt_evidence_id,
        notes=notes,
    )
    return store.create_expense(exp)


def update_expense(expense_id: str, **fields) -> dict | None:
    return store.update_expense(expense_id, **fields)


def delete_expense(expense_id: str) -> bool:
    return store.delete_expense(expense_id)


def list_expenses(load_id: str) -> list[dict]:
    return store.list_expenses(load_id)


def get_financials(load_id: str) -> dict | None:
    load = store.get_load(load_id)
    if not load:
        return None

    rate = store.get_rate_confirmation(load_id)
    expenses = store.list_expenses(load_id)
    total_expenses = sum(e["amount"] for e in expenses)

    revenue = rate["revenue"] if rate else 0.0
    profit = revenue - total_expenses
    margin_pct = (profit / revenue * 100) if revenue > 0 else 0.0

    return {
        "rate_confirmation": rate,
        "expenses": expenses,
        "summary": {
            "revenue": round(revenue, 2),
            "total_expenses": round(total_expenses, 2),
            "profit": round(profit, 2),
            "margin_pct": round(margin_pct, 1),
            "expense_count": len(expenses),
        },
    }


def get_avg_fuel_price() -> float:
    purchases = store.list_ifta_fuel_purchases()
    if not purchases:
        return 0.0
    total_amount = sum(p["amount"] for p in purchases)
    total_gallons = sum(p["gallons"] for p in purchases)
    if total_gallons <= 0:
        return 0.0
    return round(total_amount / total_gallons, 4)


def get_fleet_mpg() -> float:
    legs = store.list_ifta_trip_legs()
    purchases = store.list_ifta_fuel_purchases()
    total_miles = sum(leg["miles"] for leg in legs)
    total_gallons = sum(p["gallons"] for p in purchases)
    if total_gallons <= 0:
        return 0.0
    return round(total_miles / total_gallons, 2)


def estimate_fuel_cost(
    distance_miles: float = 0.0,
    mpg: float = 0.0,
    fuel_price: float = 0.0,
    load_id: str = "",
) -> dict:
    if load_id and not distance_miles:
        rc = store.get_rate_confirmation(load_id)
        if rc and rc.get("distance_miles"):
            distance_miles = rc["distance_miles"]

    if not mpg:
        mpg = get_fleet_mpg()
    if not fuel_price:
        fuel_price = get_avg_fuel_price()

    if distance_miles <= 0:
        return {
            "distance_miles": 0,
            "mpg": round(mpg, 2),
            "fuel_price_per_gallon": round(fuel_price, 4),
            "gallons_needed": 0,
            "estimated_cost": 0,
            "cost_per_mile": 0,
        }

    gallons_needed = distance_miles / mpg if mpg > 0 else 0.0
    estimated_cost = gallons_needed * fuel_price

    return {
        "distance_miles": round(distance_miles, 2),
        "mpg": round(mpg, 2),
        "fuel_price_per_gallon": round(fuel_price, 4),
        "gallons_needed": round(gallons_needed, 2),
        "estimated_cost": round(estimated_cost, 2),
        "cost_per_mile": round(estimated_cost / distance_miles, 4) if distance_miles > 0 else 0,
    }


def create_settlement(
    load_id: str,
    due_date: str = "",
    notes: str = "",
) -> dict:
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")

    existing = store.get_settlement(load_id)
    if existing:
        raise ValueError(f"Settlement already exists for load {load_id}")

    rate = store.get_rate_confirmation(load_id)
    invoice_amount = rate["revenue"] if rate else 0.0

    stl = Settlement(
        load_id=load_id,
        invoice_amount=invoice_amount,
        due_date=due_date,
        payment_status="invoiced",
        notes=notes,
    )
    result = store.create_settlement(stl)
    _notify_safe(lambda: notifications.notify_invoice_created(load, result))
    return result


def update_settlement(load_id: str, **fields) -> dict | None:
    return store.update_settlement(load_id, **fields)


def record_payment(
    load_id: str,
    payment_amount: float,
    payment_method: str = "ach",
    factoring_fee: float = 0.0,
    notes: str = "",
) -> dict | None:
    existing = store.get_settlement(load_id)
    if not existing:
        return None

    result = store.update_settlement(
        load_id,
        payment_amount=payment_amount,
        payment_method=payment_method,
        factoring_fee=factoring_fee,
        payment_status="paid",
        payment_date=_utc_now(),
        notes=notes or existing.get("notes", ""),
    )

    load = store.get_load(load_id)
    if load and result:
        _notify_safe(lambda: notifications.notify_payment_received(load, result))

    return result


def get_settlement(load_id: str) -> dict | None:
    return store.get_settlement(load_id)


def list_settlements(
    payment_status: str | None = None,
    customer: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    invoice_number: str | None = None,
    *,
    page: int | None = None,
    per_page: int | None = None,
) -> list[dict] | dict:
    return store.list_settlements(
        payment_status=payment_status,
        customer=customer,
        date_from=date_from,
        date_to=date_to,
        invoice_number=invoice_number,
        page=page, per_page=per_page,
    )


def get_financial_dashboard() -> dict:
    all_loads = store.list_loads()
    settlements = store.list_settlements()

    total_revenue = 0.0
    total_expenses = 0.0
    total_paid = 0.0
    total_outstanding = 0.0
    loads_with_rate = 0

    for load in all_loads:
        rate = store.get_rate_confirmation(load["load_id"])
        if rate:
            # Round per-load before accumulating, matching
            # store.get_load_profitability_data()'s convention -- summing raw
            # unrounded floats here and store.get_load_profitability_data()
            # rounding per-row before its own sum previously gave two
            # financial reports different totals for the same underlying
            # data (a real, demonstrable penny-level discrepancy, not
            # hypothetical). Round-then-sum everywhere revenue/expenses are
            # aggregated is the one convention to keep.
            total_revenue += round(rate["revenue"], 2)
            loads_with_rate += 1

        expenses = store.list_expenses(load["load_id"])
        total_expenses += round(sum(e["amount"] for e in expenses), 2)

    for stl in settlements:
        if stl["payment_status"] == "paid":
            total_paid += stl["net_payment"]
        elif stl["payment_status"] in ("invoiced", "overdue"):
            total_outstanding += stl["invoice_amount"]

    total_profit = total_revenue - total_expenses
    margin_pct = (total_profit / total_revenue * 100) if total_revenue > 0 else 0.0

    invoiced_count = sum(1 for s in settlements if s["payment_status"] == "invoiced")
    paid_count = sum(1 for s in settlements if s["payment_status"] == "paid")
    overdue_count = sum(1 for s in settlements if s["payment_status"] == "overdue")

    return {
        "total_loads": len(all_loads),
        "loads_with_rate": loads_with_rate,
        "total_revenue": round(total_revenue, 2),
        "total_expenses": round(total_expenses, 2),
        "total_profit": round(total_profit, 2),
        "margin_pct": round(margin_pct, 1),
        "total_paid": round(total_paid, 2),
        "total_outstanding": round(total_outstanding, 2),
        "invoiced_count": invoiced_count,
        "paid_count": paid_count,
        "overdue_count": overdue_count,
    }


def get_chart_data() -> dict:
    """Aggregate data for dashboard charts: loads by status, revenue by month."""
    from collections import defaultdict

    all_loads = store.list_loads()

    status_counts: dict[str, int] = defaultdict(int)
    for load in all_loads:
        status_counts[load["status"]] += 1

    monthly_revenue: dict[str, float] = defaultdict(float)
    monthly_loads: dict[str, int] = defaultdict(int)
    for load in all_loads:
        rate = store.get_rate_confirmation(load["load_id"])
        created = load.get("created_at", "")
        month_key = created[:7] if len(created) >= 7 else "unknown"
        monthly_loads[month_key] += 1
        if rate:
            monthly_revenue[month_key] += rate["revenue"]

    months_sorted = sorted(set(monthly_revenue.keys()) | set(monthly_loads.keys()))

    return {
        "loads_by_status": dict(status_counts),
        "monthly_revenue": [
            {"month": m, "revenue": round(monthly_revenue.get(m, 0), 2),
             "loads": monthly_loads.get(m, 0)}
            for m in months_sorted
        ],
    }


def check_overdue_settlements() -> list[dict]:
    """Scan invoiced settlements and mark overdue if past due date.

    Returns the list of settlements that were newly marked overdue.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    invoiced = store.list_settlements(payment_status="invoiced")
    newly_overdue = []

    for stl in invoiced:
        due = stl.get("due_date", "")
        if not due or due >= now:
            continue

        updated = store.update_settlement(stl["load_id"], payment_status="overdue")
        if updated:
            load = store.get_load(stl["load_id"])
            if load:
                _notify_safe(lambda: notifications.notify_payment_overdue(load, updated))
            newly_overdue.append(updated)

    return newly_overdue


def dispute_settlement(
    load_id: str,
    reason: str = "",
) -> dict | None:
    existing = store.get_settlement(load_id)
    if not existing:
        return None
    if existing["payment_status"] not in ("invoiced", "overdue"):
        raise ValueError(
            f"Cannot dispute settlement in status '{existing['payment_status']}'"
        )
    notes = existing.get("notes", "")
    if reason:
        notes = f"{notes}\nDISPUTE: {reason}".strip()
    result = store.update_settlement(
        load_id, payment_status="disputed", notes=notes,
    )
    load = store.get_load(load_id)
    if load and result:
        _notify_safe(lambda: notifications.notify_settlement_disputed(load, result, reason))
    return result


def write_off_settlement(
    load_id: str,
    reason: str = "",
) -> dict | None:
    existing = store.get_settlement(load_id)
    if not existing:
        return None
    if existing["payment_status"] not in ("invoiced", "overdue", "disputed"):
        raise ValueError(
            f"Cannot write off settlement in status '{existing['payment_status']}'"
        )
    notes = existing.get("notes", "")
    if reason:
        notes = f"{notes}\nWRITE-OFF: {reason}".strip()
    result = store.update_settlement(
        load_id, payment_status="written_off", notes=notes,
    )
    load = store.get_load(load_id)
    if load and result:
        _notify_safe(lambda: notifications.notify_settlement_written_off(load, result, reason))
    return result


_STALL_THRESHOLDS_HOURS: dict[str, int] = {
    "created": 24,
    "dispatched": 12,
    "en_route_pickup": 8,
    "at_pickup": 4,
    "picked_up": 4,
    "in_transit": 48,
    "at_delivery": 4,
    "delivered": 24,
}


def check_stalled_loads(thresholds: dict[str, int] | None = None) -> list[dict]:
    """Find loads that have been in their current status longer than expected.

    Returns loads with added 'hours_in_status' and 'threshold_hours' fields.
    """
    from datetime import datetime, timezone

    limits = thresholds or _STALL_THRESHOLDS_HOURS
    now = datetime.now(timezone.utc)
    stalled = []

    all_loads = store.list_loads()
    for load in all_loads:
        status = load["status"]
        if status not in limits:
            continue
        updated = load.get("updated_at", "")
        if not updated:
            continue
        try:
            ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        hours = (now - ts).total_seconds() / 3600
        if hours >= limits[status]:
            load["hours_in_status"] = round(hours, 1)
            load["threshold_hours"] = limits[status]
            stalled.append(load)

    stalled.sort(key=lambda x: x["hours_in_status"], reverse=True)
    return stalled


def notify_stalled_loads(thresholds: dict[str, int] | None = None) -> list[dict]:
    """Check for stalled loads and send email notifications for each.

    Returns the list of stalled loads that were notified.
    """
    stalled = check_stalled_loads(thresholds)
    for load in stalled:
        _notify_safe(lambda: notifications.notify_stalled(load))
    return stalled


# ── Driver Management ───────────────────────────────────────────────


def create_driver(
    name: str,
    license_number: str = "",
    license_class: str = "",
    phone: str = "",
    email: str = "",
    hire_date: str = "",
    notes: str = "",
) -> dict:
    drv = Driver(
        name=name,
        license_number=license_number,
        license_class=license_class,
        phone=phone,
        email=email,
        hire_date=hire_date,
        notes=notes,
    )
    return store.create_driver(drv)


def get_driver(driver_id: str) -> dict | None:
    return store.get_driver(driver_id)


def get_driver_by_phone(phone: str) -> dict | None:
    return store.get_driver_by_phone(phone)


def reviewer_contact_email() -> str:
    """Level 1 Transport's own dispatch contact address, for the Driver Portal's
    contact-retrieval capability. Email only -- no SMS/phone channel is configured
    anywhere in this codebase (Email API is Dispatch's only communication channel
    per CLAUDE.md's tech stack), so surfacing a phone number here would be invented,
    not retrieved."""
    from cin_lite import email_delivery
    return email_delivery.reviewer_address()


def get_load_contacts(load_id: str) -> dict:
    """Who to reach about this load: Level 1 Transport's own dispatch address,
    plus the first broker contact on file matching the load's broker_shipper
    (same substring lookup the Driver Portal has always used). Shared by the
    Driver Portal and the Stakeholder Portal so both surfaces resolve "who do
    I call" identically instead of drifting.

    An unknown load_id still returns a dict with dispatch_email populated
    (fail-open on contact info, not a crash) with broker_contact: None.
    """
    dispatch_email = reviewer_contact_email()
    load = store.get_load(load_id)
    if not load:
        return {"dispatch_email": dispatch_email, "broker_contact": None}

    broker_contact = None
    if load.get("broker_shipper"):
        matches = store.list_broker_contacts(search=load["broker_shipper"])
        broker_contact = matches[0] if matches else None

    return {"dispatch_email": dispatch_email, "broker_contact": broker_contact}


def list_drivers(
    status: str | None = None,
    name: str | None = None,
    *,
    page: int | None = None,
    per_page: int | None = None,
) -> list[dict] | dict:
    return store.list_drivers(status=status, name=name, page=page, per_page=per_page)


def update_driver(driver_id: str, **fields) -> dict | None:
    return store.update_driver(driver_id, **fields)


def deactivate_driver(driver_id: str) -> dict | None:
    return store.update_driver(driver_id, status="inactive")


def delete_driver(driver_id: str) -> bool:
    return store.delete_driver(driver_id)


def get_driver_by_name(name: str) -> dict | None:
    """Look up a driver by exact name match."""
    all_drivers = store.list_drivers(status="active")
    for d in all_drivers:
        if d["name"] == name:
            return d
    return None


# ── Equipment Management ────────────────────────────────────────────


def create_equipment(
    unit_number: str,
    equipment_type: str = "dry_van",
    make: str = "",
    model: str = "",
    year: str = "",
    vin: str = "",
    license_plate: str = "",
    notes: str = "",
) -> dict:
    eqp = Equipment(
        unit_number=unit_number,
        equipment_type=equipment_type,
        make=make,
        model=model,
        year=year,
        vin=vin,
        license_plate=license_plate,
        notes=notes,
    )
    return store.create_equipment(eqp)


def get_equipment(equipment_id: str) -> dict | None:
    return store.get_equipment(equipment_id)


def list_equipment(
    status: str | None = None,
    equipment_type: str | None = None,
    unit_number: str | None = None,
    *,
    page: int | None = None,
    per_page: int | None = None,
) -> list[dict] | dict:
    return store.list_equipment(
        status=status, equipment_type=equipment_type,
        unit_number=unit_number, page=page, per_page=per_page,
    )


def update_equipment(equipment_id: str, **fields) -> dict | None:
    return store.update_equipment(equipment_id, **fields)


def retire_equipment(equipment_id: str) -> dict | None:
    return store.update_equipment(equipment_id, status="retired")


def delete_equipment(equipment_id: str) -> bool:
    return store.delete_equipment(equipment_id)


# ── Activities ─────────────────────────────────────────────────────────


def add_activity(
    load_id: str,
    message: str,
    activity_type: str = "comment",
    author: str = "",
    source: str = "user",
) -> dict:
    from dispatch.models import LoadActivity

    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load {load_id} not found")
    activity = LoadActivity(
        load_id=load_id,
        activity_type=activity_type,
        message=message,
        author=author,
        source=source,
    )
    return store.create_activity(activity)


def list_activities(load_id: str, activity_type: str | None = None) -> list[dict]:
    return store.list_activities(load_id, activity_type=activity_type)


def delete_activity(activity_id: str) -> bool:
    return store.delete_activity(activity_id)


def get_fleet_summary() -> dict:
    """Aggregate fleet stats: active/inactive counts for drivers and equipment."""
    drivers = store.list_drivers()
    equipment = store.list_equipment()

    driver_by_status = {}
    for d in drivers:
        s = d["status"]
        driver_by_status[s] = driver_by_status.get(s, 0) + 1

    equip_by_status = {}
    equip_by_type = {}
    for e in equipment:
        s = e["status"]
        equip_by_status[s] = equip_by_status.get(s, 0) + 1
        if s == "active":
            t = e["equipment_type"]
            equip_by_type[t] = equip_by_type.get(t, 0) + 1

    active_loads = [
        ld for ld in store.list_loads()
        if ld["status"] not in ("archived", "cancelled", "completed")
    ]
    assigned_driver_ids = {ld["driver_id"] for ld in active_loads if ld.get("driver_id")}
    assigned_equip_ids = {ld["equipment_id"] for ld in active_loads if ld.get("equipment_id")}
    active_driver_count = driver_by_status.get("active", 0)
    active_equip_count = equip_by_status.get("active", 0)

    return {
        "total_drivers": len(drivers),
        "drivers_by_status": driver_by_status,
        "total_equipment": len(equipment),
        "equipment_by_status": equip_by_status,
        "active_equipment_by_type": equip_by_type,
        "drivers_assigned": len(assigned_driver_ids),
        "drivers_available": max(0, active_driver_count - len(assigned_driver_ids)),
        "equipment_assigned": len(assigned_equip_ids),
        "equipment_available": max(0, active_equip_count - len(assigned_equip_ids)),
    }


def get_load_bundle(load_id: str) -> dict | None:
    load = store.get_load(load_id)
    if not load:
        return None

    assigned_driver = None
    if load.get("driver_id"):
        assigned_driver = store.get_driver(load["driver_id"])
    assigned_equipment = None
    if load.get("equipment_id"):
        assigned_equipment = store.get_equipment(load["equipment_id"])

    return {
        "load": load,
        "visibility": store.get_visibility(load_id),
        "milestones": store.list_milestones(load_id),
        "evidence": store.list_evidence(load_id),
        "exceptions": store.list_exceptions(load_id=load_id),
        "pods": store.list_pods(load_id),
        "retention": store.get_retention_by_load(load_id),
        "financials": get_financials(load_id),
        "settlement": store.get_settlement(load_id),
        "assigned_driver": assigned_driver,
        "assigned_equipment": assigned_equipment,
        "activities": store.list_activities(load_id),
        "active_drivers": store.list_drivers(status="active"),
        "active_equipment": store.list_equipment(status="active"),
        "lane_history": get_lane_history(load_id),
        "detentions": store.list_detentions(load_id=load_id),
    }


def _sanitize_retention_for_stakeholder(retention: dict | None) -> dict | None:
    """Strip server-internal fields before a retention record reaches the
    external stakeholder portal: `archive_location` is a filesystem path,
    and `financial_summary` is exactly get_financials()['summary'] --
    Level 1 Transport's own profit/margin_pct on the load, not a
    rate/fee/cost figure covered by D11's disclosure rule."""
    if not retention:
        return None
    return {
        "final_status": retention.get("final_status", ""),
        "retention_status": retention.get("retention_status", ""),
        "archived_at": retention.get("archived_at", ""),
        "evidence_count": len(retention.get("evidence_index") or []),
    }


def get_publisher_status(load_id: str) -> dict:
    """Look up Publisher packet status for a freight load.

    Publisher's queue (portal/models/publisher.py::create_action()) is keyed
    by sandbox_id, a GovCon/sandbox-oriented concept -- freight loads have no
    sandbox_id of their own and there is no load_id field on a Publisher
    action. This reuses the synthetic sandbox_id convention already
    established for freight loads elsewhere in this codebase (End Load ->
    Publisher routing, portal/routes/dispatch_api.py's end_load(), which
    calls publisher.create_action(sandbox_id=f"LOAD-{load_id}", ...), mirroring
    cin_lite's analogous f"GOVCON-{contract_id}" convention in
    portal/routes/api.py) rather than inventing a new one or adding a
    load_id field to Publisher's schema.
    """
    from portal.models import publisher

    sandbox_id = f"LOAD-{load_id}"
    matches = [a for a in publisher.get_queue() if a.get("sandbox_id") == sandbox_id]
    if not matches:
        return {"has_packet": False, "status": None, "action_type": None}

    matches.sort(key=lambda a: a.get("updated_at", ""), reverse=True)
    latest = matches[0]
    return {
        "has_packet": True,
        "status": latest["status"],
        "action_type": latest["action_type"],
    }


def build_stakeholder_view(load_id: str) -> dict | None:
    """Assemble the read-only payload shown to an external stakeholder
    (broker/shipper/customer -- per D11 these are genuinely distinct
    parties in a Manufacturer -> Shipper -> Broker -> Level 1 Transport
    chain, not synonyms) via the HMAC-token-secured stakeholder portal.

    Deliberately narrower than get_load_bundle():
      - rate/fee/cost figures (rate confirmation, settlement/invoice) ARE
        included -- D11 establishes an open-disclosure rule for these
        parties, so there is no "curtain" to build here.
      - Level 1 Transport's own internal economics (expense breakdown,
        profit, margin_pct from get_financials()) are EXCLUDED -- D11
        covers disclosure of rate/fee/cost to the parties in the chain,
        not disclosure of Level 1 Transport's own P&L on the load.
      - the internal activity/comment thread, driver personal contact
        info (phone/email/license), and internal_note are EXCLUDED
        regardless of D11, since none of those are rate/fee/cost figures
        in the first place.
      - this view itself still returns evidence as metadata only (type/
        description/capture_time, no file_path, no download link) -- the
        file itself is served separately by the token-scoped download
        route, portal/routes/stakeholder.py::stakeholder_evidence_download
        (GET /portal/loads/<load_id>/evidence/<evidence_id>?token=...),
        which re-verifies the same stakeholder token and additionally
        confirms the evidence record's own load_id matches the load_id in
        the URL before serving anything (a stakeholder token is scoped to
        one load; without that check a valid token for load A could be
        used to enumerate and download evidence belonging to load B).
    """
    load = store.get_load(load_id)
    if not load:
        return None

    mission_visibility = get_mission_visibility(load_id)
    rate = store.get_rate_confirmation(load_id)
    settlement = store.get_settlement(load_id)

    assigned_driver = None
    if load.get("driver_id"):
        driver = store.get_driver(load["driver_id"])
        if driver:
            assigned_driver = {"name": driver.get("name", "")}

    assigned_equipment = None
    if load.get("equipment_id"):
        equipment = store.get_equipment(load["equipment_id"])
        if equipment:
            assigned_equipment = {
                "unit_number": equipment.get("unit_number", ""),
                "equipment_type": equipment.get("equipment_type", ""),
            }

    return {
        "load": {
            "load_id": load["load_id"],
            "customer": load.get("customer", ""),
            "broker_shipper": load.get("broker_shipper", ""),
            "pickup_location": load.get("pickup_location", ""),
            "delivery_location": load.get("delivery_location", ""),
            "pickup_datetime": load.get("pickup_datetime", ""),
            "delivery_datetime": load.get("delivery_datetime", ""),
            "status": load.get("status", ""),
        },
        "customer_note": mission_visibility["customer_note"],
        "next_expected_milestone": mission_visibility["next_expected_milestone"],
        "milestones": [
            {
                "event_type": m.get("event_type", ""),
                "event_time": m.get("event_time", ""),
                "location": m.get("location", ""),
                "note": m.get("note", ""),
            }
            for m in store.list_milestones(load_id)
        ],
        "evidence": [
            {
                "evidence_type": e.get("evidence_type", ""),
                "description": e.get("description", ""),
                "capture_time": e.get("capture_time", ""),
            }
            for e in store.list_evidence(load_id)
        ],
        "exceptions": [
            {
                "exception_type": x.get("exception_type", ""),
                "severity": x.get("severity", ""),
                "description": x.get("description", ""),
                "status": x.get("status", ""),
                "first_reported": x.get("first_reported", ""),
                "resolution_note": x.get("resolution_note", ""),
                "resolved_at": x.get("resolved_at", ""),
            }
            for x in store.list_exceptions(load_id=load_id)
        ],
        "pods": [
            {
                "generated_at": p.get("generated_at", ""),
                "status": p.get("status", ""),
                "recipient": p.get("recipient", ""),
                "evidence_count": len(p.get("evidence_ids") or []),
            }
            for p in store.list_pods(load_id)
        ],
        "retention": _sanitize_retention_for_stakeholder(store.get_retention_by_load(load_id)),
        "rate_confirmation": rate,
        "settlement": settlement,
        "assigned_driver": assigned_driver,
        "assigned_equipment": assigned_equipment,
        "comi_status": get_comi_status(load_id),
        "contacts": get_load_contacts(load_id),
        "publisher_status": get_publisher_status(load_id),
    }


def get_lane_history(load_id: str) -> list[dict]:
    """Find past loads on the same origin-destination lane, with rate info."""
    load = store.get_load(load_id)
    if not load:
        return []
    history = store.get_lane_history(
        load.get("pickup_location", ""),
        load.get("delivery_location", ""),
        exclude_load_id=load_id,
    )
    for h in history:
        rate = store.get_rate_confirmation(h["load_id"])
        h["rate_amount"] = rate["rate_amount"] if rate else None
        h["revenue"] = rate["revenue"] if rate else None
    return history


# ── Detention Tracking ──────────────────────────────────────────────


def start_detention(
    load_id: str,
    location_type: str = "pickup",
    free_hours: float = 2.0,
    hourly_rate: float = 75.0,
    notes: str = "",
    started_at: str = "",
) -> dict:
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")

    active = store.list_detentions(load_id=load_id, status="active")
    if active:
        raise ValueError("Load already has an active detention event")

    det = DetentionEvent(
        load_id=load_id,
        location_type=location_type,
        free_hours=free_hours,
        hourly_rate=hourly_rate,
        notes=notes,
        started_at=started_at or _utc_now(),
    )
    return store.create_detention(det)


def stop_detention(
    detention_id: str,
    ended_at: str = "",
    create_expense: bool = True,
) -> dict | None:
    det = store.get_detention(detention_id)
    if not det:
        return None
    if det["status"] != "active":
        raise ValueError(f"Detention is not active (status: {det['status']})")

    end_time = ended_at or _utc_now()
    updates: dict = {"ended_at": end_time, "status": "completed"}
    result = store.update_detention(detention_id, **updates)
    if not result:
        return None

    if create_expense and result["billable_amount"] > 0:
        exp = add_expense(
            load_id=result["load_id"],
            category="detention",
            description=f"Detention at {result['location_type']} — {result['billable_hours']:.1f}h billable",
            amount=result["billable_amount"],
            notes=result.get("notes", ""),
        )
        store.update_detention(detention_id, expense_id=exp["expense_id"], status="billed")
        result = store.get_detention(detention_id)

    return result


def update_detention(detention_id: str, **fields) -> dict | None:
    return store.update_detention(detention_id, **fields)


def delete_detention(detention_id: str) -> bool:
    return store.delete_detention(detention_id)


def list_detentions(load_id: str | None = None, status: str | None = None) -> list[dict]:
    return store.list_detentions(load_id=load_id, status=status)


def get_detention(detention_id: str) -> dict | None:
    return store.get_detention(detention_id)


def get_detention_summary() -> dict:
    all_detentions = store.list_detentions()
    total_events = len(all_detentions)
    active_count = sum(1 for d in all_detentions if d["status"] == "active")
    completed = [d for d in all_detentions if d["status"] in ("completed", "billed")]
    total_hours = sum(d.get("total_hours", 0) for d in completed)
    total_billable = sum(d.get("billable_amount", 0) for d in completed)
    pickup_count = sum(1 for d in all_detentions if d["location_type"] == "pickup")
    delivery_count = sum(1 for d in all_detentions if d["location_type"] == "delivery")

    return {
        "total_events": total_events,
        "active_count": active_count,
        "completed_count": len(completed),
        "total_hours": round(total_hours, 1),
        "total_billable": round(total_billable, 2),
        "pickup_count": pickup_count,
        "delivery_count": delivery_count,
    }


# ── Lane Templates ──────────────────────────────────────────────────


def create_lane_template(
    name: str,
    customer: str = "",
    broker_shipper: str = "",
    pickup_location: str = "",
    delivery_location: str = "",
    equipment: str = "",
    notes: str = "",
) -> dict:
    from dispatch.models import LaneTemplate
    tpl = LaneTemplate(
        name=name,
        customer=customer,
        broker_shipper=broker_shipper,
        pickup_location=pickup_location,
        delivery_location=delivery_location,
        equipment=equipment,
        notes=notes,
    )
    return store.create_lane_template(tpl)


def get_lane_template(template_id: str) -> dict | None:
    return store.get_lane_template(template_id)


def list_lane_templates() -> list[dict]:
    return store.list_lane_templates()


def update_lane_template(template_id: str, **fields) -> dict | None:
    return store.update_lane_template(template_id, **fields)


def delete_lane_template(template_id: str) -> bool:
    return store.delete_lane_template(template_id)


def create_load_from_template(template_id: str) -> dict | None:
    tpl = store.get_lane_template(template_id)
    if not tpl:
        return None
    load = create_load(
        customer=tpl["customer"],
        broker_shipper=tpl["broker_shipper"],
        pickup_location=tpl["pickup_location"],
        delivery_location=tpl["delivery_location"],
        equipment=tpl["equipment"],
        notes=tpl["notes"],
    )
    store.increment_lane_template_usage(template_id)
    return load


# ── Broker Scorecard ────────────────────────────────────────────────


def get_broker_scorecards() -> list[dict]:
    return store.get_broker_scorecards()


def get_broker_detail(broker_name: str) -> dict:
    loads = store.get_broker_loads(broker_name)
    for ld in loads:
        rate = store.get_rate_confirmation(ld["load_id"])
        ld["rate_amount"] = rate["rate_amount"] if rate else None
        ld["revenue"] = rate["revenue"] if rate else None
        settlement = store.get_settlement(ld["load_id"])
        ld["payment_status"] = settlement["payment_status"] if settlement else None
    return {"broker": broker_name, "loads": loads}


# ── Load Calendar ───────────────────────────────────────────────────


def get_load_calendar(year: int, month: int) -> dict:
    from collections import defaultdict
    import calendar

    all_loads = store.list_loads()
    pickup_by_day: dict[str, list[dict]] = defaultdict(list)
    delivery_by_day: dict[str, list[dict]] = defaultdict(list)

    month_prefix = f"{year:04d}-{month:02d}"
    for ld in all_loads:
        p = ld.get("pickup_datetime", "")
        if p and p[:7] == month_prefix:
            pickup_by_day[p[:10]].append(ld)
        d = ld.get("delivery_datetime", "")
        if d and d[:7] == month_prefix:
            delivery_by_day[d[:10]].append(ld)

    cal = calendar.Calendar(firstweekday=6)
    weeks = cal.monthdayscalendar(year, month)

    return {
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "weeks": weeks,
        "pickups": dict(pickup_by_day),
        "deliveries": dict(delivery_by_day),
    }


def global_search(query: str) -> dict:
    return store.global_search(query)


def list_uninvoiced_loads() -> list[dict]:
    return store.list_uninvoiced_loads()


def get_load_source_stats() -> dict:
    all_loads = store.list_loads()
    by_source: dict[str, int] = {}
    for ld in all_loads:
        src = ld.get("source", "") or "unset"
        by_source[src] = by_source.get(src, 0) + 1
    return {
        "total": len(all_loads),
        "by_source": by_source,
    }


_DUPLICATE_FIELDS = (
    "customer", "broker_shipper", "pickup_location", "delivery_location",
    "pickup_datetime", "delivery_datetime", "equipment", "notes",
)


def duplicate_load(load_id: str) -> dict:
    source = store.get_load(load_id)
    if not source:
        raise ValueError(f"Load not found: {load_id}")
    kwargs = {k: source.get(k, "") for k in _DUPLICATE_FIELDS}
    return create_load(**kwargs)


# ── IFTA Mileage & Fuel ─────────────────────────────────────────────


# Starting point only, copied from Hold's proven fleet_mpg_out_of_band pattern
# (tuned against Hold's own synthetic data) -- not yet reviewed against
# Dispatch's real equipment profile. Purely informational; never blocks an entry.
DEFAULT_MPG_BAND = (4.0, 9.5)


def _quarter_containing_date(date_str: str) -> tuple[int, int] | None:
    if not date_str:
        return None
    try:
        year = int(date_str[:4])
        month = int(date_str[5:7])
    except (ValueError, IndexError):
        return None
    return year, (month - 1) // 3 + 1


def _fleet_mpg_estimate(date_from: str, date_to: str, vehicle_id: str = "") -> float | None:
    """Independent of IFTA_TAX_RATES and of _ifta_aggregate() -- built from
    the same list_ifta_trip_legs()/list_ifta_fuel_purchases() primitives so
    it keeps working even when _ifta_aggregate() would refuse on a missing
    rate. Returns None on insufficient data rather than raising or guessing."""
    leg_kwargs: dict = {"date_from": date_from, "date_to": date_to}
    fuel_kwargs: dict = {"date_from": date_from, "date_to": date_to}
    if vehicle_id:
        leg_kwargs["vehicle_id"] = vehicle_id
        fuel_kwargs["vehicle_id"] = vehicle_id
    total_miles = sum(leg["miles"] for leg in store.list_ifta_trip_legs(**leg_kwargs))
    total_gallons = sum(p["gallons"] for p in store.list_ifta_fuel_purchases(**fuel_kwargs))
    if total_miles <= 0 or total_gallons <= 0:
        return None
    return total_miles / total_gallons


def add_ifta_trip_leg(
    jurisdiction: str,
    miles: float,
    date: str = "",
    vehicle_id: str = "",
    load_id: str = "",
    notes: str = "",
) -> dict:
    if jurisdiction not in IFTA_JURISDICTIONS:
        raise ValueError(f"Invalid jurisdiction: {jurisdiction}")
    if miles < 0:
        raise ValueError("Miles must be non-negative")
    leg = IFTATripLeg(
        jurisdiction=jurisdiction,
        miles=miles,
        date=date,
        vehicle_id=vehicle_id,
        load_id=load_id,
        notes=notes,
    )
    result = store.create_ifta_trip_leg(leg)

    period = _quarter_containing_date(result["date"])
    if period:
        date_from, date_to = _quarter_date_range(*period)
        mpg = _fleet_mpg_estimate(date_from, date_to, vehicle_id)
        if mpg is not None:
            low, high = DEFAULT_MPG_BAND
            if not (low <= mpg <= high):
                result["plausibility_warning"] = (
                    f"fleet_mpg {mpg:.2f} outside plausible range "
                    f"[{low}, {high}] for this period — mileage or fuel entry may be off"
                )
    return result


def update_ifta_trip_leg(leg_id: str, **kwargs) -> dict:
    existing = store.get_ifta_trip_leg(leg_id)
    if not existing:
        raise ValueError(f"Trip leg not found: {leg_id}")
    allowed = {"jurisdiction", "miles", "date", "vehicle_id", "load_id", "notes"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if "jurisdiction" in updates:
        if updates["jurisdiction"] not in IFTA_JURISDICTIONS:
            raise ValueError(f"Invalid jurisdiction: {updates['jurisdiction']}")
    if "miles" in updates and updates["miles"] < 0:
        raise ValueError("Miles must be non-negative")
    if not updates:
        return existing
    result = store.update_ifta_trip_leg(leg_id, updates)
    if not result:
        raise ValueError(f"Trip leg not found: {leg_id}")
    return result


def delete_ifta_trip_leg(leg_id: str) -> bool:
    return store.delete_ifta_trip_leg(leg_id)


def list_ifta_trip_legs(**kwargs) -> list[dict]:
    return store.list_ifta_trip_legs(**kwargs)


def add_ifta_fuel_purchase(
    jurisdiction: str,
    gallons: float,
    amount: float,
    date: str = "",
    vehicle_id: str = "",
    vendor: str = "",
    notes: str = "",
    extraction_confidence: float | None = None,
) -> dict:
    if jurisdiction not in IFTA_JURISDICTIONS:
        raise ValueError(f"Invalid jurisdiction: {jurisdiction}")
    if gallons < 0:
        raise ValueError("Gallons must be non-negative")
    if amount < 0:
        raise ValueError("Amount must be non-negative")
    purchase = IFTAFuelPurchase(
        jurisdiction=jurisdiction,
        gallons=gallons,
        amount=amount,
        date=date,
        vehicle_id=vehicle_id,
        vendor=vendor,
        notes=notes,
        extraction_confidence=extraction_confidence,
    )
    return store.create_ifta_fuel_purchase(purchase)


def update_ifta_fuel_purchase(purchase_id: str, **kwargs) -> dict:
    existing = store.get_ifta_fuel_purchase(purchase_id)
    if not existing:
        raise ValueError(f"Fuel purchase not found: {purchase_id}")
    allowed = {"jurisdiction", "gallons", "amount", "date", "vehicle_id", "vendor", "notes"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if "jurisdiction" in updates:
        if updates["jurisdiction"] not in IFTA_JURISDICTIONS:
            raise ValueError(f"Invalid jurisdiction: {updates['jurisdiction']}")
    if not updates:
        return existing
    result = store.update_ifta_fuel_purchase(purchase_id, updates)
    if not result:
        raise ValueError(f"Fuel purchase not found: {purchase_id}")
    return result


def delete_ifta_fuel_purchase(purchase_id: str) -> bool:
    return store.delete_ifta_fuel_purchase(purchase_id)


def list_ifta_fuel_purchases(**kwargs) -> list[dict]:
    return store.list_ifta_fuel_purchases(**kwargs)


DEFAULT_SUSPECT_CONFIDENCE_THRESHOLD = 0.75  # Hold's own placeholder (validators.py) -- not yet calibrated


def list_suspect_ifta_fuel_purchases(
    year: int, quarter: int, vehicle_id: str = "",
    threshold: float = DEFAULT_SUSPECT_CONFIDENCE_THRESHOLD,
) -> list[dict]:
    """Read-only: fuel purchases in this quarter whose scan-time
    extraction_confidence is below threshold. No recomputation -- that
    number was already produced once, at scan time (Phase 6b), and is
    simply read back here, direct port of Hold's own _suspect_entries()
    contract. A manually-entered purchase (extraction_confidence is
    None) never qualifies -- there was no OCR to be uncertain about."""
    if quarter not in (1, 2, 3, 4):
        raise ValueError(f"Invalid quarter: {quarter}")
    date_from, date_to = _quarter_date_range(year, quarter)
    kwargs: dict = {"date_from": date_from, "date_to": date_to}
    if vehicle_id:
        kwargs["vehicle_id"] = vehicle_id
    purchases = store.list_ifta_fuel_purchases(**kwargs)
    return [
        p for p in purchases
        if p.get("extraction_confidence") is not None and p["extraction_confidence"] < threshold
    ]


def attach_ifta_fuel_evidence(
    purchase_id: str,
    file_data: bytes,
    original_filename: str,
    description: str = "",
    uploaded_by: str = "",
) -> dict:
    """Attaches a checksummed receipt upload to an existing fuel purchase.

    Mirrors attach_evidence()'s upload handling (checksum, mime-type
    guess, _save_upload()) but writes to ifta_fuel_evidence / IFTAFuelEvidence
    instead of the load-scoped evidence table -- see IFTAFuelEvidence's
    docstring for why those can't be shared. A purchase must already
    exist (two-step flow: create the purchase, then attach its receipt --
    matching the existing load-evidence UI's own create-then-attach
    pattern rather than a combined form)."""
    purchase = store.get_ifta_fuel_purchase(purchase_id)
    if not purchase:
        raise ValueError(f"Fuel purchase not found: {purchase_id}")

    ev = IFTAFuelEvidence(
        purchase_id=purchase_id,
        description=description,
        uploaded_by=uploaded_by,
        original_filename=original_filename,
    )
    ev.compute_checksum(file_data)
    ev.file_size = len(file_data)
    import mimetypes
    ev.mime_type = mimetypes.guess_type(original_filename or "file.pdf")[0] or "application/octet-stream"
    saved = _save_upload(ev.evidence_id, original_filename or "file.pdf", file_data)
    ev.file_path = str(saved)

    created = store.create_ifta_fuel_evidence(ev)
    store.update_ifta_fuel_purchase(purchase_id, {"evidence_id": ev.evidence_id})
    return created


def get_ifta_fuel_evidence_file(evidence_id: str) -> tuple[Path, str] | None:
    ev = store.get_ifta_fuel_evidence(evidence_id)
    if not ev or not ev.get("file_path"):
        return None
    p = Path(ev["file_path"])
    if not p.is_file():
        return None
    return p, ev.get("original_filename") or p.name


def list_ifta_fuel_evidence(purchase_id: str) -> list[dict]:
    return store.list_ifta_fuel_evidence(purchase_id)


def resolve_ifta_evidence_for_snapshot(snapshot: dict) -> list[dict]:
    """Resolves each jurisdiction line's contributing fuel purchases to
    their linked receipt, if any. Direct port of Hold's
    _resolve_line_evidence() spirit: a purchase with no evidence link is
    included with evidence=None rather than raising -- evidence bundling
    must never block a report that was already computed or already
    approved."""
    resolved = []
    for jur_line in snapshot.get("jurisdictions", []):
        purchases_resolved = []
        for purchase_id in jur_line.get("purchase_ids", []):
            purchase = store.get_ifta_fuel_purchase(purchase_id)
            if not purchase:
                continue
            evidence = None
            if purchase.get("evidence_id"):
                evidence = store.get_ifta_fuel_evidence(purchase["evidence_id"])
            purchases_resolved.append({"purchase": purchase, "evidence": evidence})
        resolved.append({
            "jurisdiction": jur_line["jurisdiction"],
            "purchases": purchases_resolved,
        })
    return resolved


def _quarter_date_range(year: int, quarter: int) -> tuple[str, str]:
    starts = {1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01"}
    ends = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
    return f"{year}-{starts[quarter]}", f"{year}-{ends[quarter]}"


def _ifta_aggregate(date_from: str, date_to: str, vehicle_id: str = "") -> dict:
    from dispatch.models import IFTA_TAX_RATES

    leg_kwargs: dict = {"date_from": date_from, "date_to": date_to}
    fuel_kwargs: dict = {"date_from": date_from, "date_to": date_to}
    if vehicle_id:
        leg_kwargs["vehicle_id"] = vehicle_id
        fuel_kwargs["vehicle_id"] = vehicle_id

    legs = store.list_ifta_trip_legs(**leg_kwargs)
    purchases = store.list_ifta_fuel_purchases(**fuel_kwargs)

    miles_by_jur: dict[str, float] = {}
    legs_by_jur: dict[str, list[str]] = {}
    for leg in legs:
        j = leg["jurisdiction"]
        miles_by_jur[j] = miles_by_jur.get(j, 0) + leg["miles"]
        legs_by_jur.setdefault(j, []).append(leg["leg_id"])

    fuel_by_jur: dict[str, dict] = {}
    purchases_by_jur: dict[str, list[str]] = {}
    for p in purchases:
        j = p["jurisdiction"]
        if j not in fuel_by_jur:
            fuel_by_jur[j] = {"gallons": 0.0, "amount": 0.0}
        fuel_by_jur[j]["gallons"] += p["gallons"]
        fuel_by_jur[j]["amount"] += p["amount"]
        purchases_by_jur.setdefault(j, []).append(p["purchase_id"])

    total_miles = sum(miles_by_jur.values())
    total_gallons = sum(f["gallons"] for f in fuel_by_jur.values())
    fleet_mpg = round(total_miles / total_gallons, 4) if total_gallons > 0 else 0.0

    all_jurs = sorted(set(list(miles_by_jur.keys()) + list(fuel_by_jur.keys())))

    missing_rate_jurs = sorted(j for j in all_jurs if j not in IFTA_TAX_RATES)
    if missing_rate_jurs:
        raise ValueError(
            f"No IFTA tax rate on file for jurisdiction(s) {missing_rate_jurs} "
            f"— refusing to report a fabricated $0.00 rate. Add the missing "
            f"rate(s) to IFTA_TAX_RATES before generating this report."
        )

    jurisdictions = []
    total_tax_owed = 0.0
    total_surcharge = 0.0
    for j in all_jurs:
        miles = round(miles_by_jur.get(j, 0), 2)
        fuel = fuel_by_jur.get(j, {"gallons": 0.0, "amount": 0.0})
        taxable_gallons = round(miles / fleet_mpg, 4) if fleet_mpg > 0 else 0.0
        net_taxable = round(taxable_gallons - fuel["gallons"], 4)
        rates = IFTA_TAX_RATES[j]
        tax_rate = rates["rate"]
        surcharge_rate = rates["surcharge"]
        tax_owed = round(net_taxable * tax_rate, 2)
        surcharge = round(net_taxable * surcharge_rate, 2) if surcharge_rate else 0.0
        total_tax_owed += tax_owed
        total_surcharge += surcharge
        jurisdictions.append({
            "jurisdiction": j,
            "miles": miles,
            "fuel_gallons": round(fuel["gallons"], 4),
            "fuel_amount": round(fuel["amount"], 2),
            "taxable_gallons": taxable_gallons,
            "net_taxable_gallons": net_taxable,
            "tax_rate": tax_rate,
            "surcharge_rate": surcharge_rate,
            "tax_owed": tax_owed,
            "surcharge": surcharge,
            "total_due": round(tax_owed + surcharge, 2),
            "leg_ids": legs_by_jur.get(j, []),
            "purchase_ids": purchases_by_jur.get(j, []),
        })

    return {
        "date_from": date_from,
        "date_to": date_to,
        "vehicle_id": vehicle_id,
        "total_miles": round(total_miles, 2),
        "total_gallons": round(total_gallons, 4),
        "fleet_mpg": fleet_mpg,
        "jurisdictions": jurisdictions,
        "trip_leg_count": len(legs),
        "fuel_purchase_count": len(purchases),
        "total_tax_owed": round(total_tax_owed, 2),
        "total_surcharge": round(total_surcharge, 2),
        "total_due": round(total_tax_owed + total_surcharge, 2),
    }


def get_ifta_quarterly_report(year: int, quarter: int, vehicle_id: str = "") -> dict:
    if quarter not in (1, 2, 3, 4):
        raise ValueError(f"Invalid quarter: {quarter}")

    date_from, date_to = _quarter_date_range(year, quarter)
    result = _ifta_aggregate(date_from, date_to, vehicle_id)
    result["year"] = year
    result["quarter"] = quarter
    result["quarter_label"] = f"Q{quarter} {year}"
    return result


def get_ifta_monthly_report(year: int, month: int, vehicle_id: str = "") -> dict:
    import calendar
    if month < 1 or month > 12:
        raise ValueError(f"Invalid month: {month}")

    last_day = calendar.monthrange(year, month)[1]
    date_from = f"{year}-{month:02d}-01"
    date_to = f"{year}-{month:02d}-{last_day:02d}"
    result = _ifta_aggregate(date_from, date_to, vehicle_id)
    result["year"] = year
    result["month"] = month
    result["month_label"] = f"{calendar.month_name[month]} {year}"
    return result


def export_ifta_csv(report: dict) -> str:
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    label = report.get("quarter_label") or report.get("month_label", "IFTA Report")
    writer.writerow(["IFTA Report", label])
    writer.writerow(["Date Range", report["date_from"], "to", report["date_to"]])
    if report.get("vehicle_id"):
        writer.writerow(["Vehicle", report["vehicle_id"]])
    writer.writerow(["Fleet MPG", report["fleet_mpg"]])
    writer.writerow(["Total Miles", report["total_miles"]])
    writer.writerow(["Total Gallons", report["total_gallons"]])
    writer.writerow([])

    writer.writerow([
        "Jurisdiction", "Miles", "Taxable Gallons",
        "Fuel Purchased (gal)", "Fuel Cost ($)",
        "Net Taxable Gallons", "Tax Rate ($/gal)",
        "Surcharge Rate", "Tax Owed", "Surcharge", "Total Due",
    ])
    for j in report["jurisdictions"]:
        writer.writerow([
            j["jurisdiction"], j["miles"], j["taxable_gallons"],
            j["fuel_gallons"], j["fuel_amount"],
            j["net_taxable_gallons"], j["tax_rate"],
            j["surcharge_rate"], j["tax_owed"],
            j["surcharge"], j["total_due"],
        ])
    writer.writerow([])
    writer.writerow(["TOTALS", report["total_miles"], "", report["total_gallons"],
                      "", "", "", "", report["total_tax_owed"],
                      report["total_surcharge"], report["total_due"]])

    return output.getvalue()


# ── IFTA Report Approvals (Phase 4 finalization gate) ────────────────
#
# Direct port of Hold's proven draft/sealed pipeline
# (src/dispatch/ifta_clerk/prepare.py, src/dispatch/ifta/package.py,
# src/dispatch/ifta_clerk/recommend.py), adapted to Dispatch's own
# architecture: Dispatch has no Queue, so "submitted for approval" is
# gated by an emailed, HMAC-signed link (reusing cin_lite.email_delivery's
# existing generic token functions) instead of a Queue item; Dispatch has
# no persisted worksheet table, so the report snapshot is frozen into a
# new IFTAReportApproval row at submission time instead of being read from
# one that already existed. QuickBooks/accounting integration is
# deliberately not implemented -- see compute_ifta_payment_recommendation()
# below, ported verbatim in spirit from Hold's compute_payment_recommendation().


class IFTAApprovalError(ValueError):
    """Base class for IFTA report-approval failures."""


class AlreadySubmittedError(IFTAApprovalError):
    pass


class InvalidApprovalTokenError(IFTAApprovalError):
    pass


def _resolve_compliance_root() -> Path:
    """Sibling of cin_lite.archive's CIN root, not nested under it --
    Phase 3 found cin_lite/archive.py's ARCHIVE_ROOT resolves to
    <root>/CIN specifically (the federal-contract-intelligence domain);
    IFTA compliance records belong in their own top-level folder under
    the same DISPATCH_ARCHIVE_ROOT, not inside a folder named for an
    unrelated domain."""
    import os

    archive_root = os.environ.get("DISPATCH_ARCHIVE_ROOT")
    if archive_root:
        root = Path(archive_root) / "Compliance"
    else:
        root = Path(__file__).resolve().parent.parent / "cin_lite" / "Compliance"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_compliance_record(record_type: str, record_id: str, payload: dict) -> Path:
    """Writes one JSON artifact plus a SHA-256 sidecar, the same
    write-and-hash technique Phase 3 proved in cin_lite/archive.py,
    reimplemented locally (not cross-imported) to keep this package's
    archival separate from cin_lite's, per Phase 3's own two-archives
    finding."""
    import hashlib
    import json

    subdir = _resolve_compliance_root() / record_type
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{record_id}.json"
    content = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    path.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    sidecar = path.with_name(path.name + ".sha256")
    sidecar.write_text(
        json.dumps({"sha256": digest, "written_at": _utc_now()}), encoding="utf-8"
    )
    return path


def compute_ifta_payment_recommendation(snapshot: dict) -> dict:
    """Pure -- no file I/O, no database access, no network access.
    Direct port of Hold's compute_payment_recommendation(): wraps an
    already-computed, already-approved total_due in a recommendation
    label, inventing no new number. A negative total_due (a net credit)
    is reported as a positive "credit" amount, never a negative figure."""
    total_due = snapshot["total_due"]
    if total_due > 0:
        recommendation, amount = "remit", total_due
    elif total_due < 0:
        recommendation, amount = "credit", abs(total_due)
    else:
        recommendation, amount = "no_payment_due", 0.0
    return {
        "status": "recommendation",
        "recommendation": recommendation,
        "amount": amount,
        "total_due": total_due,
        "generated_at": _utc_now(),
    }


DEFAULT_CORNER_CLIP_MILES = 5.0


def _exc(exception_type: str, detail: str, related_record_ids: list | None = None) -> dict:
    return {
        "exception_type": exception_type,
        "detail": detail,
        "related_record_ids": related_record_ids or [],
    }


def _detect_fuel_no_miles(snapshot: dict) -> list[dict]:
    return [
        _exc(
            "fuel_no_miles",
            f"{j['jurisdiction']}: {j['fuel_gallons']:.2f} gallons purchased, 0 miles recorded",
            j.get("purchase_ids", []),
        )
        for j in snapshot.get("jurisdictions", [])
        if j["fuel_gallons"] > 0 and j["miles"] == 0
    ]


def _detect_miles_no_fuel_gap(snapshot: dict, *, miles_threshold: float = 50.0) -> list[dict]:
    return [
        _exc(
            "miles_no_fuel_gap",
            f"{j['jurisdiction']}: {j['miles']:.1f} miles recorded, 0 gallons purchased there",
            j.get("leg_ids", []),
        )
        for j in snapshot.get("jurisdictions", [])
        if j["miles"] > miles_threshold and j["fuel_gallons"] == 0
    ]


def _detect_fleet_mpg_out_of_band(snapshot: dict, *, band: tuple[float, float] = DEFAULT_MPG_BAND) -> list[dict]:
    low, high = band
    mpg = snapshot.get("fleet_mpg") or 0.0
    if mpg and not (low <= mpg <= high):
        return [_exc("fleet_mpg_out_of_band", f"fleet_mpg {mpg:.2f} outside plausible range [{low}, {high}]")]
    return []


def _detect_broken_evidence_linkage(snapshot: dict) -> list[dict]:
    """Re-verifies each linked fuel-purchase receipt's checksum against
    what was recorded at attach time -- same fail-closed technique Phase
    3 proved for the archive layer, applied here to fuel-purchase
    evidence."""
    import hashlib

    findings = []
    for j in snapshot.get("jurisdictions", []):
        for purchase_id in j.get("purchase_ids", []):
            purchase = store.get_ifta_fuel_purchase(purchase_id)
            if not purchase or not purchase.get("evidence_id"):
                continue
            ev = store.get_ifta_fuel_evidence(purchase["evidence_id"])
            if not ev:
                findings.append(_exc(
                    "broken_evidence_linkage",
                    f"fuel purchase {purchase_id}: linked evidence {purchase['evidence_id']} no longer exists",
                    [purchase_id],
                ))
                continue
            file_path = ev.get("file_path")
            if not file_path or not Path(file_path).is_file():
                findings.append(_exc(
                    "broken_evidence_linkage",
                    f"fuel purchase {purchase_id}: receipt file is missing on disk",
                    [purchase_id, ev["evidence_id"]],
                ))
                continue
            actual = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
            if actual != ev.get("checksum"):
                findings.append(_exc(
                    "broken_evidence_linkage",
                    f"fuel purchase {purchase_id}: receipt file content no longer matches its recorded checksum",
                    [purchase_id, ev["evidence_id"]],
                ))
    return findings


def _detect_late_arrival_closed_quarter(year: int, quarter: int, vehicle_id: str = "") -> list[dict]:
    """A trip leg or fuel purchase dated inside this period exists but
    isn't among the record IDs frozen into the already-sealed approval's
    snapshot -- it arrived after the quarter closed and was never part of
    what was reviewed and sealed. Direct port of Hold's
    late_arrival_closed_quarter, adapted to Dispatch's provenance
    tracking (Phase 5) instead of a fuel_type-scoped worksheet table."""
    approval = store.get_latest_ifta_report_approval(year, quarter, vehicle_id)
    if approval is None or approval["status"] != "sealed":
        return []

    snapshot = approval["snapshot_json"]
    sealed_leg_ids: set = set()
    sealed_purchase_ids: set = set()
    for j in snapshot.get("jurisdictions", []):
        sealed_leg_ids.update(j.get("leg_ids", []))
        sealed_purchase_ids.update(j.get("purchase_ids", []))

    date_from, date_to = _quarter_date_range(year, quarter)
    leg_kwargs: dict = {"date_from": date_from, "date_to": date_to}
    fuel_kwargs: dict = {"date_from": date_from, "date_to": date_to}
    if vehicle_id:
        leg_kwargs["vehicle_id"] = vehicle_id
        fuel_kwargs["vehicle_id"] = vehicle_id

    label = snapshot.get("quarter_label") or f"Q{quarter} {year}"
    findings = []
    for leg in store.list_ifta_trip_legs(**leg_kwargs):
        if leg["leg_id"] not in sealed_leg_ids:
            findings.append(_exc(
                "late_arrival_closed_quarter",
                f"trip leg {leg['leg_id']} ({leg['jurisdiction']}, {leg['date']}) falls in "
                f"already-sealed {label} — never silently absorbed",
                [leg["leg_id"]],
            ))
    for p in store.list_ifta_fuel_purchases(**fuel_kwargs):
        if p["purchase_id"] not in sealed_purchase_ids:
            findings.append(_exc(
                "late_arrival_closed_quarter",
                f"fuel purchase {p['purchase_id']} ({p['jurisdiction']}, {p['date']}) falls in "
                f"already-sealed {label} — never silently absorbed",
                [p["purchase_id"]],
            ))
    return findings


def _detect_corner_clipping(snapshot: dict, *, threshold: float = DEFAULT_CORNER_CLIP_MILES) -> list[dict]:
    return [
        _exc(
            "corner_clipping",
            f"{j['jurisdiction']}: only {j['miles']:.2f} miles — annotated, not suppressed",
            j.get("leg_ids", []),
        )
        for j in snapshot.get("jurisdictions", [])
        if 0 < j["miles"] < threshold
    ]


def _run_ifta_exception_detectors_on_snapshot(
    snapshot: dict, year: int, quarter: int, vehicle_id: str = ""
) -> list[dict]:
    findings: list[dict] = []
    findings += _detect_fuel_no_miles(snapshot)
    findings += _detect_miles_no_fuel_gap(snapshot)
    findings += _detect_fleet_mpg_out_of_band(snapshot)
    findings += _detect_broken_evidence_linkage(snapshot)
    findings += _detect_late_arrival_closed_quarter(year, quarter, vehicle_id)
    findings += _detect_corner_clipping(snapshot)
    return findings


def run_ifta_exception_detectors(year: int, quarter: int, vehicle_id: str = "") -> list[dict]:
    """Public, read-only entrypoint: resolves the live-or-sealed snapshot
    for this quarter, then runs the six ported detectors against it (of
    Hold's ten -- the other four need infrastructure Dispatch doesn't
    have; see DISPATCH_IFTA_PHASE6A_EXCEPTION_DETECTORS_LAUNCH_PACKAGE_v1
    Section 2). Advisory only -- nothing here blocks submission or
    sealing, matching Hold's own 'never auto-resolves' principle."""
    if quarter not in (1, 2, 3, 4):
        raise ValueError(f"Invalid quarter: {quarter}")
    approval = get_latest_ifta_report_approval(year, quarter, vehicle_id)
    if approval is not None and approval["status"] == "sealed":
        snapshot = approval["snapshot_json"]
    else:
        snapshot = get_ifta_quarterly_report(year, quarter, vehicle_id)
    return _run_ifta_exception_detectors_on_snapshot(snapshot, year, quarter, vehicle_id)


def submit_ifta_quarter_for_approval(year: int, quarter: int, vehicle_id: str = "") -> dict:
    """Freezes the current computed report for this period into a new
    IFTAReportApproval (status='draft') and emails the reviewer an
    approval link. Refuses if this exact period was already submitted --
    once, ever, mirroring Hold's AlreadySubmittedError: there is no path
    to resubmit a period, only to approve the one submission it got."""
    import os

    from cin_lite import email_delivery

    if quarter not in (1, 2, 3, 4):
        raise ValueError(f"Invalid quarter: {quarter}")

    existing = store.get_latest_ifta_report_approval(year, quarter, vehicle_id)
    if existing is not None:
        raise AlreadySubmittedError(
            f"{year} Q{quarter} was already submitted for approval "
            f"(approval {existing['approval_id']}, status {existing['status']!r})"
        )

    snapshot = get_ifta_quarterly_report(year, quarter, vehicle_id)

    approval = IFTAReportApproval(
        year=year, quarter=quarter, vehicle_id=vehicle_id,
        status="draft", snapshot=snapshot,
    )
    created = store.create_ifta_report_approval(approval)

    findings = _run_ifta_exception_detectors_on_snapshot(snapshot, year, quarter, vehicle_id)
    for finding in findings:
        store.create_ifta_exception(IFTAException(
            approval_id=created["approval_id"],
            exception_type=finding["exception_type"],
            detail=finding["detail"],
            related_record_ids=finding["related_record_ids"],
        ))

    token = email_delivery.make_token(created["approval_id"], "approve")
    base = os.environ.get("DISPATCH_PORTAL_URL", "http://127.0.0.1:8080").rstrip("/")
    approve_url = f"{base}/api/dispatch/ifta/report-approvals/{created['approval_id']}/approve?token={token}"
    email_delivery.send(
        subject=f"[DISPATCH] IFTA Q{quarter} {year} approval requested",
        body=(
            f"An IFTA quarterly report is ready for your approval.\n\n"
            f"Period: Q{quarter} {year}\n"
            f"Total due: ${snapshot['total_due']:.2f}\n\n"
            f"Approve: {approve_url}\n"
        ),
        to=[email_delivery.reviewer_address()],
        fallback_id=f"ifta-approval-{created['approval_id']}",
    )
    return created


def approve_ifta_quarter(approval_id: str, token: str) -> dict:
    """Verifies the emailed token, then seals: archives the frozen
    snapshot and the computed payment recommendation, flips status to
    'sealed'. Idempotent on an already-sealed approval (a repeat click on
    the same email link is a no-op success, matching Hold's
    attempt_seal()) -- the token is only re-checked when there is
    something left to do."""
    from cin_lite import email_delivery

    approval = store.get_ifta_report_approval(approval_id)
    if approval is None:
        raise ValueError(f"No such IFTA report approval: {approval_id}")
    if approval["status"] == "sealed":
        return approval

    if not email_delivery.verify_token(approval_id, "approve", token):
        raise InvalidApprovalTokenError("Invalid or expired approval token.")

    snapshot = approval["snapshot_json"]
    recommendation = compute_ifta_payment_recommendation(snapshot)
    approved_by = email_delivery.reviewer_address()
    sealed_at = _utc_now()

    _write_compliance_record(
        "ifta_sealed_report", approval_id,
        {
            "approval_id": approval_id,
            "year": approval["year"],
            "quarter": approval["quarter"],
            "vehicle_id": approval["vehicle_id"],
            "snapshot": snapshot,
            "resolved_evidence": resolve_ifta_evidence_for_snapshot(snapshot),
            "approved_by": approved_by,
            "sealed_at": sealed_at,
        },
    )
    _write_compliance_record(
        "ifta_payment_recommendation", approval_id,
        {**recommendation, "approval_id": approval_id, "sealed_at": sealed_at},
    )

    return store.update_ifta_report_approval(approval_id, {
        "status": "sealed",
        "sealed_at": sealed_at,
        "approved_by": approved_by,
        "recommendation_json": recommendation,
    })


def list_ifta_report_approvals() -> list[dict]:
    return store.list_ifta_report_approvals()


def get_ifta_report_approval(approval_id: str) -> dict | None:
    return store.get_ifta_report_approval(approval_id)


def get_latest_ifta_report_approval(year: int, quarter: int, vehicle_id: str = "") -> dict | None:
    return store.get_latest_ifta_report_approval(year, quarter, vehicle_id)


def list_ifta_exceptions(approval_id: str) -> list[dict]:
    return store.list_ifta_exceptions(approval_id)


def build_ifta_review_dashboard(year: int, quarter: int, vehicle_id: str = "") -> dict:
    """Read-only, Dispatch-native review screen for one IFTA quarter,
    assembled entirely from data Dispatch already computes elsewhere --
    no new I/O, no writes. As of Phase 6a, the Exceptions panel is a
    formal port of six of Hold's ten detectors, replacing Phase 5's ad
    hoc "Plausibility Warnings" panel (fleet_mpg_out_of_band is now one
    of the six, not a separate mechanism). As of Phase 7, a Suspect
    Entries panel surfaces scanned fuel purchases below the confidence
    threshold -- always computed live from the stored field (matching
    Hold's own choice), never persisted, never factored into
    readiness_status: it's informational, not a governed exception."""
    if quarter not in (1, 2, 3, 4):
        raise ValueError(f"Invalid quarter: {quarter}")

    approval = get_latest_ifta_report_approval(year, quarter, vehicle_id)
    sealed = approval is not None and approval["status"] == "sealed"
    suspect_entries = list_suspect_ifta_fuel_purchases(year, quarter, vehicle_id)

    if sealed:
        snapshot = approval["snapshot_json"]
        tax_position_source = "sealed"
    else:
        try:
            snapshot = get_ifta_quarterly_report(year, quarter, vehicle_id)
        except ValueError as exc:
            return {
                "year": year,
                "quarter": quarter,
                "vehicle_id": vehicle_id,
                "tax_position": None,
                "tax_position_source": "unavailable",
                "tax_position_error": str(exc),
                "evidence": [],
                "unlinked_purchase_count": 0,
                "total_purchase_count": 0,
                "exceptions": [{"exception_type": "blocked", "detail": str(exc)}],
                "suspect_entries": suspect_entries,
                "readiness_status": "blocked — " + str(exc),
                "approval_status": approval["status"] if approval else None,
                "approval": approval,
            }
        tax_position_source = "live_preview"

    evidence = resolve_ifta_evidence_for_snapshot(snapshot)
    total_purchase_count = sum(len(jur["purchases"]) for jur in evidence)
    unlinked_count = sum(
        1 for jur in evidence for entry in jur["purchases"] if entry["evidence"] is None
    )

    if sealed:
        exceptions = store.list_ifta_exceptions(approval["approval_id"])
    else:
        exceptions = _run_ifta_exception_detectors_on_snapshot(snapshot, year, quarter, vehicle_id)

    if sealed:
        readiness_status = "sealed"
    elif unlinked_count > 0:
        readiness_status = f"{unlinked_count} of {total_purchase_count} fuel purchase(s) have no receipt attached"
    elif exceptions:
        readiness_status = f"{len(exceptions)} exception(s) noted"
    elif snapshot.get("trip_leg_count", 0) == 0 and snapshot.get("fuel_purchase_count", 0) == 0:
        readiness_status = "no data recorded yet this quarter"
    else:
        readiness_status = "ready to submit"

    return {
        "year": year,
        "quarter": quarter,
        "vehicle_id": vehicle_id,
        "tax_position": snapshot,
        "tax_position_source": tax_position_source,
        "evidence": evidence,
        "unlinked_purchase_count": unlinked_count,
        "total_purchase_count": total_purchase_count,
        "exceptions": exceptions,
        "suspect_entries": suspect_entries,
        "readiness_status": readiness_status,
        "approval_status": approval["status"] if approval else None,
        "approval": approval,
    }


# ── Broker Contact Directory ─────────────────────────────────────────


def add_broker_contact(
    company_name: str,
    contact_name: str = "",
    phone: str = "",
    email: str = "",
    mc_number: str = "",
    dot_number: str = "",
    address: str = "",
    payment_terms: str = "",
    notes: str = "",
    status: str = "active",
) -> dict:
    if not company_name.strip():
        raise ValueError("Company name is required")
    if status not in BROKER_STATUSES:
        raise ValueError(f"Invalid status: {status!r}")
    existing = store.find_broker_by_name(company_name.strip())
    if existing:
        raise ValueError(f"Broker '{company_name}' already exists")
    broker = BrokerContact(
        company_name=company_name.strip(),
        contact_name=contact_name,
        phone=phone,
        email=email,
        mc_number=mc_number,
        dot_number=dot_number,
        address=address,
        payment_terms=payment_terms,
        notes=notes,
        status=status,
    )
    return store.create_broker_contact(broker)


def get_broker_contact(broker_id: str) -> dict | None:
    return store.get_broker_contact(broker_id)


def list_broker_contacts(**kwargs) -> list[dict]:
    return store.list_broker_contacts(**kwargs)


def update_broker_contact(broker_id: str, updates: dict) -> dict | None:
    existing = store.get_broker_contact(broker_id)
    if not existing:
        return None
    if "status" in updates and updates["status"] not in BROKER_STATUSES:
        raise ValueError(f"Invalid status: {updates['status']!r}")
    if "company_name" in updates:
        name = updates["company_name"].strip()
        if not name:
            raise ValueError("Company name is required")
        dup = store.find_broker_by_name(name)
        if dup and dup["broker_id"] != broker_id:
            raise ValueError(f"Broker '{name}' already exists")
        updates["company_name"] = name
    return store.update_broker_contact(broker_id, updates)


def delete_broker_contact(broker_id: str) -> bool:
    return store.delete_broker_contact(broker_id)


def get_broker_contact_with_stats(broker_id: str) -> dict | None:
    broker = store.get_broker_contact(broker_id)
    if not broker:
        return None
    loads = store.get_broker_loads(broker["company_name"])
    broker["load_count"] = len(loads)
    broker["loads"] = loads[:10]
    return broker


# ── Load Profitability Ranking ───────────────────────────────────────


def get_load_profitability(
    sort_by: str = "profit",
    sort_order: str = "desc",
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
) -> dict:
    valid_sort = {"profit", "margin_pct", "revenue", "revenue_per_mile", "total_expenses"}
    if sort_by not in valid_sort:
        raise ValueError(f"Invalid sort_by: {sort_by!r}")
    if sort_order not in ("asc", "desc"):
        raise ValueError(f"Invalid sort_order: {sort_order!r}")

    rows = store.get_load_profitability_data(
        date_from=date_from, date_to=date_to, status=status,
    )
    reverse = sort_order == "desc"
    rows.sort(key=lambda r: r.get(sort_by, 0), reverse=reverse)

    for i, r in enumerate(rows, 1):
        r["rank"] = i

    total_revenue = sum(r["revenue"] for r in rows)
    total_expenses = sum(r["total_expenses"] for r in rows)
    total_profit = total_revenue - total_expenses
    avg_margin = (
        sum(r["margin_pct"] for r in rows) / len(rows)
        if rows else 0.0
    )

    return {
        "loads": rows,
        "summary": {
            "total_loads": len(rows),
            "total_revenue": round(total_revenue, 2),
            "total_expenses": round(total_expenses, 2),
            "total_profit": round(total_profit, 2),
            "avg_margin_pct": round(avg_margin, 1),
            "profitable_count": sum(1 for r in rows if r["profit"] > 0),
            "unprofitable_count": sum(1 for r in rows if r["profit"] < 0),
        },
    }


# ── Driver Pay ──────────────────────────────────────────────────────


def add_driver_pay(
    driver_id: str,
    pay_type: str,
    amount: float = 0.0,
    *,
    load_id: str = "",
    description: str = "",
    rate: float = 0.0,
    miles: float = 0.0,
    hours: float = 0.0,
    percentage: float = 0.0,
    pay_period: str = "",
    notes: str = "",
) -> dict:
    from dispatch.models import PAY_TYPES, DriverPay

    driver = get_driver(driver_id)
    if not driver:
        raise ValueError("Driver not found")
    if pay_type not in PAY_TYPES:
        raise ValueError(f"Invalid pay type: {pay_type}")
    if load_id:
        load = get_load(load_id)
        if not load:
            raise ValueError("Load not found")
        if pay_type == "percentage" and percentage > 0:
            rc = store.get_rate_confirmation(load_id)
            if rc:
                rev = rc["rate_amount"]
                if rc["rate_type"] == "per_mile":
                    rev = rc["rate_amount"] * rc["distance_miles"]
                amount = round(rev * percentage / 100, 2)
    pay = DriverPay(
        driver_id=driver_id,
        load_id=load_id,
        pay_type=pay_type,
        description=description,
        amount=amount,
        rate=rate,
        miles=miles,
        hours=hours,
        percentage=percentage,
        pay_period=pay_period,
        notes=notes,
    )
    return store.create_driver_pay(pay)


def get_driver_pay_entry(pay_id: str) -> dict | None:
    return store.get_driver_pay(pay_id)


def list_driver_pay(
    driver_id: str | None = None,
    load_id: str | None = None,
    status: str | None = None,
    pay_period: str | None = None,
) -> list[dict]:
    return store.list_driver_pay(
        driver_id=driver_id,
        load_id=load_id,
        status=status,
        pay_period=pay_period,
    )


def update_driver_pay(pay_id: str, **fields) -> dict | None:
    from dispatch.models import PAY_STATUSES, PAY_TYPES

    if "pay_type" in fields and fields["pay_type"] not in PAY_TYPES:
        raise ValueError(f"Invalid pay type: {fields['pay_type']}")
    if "status" in fields and fields["status"] not in PAY_STATUSES:
        raise ValueError(f"Invalid status: {fields['status']}")
    return store.update_driver_pay(pay_id, **fields)


def delete_driver_pay(pay_id: str) -> bool:
    return store.delete_driver_pay(pay_id)


def get_driver_pay_summary(
    driver_id: str,
    pay_period: str | None = None,
) -> dict:
    return store.get_driver_pay_summary(driver_id, pay_period=pay_period)


def approve_driver_pay(pay_ids: list[str]) -> int:
    count = 0
    for pay_id in pay_ids:
        result = store.update_driver_pay(pay_id, status="approved")
        if result:
            count += 1
    return count


def mark_driver_pay_paid(pay_ids: list[str], paid_date: str = "") -> int:
    from dispatch.models import _utc_now

    if not paid_date:
        paid_date = _utc_now()[:10]
    count = 0
    for pay_id in pay_ids:
        result = store.update_driver_pay(
            pay_id, status="paid", paid_date=paid_date
        )
        if result:
            count += 1
    return count


# ── Maintenance Schedules ───────────────────────────────────────────


def add_maintenance_schedule(
    equipment_id: str,
    service_type: str,
    *,
    description: str = "",
    interval_miles: float = 0.0,
    interval_days: int = 0,
    next_due_date: str = "",
    next_due_miles: float = 0.0,
    cost_estimate: float = 0.0,
    vendor: str = "",
    notes: str = "",
) -> dict:
    from dispatch.models import SERVICE_TYPES, MaintenanceSchedule

    equip = get_equipment(equipment_id)
    if not equip:
        raise ValueError("Equipment not found")
    if service_type not in SERVICE_TYPES:
        raise ValueError(f"Invalid service type: {service_type}")
    sched = MaintenanceSchedule(
        equipment_id=equipment_id,
        service_type=service_type,
        description=description,
        interval_miles=interval_miles,
        interval_days=interval_days,
        next_due_date=next_due_date,
        next_due_miles=next_due_miles,
        cost_estimate=cost_estimate,
        vendor=vendor,
        notes=notes,
    )
    return store.create_maintenance_schedule(sched)


def get_maintenance_schedule(schedule_id: str) -> dict | None:
    return store.get_maintenance_schedule(schedule_id)


def list_maintenance_schedules(
    equipment_id: str | None = None,
    status: str | None = None,
) -> list[dict]:
    return store.list_maintenance_schedules(
        equipment_id=equipment_id, status=status,
    )


def update_maintenance_schedule(schedule_id: str, **fields) -> dict | None:
    from dispatch.models import MAINTENANCE_STATUSES, SERVICE_TYPES

    if "service_type" in fields and fields["service_type"] not in SERVICE_TYPES:
        raise ValueError(f"Invalid service type: {fields['service_type']}")
    if "status" in fields and fields["status"] not in MAINTENANCE_STATUSES:
        raise ValueError(f"Invalid status: {fields['status']}")
    return store.update_maintenance_schedule(schedule_id, **fields)


def delete_maintenance_schedule(schedule_id: str) -> bool:
    return store.delete_maintenance_schedule(schedule_id)


def complete_maintenance(
    schedule_id: str,
    service_date: str = "",
    service_miles: float = 0.0,
) -> dict | None:
    from datetime import datetime, timedelta
    from dispatch.models import _utc_now

    sched = store.get_maintenance_schedule(schedule_id)
    if not sched:
        return None
    if not service_date:
        service_date = _utc_now()[:10]
    updates: dict = {
        "status": "completed",
        "last_service_date": service_date,
    }
    if service_miles:
        updates["last_service_miles"] = service_miles
    if sched["interval_days"] > 0:
        next_date = (
            datetime.fromisoformat(service_date)
            + timedelta(days=sched["interval_days"])
        ).strftime("%Y-%m-%d")
        updates["next_due_date"] = next_date
        updates["status"] = "scheduled"
    if sched["interval_miles"] > 0 and service_miles:
        updates["next_due_miles"] = service_miles + sched["interval_miles"]
        updates["status"] = "scheduled"
    return store.update_maintenance_schedule(schedule_id, **updates)


def get_upcoming_maintenance(days_ahead: int = 7) -> list[dict]:
    return store.get_upcoming_maintenance(days_ahead=days_ahead)


def get_overdue_maintenance() -> list[dict]:
    return store.get_overdue_maintenance()


def check_maintenance_alerts() -> dict:
    overdue = store.get_overdue_maintenance()
    for item in overdue:
        if item["status"] != "overdue":
            store.update_maintenance_schedule(item["schedule_id"], status="overdue")
    upcoming = store.get_upcoming_maintenance(days_ahead=7)
    for item in upcoming:
        if item["status"] == "scheduled":
            store.update_maintenance_schedule(item["schedule_id"], status="due")
    return {
        "overdue": len(overdue),
        "due_soon": len([u for u in upcoming if u["schedule_id"] not in
                         {o["schedule_id"] for o in overdue}]),
    }


# ── Compliance Document Tracker ─────────────────────────────────────


def add_compliance_document(
    doc_type: str,
    title: str,
    entity_type: str = "company",
    entity_id: str = "",
    issuing_authority: str = "",
    doc_number: str = "",
    issue_date: str = "",
    expiry_date: str = "",
    alert_days: int = 30,
    notes: str = "",
) -> dict:
    from dispatch.models import ComplianceDocument

    if not title.strip():
        raise ValueError("Title is required")
    if alert_days < 0:
        raise ValueError("Alert days must be non-negative")
    doc = ComplianceDocument(
        entity_type=entity_type,
        entity_id=entity_id,
        doc_type=doc_type,
        title=title,
        issuing_authority=issuing_authority,
        doc_number=doc_number,
        issue_date=issue_date,
        expiry_date=expiry_date,
        alert_days=alert_days,
        notes=notes,
    )
    return store.create_compliance_document(doc)


def update_compliance_document(doc_id: str, **fields) -> dict:
    from dispatch.models import COMPLIANCE_DOC_TYPES, COMPLIANCE_DOC_STATUSES, COMPLIANCE_ENTITY_TYPES
    if "doc_type" in fields:
        from dispatch.models import _validate_choice
        _validate_choice(fields["doc_type"], COMPLIANCE_DOC_TYPES, "doc_type")
    if "status" in fields:
        from dispatch.models import _validate_choice
        _validate_choice(fields["status"], COMPLIANCE_DOC_STATUSES, "status")
    if "entity_type" in fields:
        from dispatch.models import _validate_choice
        _validate_choice(fields["entity_type"], COMPLIANCE_ENTITY_TYPES, "entity_type")
    if "alert_days" in fields and fields["alert_days"] < 0:
        raise ValueError("Alert days must be non-negative")
    result = store.update_compliance_document(doc_id, **fields)
    if not result:
        raise ValueError(f"Compliance document {doc_id} not found")
    return result


def delete_compliance_document(doc_id: str) -> bool:
    return store.delete_compliance_document(doc_id)


def get_compliance_document(doc_id: str) -> dict | None:
    return store.get_compliance_document(doc_id)


def list_compliance_documents(**filters) -> list[dict]:
    return store.list_compliance_documents(**filters)


def get_expiring_compliance_documents(days_ahead: int = 30) -> list[dict]:
    return store.get_expiring_compliance_documents(days_ahead=days_ahead)


def check_compliance_alerts() -> dict:
    from dispatch.models import _utc_now
    today = _utc_now()[:10]
    all_docs = store.list_compliance_documents(status="active")
    expired_count = 0
    expiring_count = 0
    for doc in all_docs:
        if doc.get("is_expired"):
            store.update_compliance_document(doc["doc_id"], status="expired")
            expired_count += 1
        elif doc.get("needs_alert"):
            store.update_compliance_document(doc["doc_id"], status="expiring_soon")
            expiring_count += 1
    return {
        "expired": expired_count,
        "expiring_soon": expiring_count,
    }
