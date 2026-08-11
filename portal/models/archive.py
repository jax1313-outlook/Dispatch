"""Archive model — completed history and evidence.

Archive stores completed records, decisions, evidence, cards, briefs,
source records, documents, POD/BOL records, detention evidence, and
audit bundles. Archive is the system of record for completed history.

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

from portal.models import get_archive_dir

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
]

SECTION_LABELS = {
    "load": "Load Archive",
    "decision": "Decision Archive",
    "publisher": "Publisher Archive",
    "location_history": "Location History Archive",
    "broker_history": "Broker History Archive",
}


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
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


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


def total_count() -> int:
    data = _load()
    return sum(len(records) for records in data.values())
