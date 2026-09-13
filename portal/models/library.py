"""Library model — a compatibility projection of the Library Department. Not a second Library.

**Authority (owner ruling, Mike Zachary, 2026-09-13).** The separate Library repository is the
authoritative Library Department and `D:\\Memory` is its physical shelf. Dispatch and Portal
consume or display Library information through bounded interfaces. This module keeps the Portal's
existing routes, pages, document upload, operations feed and Intelligence promotion working while
that is true:

  * **Catalog mode** -- `DISPATCH_LIBRARY_CATALOG` names the Library catalog. Every read is a
    projection of the catalog into the shape this module has always returned, and every write
    goes to the catalog's own paths: a human placement, or a candidate for review. No
    `library.json` is read or written. Edits and deletions are refused, because the Library never
    edits or deletes -- a change is a new version. If the variable is set but `dispatch_library`
    cannot be imported, every call refuses rather than falling back to JSON, which would quietly
    make the JSON a second Library.
  * **Legacy mode** -- no catalog configured. The JSON store behaves as it did, with one change:
    it lives in the portal data directory and never in the Library shelf. When
    `DISPATCH_MEMORY_ROOT` is set, neither `library.json` nor `LibraryDocuments` is written there;
    if the portal data directory *is* the shelf, writes refuse and reads come back empty.

Uploaded documents are bytes the Portal received, not files a person put on the shelf, so in both
modes they are kept under the portal data directory's `LibraryDocuments`. In catalog mode the
Library records the placement -- who, what type, the file's SHA-256 -- and the version's body names
the stored document.

Governance gate (Stage 5 of DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1.md): a human
placing a document is the approval -- no second gate is added for that path. A machine-submitted
candidate starts pending review and becomes approved only through `review_candidate()` with an
external, non-system reviewer. In catalog mode the Library also validates it first.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from dispatch.models import ALLOWED_EXTENSIONS, MAX_FILE_SIZE
from portal.models import get_data_dir, atomic_write_json

LIBRARY_CATALOG_ENV = "DISPATCH_LIBRARY_CATALOG"
DOCUMENT_PREFIX = "portal-document:"

SECTIONS = [
    "company",
    "broker",
    "customer",
    "location_intelligence",
    "operations",
    "intelligence",
]

#: Where each Portal section lives among the fifteen Library collections. `intelligence` has no
#: single collection -- Operational Intelligence is unmapped pending ownership review -- so in
#: catalog mode it reads empty and refuses writes instead of guessing one.
SECTION_COLLECTIONS = {
    "company": "Company",
    "broker": "Broker",
    "customer": "Customer",
    "location_intelligence": "Location_Intelligence",
    "operations": "Operations",
    "intelligence": None,
}

RECORD_STATUSES = ["approved", "pending_review", "rejected"]

# Identities that may never be used as a reviewer. The nine refused by the Library (plan v2
# ruling 6), compared the way the Library compares them: case, spaces and hyphens folded.
RESERVED_SYSTEM_IDENTITIES = {
    "PUBLISHER", "SYSTEM", "AUTOMATION", "INTELLIGENCE", "LIBRARY", "JOE", "DISPATCH", "COMI",
    "EMAIL_HELPER",
}


def _normalise_identity(name: str | None) -> str:
    return (name or "").strip().upper().replace(" ", "_").replace("-", "_")


class LibraryApprovalError(ValueError):
    """Raised when a machine-submitted candidate is reviewed without a valid external
    reviewer identity, or when review_candidate() targets a record that isn't pending_review."""


class LibraryAuthorityError(ValueError):
    """The operation belongs to the authoritative Library and this projection will not do it."""


class LibraryProjectionError(RuntimeError):
    """The JSON store or its documents would have been written into the Library shelf."""


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


# ── where the projection may live ─────────────────────────────────────────────

def _shelf_root() -> Path | None:
    explicit = os.environ.get("DISPATCH_MEMORY_ROOT", "").strip()
    return Path(explicit) if explicit else None


def _same_directory(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def _projection_dir() -> Path:
    """The portal data directory, unless that is the Library shelf."""
    data = get_data_dir()
    shelf = _shelf_root()
    if shelf is not None and _same_directory(data, shelf):
        raise LibraryProjectionError(
            f"PORTAL_DATA_DIR and DISPATCH_MEMORY_ROOT are both {data}. That directory is the Library "
            "shelf; the Portal's library.json and LibraryDocuments may not be written into it. Point "
            "PORTAL_DATA_DIR at the portal data directory, or configure DISPATCH_LIBRARY_CATALOG."
        )
    return data


def _library_path() -> Path:
    d = _projection_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "library.json"


def documents_dir() -> Path:
    """Where uploaded Library documents are kept: the portal data directory, never the shelf."""
    d = _projection_dir() / "LibraryDocuments"
    d.mkdir(parents=True, exist_ok=True)
    return d


def projection_status() -> dict:
    """What this module is doing, for an operator: mode, store, and anything left in the shelf."""
    status = {"mode": "catalog" if _catalog_configured() else "legacy"}
    if status["mode"] == "catalog":
        status["catalog"] = os.environ.get(LIBRARY_CATALOG_ENV)
    else:
        try:
            status["store"] = str(_projection_dir() / "library.json")
        except LibraryProjectionError as exc:
            status["refused"] = str(exc)
    shelf = _shelf_root()
    if shelf is not None:
        left = [name for name in ("library.json", "LibraryDocuments") if (shelf / name).exists()]
        if left:
            status["left_in_shelf"] = [str(shelf / name) for name in left]
    return status


# ── catalog mode ─────────────────────────────────────────────────────────────

def _catalog_configured() -> bool:
    return bool(os.environ.get(LIBRARY_CATALOG_ENV, "").strip())


def _open_library():
    try:
        from dispatch_library.catalog import open_library
    except ImportError as exc:
        raise LibraryAuthorityError(
            f"{LIBRARY_CATALOG_ENV} is set, but the Library (dispatch_library) cannot be imported: {exc}. "
            "Refusing to fall back to library.json, which would make it a second Library."
        ) from exc
    return open_library(os.environ[LIBRARY_CATALOG_ENV], memory_root=_shelf_root(), consumer_role="PORTAL")


def _code_for(section: str, name: str) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-") or "RECORD"
    return f"PORTAL-{section.upper()}-{slug}"


def _object_record(section: str, obj, lib) -> dict:
    metadata = {
        "object_type": obj.object_type,
        "version": obj.version_label,
        "lifecycle_state": obj.lifecycle_state,
        "library_object_id": obj.library_object_id,
        "capture_channel": obj.capture_channel,
    }
    metadata.update(lib.catalog.metadata(obj.object_code))
    body = obj.body_or_uri or ""
    if body.startswith(DOCUMENT_PREFIX):
        metadata["document"] = body[len(DOCUMENT_PREFIX):]
    return {
        "id": obj.object_code,
        "section": section,
        "name": obj.title,
        "content": "" if body.startswith(DOCUMENT_PREFIX) else body,
        "metadata": metadata,
        "status": "approved",
        "submitted_by": "human" if obj.source.value == "HUMAN_PLACED" else "machine",
        "reviewed_by": obj.accepted_by if obj.source.value == "APPROVED_CANDIDATE" else None,
        "reviewed_at": obj.accepted_at if obj.source.value == "APPROVED_CANDIDATE" else None,
        "accepted_by": obj.accepted_by,
        "created_at": obj.accepted_at,
        "updated_at": obj.accepted_at,
        "authority": "library_catalog",
    }


def _candidate_record(section: str, row) -> dict:
    status = {"REJECTED": "rejected"}.get(row["status"], "pending_review")
    return {
        "id": row["candidate_id"],
        "section": section,
        "name": row["proposed_title"],
        "content": row["proposed_body_or_reference"],
        "metadata": {
            "source_type": row["source_type"],
            "source_finding_id": row["source_finding_id"],
            "candidate_status": row["status"],
            "proposed_object_code": row["proposed_object_code"],
            "recommended_object_type": row["recommended_object_type"],
            "object_type": row["proposed_object_type"],
            "validation_result": row["validation_result"],
        },
        "status": status,
        "submitted_by": "human" if row["submitted_by_role"] == "HUMAN" else "machine",
        "reviewed_by": row["reviewed_by"],
        "reviewed_at": row["reviewed_at"],
        "created_at": row["created_at"],
        "updated_at": row["reviewed_at"] or row["created_at"],
        "authority": "library_catalog",
    }


def _catalog_section(lib, section: str) -> list[dict]:
    collection = SECTION_COLLECTIONS.get(section)
    if collection is None:
        return []
    records = [_object_record(section, obj, lib) for obj in lib.list_current(collection)]
    for row in lib.catalog.candidates(("SUBMITTED", "PENDING_REVIEW", "VALIDATED", "DEFERRED", "REJECTED")):
        if row["proposed_collection_id"] == collection:
            records.append(_candidate_record(section, row))
    return records


def _collection_for(section: str) -> str:
    collection = SECTION_COLLECTIONS[section]
    if collection is None:
        raise ValueError(
            f"the {section!r} section has no Library collection (Operational Intelligence is unmapped "
            "pending ownership review); nothing was placed"
        )
    return collection


def _catalog_add(section: str, name: str, content: str, metadata: dict, submitted_by: str) -> dict:
    collection = _collection_for(section)
    lib = _open_library()
    try:
        if submitted_by == "human":
            accepted_by = metadata.get("accepted_by")
            if not accepted_by:
                raise ValueError("a human placement names the person placing it (metadata.accepted_by)")
            obj = lib.ingest_human_document(
                metadata.get("object_code") or _code_for(section, name), collection, name, content or "",
                accepted_by, object_type=metadata.get("object_type"),
                capture_channel=metadata.get("capture_channel"),
            )
            return _object_record(section, obj, lib)

        source_type = metadata.get("source_type") or "DISPATCH"
        role = "INTELLIGENCE" if source_type == "INTELLIGENCE" else "DISPATCH"
        row = lib.catalog.submit_candidate(
            submitted_by_role=role, source_type=source_type, collection=collection,
            proposed_object_code=metadata.get("object_code") or _code_for(section, name),
            proposed_title=name, proposed_body_or_reference=content or name,
            source_finding_id=metadata.get("source_finding_id"),
            mission_record_id=metadata.get("mission_record_id"),
            workflow_event_id=metadata.get("workflow_event_id"),
            proposed_object_type=metadata.get("object_type"),
        )
        return _candidate_record(section, row)
    finally:
        lib.close()


def _section_for_collection(collection: str) -> str:
    return next((s for s, c in SECTION_COLLECTIONS.items() if c == collection), "")


def _catalog_review(record_id: str, approve: bool, reviewed_by: str) -> dict:
    lib = _open_library()
    try:
        row = lib.catalog.candidate_row(record_id)
        if row is None:
            if lib.catalog.object_row(record_id) is not None:
                raise LibraryApprovalError(
                    f"record {record_id!r} is an accepted Library object, not a candidate awaiting review"
                )
            raise KeyError(f"Library record not found: {record_id}")
        if row["status"] not in ("PENDING_REVIEW", "VALIDATED"):
            raise LibraryApprovalError(f"record {record_id!r} is {row['status']}; it awaits no review")
        try:
            if approve and row["status"] == "PENDING_REVIEW":
                passed, problems = lib.catalog.validate_candidate(record_id)
                if not passed:
                    raise LibraryApprovalError(
                        "the Library has not validated this candidate: " + "; ".join(problems)
                    )
            decided = lib.catalog.decide_candidate(record_id, "APPROVED" if approve else "REJECTED", reviewed_by)
        except LibraryApprovalError:
            raise
        except ValueError as exc:
            raise LibraryApprovalError(str(exc)) from exc
        section = _section_for_collection(decided["proposed_collection_id"])
        if approve:
            obj = lib.current(decided["proposed_object_code"])
            record = _object_record(section, obj, lib)
            record["metadata"].update(source_type=decided["source_type"],
                                      source_finding_id=decided["source_finding_id"])
            return record
        return _candidate_record(section, decided)
    finally:
        lib.close()


# ── the module's public surface ──────────────────────────────────────────────

def _load() -> dict:
    if _catalog_configured():
        lib = _open_library()
        try:
            return {section: records for section in SECTIONS if (records := _catalog_section(lib, section))}
        finally:
            lib.close()
    try:
        path = _library_path()
    except LibraryProjectionError:
        return {}
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

    submitted_by="human" (default): the placing human's action IS the approval. In catalog mode the
    Library also needs `metadata.accepted_by` (the person) and `metadata.object_type`; without a
    type it refuses and records a missing-field notice.

    submitted_by="machine": a candidate pending review. In catalog mode it is a Library candidate:
    Intelligence when `metadata.source_type == "INTELLIGENCE"`, otherwise Dispatch, which must name
    `metadata.mission_record_id` or `metadata.workflow_event_id`.
    """
    if section not in SECTIONS:
        raise ValueError(f"Invalid library section: {section}")
    if submitted_by not in ("human", "machine"):
        raise ValueError(f"Invalid submitted_by: {submitted_by!r} (must be 'human' or 'machine')")
    if _catalog_configured():
        return _catalog_add(section, name, content, dict(metadata or {}), submitted_by)

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


# ── Documents ───────────────────────────────────────────────────────
#
# Built 2026-09-09. Until this existed a Library record could hold a name and
# some text, and nothing else. Every asset Publisher's packet manifest asks for
# -- W-9, insurance, authority, rate sheets, terms -- is a document, and there
# was no way to put one in. The missing-asset list could be satisfied by typing
# a name, which is the kind of premature truth this codebase is careful about
# everywhere else.
#
# Files live under the portal data directory's LibraryDocuments -- never in the
# Library shelf (owner ruling, 2026-09-13). The record keeps the filename, the
# size and the stored name, so what Publisher needs to fetch is on the record.


def _safe_stored_name(record_id: str, original_filename: str) -> str:
    """A stored filename that cannot escape the documents directory.

    The record id leads, so two uploads of `w9.pdf` never collide, and only the
    extension is taken from what the browser sent. A filename is attacker- or
    accident-supplied text; it does not get to choose a path.
    """
    ext = ""
    if "." in original_filename:
        candidate = original_filename.rsplit(".", 1)[-1].lower()
        if candidate.isalnum() and len(candidate) <= 8:
            ext = "." + candidate
    return f"{record_id}{ext}"


def _check_document(file_data: bytes, original_filename: str) -> None:
    if not file_data:
        raise ValueError("a document needs a file")
    if len(file_data) > MAX_FILE_SIZE:
        raise ValueError(
            f"file exceeds the {MAX_FILE_SIZE // (1024 * 1024)} MB limit")
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"file type not allowed: .{ext}" if ext else "file has no extension")


def add_document(section: str, name: str, file_data: bytes,
                 original_filename: str, content: str = "",
                 metadata: dict | None = None,
                 submitted_by: str = "human") -> dict:
    """Place one document in the Library.

    Legacy mode: the record is created first so its id can name the file; if writing the file
    fails, the record is removed rather than left pointing at nothing.

    Catalog mode: the Library never deletes, so the order is reversed. The file is written first,
    under a name derived from the object code and its SHA-256; then the Library accepts the
    placement (a named person and an object type). If the Library refuses, the file just written
    is removed and no record exists.
    """
    _check_document(file_data, original_filename)
    if submitted_by not in ("human", "machine"):
        raise ValueError(f"Invalid submitted_by: {submitted_by!r} (must be 'human' or 'machine')")

    if _catalog_configured():
        if submitted_by != "human":
            raise LibraryAuthorityError(
                "a document upload is a human placement; machine nominations are Library candidates"
            )
        metadata = dict(metadata or {})
        collection = _collection_for(section)
        code = metadata.get("object_code") or _code_for(section, name)
        digest = hashlib.sha256(file_data).hexdigest()
        stored = _safe_stored_name(f"{code}-{digest[:12]}", original_filename)
        target = documents_dir() / stored
        existed = target.exists()
        if not existed:
            target.write_bytes(file_data)
        lib = _open_library()
        try:
            try:
                obj = lib.ingest_human_document(
                    code, collection, name, f"{DOCUMENT_PREFIX}{stored}", metadata.get("accepted_by") or "",
                    object_type=metadata.get("object_type"), capture_channel=metadata.get("capture_channel"),
                )
            except ValueError:
                if not existed:
                    target.unlink(missing_ok=True)
                if not metadata.get("accepted_by"):
                    raise ValueError("a document placement names the person placing it (accepted_by)") from None
                raise
            for key, value, kind in (("original_filename", original_filename, "TEXT"),
                                     ("size_bytes", str(len(file_data)), "INTEGER"),
                                     ("sha256", digest, "TEXT")):
                lib.catalog.set_metadata(code, key, value, kind)
            return _object_record(section, lib.current(code), lib)
        finally:
            lib.close()

    record = add_record(section, name, content=content,
                        metadata=metadata, submitted_by=submitted_by)
    stored = _safe_stored_name(record["id"], original_filename)
    try:
        (documents_dir() / stored).write_bytes(file_data)
    except OSError:
        delete_record(record["id"])
        raise

    record["metadata"] = dict(record.get("metadata") or {})
    record["metadata"].update({
        "document": stored,
        "original_filename": original_filename,
        "size_bytes": len(file_data),
    })
    return update_record(record["id"], metadata=record["metadata"])


def document_path(record_id: str) -> Path | None:
    """The file behind a record, or None when the record has no document or the
    file is not where the record says it is."""
    if _catalog_configured():
        lib = _open_library()
        try:
            obj = lib.current(record_id)
        finally:
            lib.close()
        if obj is None or not (obj.body_or_uri or "").startswith(DOCUMENT_PREFIX):
            return None
        path = documents_dir() / obj.body_or_uri[len(DOCUMENT_PREFIX):]
        return path if path.exists() else None
    for records in _load().values():
        for record in records:
            if record.get("id") != record_id:
                continue
            stored = (record.get("metadata") or {}).get("document")
            if not stored:
                return None
            path = documents_dir() / stored
            return path if path.exists() else None
    return None


def review_candidate(record_id: str, approve: bool, reviewed_by: str) -> dict:
    """Promote or reject a machine-submitted (`pending_review`) record.

    `reviewed_by` must be a real, external, non-system identity. In catalog mode the Library
    validates the candidate before the approval is recorded.
    """
    if not reviewed_by or not reviewed_by.strip() or _normalise_identity(reviewed_by) in RESERVED_SYSTEM_IDENTITIES:
        raise LibraryApprovalError(
            "review_candidate() requires a real, external, non-system reviewed_by identity "
            "(a submitting system may not approve its own candidate)."
        )
    if _catalog_configured():
        rec = _catalog_review(record_id, approve, reviewed_by)
        if approve:
            _trigger_publisher_on_approval(rec)
        return rec

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
    by intelligence.promote_to_candidate()). Any other approval is a no-op here, not an error.
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
    if _catalog_configured():
        raise LibraryAuthorityError(
            "the Library never edits an accepted record in place; place the change as a new version, "
            "or submit it as a candidate"
        )
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
    if _catalog_configured():
        raise LibraryAuthorityError(
            "the Library never deletes a record; supersede it, or mark it for retention review"
        )
    data = _load()
    for section, section_records in data.items():
        for i, rec in enumerate(section_records):
            if rec["id"] == record_id:
                removed = section_records.pop(i)
                _save(data)
                return removed
    raise KeyError(f"Library record not found: {record_id}")


def get_available_company_assets() -> list[str]:
    """Names of company assets that are approved and usable.

    A pending_review record never counts. In catalog mode neither does a current asset that is
    REVIEW_DUE: it is blocked from external use until a person renews it.
    """
    records = get_section("company")
    return [
        r["name"] for r in records
        if r.get("status") == "approved"
        and (r.get("metadata") or {}).get("lifecycle_state") != "REVIEW_DUE"
    ]


def get_missing_company_assets() -> list[str]:
    """Return company assets that are required but not yet uploaded."""
    available = set(get_available_company_assets())
    return [a for a in COMPANY_ASSETS if a not in available]
