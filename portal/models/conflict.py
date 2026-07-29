"""Conflict Notice management.

Visible errors are preferred over silent failures.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from portal.models import get_data_dir

CONFLICT_TYPES = [
    "missing_broker_email",
    "missing_source_link",
    "missing_rate",
    "missing_pickup_window",
    "equipment_mismatch",
    "hard_stop",
    "delivery_appointment_conflict",
    "hos_eld_conflict",
    "publisher_missing_document",
    "library_missing_asset",
    "corrupt_sandbox_data",
]

SEVERITIES = ["info", "warning", "critical"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _conflicts_path() -> Path:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "conflicts.json"


def _load() -> list[dict]:
    path = _conflicts_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def _save(data: list[dict]) -> None:
    path = _conflicts_path()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_all() -> list[dict]:
    return _load()


def get_unresolved() -> list[dict]:
    return [n for n in _load() if not n.get("resolved")]


def create_notice(
    conflict_type: str,
    severity: str,
    sandbox_id: str,
    explanation: str,
    recommended_action: str,
    human_decision_required: bool = True,
) -> dict:
    notices = _load()
    now = _utc_now()
    notice = {
        "id": f"CN-{len(notices) + 1:04d}",
        "conflict_type": conflict_type,
        "severity": severity,
        "sandbox_id": sandbox_id,
        "explanation": explanation,
        "recommended_action": recommended_action,
        "human_decision_required": human_decision_required,
        "resolved": False,
        "created_at": now,
    }
    notices.append(notice)
    _save(notices)
    return notice


def resolve_notice(notice_id: str) -> dict:
    notices = _load()
    for notice in notices:
        if notice["id"] == notice_id:
            notice["resolved"] = True
            _save(notices)
            return notice
    raise KeyError(f"Conflict Notice not found: {notice_id}")


def check_dispatch_card(card_data: dict, sandbox_id: str) -> list[dict]:
    """Generate conflict notices for missing/problematic dispatch card data."""
    generated: list[dict] = []

    if not card_data.get("broker_email"):
        generated.append(
            create_notice(
                "missing_broker_email",
                "warning",
                sandbox_id,
                "No broker email address available for this load.",
                "Locate broker contact information before sending inquiry.",
            )
        )
    if not card_data.get("source_link"):
        generated.append(
            create_notice(
                "missing_source_link",
                "info",
                sandbox_id,
                "No source link available for this load.",
                "Verify load details from original posting.",
            )
        )
    if not card_data.get("rate"):
        generated.append(
            create_notice(
                "missing_rate",
                "warning",
                sandbox_id,
                "No rate information available for this load.",
                "Contact broker for rate details before pursuing.",
            )
        )
    if not card_data.get("pickup_window"):
        generated.append(
            create_notice(
                "missing_pickup_window",
                "info",
                sandbox_id,
                "No pickup window specified.",
                "Confirm pickup timing with broker.",
            )
        )
    if card_data.get("equipment_match") == "mismatch":
        generated.append(
            create_notice(
                "equipment_mismatch",
                "critical",
                sandbox_id,
                f"Equipment mismatch: load requires {card_data.get('equipment_required', 'Unknown')}.",
                "Do not pursue — equipment does not match.",
            )
        )
    if card_data.get("hard_stop"):
        generated.append(
            create_notice(
                "hard_stop",
                "critical",
                sandbox_id,
                f"Hard stop: {card_data.get('hard_stop_reason', 'See details')}.",
                "Do not pursue without resolving hard stop.",
            )
        )
    return generated


def check_library_assets() -> list[dict]:
    """Generate conflict notices for missing Library company assets."""
    required = ["W-9", "Insurance", "Authority", "Business Card", "Rate Sheets", "Terms"]
    generated: list[dict] = []
    for asset in required:
        generated.append(
            create_notice(
                "library_missing_asset",
                "info",
                "LIBRARY",
                f"Company Library: '{asset}' not yet uploaded.",
                f"Upload {asset} to Company Library when available.",
                human_decision_required=False,
            )
        )
    return generated
