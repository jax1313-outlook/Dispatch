"""Canonical data models for the Dispatch Spine's six deterministic schemas.

Mirrors dispatch/models.py's dataclass + validation + serialization style
(reused, not reinvented -- see DISPATCH_STAGE4_SPINE_SCHEMA_DESIGN_v1.md).
Field names and types follow docs/DISPATCH_SPINE_SPECIFICATION_v1.md
Sections 5-14.

ID format deviates from that design document in one respect, flagged
explicitly: the design called for plain UUIDs, matching the Spec's own
JSON examples. Every one of the 15+ existing entity types in
dispatch/models.py instead uses the `_gen_id(prefix)` helper
(`PREFIX-YYYYMMDD-hex8`), with zero exceptions. Reuse-before-rebuild
favors matching that universal existing convention over introducing the
one plain-UUID scheme in the codebase; this is a deliberate,
implementation-time deviation from the literal approved design, not a
silent one -- easy to change back if Mike prefers the literal Spec
format.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from dispatch.models import _gen_id, _utc_now, _validate_choice

REQUIRED_CLOSING = "This is a recommendation only. No action is authorized. Mike decides."

STATE_LIST = [
    "CREATED",
    "VALIDATION_PENDING",
    "VALIDATION_FAILED",
    "VALIDATED",
    "SCORING_PENDING",
    "SCORED",
    "COGNITIVE_REVIEW_PENDING",
    "COGNITIVE_REVIEW_COMPLETE",
    "ROUTING_PENDING",
    "ROUTED_TO_MANAGER",
    "ROUTED_TO_INTELLIGENCE",
    "ROUTED_TO_PUBLISHER",
    "ROUTED_TO_LIBRARY_REVIEW",
    "ROUTED_TO_ARCHIVE",
    "PORTAL_CARD_PENDING",
    "PORTAL_CARD_CREATED",
    "WAITING_FOR_MIKE",
    "MIKE_APPROVED",
    "MIKE_REJECTED",
    "MIKE_REQUESTED_REVISION",
    "DEFERRED",
    "CONFLICT_RAISED",
    "CONFLICT_RESOLVED",
    "COMPLETED",
    "ARCHIVED",
]

CARD_LEVELS = [0, 1, 2, 3, 4, 5]

APPROVAL_ACTIONS = [
    "APPROVE_DRAFT",
    "REJECT_DRAFT",
    "REQUEST_REVISION",
    "APPROVE_PACKET",
    "APPROVE_LIBRARY_PROMOTION",
    "APPROVE_ARCHIVE_DELETE",
    "APPROVE_ARCHIVE_KEEP",
    "APPROVE_LOAD_PURSUIT",
    "REJECT_LOAD_PURSUIT",
    "APPROVE_DEPLOYMENT",
]

CONFLICT_TYPES = [
    "MISSING_SOURCE",
    "CONTRADICTORY_SOURCE",
    "ROLE_BOUNDARY_RISK",
    "AUTHORITY_RISK",
    "FABRICATION_RISK",
    "VALIDATION_FAILURE",
    "COMPLIANCE_RISK",
    "LEGAL_RISK",
    "ARCHITECTURE_DRIFT_RISK",
    "PORTAL_VISIBILITY_RISK",
]


@dataclass
class WorkItem:
    work_item_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    source_type: str = ""
    source_id: str = ""
    current_state: str = "CREATED"
    priority: str = ""
    consequence_level: int = 0
    assigned_function: str = ""
    required_action: str = ""
    source_confidence: str = ""
    due_date: str | None = None
    related_files: list = field(default_factory=list)
    source_refs: list = field(default_factory=list)
    validation_status: str = ""
    scoring_status: str = ""
    cognitive_status: str = ""
    portal_card_id: str | None = None
    final_disposition: str | None = None

    def __post_init__(self) -> None:
        if not self.work_item_id:
            self.work_item_id = _gen_id("WI")
        now = _utc_now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        _validate_choice(self.current_state, STATE_LIST, "current_state")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Event:
    event_id: str = ""
    timestamp: str = ""
    work_item_id: str = ""
    event_type: str = ""
    actor_type: str = ""
    actor_id: str = ""
    previous_state: str | None = None
    new_state: str = ""
    summary: str = ""
    source_refs: list = field(default_factory=list)
    requires_audit: bool = False

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = _gen_id("EVT")
        if not self.timestamp:
            self.timestamp = _utc_now()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PortalCard:
    card_id: str = ""
    work_item_id: str = ""
    created_at: str = ""
    card_level: int = 0
    card_type: str = ""
    title: str = ""
    summary: str = ""
    source_refs: list = field(default_factory=list)
    recommendation: str = ""
    decision_needed: str | None = None
    allowed_actions: list = field(default_factory=list)
    required_closing: str = REQUIRED_CLOSING

    def __post_init__(self) -> None:
        if not self.card_id:
            self.card_id = _gen_id("CARD")
        if not self.created_at:
            self.created_at = _utc_now()
        _validate_choice(self.card_level, CARD_LEVELS, "card_level")
        if not self.required_closing:
            self.required_closing = REQUIRED_CLOSING

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ApprovalEvent:
    approval_event_id: str = ""
    timestamp: str = ""
    session_id: str | None = None
    user_id: str | None = None
    role: str | None = None
    work_item_id: str = ""
    portal_card_id: str | None = None
    object_type: str = ""
    object_id: str = ""
    object_version: int = 1
    action: str = ""
    previous_state: str | None = None
    new_state: str = ""
    comments: str = ""
    authentication_context: dict | None = None
    audit_id: str = ""

    def __post_init__(self) -> None:
        if not self.approval_event_id:
            self.approval_event_id = _gen_id("APV")
        if not self.timestamp:
            self.timestamp = _utc_now()
        _validate_choice(self.action, APPROVAL_ACTIONS, "action")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConflictEvent:
    conflict_id: str = ""
    timestamp: str = ""
    work_item_id: str = ""
    conflict_type: str = ""
    affected_layer: str = ""
    affected_function: str = ""
    trigger: str = ""
    details: str = ""
    options: list = field(default_factory=list)
    recommended_path: str = ""
    human_decision_needed: bool = True
    current_state: str = ""

    def __post_init__(self) -> None:
        if not self.conflict_id:
            self.conflict_id = _gen_id("CNF")
        if not self.timestamp:
            self.timestamp = _utc_now()
        _validate_choice(self.conflict_type, CONFLICT_TYPES, "conflict_type")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditEvent:
    audit_id: str = ""
    timestamp: str = ""
    work_item_id: str | None = None
    event_id: str | None = None
    actor_type: str = ""
    actor_id: str = ""
    action: str = ""
    previous_state: str | None = None
    new_state: str | None = None
    source_refs: list = field(default_factory=list)
    hash: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.audit_id:
            self.audit_id = _gen_id("AUD")
        if not self.timestamp:
            self.timestamp = _utc_now()

    def to_dict(self) -> dict:
        return asdict(self)
