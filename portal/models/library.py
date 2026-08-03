"""Library model — approved reusable knowledge and production parts.

Library stores approved current facts, reusable intelligence, packets,
forms, rate sheets, and production parts. Library is not temporary workspace.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from portal.models import get_memory_dir

SECTIONS = [
    "company",
    "broker",
    "customer",
    "location_intelligence",
    "operations",
    "intelligence",
]

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
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_all() -> dict:
    return _load()


def get_section(section: str) -> list[dict]:
    return _load().get(section, [])


def add_record(section: str, name: str, content: str = "",
               metadata: dict | None = None) -> dict:
    if section not in SECTIONS:
        raise ValueError(f"Invalid library section: {section}")
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
        "status": "approved",
        "created_at": now,
        "updated_at": now,
    }
    data[section].append(record)
    _save(data)
    return record


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
    """Return names of company assets that have been uploaded."""
    records = get_section("company")
    return [r["name"] for r in records]


def get_missing_company_assets() -> list[str]:
    """Return company assets that are required but not yet uploaded."""
    available = set(get_available_company_assets())
    return [a for a in COMPANY_ASSETS if a not in available]
