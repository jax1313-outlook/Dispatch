"""Adapter: portal/models/intelligence.py records -> canonical LibraryObject.

**Why this maps into LibraryObject, not IntelligenceFinding** -- this is the one non-obvious
design decision in this adapter set, so it's documented here rather than left implicit:

Dispatch's `portal/models/intelligence.py` docstring describes it as "reusable intelligence
records... Experience becomes an asset" -- accumulated, persistent, reusable knowledge (broker
patterns, location notes, route history). The tri-department build's `IntelligenceFinding` is a
different thing: a per-document analysis result with a routing_queue, risk_flags, and a
verification_status tied to one specific source document, explicitly never truth
(`is_final_decision`/`library_truth` fixed False -- see DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md
Section 3.1). Dispatch's intelligence records have no per-document analysis shape at all -- no
routing queue, no risk flags, no source document reference -- they are closer in kind to what the
tri-department build calls a Library object (or an already-approved Library Candidate) than to a
Finding. Forcing them into IntelligenceFinding's shape would mean inventing routing_queue/
risk_flags/verification_status values that Dispatch's data does not contain -- exactly what the
No-Fabrication Rule forbids. Mapping to LibraryObject only requires translating fields that
actually exist on both sides.

Pure functions only: no file I/O, no writes.
"""
from __future__ import annotations

from typing import Any, Dict, List

from reconciliation.adapters.library_adapter import UNKNOWN_APPROVER
from reconciliation.contracts import LibraryObject, LibraryObjectSource, LibraryObjectStatus

# Dispatch's 6 intel_types (portal/models/intelligence.py INTEL_TYPES) -> the tri-department
# 15-collection taxonomy. "position" and "market" have no matching canonical collection --
# mapped to Reference rather than guessing a more specific one.
INTEL_TYPE_TO_COLLECTION = {
    "location": "Location_Intelligence",
    "broker": "Broker",
    "customer": "Customer",
    "route": "Route_Intelligence",
    "position": "Reference",
    "market": "Reference",
}

UNKNOWN_APPROVER_INTEL = UNKNOWN_APPROVER.replace(
    "portal/models/library.py", "portal/models/intelligence.py"
)


def dispatch_record_to_library_object(record: Dict[str, Any]) -> LibraryObject:
    """Translate one Dispatch intelligence record into a canonical-shaped LibraryObject.

    See module docstring for why the target is LibraryObject rather than IntelligenceFinding.
    """
    intel_type = record["intel_type"]
    collection = INTEL_TYPE_TO_COLLECTION.get(intel_type)
    if collection is None:
        raise ValueError(
            f"Dispatch intelligence type {intel_type!r} has no mapping in "
            f"INTEL_TYPE_TO_COLLECTION (known types: {sorted(INTEL_TYPE_TO_COLLECTION)}) -- "
            f"extend the mapping rather than guessing."
        )

    return LibraryObject(
        object_code=record["id"],
        collection=collection,
        title=record.get("subject", record["id"]),
        version=1,
        status=LibraryObjectStatus.CURRENT,
        source=LibraryObjectSource.LEGACY_UNVERIFIED_ORIGIN,
        body_or_uri=record.get("content", ""),
        accepted_by=UNKNOWN_APPROVER_INTEL,
        accepted_at=record.get("created_at", record.get("updated_at", "")),
        tags=[f"dispatch_intel_type:{intel_type}"] + (
            [f"dispatch_source:{record['source']}"] if record.get("source") else []
        ),
    )


def adapt_all(intelligence_data: Dict[str, List[Dict[str, Any]]]) -> List[LibraryObject]:
    """Translate the full dict returned by portal.models.intelligence.get_all()."""
    results: List[LibraryObject] = []
    for records in intelligence_data.values():
        for record in records:
            results.append(dispatch_record_to_library_object(record))
    return results
