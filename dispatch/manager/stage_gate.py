"""Manager's Stage Gate summary -- Stage 12 Phase M4, per
DISPATCH_STAGE12_MANAGER_M4_MIRROR_DESIGN_v1.md.

Read-only against docs/STAGE_STATUS.json, a hand-authored, structured
mirror of Claude-3's DISPATCH_STAGE_LAUNCH_PACKAGES_v1.md and
DISPATCH_BLUEPRINT_DECISION_LOG.md -- refreshed manually, as one more
step in the same habit that already updates those two Claude-3
documents after every stage action. This module never writes to
docs/, never reaches Claude-3 or GitHub, never touches any Spine
table -- it only reads one local JSON file and summarizes it.

Deliberately outside the signal pipeline (signals.py/classify.py/
priority.py/staff_report.py): stage status is a standing snapshot
that gets *replaced* wholesale on each refresh, not a discrete event
needing dedup. It gets its own always-fresh summary here instead of a
fake Work Item.

Fails soft, always: a missing or malformed mirror file must never
raise -- the caller (portal/routes/manager.py) gets None and simply
omits the Stage Gate panel, leaving the rest of /manager (the
already-shipped signal pipeline) completely unaffected.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

_STATUS_FILE = Path(__file__).resolve().parent.parent.parent / "docs" / "STAGE_STATUS.json"
_SUPPORTED_SCHEMA_VERSION = 1
_STALE_AFTER_DAYS = 14


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def load_stage_status() -> dict | None:
    """Reads and validates docs/STAGE_STATUS.json. Returns None on any
    failure (missing file, invalid JSON, unsupported schema version,
    missing required keys) -- never raises.
    """
    try:
        raw = _STATUS_FILE.read_text()
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None
    if data.get("schema_version") != _SUPPORTED_SCHEMA_VERSION:
        return None
    if "stages" not in data or not isinstance(data["stages"], list):
        return None

    return data


def build_summary() -> dict | None:
    """Returns a display-ready summary dict, or None if the mirror
    file is unavailable/invalid. Never raises.
    """
    data = load_stage_status()
    if data is None:
        return None

    stages = data["stages"]
    blocked_stages = [s for s in stages if s.get("blocked")]
    card_level = 2 if blocked_stages else 1

    synced_at = _parse_ts(data.get("last_synced", ""))
    stale = False
    if synced_at is not None:
        stale = (datetime.now(timezone.utc) - synced_at) > timedelta(days=_STALE_AFTER_DAYS)

    return {
        "last_synced": data.get("last_synced"),
        "stale": stale,
        "stage_count": len(stages),
        "blocked_stages": blocked_stages,
        "next_recommended_stage": data.get("next_recommended_stage"),
        "next_recommended_reason": data.get("next_recommended_reason"),
        "card_level": card_level,
        "stages": stages,
    }
