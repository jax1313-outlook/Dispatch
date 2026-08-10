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

# Card consequence level, per docs/DISPATCH_CONSTITUTION_v3.md Section 17
# and docs/DISPATCH_FINAL_BLUEPRINT_v1.md Section 4.4:
# 0 Silent Log, 1 Status, 2 Review, 3 Decision, 4 Conflict, 5 Authority.
CARD_LEVELS = [0, 1, 2, 3, 4, 5]

# Auto-derivation defaults per status, per Version Doctrine's
# "refine, don't silently auto-decide" posture (ALERT_GOVERNANCE_DOCTRINE.md
# Section 1) -- an explicit set_card_level() override always wins over this.
_STATUS_CARD_LEVEL = {
    "OPEN": 2,
    "INTERESTED": 1,
    "PURSUE": 2,
    "WATCH": 1,
    "PASS": 0,
    "INQUIRY_DRAFTED": 3,
    "INQUIRY_SENT_MANUAL": 1,
    "PUBLISHER_REQUIRED": 3,
    "BOOKED": 1,
    "EXPIRED": 0,
    "CLOSED": 0,
}

# Matches helpers.SCORE_HIGH_THRESHOLD -- a high-value opportunity still
# awaiting a decision is bumped to Decision level regardless of its status's
# default, so it doesn't get lost among ordinary Review-level cards.
_HIGH_VALUE_SCORE_THRESHOLD = 90
_HIGH_VALUE_STATUSES = {"OPEN", "INTERESTED", "PURSUE", "WATCH"}


def _derive_card_level(status: str, score: int | None) -> int:
    level = _STATUS_CARD_LEVEL.get(status, 2)
    if (
        score is not None
        and score >= _HIGH_VALUE_SCORE_THRESHOLD
        and status in _HIGH_VALUE_STATUSES
        and level < 3
    ):
        return 3
    return level


def _detect_change_label(
    old_entry: dict,
    card_data: dict,
    intelligence: dict | None,
    flags: list[str] | None,
    summary: str,
    score: int | None,
    decision: dict | None,
) -> str | None:
    """Returns a plain-language Last Change label if this update is
    materially different from what's stored, or None if it's noise that
    shouldn't bump the version -- Dispatch Version Doctrine Section 6:
    "A version should not increase for meaningless system noise unless
    the object record itself materially changes."
    """
    old_cd = old_entry.get("card_data", {}) or {}
    if old_cd.get("rate") != card_data.get("rate"):
        return "Rate Updated"
    if (old_cd.get("pickup_window"), old_cd.get("delivery_window")) != (
        card_data.get("pickup_window"),
        card_data.get("delivery_window"),
    ):
        return "Schedule Changed"
    old_score = old_entry.get("score")
    if score is not None and score != old_score:
        if old_score is None:
            return "Score Added"
        return "Score Increased" if score > old_score else "Score Decreased"
    if summary and summary != old_entry.get("summary"):
        return "Summary Updated"
    old_action = (old_entry.get("decision") or {}).get("action")
    new_action = (decision or {}).get("action")
    if decision is not None and new_action != old_action:
        return "Routing Recommendation Changed"
    if flags is not None and set(flags) != set(old_entry.get("flags") or []):
        return "Flags Updated"
    if card_data != old_cd:
        return "Details Updated"
    return None


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


def _with_version_defaults(entry: dict) -> dict:
    """Backfills version/card_level fields at read time for entries
    written before Stage 5 -- no migration script needed, matching this
    codebase's existing pattern of tolerating legacy records gracefully
    rather than requiring a one-time data migration."""
    entry.setdefault("version", 1)
    entry.setdefault("last_change", "Created")
    entry.setdefault("card_level_override", False)
    if "card_level" not in entry:
        entry["card_level"] = _derive_card_level(entry.get("status", "OPEN"), entry.get("score"))
    return entry


def get_all() -> dict:
    return {sid: _with_version_defaults(e) for sid, e in _load().items()}


def get(sandbox_id: str) -> dict | None:
    entry = _load().get(sandbox_id)
    return _with_version_defaults(entry) if entry is not None else None


def update_scoring(sandbox_id: str, scoring: dict) -> dict | None:
    """Update Position/HOS fields and score from a scoring result dict."""
    data = _load()
    if sandbox_id not in data:
        return None
    entry = data[sandbox_id]
    old_score = entry.get("score")
    old_deadhead = entry.get("card_data", {}).get("deadhead_miles")
    old_fuel = entry.get("card_data", {}).get("fuel_estimate")
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

    new_score = entry.get("score")
    label = None
    if "score" in scoring and new_score != old_score:
        if old_score is None:
            label = "Score Added"
        else:
            label = "Score Increased" if new_score > old_score else "Score Decreased"
    elif entry["card_data"].get("deadhead_miles") != old_deadhead or (
        entry["card_data"].get("fuel_estimate") != old_fuel
    ):
        label = "Route Data Updated"
    if label:
        entry["version"] = entry.get("version", 1) + 1
        entry["last_change"] = label
        if not entry.get("card_level_override"):
            entry["card_level"] = _derive_card_level(entry["status"], new_score)

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
        change_label = _detect_change_label(
            entry, card_data, intelligence, flags, summary, score, decision
        )
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
        if change_label:
            entry["version"] = entry.get("version", 1) + 1
            entry["last_change"] = change_label
            if not entry.get("card_level_override"):
                entry["card_level"] = _derive_card_level(entry["status"], entry.get("score"))
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
            "version": 1,
            "last_change": "Created",
            "card_level": _derive_card_level("OPEN", score),
            "card_level_override": False,
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
    if new_status != old_status:
        entry["version"] = entry.get("version", 1) + 1
        entry["last_change"] = f"Status Changed to {new_status}"
        if not entry.get("card_level_override"):
            entry["card_level"] = _derive_card_level(new_status, entry.get("score"))
    _save(data)
    return entry


def set_card_level(sandbox_id: str, level: int, note: str = "") -> dict:
    """Manager/Mike override of a card's auto-derived consequence level.

    Once set, `_derive_card_level()`'s automatic recompute (on status or
    score changes) is skipped for this entry until the override is
    cleared -- matches ALERT_GOVERNANCE_DOCTRINE.md's "refine, don't
    silently auto-decide" posture: the system proposes a level, Mike may
    override it, and the override sticks.
    """
    if level not in CARD_LEVELS:
        raise ValueError(f"Invalid card_level: {level}")
    data = _load()
    if sandbox_id not in data:
        raise KeyError(f"Sandbox entry not found: {sandbox_id}")
    now = _utc_now()
    entry = data[sandbox_id]
    entry["card_level"] = level
    entry["card_level_override"] = True
    entry["updated_at"] = now
    entry["version"] = entry.get("version", 1) + 1
    entry["last_change"] = f"Card Level Set to {level}" + (f" ({note})" if note else "")
    entry["events"].append({
        "action": "card_level_override",
        "level": level,
        "note": note,
        "timestamp": now,
    })
    _save(data)
    return entry


def clear_card_level_override(sandbox_id: str) -> dict:
    """Return a card to auto-derived card_level going forward."""
    data = _load()
    if sandbox_id not in data:
        raise KeyError(f"Sandbox entry not found: {sandbox_id}")
    entry = data[sandbox_id]
    entry["card_level_override"] = False
    entry["card_level"] = _derive_card_level(entry["status"], entry.get("score"))
    entry["updated_at"] = _utc_now()
    _save(data)
    return entry


def set_inquiry_draft(sandbox_id: str, draft: dict) -> dict:
    data = _load()
    if sandbox_id not in data:
        raise KeyError(f"Sandbox entry not found: {sandbox_id}")
    now = _utc_now()
    entry = data[sandbox_id]
    entry["inquiry_draft"] = draft
    entry["updated_at"] = now
    entry["version"] = entry.get("version", 1) + 1
    entry["last_change"] = "Inquiry Draft Created"
    _save(data)
    return entry


def link_engine_load(sandbox_id: str, engine_load_id: str) -> dict:
    """Store an engine load_id on a sandbox entry after booking."""
    data = _load()
    if sandbox_id not in data:
        raise KeyError(f"Sandbox entry not found: {sandbox_id}")
    now = _utc_now()
    entry = data[sandbox_id]
    entry["engine_load_id"] = engine_load_id
    entry["updated_at"] = now
    entry["version"] = entry.get("version", 1) + 1
    entry["last_change"] = "Linked to Dispatch Load"
    entry["events"].append({
        "action": "engine_linked",
        "note": f"Linked to engine load {engine_load_id}",
        "timestamp": now,
    })
    _save(data)
    return entry


def update_engine_status(sandbox_id: str, engine_status: str) -> dict | None:
    """Sync engine load status back to the sandbox entry's card_data."""
    data = _load()
    if sandbox_id not in data:
        return None
    entry = data[sandbox_id]
    old_status = entry["card_data"].get("engine_status")
    entry["card_data"]["engine_status"] = engine_status
    entry["updated_at"] = _utc_now()
    if engine_status != old_status:
        entry["version"] = entry.get("version", 1) + 1
        entry["last_change"] = f"Engine Status: {engine_status.replace('_', ' ').title()}"
    _save(data)
    return entry


def add_note(sandbox_id: str, note: str) -> dict:
    data = _load()
    if sandbox_id not in data:
        raise KeyError(f"Sandbox entry not found: {sandbox_id}")
    existing = data[sandbox_id].get("notes", "")
    data[sandbox_id]["notes"] = (existing + "\n" + note).strip() if existing else note
    data[sandbox_id]["updated_at"] = _utc_now()
    _save(data)
    return data[sandbox_id]
