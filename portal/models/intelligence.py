"""Operational Intelligence model — reusable intelligence records.

Stores broker, customer, location, facility, route, return-route,
position, and market intelligence. Experience becomes an asset.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from portal.models import get_memory_dir

INTEL_TYPES = [
    "location",
    "broker",
    "customer",
    "route",
    "position",
    "market",
]

INTEL_LABELS = {
    "location": "Location Intelligence",
    "broker": "Broker Intelligence",
    "customer": "Customer Intelligence",
    "route": "Route Intelligence",
    "position": "Position Intelligence",
    "market": "Market Intelligence",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _intel_path() -> Path:
    d = get_memory_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "intelligence.json"


def _load() -> dict:
    path = _intel_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save(data: dict) -> None:
    path = _intel_path()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_all() -> dict:
    return _load()


def get_by_type(intel_type: str) -> list[dict]:
    return _load().get(intel_type, [])


def create_record(intel_type: str, subject: str, content: str,
                  source: str = "", metadata: dict | None = None) -> dict:
    if intel_type not in INTEL_TYPES:
        raise ValueError(f"Invalid intelligence type: {intel_type}")
    data = _load()
    if intel_type not in data:
        data[intel_type] = []
    now = _utc_now()
    record = {
        "id": f"INT-{intel_type.upper()[:3]}-{len(data[intel_type]) + 1:04d}",
        "intel_type": intel_type,
        "subject": subject,
        "content": content,
        "source": source,
        "metadata": metadata or {},
        "created_at": now,
        "updated_at": now,
    }
    data[intel_type].append(record)
    _save(data)
    return record


def update_record(record_id: str, content: str | None = None,
                  metadata: dict | None = None) -> dict:
    data = _load()
    for type_records in data.values():
        for rec in type_records:
            if rec["id"] == record_id:
                if content is not None:
                    rec["content"] = content
                if metadata is not None:
                    rec["metadata"] = metadata
                rec["updated_at"] = _utc_now()
                _save(data)
                return rec
    raise KeyError(f"Intelligence record not found: {record_id}")


def total_count() -> int:
    data = _load()
    return sum(len(records) for records in data.values())


def promote_to_candidate(record_id: str) -> dict:
    """Promote a broker-type Intelligence record into a Library candidate.

    Stage 1 of DISPATCH_END_TO_END_DEPLOYMENT_PLAN_v1.md (Claude-3 repo) -- the first wired
    object-flow link between departments. Scoped narrowly to intel_type="broker" records only:
    the only Intelligence type with a real automated producer (create_inquiry(), portal/routes/
    api.py). Raises for any other intel_type -- the other five types are out of scope for this
    stage, not silently supported.

    Delegates to library.add_record(submitted_by="machine"), so the resulting record starts
    pending_review and only becomes Library truth via review_candidate() -- this function grants
    no approval itself.
    """
    data = _load()
    record = None
    for type_records in data.values():
        for rec in type_records:
            if rec["id"] == record_id:
                record = rec
                break
        if record is not None:
            break
    if record is None:
        raise KeyError(f"Intelligence record not found: {record_id}")
    if record["intel_type"] != "broker":
        raise ValueError(
            f"promote_to_candidate() is scoped to intel_type='broker' records only "
            f"(Stage 1 of DISPATCH_END_TO_END_DEPLOYMENT_PLAN_v1.md); got "
            f"intel_type={record['intel_type']!r} for {record_id!r}."
        )

    from portal.models import library as lib_model

    return lib_model.add_record(
        section="broker",
        name=record["subject"],
        content=record["content"],
        metadata={"source_finding_id": record["id"], "source_type": "INTELLIGENCE"},
        submitted_by="machine",
    )
