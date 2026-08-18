"""Local mirrors of the canonical shared object contracts.

Field names and enum values here MUST match `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md` (Claude-3
repo) and the tri-department repos' own `models.py` files exactly, for the objects that have a
literal canonical definition (`LibraryObject`, `LibraryCandidate`). Where Dispatch's existing data
does not carry enough information to construct a full canonical object one-to-one (Publisher and
Archive), this module defines purpose-built "view" dataclasses instead of forcing a bad fit --
see the docstrings on `PublisherActionCanonicalView` and `ArchiveRecordCanonicalView` for why.

No object in this module is truth. These are read-only translations of Dispatch's existing
records for reporting/migration-planning purposes (Stage 4). Nothing here is written back to any
store, and nothing here changes any approval/status semantics (that is Stage 5).
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class LibraryObjectStatus(str, Enum):
    CURRENT = "CURRENT"
    SUPERSEDED = "SUPERSEDED"
    DRAFT_CANDIDATE = "DRAFT_CANDIDATE"


class LibraryObjectSource(str, Enum):
    HUMAN_PLACED = "HUMAN_PLACED"
    APPROVED_CANDIDATE = "APPROVED_CANDIDATE"
    # Not part of the canonical enum (DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md only defines the
    # two values above). Added here, explicitly and visibly, because Dispatch's existing library
    # records predate the tri-department Library's review-gate distinction entirely -- calling
    # them HUMAN_PLACED would claim a fact (a human explicitly reviewed and placed this) that
    # is not established by anything in portal/models/library.py's own data. Flagging the
    # ambiguity honestly is the No-Fabrication-compliant choice; silently picking HUMAN_PLACED
    # would not be.
    LEGACY_UNVERIFIED_ORIGIN = "LEGACY_UNVERIFIED_ORIGIN"


class LibraryCandidateStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SubmittedBy(str, Enum):
    INTELLIGENCE = "INTELLIGENCE"
    PUBLISHER = "PUBLISHER"


def _asdict(obj: Any) -> Dict[str, Any]:
    def _convert(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, list):
            return [_convert(v) for v in value]
        if dataclasses.is_dataclass(value):
            return _asdict(value)
        return value

    return {f.name: _convert(getattr(obj, f.name)) for f in dataclasses.fields(obj)}


@dataclasses.dataclass
class LibraryObject:
    """Mirrors DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md Section 4.1 field-for-field."""

    object_code: str
    collection: str
    title: str
    version: int
    status: LibraryObjectStatus
    source: LibraryObjectSource
    body_or_uri: str
    accepted_by: str
    accepted_at: str = dataclasses.field(default_factory=_utc_now)
    supersedes_version: Optional[int] = None
    tags: List[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return _asdict(self)


@dataclasses.dataclass
class LibraryCandidate:
    """Mirrors DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md Section 3.5 field-for-field."""

    submitted_by: SubmittedBy
    source_type: str
    collection: str
    proposed_object_code: str
    proposed_title: str
    proposed_body_or_reference: str
    source_finding_id: Optional[str] = None
    status: LibraryCandidateStatus = LibraryCandidateStatus.PENDING_REVIEW
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    candidate_id: Optional[str] = None
    created_at: str = dataclasses.field(default_factory=_utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return _asdict(self)


@dataclasses.dataclass
class PublisherActionCanonicalView:
    """A read-only canonical-shaped VIEW of a Dispatch portal/models/publisher.py action.

    This is deliberately NOT a reconstruction of the tri-department build's DraftReviewPackage --
    that object references readiness_packet_id/inventory_id/missing_notice_id, none of which
    Dispatch's action queue produces. Forcing those fields to exist would mean inventing IDs for
    objects that were never created, which is exactly what the No-Fabrication Rule forbids.
    Instead this view reports what IS known about a Dispatch action in canonical-adjacent terms,
    and is explicit about the one fact that matters most for Stage 5: whether an enforced
    approval gate actually stands behind `approved_by`. Stage 5 has since added that real code
    gate to `portal/models/publisher.py::update_action_status()` (the `APPROVED` transition now
    unconditionally requires a real, external, non-system `approved_by` or raises
    `PublisherApprovalError`), so `is_approval_enforced` is now always True -- see
    `reconciliation/adapters/publisher_adapter.py::dispatch_action_to_canonical_view()` for why
    that's a code-path fact rather than a per-record verification, and
    `would_pass_tri_department_gate()` for the separate per-record question.
    """

    action_id: str
    action_type: str
    status: str
    approved_by: Optional[str]
    is_approval_enforced: bool
    missing_data: List[str]
    manifest: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return _asdict(self)


@dataclasses.dataclass
class ArchiveRecordCanonicalView:
    """A read-only canonical-shaped VIEW of an archived record.

    Same rationale as PublisherActionCanonicalView: the tri-department build's
    ArchiveHandoffPackage references a review_id whose approval was structurally verified before
    the handoff could be constructed (create_archive_handoff() blocks otherwise). Dispatch's
    existing archive paths (both cin_lite/archive.py and portal/models/archive.py) have no such
    precondition today, so `had_verified_approval` reports what's actually knowable from the
    archived record, not what the tri-department contract would require.
    """

    record_id: str
    section: str
    source_id: str
    had_verified_approval: bool
    archived_at: str

    def to_dict(self) -> Dict[str, Any]:
        return _asdict(self)
