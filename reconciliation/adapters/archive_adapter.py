"""Adapter: portal/models/archive.py records -> ArchiveRecordCanonicalView.

Scoped to the "publisher" archive section specifically, because that is the exact path named in
DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1.md's Hard Conflict List item 3:
"Archive handoff lacks approval-status precondition." `cin_lite/archive.py` (the canonical
Archive engine per Section 3 of the matrix) uses a different record shape entirely
(contract_id-keyed, not this module's `id`/`section`/`record_data` shape) and would need its own
adapter if a future stage needs one -- out of scope here, since Stage 4's immediate value is
making the Publisher-approval-gate gap inspectable, not adapting every Archive engine at once.

Pure functions only: no file I/O, no writes.
"""
from __future__ import annotations

from typing import Any, Dict, List

from reconciliation.adapters.publisher_adapter import RESERVED_SYSTEM_IDENTITIES
from reconciliation.contracts import ArchiveRecordCanonicalView


def dispatch_archive_record_to_canonical_view(record: Dict[str, Any]) -> ArchiveRecordCanonicalView:
    """Translate one portal/models/archive.py record into a canonical-shaped read-only view.

    `had_verified_approval` is only meaningful for section == "publisher" records (the ones
    produced by archive_publisher_action()) -- it inspects record_data.approved_by, which will
    be absent on every record today because Stage 5 (the enforced approval gate that would
    populate it) has not been applied. For any other section, this field is reported as False
    with no claim that "unapproved" is even a meaningful concept for that section (e.g. "load"
    and "location_history" records aren't Publisher-approval-gated at all) -- callers should
    treat a False on a non-publisher section as "not applicable," not "failed a check."
    """
    record_data = record.get("record_data", {})
    had_verified_approval = False
    if record.get("section") == "publisher":
        approved_by = record_data.get("approved_by")
        had_verified_approval = bool(
            approved_by and approved_by.strip().upper() not in RESERVED_SYSTEM_IDENTITIES
        )

    return ArchiveRecordCanonicalView(
        record_id=record["id"],
        section=record["section"],
        source_id=record["source_id"],
        had_verified_approval=had_verified_approval,
        archived_at=record.get("archived_at", ""),
    )


def adapt_all(archive_data: Dict[str, List[Dict[str, Any]]]) -> List[ArchiveRecordCanonicalView]:
    """Translate the full dict returned by portal.models.archive.get_all()."""
    results: List[ArchiveRecordCanonicalView] = []
    for records in archive_data.values():
        for record in records:
            results.append(dispatch_archive_record_to_canonical_view(record))
    return results


def unverified_publisher_archive_count(archive_data: Dict[str, List[Dict[str, Any]]]) -> int:
    """How many archived Publisher actions have no verifiable approval on record?

    This is the concrete, countable form of Hard Conflict List item 3 -- a number Mike can look
    at directly rather than trusting a prose claim that the gap exists.
    """
    views = adapt_all(archive_data)
    return sum(1 for v in views if v.section == "publisher" and not v.had_verified_approval)
