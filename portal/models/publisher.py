"""Publisher action card management.

Publisher produces documents from approved inputs only.
Publisher must not invent facts.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from portal.models import get_data_dir

# A field update is not among these. ACTION_TYPES are documents Publisher
# produces and a human approves; changing a phone number on a record is neither.
# See apply_mission_update below, which makes the change directly and leaves a
# trail rather than raising a card nobody needs to approve.
ACTION_TYPES = [
    "Broker Packet Required",
    "Direct Shipper Packet Required",
    "Rate Sheet Request",
    "Rate Confirmation Package Required",
    "DocuSign Package Ready",
    "Arrival Notice Draft",
    "POD/BOL Document Package Draft",
    "Detention Evidence Draft",
]

PUBLISHER_STATUSES = ["PENDING", "DRAFT", "READY", "APPROVED", "ARCHIVED"]

BROKER_PACKET_MANIFEST = ["Business Card", "W-9", "Insurance", "Authority", "Rate Sheet", "Terms"]
DIRECT_SHIPPER_MANIFEST = ["Business Card", "Capabilities Summary", "Insurance", "Rate Sheet", "Terms"]
RATE_CONFIRMATION_MANIFEST = [
    "Thank-you Cover Letter",
    "Rate Confirmation",
    "Terms",
    "Supporting Documents",
    "DocuSign-ready Marker",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _publisher_path() -> Path:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "publisher_queue.json"


def _load() -> list[dict]:
    path = _publisher_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def _save(data: list[dict]) -> None:
    path = _publisher_path()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_queue() -> list[dict]:
    return _load()


def _manifest_for(action_type: str) -> list[str]:
    if "Broker Packet" in action_type:
        return list(BROKER_PACKET_MANIFEST)
    if "Direct Shipper" in action_type:
        return list(DIRECT_SHIPPER_MANIFEST)
    if "Rate Confirmation" in action_type:
        return list(RATE_CONFIRMATION_MANIFEST)
    return []


def create_action(
    action_type: str,
    sandbox_id: str,
    trigger_reason: str,
    available_data: list[str] | None = None,
    missing_data: list[str] | None = None,
) -> dict:
    queue = _load()
    now = _utc_now()
    manifest = _manifest_for(action_type)

    action = {
        "id": f"PUB-{len(queue) + 1:04d}",
        "action_type": action_type,
        "sandbox_id": sandbox_id,
        "status": "PENDING",
        "trigger_reason": trigger_reason,
        "available_data": available_data or [],
        "missing_data": missing_data or [],
        "manifest": manifest,
        "recommended_product": action_type,
        "human_approval_required": True,
        "created_at": now,
        "updated_at": now,
    }
    queue.append(action)
    _save(queue)
    return action


def update_action_status(action_id: str, new_status: str) -> dict:
    if new_status not in PUBLISHER_STATUSES:
        raise ValueError(f"Invalid publisher status: {new_status}")
    queue = _load()
    for action in queue:
        if action["id"] == action_id:
            action["status"] = new_status
            action["updated_at"] = _utc_now()
            _save(queue)
            return action
    raise KeyError(f"Publisher action not found: {action_id}")


# ---- Mission Record updates ------------------------------------------------
#
# JOE hears the driver and hands it over. Publisher makes the change, because
# Publisher is the production clerk and Dispatch owns the record:
#
#     Mike -> JOE -> Publisher -> Dispatch -> Mission Record
#
# Giving JOE a write path would quietly make him the owner of mission data,
# which is the one thing the authority model does not allow. So the write lives
# here, and `dispatch/joe_update.py` has no way to reach a store at all.

#: Fields Publisher will write from a spoken request. Everything the Mission
#: Template can capture, plus load control, and nothing else -- a request
#: naming `committed_at` or `mission_number` is refused rather than obeyed.
def _writable_keys() -> set:
    from dispatch import mission_template as mt

    keys = {f.key for f in mt.TEMPLATE}
    keys |= {"customer_email", "control_email", "amount", "cod",
             "payment_type", "rate_basis", "pod_required"}
    return keys


#: Never writable, whoever asks. Identity and the commitment gate are not
#: things a sentence in a cab may move.
PROTECTED_KEYS = ("id", "load_number", "mission_number", "committed_at",
                  "accepted_at", "created_at", "events", "card_data",
                  "intake_source", "intake_taken_by", "rejected_at")


def apply_mission_update(sandbox_id: str, field: str, value: str, *,
                         requested_by: str, sandbox_module,
                         reason: str = "") -> dict:
    """Make the change JOE was asked for, and leave a trail of who asked.

    Additive and single-field. It records what was there before, because a
    number corrected on a phone call is sometimes corrected wrongly, and the
    previous value is the cheapest way back.
    """
    field = str(field or "").strip()
    value = str(value or "").strip()

    if field in PROTECTED_KEYS:
        return {"ok": False, "applied": False, "field": field,
                "note": "That one is not mine to change."}
    if field not in _writable_keys():
        return {"ok": False, "applied": False, "field": field,
                "note": "I do not have a field by that name."}
    if not str(requested_by or "").strip():
        return {"ok": False, "applied": False, "field": field,
                "note": "A change arrives on somebody's word. I need whose."}

    record = sandbox_module.get(sandbox_id)
    if not record:
        return {"ok": False, "applied": False, "field": field,
                "note": "That mission is not on this machine."}

    data = sandbox_module._load()
    stored = data.get(sandbox_id) or {}

    # Load control lives in its own block on the record, so a change to it goes
    # where the stop cards read from rather than into a flat field nobody looks
    # at.
    if field.startswith("control_"):
        control = dict(stored.get("load_control") or {})
        previous = control.get(field, "")
        control[field] = value
        stored["load_control"] = control
    else:
        previous = stored.get(field, "")
        stored[field] = value

    now = _utc_now()
    stored["updated_at"] = now
    stored.setdefault("events", []).append({
        "action": "field_updated",
        "field": field,
        "from": previous,
        "to": value,
        "requested_by": requested_by,
        "via": "JOE",
        "reason": reason,
        "timestamp": now,
    })
    data[sandbox_id] = stored
    sandbox_module._save(data)

    return {"ok": True, "applied": True, "field": field, "value": value,
            "previous": previous, "at": now}
