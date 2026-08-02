"""Canonical data models for the seven dispatch objects.

Each model is a plain dataclass with validation and serialization.
Field names and types follow the Dispatch Data Engine Coding Resources Report.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gen_id(prefix: str) -> str:
    short = uuid.uuid4().hex[:8].upper()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{prefix}-{stamp}-{short}"


LOAD_STATUSES = [
    "created",
    "dispatched",
    "en_route_pickup",
    "at_pickup",
    "picked_up",
    "in_transit",
    "at_delivery",
    "delivered",
    "completed",
    "archived",
    "cancelled",
]

MILESTONE_TYPES = [
    "dispatched",
    "en_route_pickup",
    "arrived_pickup",
    "loaded",
    "departed_pickup",
    "in_transit",
    "checkpoint",
    "arrived_delivery",
    "delivered",
    "pod_received",
    "completed",
]

MILESTONE_SOURCES = ["driver", "dispatcher", "system", "customer", "eld", "email"]

EVIDENCE_TYPES = ["bol", "pod", "photo", "screenshot", "message", "document", "other"]

EXCEPTION_TYPES = [
    "delay",
    "damage",
    "missing_paperwork",
    "equipment_issue",
    "access_issue",
    "weather",
    "detention",
    "refused",
    "other",
]

SEVERITY_LEVELS = ["low", "medium", "high", "critical"]

EXCEPTION_STATUSES = ["open", "investigating", "resolved", "closed"]

POD_STATUSES = ["draft", "complete", "delivered"]

RETENTION_STATUSES = ["active", "archived", "expired"]

VALIDATION_STATUSES = ["pending", "validated", "disputed"]

RATE_TYPES = ["flat", "per_mile"]

SETTLEMENT_STATUSES = [
    "draft",
    "invoiced",
    "paid",
    "overdue",
    "disputed",
    "written_off",
]

PAYMENT_METHODS = ["check", "ach", "wire", "factored", "other"]

EXPENSE_CATEGORIES = [
    "fuel",
    "tolls",
    "lumper",
    "detention",
    "repair",
    "insurance",
    "scale",
    "parking",
    "other",
]

DRIVER_STATUSES = ["active", "inactive", "on_leave"]

LICENSE_CLASSES = ["A", "B", "C"]

EQUIPMENT_TYPES = [
    "dry_van",
    "reefer",
    "flatbed",
    "step_deck",
    "lowboy",
    "tanker",
    "container",
    "box_truck",
    "straight_truck",
    "other",
]

EQUIPMENT_STATUSES = ["active", "inactive", "maintenance", "retired"]

ACTIVITY_TYPES = ["comment", "status_change", "assignment", "system"]

ACTIVITY_SOURCES = ["user", "system"]

DETENTION_LOCATIONS = ["pickup", "delivery"]

DETENTION_STATUSES = ["active", "completed", "billed"]


def _validate_choice(value: str, choices: list[str], field_name: str) -> None:
    if value not in choices:
        raise ValueError(f"Invalid {field_name}: {value!r}. Must be one of {choices}")


@dataclass
class Load:
    load_id: str = ""
    customer: str = ""
    broker_shipper: str = ""
    pickup_location: str = ""
    delivery_location: str = ""
    pickup_datetime: str = ""
    delivery_datetime: str = ""
    equipment: str = ""
    driver: str = ""
    driver_id: str = ""
    equipment_id: str = ""
    status: str = "created"
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.load_id:
            self.load_id = _gen_id("LOAD")
        now = _utc_now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        _validate_choice(self.status, LOAD_STATUSES, "status")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LoadVisibilityRecord:
    load_id: str = ""
    current_status: str = "created"
    last_milestone: str | None = None
    next_expected_milestone: str | None = None
    exception_flag: bool = False
    customer_note: str = ""
    internal_note: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.updated_at:
            self.updated_at = _utc_now()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MilestoneEvent:
    milestone_id: str = ""
    load_id: str = ""
    event_type: str = ""
    event_time: str = ""
    location: str = ""
    source: str = "dispatcher"
    note: str = ""
    entered_by: str = ""
    validation_status: str = "pending"

    def __post_init__(self) -> None:
        if not self.milestone_id:
            self.milestone_id = _gen_id("MS")
        if not self.event_time:
            self.event_time = _utc_now()
        if self.event_type:
            _validate_choice(self.event_type, MILESTONE_TYPES, "event_type")
        _validate_choice(self.source, MILESTONE_SOURCES, "source")
        _validate_choice(self.validation_status, VALIDATION_STATUSES, "validation_status")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvidenceItem:
    evidence_id: str = ""
    load_id: str = ""
    related_milestone_id: str | None = None
    evidence_type: str = "document"
    file_path: str | None = None
    capture_time: str = ""
    description: str = ""
    uploaded_by: str = ""
    checksum: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_id:
            self.evidence_id = _gen_id("EV")
        if not self.capture_time:
            self.capture_time = _utc_now()
        _validate_choice(self.evidence_type, EVIDENCE_TYPES, "evidence_type")

    def to_dict(self) -> dict:
        return asdict(self)

    def compute_checksum(self, data: bytes) -> str:
        self.checksum = hashlib.sha256(data).hexdigest()
        return self.checksum


@dataclass
class ExceptionNotice:
    exception_id: str = ""
    load_id: str = ""
    related_milestone_id: str | None = None
    exception_type: str = "other"
    severity: str = "medium"
    description: str = ""
    first_reported: str = ""
    status: str = "open"
    resolution_note: str = ""
    resolved_at: str | None = None

    def __post_init__(self) -> None:
        if not self.exception_id:
            self.exception_id = _gen_id("EXC")
        if not self.first_reported:
            self.first_reported = _utc_now()
        _validate_choice(self.exception_type, EXCEPTION_TYPES, "exception_type")
        _validate_choice(self.severity, SEVERITY_LEVELS, "severity")
        _validate_choice(self.status, EXCEPTION_STATUSES, "status")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PODPackage:
    pod_id: str = ""
    load_id: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    generated_at: str = ""
    status: str = "draft"
    recipient: str = ""
    file_path: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.pod_id:
            self.pod_id = _gen_id("POD")
        if not self.generated_at:
            self.generated_at = _utc_now()
        _validate_choice(self.status, POD_STATUSES, "status")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RetentionArchive:
    archive_id: str = ""
    load_id: str = ""
    final_status: str = "completed"
    pod_package_id: str | None = None
    evidence_index: list[str] = field(default_factory=list)
    financial_summary: dict = field(default_factory=dict)
    archive_location: str = ""
    retention_status: str = "active"
    archived_at: str = ""

    def __post_init__(self) -> None:
        if not self.archive_id:
            self.archive_id = _gen_id("RET")
        if not self.archived_at:
            self.archived_at = _utc_now()
        _validate_choice(self.retention_status, RETENTION_STATUSES, "retention_status")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RateConfirmation:
    confirmation_id: str = ""
    load_id: str = ""
    rate_amount: float = 0.0
    rate_type: str = "flat"
    distance_miles: float = 0.0
    confirmed_by: str = ""
    notes: str = ""
    confirmed_at: str = ""

    def __post_init__(self) -> None:
        if not self.confirmation_id:
            self.confirmation_id = _gen_id("RC")
        if not self.confirmed_at:
            self.confirmed_at = _utc_now()
        _validate_choice(self.rate_type, RATE_TYPES, "rate_type")

    @property
    def revenue(self) -> float:
        if self.rate_type == "per_mile" and self.distance_miles:
            return self.rate_amount * self.distance_miles
        return self.rate_amount

    def to_dict(self) -> dict:
        d = asdict(self)
        d["revenue"] = self.revenue
        return d


@dataclass
class Expense:
    expense_id: str = ""
    load_id: str = ""
    category: str = "other"
    description: str = ""
    amount: float = 0.0
    incurred_at: str = ""
    receipt_evidence_id: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.expense_id:
            self.expense_id = _gen_id("EXP")
        if not self.incurred_at:
            self.incurred_at = _utc_now()
        _validate_choice(self.category, EXPENSE_CATEGORIES, "category")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Settlement:
    settlement_id: str = ""
    load_id: str = ""
    invoice_number: str = ""
    invoice_amount: float = 0.0
    invoice_date: str = ""
    due_date: str = ""
    payment_status: str = "draft"
    payment_amount: float = 0.0
    payment_date: str = ""
    payment_method: str = ""
    factoring_fee: float = 0.0
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.settlement_id:
            self.settlement_id = _gen_id("STL")
        if not self.invoice_number:
            self.invoice_number = f"INV-{self.settlement_id[4:]}"
        if not self.invoice_date:
            self.invoice_date = _utc_now()
        _validate_choice(self.payment_status, SETTLEMENT_STATUSES, "payment_status")
        if self.payment_method:
            _validate_choice(self.payment_method, PAYMENT_METHODS, "payment_method")

    @property
    def net_payment(self) -> float:
        return self.payment_amount - self.factoring_fee

    def to_dict(self) -> dict:
        d = asdict(self)
        d["net_payment"] = self.net_payment
        return d


@dataclass
class Driver:
    driver_id: str = ""
    name: str = ""
    license_number: str = ""
    license_class: str = ""
    phone: str = ""
    email: str = ""
    status: str = "active"
    hire_date: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.driver_id:
            self.driver_id = _gen_id("DRV")
        if not self.created_at:
            self.created_at = _utc_now()
        if not self.updated_at:
            self.updated_at = self.created_at
        _validate_choice(self.status, DRIVER_STATUSES, "status")
        if self.license_class:
            _validate_choice(self.license_class, LICENSE_CLASSES, "license_class")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Equipment:
    equipment_id: str = ""
    unit_number: str = ""
    equipment_type: str = "dry_van"
    make: str = ""
    model: str = ""
    year: str = ""
    vin: str = ""
    license_plate: str = ""
    status: str = "active"
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.equipment_id:
            self.equipment_id = _gen_id("EQP")
        if not self.created_at:
            self.created_at = _utc_now()
        if not self.updated_at:
            self.updated_at = self.created_at
        _validate_choice(self.equipment_type, EQUIPMENT_TYPES, "equipment_type")
        _validate_choice(self.status, EQUIPMENT_STATUSES, "status")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LoadActivity:
    activity_id: str = ""
    load_id: str = ""
    activity_type: str = "comment"
    message: str = ""
    author: str = ""
    source: str = "user"
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.activity_id:
            self.activity_id = _gen_id("ACT")
        if not self.created_at:
            self.created_at = _utc_now()
        _validate_choice(self.activity_type, ACTIVITY_TYPES, "activity_type")
        _validate_choice(self.source, ACTIVITY_SOURCES, "source")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DetentionEvent:
    detention_id: str = ""
    load_id: str = ""
    location_type: str = "pickup"
    started_at: str = ""
    ended_at: str = ""
    free_hours: float = 2.0
    hourly_rate: float = 75.0
    status: str = "active"
    notes: str = ""
    expense_id: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.detention_id:
            self.detention_id = _gen_id("DET")
        if not self.started_at:
            self.started_at = _utc_now()
        if not self.created_at:
            self.created_at = _utc_now()
        _validate_choice(self.location_type, DETENTION_LOCATIONS, "location_type")
        _validate_choice(self.status, DETENTION_STATUSES, "status")

    @property
    def total_hours(self) -> float:
        if not self.ended_at:
            return 0.0
        try:
            start = datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
            end = datetime.fromisoformat(self.ended_at.replace("Z", "+00:00"))
            return max(0.0, (end - start).total_seconds() / 3600)
        except (ValueError, TypeError):
            return 0.0

    @property
    def billable_hours(self) -> float:
        return max(0.0, self.total_hours - self.free_hours)

    @property
    def billable_amount(self) -> float:
        return round(self.billable_hours * self.hourly_rate, 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_hours"] = round(self.total_hours, 2)
        d["billable_hours"] = round(self.billable_hours, 2)
        d["billable_amount"] = self.billable_amount
        return d


@dataclass
class LaneTemplate:
    template_id: str = ""
    name: str = ""
    customer: str = ""
    broker_shipper: str = ""
    pickup_location: str = ""
    delivery_location: str = ""
    equipment: str = ""
    notes: str = ""
    usage_count: int = 0
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.template_id:
            self.template_id = _gen_id("LNT")
        if not self.created_at:
            self.created_at = _utc_now()
        if not self.updated_at:
            self.updated_at = self.created_at
        if not self.name:
            raise ValueError("Lane template name is required")

    def to_dict(self) -> dict:
        return asdict(self)
