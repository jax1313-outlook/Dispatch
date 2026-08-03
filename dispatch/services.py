"""Dispatch Data Engine service functions.

Business logic for the full load lifecycle: create -> dispatch -> pickup
-> transit -> deliver -> POD -> archive.
"""

from __future__ import annotations

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
    IFTAFuelPurchase,
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
    *,
    page: int | None = None,
    per_page: int | None = None,
) -> list[dict] | dict:
    return store.list_loads(
        status=status, customer=customer,
        date_from=date_from, date_to=date_to,
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


def update_evidence(evidence_id: str, **fields) -> dict | None:
    return store.update_evidence(evidence_id, **fields)


def delete_evidence(evidence_id: str) -> bool:
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
                notifications.notify_payment_overdue(load, updated)
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
        notifications.notify_settlement_disputed(load, result, reason)
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
        notifications.notify_settlement_written_off(load, result, reason)
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
        notifications.notify_stalled(load)
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
    return store.create_ifta_trip_leg(leg)


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


def _quarter_date_range(year: int, quarter: int) -> tuple[str, str]:
    starts = {1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01"}
    ends = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
    return f"{year}-{starts[quarter]}", f"{year}-{ends[quarter]}"


def get_ifta_quarterly_report(year: int, quarter: int, vehicle_id: str = "") -> dict:
    if quarter not in (1, 2, 3, 4):
        raise ValueError(f"Invalid quarter: {quarter}")

    date_from, date_to = _quarter_date_range(year, quarter)
    leg_kwargs: dict = {"date_from": date_from, "date_to": date_to}
    fuel_kwargs: dict = {"date_from": date_from, "date_to": date_to}
    if vehicle_id:
        leg_kwargs["vehicle_id"] = vehicle_id
        fuel_kwargs["vehicle_id"] = vehicle_id

    legs = store.list_ifta_trip_legs(**leg_kwargs)
    purchases = store.list_ifta_fuel_purchases(**fuel_kwargs)

    miles_by_jur: dict[str, float] = {}
    for leg in legs:
        j = leg["jurisdiction"]
        miles_by_jur[j] = miles_by_jur.get(j, 0) + leg["miles"]

    fuel_by_jur: dict[str, dict] = {}
    for p in purchases:
        j = p["jurisdiction"]
        if j not in fuel_by_jur:
            fuel_by_jur[j] = {"gallons": 0.0, "amount": 0.0}
        fuel_by_jur[j]["gallons"] += p["gallons"]
        fuel_by_jur[j]["amount"] += p["amount"]

    total_miles = sum(miles_by_jur.values())
    total_gallons = sum(f["gallons"] for f in fuel_by_jur.values())
    fleet_mpg = round(total_miles / total_gallons, 4) if total_gallons > 0 else 0.0

    all_jurs = sorted(set(list(miles_by_jur.keys()) + list(fuel_by_jur.keys())))
    jurisdictions = []
    for j in all_jurs:
        miles = round(miles_by_jur.get(j, 0), 2)
        fuel = fuel_by_jur.get(j, {"gallons": 0.0, "amount": 0.0})
        taxable_gallons = round(miles / fleet_mpg, 4) if fleet_mpg > 0 else 0.0
        net_taxable = round(taxable_gallons - fuel["gallons"], 4)
        jurisdictions.append({
            "jurisdiction": j,
            "miles": miles,
            "fuel_gallons": round(fuel["gallons"], 4),
            "fuel_amount": round(fuel["amount"], 2),
            "taxable_gallons": taxable_gallons,
            "net_taxable_gallons": net_taxable,
        })

    return {
        "year": year,
        "quarter": quarter,
        "quarter_label": f"Q{quarter} {year}",
        "date_from": date_from,
        "date_to": date_to,
        "vehicle_id": vehicle_id,
        "total_miles": round(total_miles, 2),
        "total_gallons": round(total_gallons, 4),
        "fleet_mpg": fleet_mpg,
        "jurisdictions": jurisdictions,
        "trip_leg_count": len(legs),
        "fuel_purchase_count": len(purchases),
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
