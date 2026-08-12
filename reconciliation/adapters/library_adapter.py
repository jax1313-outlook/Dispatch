"""Adapter: portal/models/library.py records -> canonical LibraryObject.

Per DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1.md Section 3: "Library: replace
governance, adapt taxonomy." This module is the taxonomy-adaptation half. It does not touch
governance (Stage 5) -- it only translates section names and record shape.

Pure functions only: takes the dict Dispatch's `portal.models.library.get_all()` already
returns, produces `reconciliation.contracts.LibraryObject` instances. No file I/O, no writes.
"""
from __future__ import annotations

from typing import Any, Dict, List

from reconciliation.contracts import LibraryObject, LibraryObjectSource, LibraryObjectStatus

# Dispatch's 6 sections -> the tri-department build's 15-collection taxonomy
# (DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md Section 4.1). Every Dispatch section has an
# unambiguous, name-matching target except "intelligence", which Dispatch's own docstring
# ("Library stores... reusable intelligence...") doesn't scope to a single canonical
# collection -- mapped to Reference as the generic catch-all bucket rather than guessing which
# of Location_Intelligence/Route_Intelligence/Company it belongs to per record.
SECTION_TO_COLLECTION = {
    "company": "Company",
    "broker": "Broker",
    "customer": "Customer",
    "location_intelligence": "Location_Intelligence",
    "operations": "Operations",
    "intelligence": "Reference",
}

# Dispatch's add_record() hardcodes status="approved" on every record (see
# DISPATCH_DEPARTMENT_RECONCILIATION_v1.md Section 2). There is no "who approved this" field
# anywhere in Dispatch's Library schema, so accepted_by cannot honestly be a real name --
# inventing one would violate the No-Fabrication Rule. This constant marks that gap explicitly
# instead of hiding it behind a plausible-looking but false identity.
UNKNOWN_APPROVER = "UNKNOWN — migrated from portal/models/library.py; original approver not recorded"


def dispatch_record_to_library_object(section: str, record: Dict[str, Any]) -> LibraryObject:
    """Translate one Dispatch library record into a canonical-shaped LibraryObject.

    Always returns source=LEGACY_UNVERIFIED_ORIGIN (see contracts.py docstring for why this is
    not HUMAN_PLACED) and status=CURRENT (Dispatch's own record is already live/in-use data;
    marking it anything else would misrepresent its actual role in the running system).
    """
    collection = SECTION_TO_COLLECTION.get(section)
    if collection is None:
        raise ValueError(
            f"Dispatch library section {section!r} has no mapping in SECTION_TO_COLLECTION "
            f"(known sections: {sorted(SECTION_TO_COLLECTION)}) -- this means Dispatch's "
            f"portal/models/library.py added a new SECTIONS entry that this adapter does not "
            f"yet know about; extend the mapping rather than guessing."
        )

    return LibraryObject(
        object_code=record["id"],
        collection=collection,
        title=record.get("name", record["id"]),
        version=1,
        status=LibraryObjectStatus.CURRENT,
        source=LibraryObjectSource.LEGACY_UNVERIFIED_ORIGIN,
        body_or_uri=record.get("content", ""),
        accepted_by=UNKNOWN_APPROVER,
        accepted_at=record.get("created_at", record.get("updated_at", "")),
        tags=[f"dispatch_section:{section}"],
    )


def adapt_all(library_data: Dict[str, List[Dict[str, Any]]]) -> List[LibraryObject]:
    """Translate the full dict returned by portal.models.library.get_all() into LibraryObjects.

    Caller is responsible for actually calling get_all() -- this function takes plain data so it
    stays testable without file I/O and without importing portal.models.library at module load
    time (this package should not require Dispatch's Flask app context to be importable).
    """
    results: List[LibraryObject] = []
    for section, records in library_data.items():
        for record in records:
            results.append(dispatch_record_to_library_object(section, record))
    return results
