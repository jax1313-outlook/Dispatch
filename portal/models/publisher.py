"""Publisher action card management.

Publisher produces documents from approved inputs only.
Publisher must not invent facts.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from portal.models import get_data_dir

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
