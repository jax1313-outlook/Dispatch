"""Dispatch Data Engine service functions.

Business logic for the full load lifecycle: create -> dispatch -> pickup
-> transit -> deliver -> POD -> archive.
"""

from __future__ import annotations

from dispatch.models import (
    EXCEPTION_STATUSES,
    LOAD_STATUSES,
    EvidenceItem,
    ExceptionNotice,
    Load,
    LoadVisibilityRecord,
    MilestoneEvent,
    PODPackage,
    RetentionArchive,
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
    notes: str = "",
) -> dict:
    load = Load(
        customer=customer,
        broker_shipper=broker_shipper,
        pickup_location=pickup_location,
        delivery_location=delivery_location,
        pickup_datetime=pickup_datetime,
        delivery_datetime=delivery_datetime,
        equipment=equipment,
        driver=driver,
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
    return store.update_load(load_id, **fields)


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

    ret = RetentionArchive(
        load_id=load_id,
        final_status=load["status"],
        pod_package_id=pod_id,
        evidence_index=evidence_ids,
        archive_location=f"retention/{load_id}",
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


def get_load_bundle(load_id: str) -> dict | None:
    load = store.get_load(load_id)
    if not load:
        return None
    return {
        "load": load,
        "visibility": store.get_visibility(load_id),
        "milestones": store.list_milestones(load_id),
        "evidence": store.list_evidence(load_id),
        "exceptions": store.list_exceptions(load_id=load_id),
        "pods": store.list_pods(load_id),
        "retention": store.get_retention_by_load(load_id),
    }
