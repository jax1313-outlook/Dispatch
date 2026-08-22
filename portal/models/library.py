"""Library model — approved reusable knowledge and production parts.

Library stores approved current facts, reusable intelligence, packets,
forms, rate sheets, and production parts. Library is not temporary workspace.

Governance gate (Stage 5 of DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1.md,
Claude-3 repo, Hard Conflict List item 1): a human placing a document is the approval -- no
second gate is added for that path, matching tri-department Library's own
`ingest_human_document()` behavior and Constitution Section 7.4 ("Library begins as a reliable
service"). A machine-submitted candidate is different: it starts `pending_review` and can only
become `approved` via `review_candidate()`, which requires an external, non-system reviewer
identity -- mirroring tri-department Library's `review_candidate()` gate exactly. As of this
change, nothing in Dispatch actually calls `add_record(..., submitted_by="machine")` yet (the
only caller, `portal/routes/api.py::library_add()`, does not pass `submitted_by`, so it keeps
today's human-placed, auto-approved behavior unchanged) -- this closes a latent gap before
anything machine-driven exists to hit it, not an active violation happening today.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from portal.models import get_memory_dir, atomic_write_json

SECTIONS = [
    "company",
    "broker",
    "customer",
    "location_intelligence",
    "operations",
    "intelligence",
]

RECORD_STATUSES = ["approved", "pending_review", "rejected"]

# Identities that may never be used as a reviewer -- a submitting system may not approve its
# own candidate. Matches dispatch_library.models.RESERVED_SYSTEM_IDENTITIES /
# dispatch_publisher.models.RESERVED_SYSTEM_IDENTITIES from the tri-department build.
RESERVED_SYSTEM_IDENTITIES = {"PUBLISHER", "SYSTEM", "AUTOMATION", "INTELLIGENCE", "LIBRARY"}


class LibraryApprovalError(ValueError):
    """Raised when a machine-submitted candidate is reviewed without a valid external
    reviewer identity, or when review_candidate() targets a record that isn't pending_review."""

COMPANY_ASSETS = [
    "W-9", "Insurance", "Authority", "Business Card", "Rate Sheets",
    "Terms", "Capabilities", "Compliance Documents", "Fleet/Equipment",
    "Driver Qualifications",
]

LOCATION_FIELDS = [
    "Facility Name", "Address", "Gate Notes", "Dock Notes",
    "Check-in Procedure", "Security Requirements", "Liftgate Requirement",
    "Pallet Jack Requirement", "Forklift Availability", "Load Time",
    "Unload Time", "Detention History", "Driver Notes",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _library_path() -> Path:
    d = get_memory_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "library.json"


def _load() -> dict:
    path = _library_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save(data: dict) -> None:
    path = _library_path()
    atomic_write_json(path, data)


def get_all() -> dict:
    return _load()


def get_section(section: str) -> list[dict]:
    return _load().get(section, [])


def add_record(section: str, name: str, content: str = "",
               metadata: dict | None = None, submitted_by: str = "human") -> dict:
    """Add a Library record.

    submitted_by="human" (default): the placing human's action IS the approval -- the record
    is immediately `status="approved"`, exactly as before this change. This is the only path
    Dispatch's UI (`portal/routes/api.py::library_add()`) uses today.

    submitted_by="machine": the record starts `status="pending_review"` and is not returned by
    `get_available_company_assets()` until `review_candidate()` promotes it. Use this for any
    future automated/agent-driven nomination path (e.g. a Publisher content-generation worker
    proposing a reusable template) -- never call this with submitted_by="machine" from a path a
    human directly and knowingly triggered.
    """
    if section not in SECTIONS:
        raise ValueError(f"Invalid library section: {section}")
    if submitted_by not in ("human", "machine"):
        raise ValueError(f"Invalid submitted_by: {submitted_by!r} (must be 'human' or 'machine')")
    data = _load()
    if section not in data:
        data[section] = []
    now = _utc_now()
    record = {
        "id": f"LIB-{section.upper()[:3]}-{len(data[section]) + 1:04d}",
        "section": section,
        "name": name,
        "content": content,
        "metadata": metadata or {},
        "status": "approved" if submitted_by == "human" else "pending_review",
        "submitted_by": submitted_by,
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": now,
        "updated_at": now,
    }
    data[section].append(record)
    _save(data)
    return record


def review_candidate(record_id: str, approve: bool, reviewed_by: str) -> dict:
    """Promote or reject a machine-submitted (`pending_review`) record.

    Mirrors tri-department Library's `review_candidate()` gate: `reviewed_by` must be a real,
    external, non-system identity. Raises LibraryApprovalError if it isn't, or if the target
    record is not currently `pending_review` (a human-placed record is never pending_review, so
    this function is simply not the right call for one -- use update_record() instead).
    """
    if not reviewed_by or reviewed_by.strip().upper() in RESERVED_SYSTEM_IDENTITIES:
        raise LibraryApprovalError(
            "review_candidate() requires a real, external, non-system reviewed_by identity "
            "(a submitting system may not approve its own candidate)."
        )
    data = _load()
    for section_records in data.values():
        for rec in section_records:
            if rec["id"] == record_id:
                if rec.get("status") != "pending_review":
                    raise LibraryApprovalError(
                        f"record {record_id!r} is not pending_review (status="
                        f"{rec.get('status')!r}); only machine-submitted candidates awaiting "
                        f"review can be passed to review_candidate()."
                    )
                rec["status"] = "approved" if approve else "rejected"
                rec["reviewed_by"] = reviewed_by
                rec["reviewed_at"] = _utc_now()
                rec["updated_at"] = _utc_now()
                _save(data)
                if approve:
                    _trigger_publisher_on_approval(rec)
                return rec
    raise KeyError(f"Library record not found: {record_id}")


def _trigger_publisher_on_approval(rec: dict) -> None:
    """Stage 1 of DISPATCH_END_TO_END_DEPLOYMENT_PLAN_v1.md (Claude-3 repo): approving a Library
    candidate that originated from an Intelligence finding creates a Publisher action.

    Scoped narrowly -- fires only for candidates carrying Intelligence provenance metadata (set
    by intelligence.promote_to_candidate(), currently the only submitted_by="machine" caller in
    the codebase, so in practice this is the only kind of pending_review record that exists
    today). A future submitted_by="machine" caller without this metadata is a no-op here, not an
    error -- this stage does not claim to handle every possible machine-submitted candidate.
    """
    if rec.get("metadata", {}).get("source_type") != "INTELLIGENCE":
        return

    from portal.models import publisher as pub_model

    pub_model.create_action(
        action_type="Broker Packet Required",
        sandbox_id=f"LIBRARY-{rec['id']}",
        trigger_reason=(
            f"Library candidate {rec['id']} approved (source: Intelligence finding "
            f"{rec['metadata'].get('source_finding_id', 'UNKNOWN')})"
        ),
        available_data=get_available_company_assets(),
        missing_data=get_missing_company_assets(),
    )


def update_record(record_id: str, name: str | None = None,
                  content: str | None = None,
                  metadata: dict | None = None) -> dict:
    data = _load()
    for section_records in data.values():
        for rec in section_records:
            if rec["id"] == record_id:
                if name is not None:
                    rec["name"] = name
                if content is not None:
                    rec["content"] = content
                if metadata is not None:
                    rec["metadata"] = metadata
                rec["updated_at"] = _utc_now()
                _save(data)
                return rec
    raise KeyError(f"Library record not found: {record_id}")


def delete_record(record_id: str) -> dict:
    data = _load()
    for section, section_records in data.items():
        for i, rec in enumerate(section_records):
            if rec["id"] == record_id:
                removed = section_records.pop(i)
                _save(data)
                return removed
    raise KeyError(f"Library record not found: {record_id}")


def get_available_company_assets() -> list[str]:
    """Return names of company assets that have been uploaded AND approved.

    A pending_review (machine-submitted, unreviewed) record must not count as available -- that
    would let an unreviewed candidate silently satisfy a missing-asset check, which is exactly
    the kind of premature-truth path this governance gate exists to close. Pre-existing records
    (all of which have status="approved", since submitted_by="machine" did not exist before this
    change) are unaffected by this filter.
    """
    records = get_section("company")
    return [r["name"] for r in records if r.get("status") == "approved"]


def get_missing_company_assets() -> list[str]:
    """Return company assets that are required but not yet uploaded."""
    available = set(get_available_company_assets())
    return [a for a in COMPANY_ASSETS if a not in available]
