"""Dispatch Data Engine service functions.

Business logic for the full load lifecycle: create -> dispatch -> pickup
-> transit -> deliver -> POD -> archive.
"""

from __future__ import annotations

from dispatch.models import (
    EXCEPTION_STATUSES,
    LOAD_STATUSES,
    Driver,
    Equipment,
    EvidenceItem,
    ExceptionNotice,
    Expense,
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
    "cancelled": set(),
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


def list_loads(status: str | None = None) -> list[dict]:
    return store.list_loads(status=status)


def update_load(load_id: str, **fields) -> dict | None:
    if "driver_id" in fields and fields["driver_id"]:
        _validate_driver_assignment(fields["driver_id"])
    if "equipment_id" in fields and fields["equipment_id"]:
        _validate_equipment_assignment(fields["equipment_id"])
    if "status" in fields:
        current = store.get_load(load_id)
        if current:
            validate_status_transition(current["status"], fields["status"])
    return store.update_load(load_id, **fields)


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
        notifications.notify_dispatched(updated)


def get_visibility(load_id: str) -> dict | None:
    return store.get_visibility(load_id)


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
        notifications.notify_delivered(updated_load, result)

    return result


def get_timeline(load_id: str) -> list[dict]:
    return store.list_milestones(load_id)


def attach_evidence(
    load_id: str,
    evidence_type: str = "document",
    description: str = "",
    file_path: str | None = None,
    related_milestone_id: str | None = None,
    uploaded_by: str = "",
    file_data: bytes | None = None,
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
    )
    if file_data:
        ev.compute_checksum(file_data)
    return store.create_evidence(ev)


def list_evidence(load_id: str) -> list[dict]:
    return store.list_evidence(load_id)


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
        notifications.notify_exception(load, result)

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
    load_id: str | None = None, status: str | None = None
) -> list[dict]:
    return store.list_exceptions(load_id=load_id, status=status)


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

    notifications.notify_pod_generated(load, result)

    return result


def get_pod(pod_id: str) -> dict | None:
    return store.get_pod(pod_id)


def list_pods(load_id: str) -> list[dict]:
    return store.list_pods(load_id)


def archive_load(load_id: str) -> dict:
    load = store.get_load(load_id)
    if not load:
        raise ValueError(f"Load not found: {load_id}")

    existing = store.get_retention_by_load(load_id)
    if existing:
        raise ValueError(f"Load {load_id} is already archived")

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

    notifications.notify_archived(load, result)

    return result


def get_retention(load_id: str) -> dict | None:
    return store.get_retention_by_load(load_id)


def list_retentions() -> list[dict]:
    return store.list_retentions()


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
    notifications.notify_invoice_created(load, result)
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
        notifications.notify_payment_received(load, result)

    return result


def get_settlement(load_id: str) -> dict | None:
    return store.get_settlement(load_id)


def list_settlements(payment_status: str | None = None) -> list[dict]:
    return store.list_settlements(payment_status=payment_status)


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
            total_revenue += rate["revenue"]
            loads_with_rate += 1

        expenses = store.list_expenses(load["load_id"])
        total_expenses += sum(e["amount"] for e in expenses)

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
                notifications.notify_payment_overdue(load, updated)
            newly_overdue.append(updated)

    return newly_overdue


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


def list_drivers(status: str | None = None) -> list[dict]:
    return store.list_drivers(status=status)


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
) -> list[dict]:
    return store.list_equipment(status=status, equipment_type=equipment_type)


def update_equipment(equipment_id: str, **fields) -> dict | None:
    return store.update_equipment(equipment_id, **fields)


def retire_equipment(equipment_id: str) -> dict | None:
    return store.update_equipment(equipment_id, status="retired")


def delete_equipment(equipment_id: str) -> bool:
    return store.delete_equipment(equipment_id)


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

    return {
        "total_drivers": len(drivers),
        "drivers_by_status": driver_by_status,
        "total_equipment": len(equipment),
        "equipment_by_status": equip_by_status,
        "active_equipment_by_type": equip_by_type,
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
        "active_drivers": store.list_drivers(status="active"),
        "active_equipment": store.list_equipment(status="active"),
    }
