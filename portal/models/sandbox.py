"""Sandbox state management — local JSON storage.

The sandbox holds temporary analysis, card state, and pending decisions.
Each card (SAM or Dispatch) gets a sandbox entry that tracks its lifecycle.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from portal.models import get_data_dir, atomic_write_json

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

# This sandbox is shared: every entry already carries source_type ("dispatch"
# for freight, "sam" for CIN-Lite/SAM opportunities) in its sid
# (SBX-{SOURCE_TYPE}-{source_id}) and its stored fields. Any freight-only
# operation -- the HOLD sweep below, a future Operations Cockpit view, etc. --
# must read through get_all_for_source() rather than get_all(), so it can
# never see or act on another program's entries just because they live in
# the same store. See DISPATCH_PROMOTION_PLAN_FIRST_LIVE_LOAD.md (Claude-3
# sandbox repo) item 4 for the scoping design and its test coverage.
SANDBOX_SOURCE_FREIGHT = "dispatch"

# HOLD: a freight sandbox entry that loses a booking decision gets a 3-hour
# window before it's swept. Per Mike's ruling (see the promotion plan's HOLD
# sign-off log), a Sandbox/HOLD entry is a decision-support artifact, not a
# Dispatch record -- records are created only by ingestion or Publisher --
# so run_hold_sweep() below deletes expired entries outright rather than
# archiving them; that does not fall under the Library/Archive retention
# doctrine.
#
# What THIS entry ends up on a HOLD clock (i.e. which open entries count as
# "losing siblings" when another is booked) is not decided by this schema
# today -- there is no "competing candidates for one decision" relationship
# between sandbox entries yet. start_hold() below only does the timer
# bookkeeping once a caller has already decided an entry is on HOLD; it does
# not itself decide who's on HOLD. That decision is intentionally left open
# rather than guessed at here -- see the promotion plan for the open
# question.
HOLD_HOURS = 3


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


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
    atomic_write_json(path, data)


def get_all() -> dict:
    return _load()


def get_all_for_source(source_type: str = SANDBOX_SOURCE_FREIGHT) -> dict:
    """All sandbox entries for ONE program only.

    Defaults to freight. A caller must explicitly pass another
    source_type (e.g. "sam") to see anything outside freight -- the
    default is the safe one, not the permissive one.
    """
    return {sid: entry for sid, entry in _load().items() if entry.get("source_type") == source_type}


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
    data_origin: str = "LIVE",
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
        # An entry that was ever SIMULATED stays SIMULATED. Re-ingesting a
        # sample must not launder it into a live record.
        if entry.get("data_origin") != "SIMULATED":
            entry["data_origin"] = data_origin
    else:
        entry = {
            "id": sid,
            "source_type": source_type,
            "source_id": source_id,
            "data_origin": data_origin,
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
            "hold_started_at": None,
            "hold_expires_at": None,
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


def start_hold(sandbox_id: str, now: datetime | None = None) -> dict:
    """Start the HOLD_HOURS clock on one sandbox entry.

    This only does the timer bookkeeping. It does not decide WHICH
    entries should go on HOLD -- that requires a "competing candidates
    for one decision" relationship this schema doesn't have yet (see
    module docstring above). A caller who has already decided an entry
    lost a booking decision calls this to start its clock.
    """
    data = _load()
    if sandbox_id not in data:
        raise KeyError(f"Sandbox entry not found: {sandbox_id}")
    now_dt = now or datetime.now(timezone.utc)
    started = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    expires = (now_dt + timedelta(hours=HOLD_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = data[sandbox_id]
    entry["hold_started_at"] = started
    entry["hold_expires_at"] = expires
    entry["updated_at"] = started
    entry["events"].append({"action": "hold_started", "expires_at": expires, "timestamp": started})
    _save(data)
    return entry


def run_hold_sweep(source_type: str = SANDBOX_SOURCE_FREIGHT, now: datetime | None = None) -> list[str]:
    """Delete (not archive) every entry, IN THE GIVEN PROGRAM ONLY, whose
    HOLD clock has expired.

    Defaults to freight; sweeping any other program's entries requires
    a caller to explicitly pass its source_type -- the default must
    never be "everything in the store." Deleted, not archived: a
    Sandbox/HOLD entry is a decision-support artifact, not a Dispatch
    record, so this does not fall under the no-delete-without-Mike
    retention doctrine that governs Library and Archive.

    Returns the ids of deleted entries.
    """
    now_dt = now or datetime.now(timezone.utc)
    data = _load()
    expired_ids = [
        sid for sid, entry in data.items()
        if entry.get("source_type") == source_type
        and entry.get("hold_expires_at")
        and now_dt >= _parse_utc(entry["hold_expires_at"])
    ]
    for sid in expired_ids:
        del data[sid]
    if expired_ids:
        _save(data)
    return expired_ids


def clear_simulated(source_type: str | None = None) -> list[str]:
    """Remove every SIMULATED entry. Returns the ids removed.

    The one-click clear behind BLOCK-01. It removes only records marked
    SIMULATED -- a live record is never deleted by this, whatever else is true
    of it, because a clear that could take real freight with it is a clear
    nobody would dare press.

    Entries with no `data_origin` predate the marking and are left alone: this
    function deletes what it can prove is sample data, not what it cannot
    prove is real.
    """
    data = _load()
    removed = [
        sid for sid, entry in data.items()
        if entry.get("data_origin") == "SIMULATED"
        and (source_type is None or entry.get("source_type") == source_type)
    ]
    for sid in removed:
        del data[sid]
    if removed:
        _save(data)
    return removed


def simulated_count(source_type: str | None = None) -> int:
    """How many SIMULATED entries are present."""
    return len([
        1 for entry in _load().values()
        if entry.get("data_origin") == "SIMULATED"
        and (source_type is None or entry.get("source_type") == source_type)
    ])
