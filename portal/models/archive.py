"""Archive model — completed history and evidence.

Archive stores completed records, decisions, evidence, cards, briefs,
source records, documents, POD/BOL records, detention evidence, and
audit bundles. Archive is the system of record for completed history.

Archive Review Queue (recovered from Stage 6,
DISPATCH_STAGE6_ARCHIVE_BUILD_DESIGN_v1.md): age-based, not
version-based -- create_record() below has always silently no-op'd on a
repeat source_id, so there is no multi-version history for Archive
records at all, and the literal "Current + 3 Previous" trigger
ARCHIVE_REVIEW_POLICY.md specifies cannot exist until Archive records
gain real version history. REVIEW_AGE_DAYS is a documented, tunable
default standing in for that until then. IT IS NOT DOCTRINE, and the
number is Mike's to set -- flagged in the Wave 1 report as decision 3.

Governance gate (Stage 5 of DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1.md,
Claude-3 repo, Hard Conflict List item 3): `archive_publisher_action()` previously archived
whatever it was given with no precondition. It now refuses to archive a Publisher action that
was never approved, mirroring tri-department Publisher's `create_archive_handoff()`, which
blocks unless the referenced review is APPROVED_BY_MIKE.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from portal.models import get_archive_dir, atomic_write_json

# Same reserved-identity set as portal.models.publisher.RESERVED_SYSTEM_IDENTITIES. Duplicated
# rather than imported to keep this module's only real dependency (portal.models) unchanged --
# archive.py and publisher.py are siblings, and importing one model module from another for a
# single constant is not worth the coupling.
RESERVED_SYSTEM_IDENTITIES = {"PUBLISHER", "SYSTEM", "AUTOMATION", "INTELLIGENCE", "LIBRARY"}


class ArchiveApprovalError(ValueError):
    """Raised when attempting to archive a Publisher action that was never approved by a real,
    external, non-system identity."""

ARCHIVE_SECTIONS = [
    "load",
    "decision",
    "publisher",
    "location_history",
    "broker_history",
    "intelligence",
]

SECTION_LABELS = {
    "load": "Load Archive",
    "decision": "Decision Archive",
    "publisher": "Publisher Archive",
    "location_history": "Location History Archive",
    "broker_history": "Broker History Archive",
    "intelligence": "Intelligence Archive",
}


REVIEW_STATUSES = ["pending", "kept", "deleted"]
REVIEW_AGE_DAYS = 180


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _archive_path() -> Path:
    d = get_archive_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "archive.json"


def _load() -> dict:
    path = _archive_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save(data: dict) -> None:
    path = _archive_path()
    atomic_write_json(path, data)


def get_all() -> dict:
    return _load()


def get_section(section: str) -> list[dict]:
    return _load().get(section, [])


def create_record(section: str, source_id: str, title: str,
                  record_data: dict, decision_summary: str = "",
                  evidence: dict | None = None) -> dict:
    if section not in ARCHIVE_SECTIONS:
        raise ValueError(f"Invalid archive section: {section}")
    data = _load()
    if section not in data:
        data[section] = []

    for existing in data[section]:
        if existing.get("source_id") == source_id:
            return existing

    now = _utc_now()
    record = {
        "id": f"ARC-{section.upper()[:3]}-{len(data[section]) + 1:04d}",
        "section": section,
        "source_id": source_id,
        "title": title,
        "record_data": record_data,
        "decision_summary": decision_summary,
        "evidence": evidence or {},
        "archived_at": now,
        "review_status": "pending",
        "reviewed_at": None,
        "reviewed_by": None,
        "disposition_reason": None,
    }
    data[section].append(record)
    _save(data)
    return record


def archive_from_sandbox(entry: dict) -> dict:
    """Create an archive record from a sandbox entry."""
    source_type = entry.get("source_type", "unknown")
    decision = entry.get("decision", {})
    decision_summary = (
        f"{decision.get('action', 'unknown')} — {decision.get('reason', 'no reason')}"
        if decision else f"Status: {entry.get('status', 'unknown')}"
    )

    section = "load" if source_type == "dispatch" else "decision"

    return create_record(
        section=section,
        source_id=entry["id"],
        title=entry.get("title", "Unknown"),
        record_data={
            "source_type": source_type,
            "source_id": entry.get("source_id", ""),
            "card_data": entry.get("card_data", {}),
            "score": entry.get("score"),
            "status": entry.get("status", ""),
            "flags": entry.get("flags", []),
            "intelligence": entry.get("intelligence", {}),
            "events": entry.get("events", []),
            "notes": entry.get("notes", ""),
        },
        decision_summary=decision_summary,
        evidence={
            "inquiry_draft": entry.get("inquiry_draft"),
            "publisher_actions": entry.get("publisher_actions", []),
        },
    )


def archive_publisher_action(action: dict) -> dict:
    """Archive a completed publisher action.

    Checks `action["approved_by"]`, not `action["status"]`: by the time the real caller
    (`portal/routes/api.py::update_publisher_action()`) reaches this function, it has already
    called `publisher.update_action_status(action_id, "ARCHIVED", ...)`, so `status` is already
    "ARCHIVED" here, never "APPROVED" -- `approved_by` is what `update_action_status()` stamps
    once, during the APPROVED transition, and it persists forward through to ARCHIVED, so it's
    the only reliable signal of whether this action was ever actually approved.
    """
    approved_by = action.get("approved_by")
    if not approved_by or approved_by.strip().upper() in RESERVED_SYSTEM_IDENTITIES:
        raise ArchiveApprovalError(
            f"Publisher action {action.get('id')!r} cannot be archived: no valid approved_by "
            f"identity recorded. Publisher outputs must be approved by a real, external, "
            f"non-system identity before archival."
        )

    return create_record(
        section="publisher",
        source_id=action["id"],
        title=f"{action['action_type']} — {action.get('sandbox_id', '')}",
        record_data=action,
        decision_summary=(
            f"Publisher action approved by {approved_by} and archived: {action['status']}"
        ),
    )


def archive_from_intelligence(record: dict) -> dict:
    """Create an archive record from an Intelligence record.

    Part B of OPERATIONAL_INTELLIGENCE_VERIFICATION_LABELING_SCOPE_v1.md (Claude-3 repo) --
    closes INTELLIGENCE_COMPLETENESS_REVIEW_v1.md's "must always archive" finding. No approval
    precondition, unlike archive_publisher_action() -- Intelligence's contract requires archiving
    unconditionally, on creation, not gated on any review state (the review/verification concern
    is Part A's separate verification_status field, not an archival gate). create_record()'s
    existing source_id de-duplication makes this safe to call every time a record is created,
    including once this function's own caller is invoked more than once for the same record.
    """
    return create_record(
        section="intelligence",
        source_id=record["id"],
        title=record.get("subject", "Unknown"),
        record_data=record,
        decision_summary=f"Intelligence record captured: {record.get('intel_type', 'unknown')}",
    )


def total_count() -> int:
    data = _load()
    return sum(len(records) for records in data.values())


def _age_days(archived_at: str) -> float | None:
    try:
        ts = datetime.strptime(archived_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return (datetime.now(timezone.utc) - ts).total_seconds() / 86400


def list_review_queue(age_days: int = REVIEW_AGE_DAYS) -> list[dict]:
    """Records still pending review whose age exceeds the threshold --
    the Archive Review Queue. Records written before this field existed
    default to 'pending' via .get(), so nothing predating this recovery
    is silently excluded."""
    data = _load()
    queue: list[dict] = []
    for section, records in data.items():
        for record in records:
            if record.get("review_status", "pending") != "pending":
                continue
            age = _age_days(record.get("archived_at", ""))
            if age is None or age < age_days:
                continue
            queue.append({**record, "age_days": round(age, 1)})
    queue.sort(key=lambda r: r["age_days"], reverse=True)
    return queue


def mark_reviewed(record_id: str, section: str, disposition: str,
                  reason: str = "", reviewed_by: str | None = None) -> dict:
    """Records a Keep/Delete decision.

    'deleted' means the disposition is recorded, never that the record or its
    evidence is physically removed -- per ARCHIVE_REVIEW_POLICY.md Section 6, a
    delete is an approved decision with a full audit trail, not a file-system
    purge. Refuses a record already reviewed, once, ever, matching this
    codebase's existing refuse-resubmission convention (IFTAReportApproval's
    AlreadySubmittedError) rather than letting a second decision overwrite the
    first.
    """
    if disposition not in ("kept", "deleted"):
        raise ValueError(f"Invalid disposition: {disposition!r}")
    data = _load()
    records = data.get(section, [])
    for record in records:
        if record["id"] == record_id:
            if record.get("review_status", "pending") != "pending":
                raise ValueError(
                    f"Archive record {record_id} already reviewed "
                    f"(status={record['review_status']!r})"
                )
            record["review_status"] = disposition
            record["reviewed_at"] = _utc_now()
            record["reviewed_by"] = reviewed_by
            record["disposition_reason"] = reason
            _save(data)
            return record
    raise KeyError(f"Archive record not found: {record_id} in section {section!r}")
