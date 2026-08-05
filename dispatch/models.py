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

LOAD_SOURCES = [
    "direct",
    "dat",
    "truckstop",
    "broker_call",
    "email",
    "referral",
    "website",
    "other",
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
    source: str = ""
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
        if self.source:
            _validate_choice(self.source, LOAD_SOURCES, "source")

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


ALLOWED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", "gif", "tif", "tiff",
    "doc", "docx", "xls", "xlsx", "csv", "txt", "rtf",
    "zip", "bmp", "webp",
}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB


@dataclass
class EvidenceItem:
    evidence_id: str = ""
    load_id: str = ""
    related_milestone_id: str | None = None
    evidence_type: str = "document"
    file_path: str | None = None
    original_filename: str = ""
    file_size: int = 0
    mime_type: str = ""
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
class IFTAFuelEvidence:
    """A checksummed receipt upload linked to one IFTA fuel purchase.

    Deliberately not `EvidenceItem` reused with an empty `load_id`: the
    `evidence` table's `load_id` column is a NOT NULL foreign key into
    `loads` (enforced -- `PRAGMA foreign_keys=ON`), so an evidence row with
    no real load can't be inserted there. Fuel purchases aren't scoped to
    a load, so this is a small, separately-scoped mirror of the same
    checksummed-upload shape instead.
    """

    evidence_id: str = ""
    purchase_id: str = ""
    original_filename: str = ""
    file_path: str | None = None
    file_size: int = 0
    mime_type: str = ""
    checksum: str | None = None
    description: str = ""
    uploaded_by: str = ""
    capture_time: str = ""

    def __post_init__(self) -> None:
        if not self.evidence_id:
            self.evidence_id = _gen_id("FUELEV")
        if not self.capture_time:
            self.capture_time = _utc_now()

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


SERVICE_TYPES = [
    "oil_change", "tire_rotation", "tire_replacement", "brake_inspection",
    "brake_replacement", "engine_service", "transmission_service",
    "dot_inspection", "general_inspection", "hvac_service", "electrical",
    "suspension", "alignment", "other",
]
MAINTENANCE_STATUSES = ["scheduled", "due", "overdue", "completed", "skipped"]


@dataclass
class MaintenanceSchedule:
    schedule_id: str = ""
    equipment_id: str = ""
    service_type: str = "other"
    description: str = ""
    interval_miles: float = 0.0
    interval_days: int = 0
    last_service_date: str = ""
    last_service_miles: float = 0.0
    next_due_date: str = ""
    next_due_miles: float = 0.0
    status: str = "scheduled"
    cost_estimate: float = 0.0
    vendor: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.schedule_id:
            self.schedule_id = _gen_id("MNT")
        if not self.created_at:
            self.created_at = _utc_now()
        if not self.updated_at:
            self.updated_at = self.created_at
        if not self.equipment_id:
            raise ValueError("Equipment ID is required")
        _validate_choice(self.service_type, SERVICE_TYPES, "service_type")
        _validate_choice(self.status, MAINTENANCE_STATUSES, "status")

    @property
    def is_overdue(self) -> bool:
        if not self.next_due_date:
            return False
        return self.next_due_date < _utc_now()[:10]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_overdue"] = self.is_overdue
        return d


COMPLIANCE_DOC_TYPES = [
    "insurance_liability",
    "insurance_cargo",
    "insurance_physical",
    "ifta_license",
    "irp_registration",
    "usdot_biennial",
    "ucr_registration",
    "medical_card",
    "cdl",
    "drug_test",
    "mvr",
    "hazmat_endorsement",
    "twic_card",
    "bod_filing",
    "operating_authority",
    "other",
]
COMPLIANCE_DOC_STATUSES = ["active", "expiring_soon", "expired", "renewed"]
COMPLIANCE_ENTITY_TYPES = ["company", "driver", "equipment"]


@dataclass
class ComplianceDocument:
    doc_id: str = ""
    entity_type: str = "company"
    entity_id: str = ""
    doc_type: str = "other"
    title: str = ""
    issuing_authority: str = ""
    doc_number: str = ""
    issue_date: str = ""
    expiry_date: str = ""
    alert_days: int = 30
    status: str = "active"
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.doc_id:
            self.doc_id = _gen_id("COMP")
        if not self.created_at:
            self.created_at = _utc_now()
        if not self.updated_at:
            self.updated_at = self.created_at
        _validate_choice(self.doc_type, COMPLIANCE_DOC_TYPES, "doc_type")
        _validate_choice(self.status, COMPLIANCE_DOC_STATUSES, "status")
        _validate_choice(self.entity_type, COMPLIANCE_ENTITY_TYPES, "entity_type")

    @property
    def is_expired(self) -> bool:
        if not self.expiry_date:
            return False
        return self.expiry_date < _utc_now()[:10]

    @property
    def days_until_expiry(self) -> int | None:
        if not self.expiry_date:
            return None
        from datetime import datetime
        today = datetime.fromisoformat(_utc_now()[:10])
        expiry = datetime.fromisoformat(self.expiry_date)
        return (expiry - today).days

    @property
    def needs_alert(self) -> bool:
        d = self.days_until_expiry
        if d is None:
            return False
        return d <= self.alert_days

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_expired"] = self.is_expired
        d["days_until_expiry"] = self.days_until_expiry
        d["needs_alert"] = self.needs_alert
        return d


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


IFTA_JURISDICTIONS = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
    "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE",
    "QC", "SK", "YT",
]

IFTA_QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

IFTA_TAX_RATES: dict[str, dict[str, float]] = {
    "AL": {"rate": 0.29, "surcharge": 0.0},
    "AK": {"rate": 0.08, "surcharge": 0.0},
    "AZ": {"rate": 0.26, "surcharge": 0.0},
    "AR": {"rate": 0.285, "surcharge": 0.0},
    "CA": {"rate": 0.389, "surcharge": 0.0},
    "CO": {"rate": 0.205, "surcharge": 0.0},
    "CT": {"rate": 0.451, "surcharge": 0.0},
    "DE": {"rate": 0.22, "surcharge": 0.0},
    "FL": {"rate": 0.36, "surcharge": 0.0},
    "GA": {"rate": 0.334, "surcharge": 0.0},
    "HI": {"rate": 0.16, "surcharge": 0.0},
    "ID": {"rate": 0.38, "surcharge": 0.0},
    "IL": {"rate": 0.467, "surcharge": 0.0},
    "IN": {"rate": 0.54, "surcharge": 0.11},
    "IA": {"rate": 0.325, "surcharge": 0.0},
    "KS": {"rate": 0.26, "surcharge": 0.0},
    "KY": {"rate": 0.282, "surcharge": 0.02},
    "LA": {"rate": 0.20, "surcharge": 0.0},
    "ME": {"rate": 0.312, "surcharge": 0.0},
    "MD": {"rate": 0.365, "surcharge": 0.0},
    "MA": {"rate": 0.24, "surcharge": 0.0},
    "MI": {"rate": 0.30, "surcharge": 0.0},
    "MN": {"rate": 0.285, "surcharge": 0.0},
    "MS": {"rate": 0.18, "surcharge": 0.0},
    "MO": {"rate": 0.195, "surcharge": 0.0},
    "MT": {"rate": 0.3275, "surcharge": 0.0},
    "NE": {"rate": 0.306, "surcharge": 0.0},
    "NV": {"rate": 0.27, "surcharge": 0.0055},
    "NH": {"rate": 0.222, "surcharge": 0.0},
    "NJ": {"rate": 0.414, "surcharge": 0.0},
    "NM": {"rate": 0.21, "surcharge": 0.01},
    "NY": {"rate": 0.342, "surcharge": 0.0},
    "NC": {"rate": 0.382, "surcharge": 0.0},
    "ND": {"rate": 0.23, "surcharge": 0.0},
    "OH": {"rate": 0.385, "surcharge": 0.0},
    "OK": {"rate": 0.19, "surcharge": 0.0},
    "OR": {"rate": 0.38, "surcharge": 0.0},
    "PA": {"rate": 0.576, "surcharge": 0.0},
    "RI": {"rate": 0.34, "surcharge": 0.0},
    "SC": {"rate": 0.26, "surcharge": 0.0},
    "SD": {"rate": 0.30, "surcharge": 0.0},
    "TN": {"rate": 0.27, "surcharge": 0.0},
    "TX": {"rate": 0.20, "surcharge": 0.0},
    "UT": {"rate": 0.315, "surcharge": 0.0},
    "VT": {"rate": 0.32, "surcharge": 0.0},
    "VA": {"rate": 0.302, "surcharge": 0.0},
    "WA": {"rate": 0.494, "surcharge": 0.0},
    "WV": {"rate": 0.357, "surcharge": 0.0},
    "WI": {"rate": 0.329, "surcharge": 0.0},
    "WY": {"rate": 0.24, "surcharge": 0.0},
    "DC": {"rate": 0.235, "surcharge": 0.0},
    "AB": {"rate": 0.13, "surcharge": 0.0},
    "BC": {"rate": 0.277, "surcharge": 0.0},
    "MB": {"rate": 0.14, "surcharge": 0.0},
    "NB": {"rate": 0.155, "surcharge": 0.0},
    "NL": {"rate": 0.165, "surcharge": 0.0},
    "NS": {"rate": 0.155, "surcharge": 0.0},
    "NT": {"rate": 0.107, "surcharge": 0.0},
    "NU": {"rate": 0.064, "surcharge": 0.0},
    "ON": {"rate": 0.143, "surcharge": 0.0},
    "PE": {"rate": 0.132, "surcharge": 0.0},
    "QC": {"rate": 0.192, "surcharge": 0.0},
    "SK": {"rate": 0.15, "surcharge": 0.0},
    "YT": {"rate": 0.062, "surcharge": 0.0},
}


@dataclass
class IFTATripLeg:
    leg_id: str = ""
    load_id: str = ""
    jurisdiction: str = ""
    miles: float = 0.0
    date: str = ""
    vehicle_id: str = ""
    notes: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.leg_id:
            self.leg_id = _gen_id("IFTA")
        if not self.created_at:
            self.created_at = _utc_now()
        if not self.date:
            self.date = _utc_now()[:10]
        if self.jurisdiction:
            _validate_choice(self.jurisdiction, IFTA_JURISDICTIONS, "jurisdiction")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IFTAFuelPurchase:
    purchase_id: str = ""
    jurisdiction: str = ""
    date: str = ""
    gallons: float = 0.0
    amount: float = 0.0
    vehicle_id: str = ""
    vendor: str = ""
    notes: str = ""
    created_at: str = ""
    evidence_id: str | None = None

    def __post_init__(self) -> None:
        if not self.purchase_id:
            self.purchase_id = _gen_id("FUEL")
        if not self.created_at:
            self.created_at = _utc_now()
        if not self.date:
            self.date = _utc_now()[:10]
        if self.jurisdiction:
            _validate_choice(self.jurisdiction, IFTA_JURISDICTIONS, "jurisdiction")

    @property
    def price_per_gallon(self) -> float:
        if self.gallons > 0:
            return round(self.amount / self.gallons, 4)
        return 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["price_per_gallon"] = self.price_per_gallon
        return d


IFTA_REPORT_APPROVAL_STATUSES = ["draft", "sealed"]
IFTA_PAYMENT_RECOMMENDATIONS = ["remit", "credit", "no_payment_due"]


@dataclass
class IFTAReportApproval:
    """A frozen, submitted-for-approval snapshot of one quarter's IFTA
    report. Mirrors Hold's proven ifta_worksheets draft/sealed lifecycle
    (src/dispatch/ifta/package.py) -- 'draft' from submission until the
    reviewer's approval link is verified, then 'sealed' once, never
    reverted. The snapshot is frozen at submission time so later edits to
    trip legs/fuel purchases can never silently change what's under
    review or what gets sealed."""
    approval_id: str = ""
    year: int = 0
    quarter: int = 0
    vehicle_id: str = ""
    status: str = "draft"
    snapshot: dict = field(default_factory=dict)
    recommendation: dict | None = None
    submitted_at: str = ""
    sealed_at: str | None = None
    approved_by: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.approval_id:
            self.approval_id = _gen_id("IFTAAPR")
        if not self.created_at:
            self.created_at = _utc_now()
        if not self.submitted_at:
            self.submitted_at = _utc_now()
        _validate_choice(self.status, IFTA_REPORT_APPROVAL_STATUSES, "status")

    def to_dict(self) -> dict:
        return asdict(self)


IFTA_EXCEPTION_TYPES = [
    "fuel_no_miles",
    "miles_no_fuel_gap",
    "fleet_mpg_out_of_band",
    "broken_evidence_linkage",
    "late_arrival_closed_quarter",
    "corner_clipping",
]


@dataclass
class IFTAException:
    """One detector finding for one submitted quarter -- six of Hold's
    ten exception types (src/dispatch/ifta/exceptions.py), the ones that
    port to data Dispatch actually has. Advisory only: nothing in this
    codebase reads an exception as a reason to block a submission or a
    seal. Persisted once, at submission time, alongside the frozen
    IFTAReportApproval snapshot it was computed from -- never updated or
    deleted after that, matching Hold's insert-only ifta_exceptions
    convention."""
    exception_id: str = ""
    approval_id: str = ""
    exception_type: str = ""
    detail: str = ""
    related_record_ids: list = field(default_factory=list)
    detected_at: str = ""

    def __post_init__(self) -> None:
        if not self.exception_id:
            self.exception_id = _gen_id("IFTAEXC")
        if not self.detected_at:
            self.detected_at = _utc_now()
        if self.exception_type:
            _validate_choice(self.exception_type, IFTA_EXCEPTION_TYPES, "exception_type")

    def to_dict(self) -> dict:
        return asdict(self)


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


PAY_TYPES = ["per_mile", "per_load", "percentage", "hourly", "bonus", "deduction", "reimbursement"]
PAY_STATUSES = ["pending", "approved", "paid"]


@dataclass
class DriverPay:
    pay_id: str = ""
    driver_id: str = ""
    load_id: str = ""
    pay_type: str = "per_mile"
    description: str = ""
    amount: float = 0.0
    rate: float = 0.0
    miles: float = 0.0
    hours: float = 0.0
    percentage: float = 0.0
    pay_period: str = ""
    status: str = "pending"
    paid_date: str = ""
    notes: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.pay_id:
            self.pay_id = _gen_id("PAY")
        if not self.created_at:
            self.created_at = _utc_now()
        if not self.driver_id:
            raise ValueError("Driver ID is required")
        _validate_choice(self.pay_type, PAY_TYPES, "pay_type")
        _validate_choice(self.status, PAY_STATUSES, "status")
        if not self.amount and self.rate:
            if self.pay_type == "per_mile" and self.miles:
                self.amount = round(self.rate * self.miles, 2)
            elif self.pay_type == "hourly" and self.hours:
                self.amount = round(self.rate * self.hours, 2)

    def to_dict(self) -> dict:
        return asdict(self)


BROKER_STATUSES = ["active", "inactive", "blacklisted"]


@dataclass
class BrokerContact:
    broker_id: str = ""
    company_name: str = ""
    contact_name: str = ""
    phone: str = ""
    email: str = ""
    mc_number: str = ""
    dot_number: str = ""
    address: str = ""
    payment_terms: str = ""
    notes: str = ""
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.broker_id:
            self.broker_id = _gen_id("BRK")
        if not self.created_at:
            self.created_at = _utc_now()
        if not self.updated_at:
            self.updated_at = self.created_at
        if not self.company_name:
            raise ValueError("Broker company name is required")
        if self.status:
            _validate_choice(self.status, BROKER_STATUSES, "status")

    def to_dict(self) -> dict:
        return asdict(self)
