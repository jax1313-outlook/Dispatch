"""The audit log: what was done, on whose authority, and what it changed.

    Every Joe action is logged and attributed to that authority.
    Joe never acts on self-generated intent.

Append-only. Entries are added and never edited or removed, because the log's
whole value is that it cannot be tidied up afterwards. A record of what
happened that can be adjusted is a record of what somebody preferred.

WHY THIS EXISTS SEPARATELY FROM THE MISSION RECORD
==================================================

The Mission Record says what is true now. The audit log says how it got that
way and who said so. On a delegated agent that is not bookkeeping: Joe acts on
the driver's intent, and the line between "the driver asked for this" and "the
machine decided this" has to be reconstructable months later, from the record
rather than from memory.

    timestamp · driver identity · intent · action · old -> new · result

PLATFORM AGNOSTIC
=================

Joe is an operational role, not a feature of whatever brain is rented. Nothing
here names a vendor, including the channels: they are named for what they are
-- a conversation, a screen, a call -- so a different brain or a different
front end produces the same audit trail in the same shape. The first certified
stack is one implementation, not the definition.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from portal.models import get_data_dir

#: How an instruction reached Dispatch. Recorded, never inferred -- "which way
#: did this come in" is a real question when something goes wrong.
#:
#: Named for what they are rather than for a product. A constant called after
#: somebody's chat application would bake that vendor into the contract, and
#: the channel is data: any string a caller sends is stored, so a new one is
#: never a schema change and never a code branch.
CHANNEL_CHAT = "CHAT"
CHANNEL_VOICE = "VOICE"
CHANNEL_MISSION_SCREEN = "MISSION_SCREEN"
CHANNEL_PORTAL = "PORTAL"
CHANNEL_API = "API"

#: What the entry says happened. Honest Reporting Rule: partial completion is
#: reported part by part, so a result is one of three and never a guess.
RESULT_SUCCESS = "SUCCESS"
RESULT_PARTIAL = "PARTIAL"
RESULT_FAILURE = "FAILURE"

RESULTS = (RESULT_SUCCESS, RESULT_PARTIAL, RESULT_FAILURE)


def _log_path() -> Path:
    return Path(get_data_dir()) / "joe_audit.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record(*, action: str, driver: str, intent: str = "",
           channel: str = CHANNEL_API, mission_id: str = "",
           field: str = "", old_value="", new_value="",
           result: str = RESULT_SUCCESS, note: str = "",
           authority: str = "") -> dict:
    """Append one entry. Never edits, never removes, never fails loudly.

    `driver` is the human whose authority this action carries. It is required:
    an action with nobody's name on it is an action nobody authorised, and the
    doctrine has exactly one hard wall -- Mike remains commander.
    """
    entry = {
        "timestamp": _utc_now(),
        "driver": str(driver or "").strip(),
        "authority": str(authority or driver or "").strip(),
        "channel": str(channel or CHANNEL_API),
        "intent": str(intent or ""),
        "action": str(action or ""),
        "mission_id": str(mission_id or ""),
        "field": str(field or ""),
        "old_value": "" if old_value is None else str(old_value),
        "new_value": "" if new_value is None else str(new_value),
        "result": result if result in RESULTS else RESULT_FAILURE,
        "note": str(note or ""),
    }

    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    return entry


def entries(*, mission_id: str = "", limit: int = 200) -> list:
    """Read the log back. Newest last, as it was written.

    A malformed line is skipped rather than allowed to take down a page: a log
    that cannot be read is worse than a log with a gap in it, and the gap is
    visible.
    """
    path = _log_path()
    if not path.exists():
        return []

    found = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if mission_id and entry.get("mission_id") != mission_id:
                continue
            found.append(entry)
    return found[-int(limit):] if limit else found


def last_for(mission_id: str) -> dict:
    """The most recent entry for one mission, or an empty dict."""
    found = entries(mission_id=mission_id, limit=1)
    return found[0] if found else {}
