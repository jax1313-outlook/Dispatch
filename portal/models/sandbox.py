"""Sandbox state management — local JSON storage.

The sandbox holds temporary analysis, card state, and pending decisions.
Each card (SAM or Dispatch) gets a sandbox entry that tracks its lifecycle.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from portal.models import get_data_dir

STATUSES = [
    "OPEN",
    "INTERESTED",
    "PURSUE",
    "WATCH",
    "PASS",
    "INQUIRY_DRAFTED",
    "INQUIRY_SENT_MANUAL",
    "PUBLISHER_REQUIRED",
    "BOOKED",
    "EXPIRED",
    "CLOSED",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sandbox_path() -> Path:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "sandbox.json"


def _load() -> dict:
    path = _sandbox_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save(data: dict) -> None:
    path = _sandbox_path()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_all() -> dict:
    return _load()


def get(sandbox_id: str) -> dict | None:
    return _load().get(sandbox_id)


def update_scoring(sandbox_id: str, scoring: dict) -> dict | None:
    """Update Position/HOS fields and score from a scoring result dict."""
    data = _load()
    if sandbox_id not in data:
        return None
    entry = data[sandbox_id]
    for field in ("position_impact", "return_home_required", "tomorrow_position_risk",
                  "hos_risk", "route_risk", "economic_opportunity_flag"):
        if field in scoring:
            entry[field] = scoring[field]
    if "score" in scoring:
        entry["score"] = scoring["score"]
    if "deadhead_miles" in scoring and scoring["deadhead_miles"] is not None:
        entry["card_data"]["deadhead_miles"] = scoring["deadhead_miles"]
    if "fuel_estimate" in scoring and scoring["fuel_estimate"] is not None:
        entry["card_data"]["fuel_estimate"] = scoring["fuel_estimate"]
    entry["updated_at"] = _utc_now()
    _save(data)
    return entry


def create_entry(
    source_type: str,
    source_id: str,
    title: str,
    card_data: dict,
    intelligence: dict | None = None,
    flags: list[str] | None = None,
    summary: str = "",
    score: int | None = None,
    decision: dict | None = None,
) -> dict:
    data = _load()
    sid = f"SBX-{source_type.upper()}-{source_id}"
    now = _utc_now()

    if sid in data:
        entry = data[sid]
        entry["card_data"] = card_data
        entry["updated_at"] = now
        if intelligence is not None:
            entry["intelligence"] = intelligence
        if flags is not None:
            entry["flags"] = flags
        if summary:
            entry["summary"] = summary
        if score is not None:
            entry["score"] = score
        if decision is not None:
            entry["decision"] = decision
    else:
        entry = {
            "id": sid,
            "source_type": source_type,
            "source_id": source_id,
            "status": "OPEN",
            "title": title,
            "score": score,
            "created_at": now,
            "updated_at": now,
            "events": [{"action": "created", "status": "OPEN", "timestamp": now}],
            "card_data": card_data,
            "intelligence": intelligence or {},
            "flags": flags or [],
            "summary": summary,
            "decision": decision or {},
            "inquiry_draft": None,
            "publisher_actions": [],
            "notes": "",
            "position_impact": "Unknown",
            "return_home_required": "Unknown",
            "tomorrow_position_risk": "Unknown",
            "hos_risk": "Unknown",
            "route_risk": "Unknown",
            "economic_opportunity_flag": "Unknown",
        }
    data[sid] = entry
    _save(data)
    return entry


def update_status(sandbox_id: str, new_status: str, note: str = "") -> dict:
    if new_status not in STATUSES:
        raise ValueError(f"Invalid status: {new_status}")
    data = _load()
    if sandbox_id not in data:
        raise KeyError(f"Sandbox entry not found: {sandbox_id}")

    now = _utc_now()
    entry = data[sandbox_id]
    old_status = entry["status"]
    entry["status"] = new_status
    entry["updated_at"] = now
    entry["events"].append(
        {"action": "status_change", "from": old_status, "to": new_status, "note": note, "timestamp": now}
    )
    _save(data)
    return entry


def set_inquiry_draft(sandbox_id: str, draft: dict) -> dict:
    data = _load()
    if sandbox_id not in data:
        raise KeyError(f"Sandbox entry not found: {sandbox_id}")
    data[sandbox_id]["inquiry_draft"] = draft
    data[sandbox_id]["updated_at"] = _utc_now()
    _save(data)
    return data[sandbox_id]


def link_engine_load(sandbox_id: str, engine_load_id: str) -> dict:
    """Store an engine load_id on a sandbox entry after booking."""
    data = _load()
    if sandbox_id not in data:
        raise KeyError(f"Sandbox entry not found: {sandbox_id}")
    now = _utc_now()
    data[sandbox_id]["engine_load_id"] = engine_load_id
    data[sandbox_id]["updated_at"] = now
    data[sandbox_id]["events"].append({
        "action": "engine_linked",
        "note": f"Linked to engine load {engine_load_id}",
        "timestamp": now,
    })
    _save(data)
    return data[sandbox_id]


def update_engine_status(sandbox_id: str, engine_status: str) -> dict | None:
    """Sync engine load status back to the sandbox entry's card_data."""
    data = _load()
    if sandbox_id not in data:
        return None
    data[sandbox_id]["card_data"]["engine_status"] = engine_status
    data[sandbox_id]["updated_at"] = _utc_now()
    _save(data)
    return data[sandbox_id]


def add_note(sandbox_id: str, note: str) -> dict:
    data = _load()
    if sandbox_id not in data:
        raise KeyError(f"Sandbox entry not found: {sandbox_id}")
    existing = data[sandbox_id].get("notes", "")
    data[sandbox_id]["notes"] = (existing + "\n" + note).strip() if existing else note
    data[sandbox_id]["updated_at"] = _utc_now()
    _save(data)
    return data[sandbox_id]
