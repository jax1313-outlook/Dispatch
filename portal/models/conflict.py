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
    "scheduling_overlap",
    "turnaround_too_tight",
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


def resolve_notice(notice_id: str, resolution_note: str = "") -> dict:
    notices = _load()
    for notice in notices:
        if notice["id"] == notice_id:
            notice["resolved"] = True
            notice["resolved_at"] = _utc_now()
            if resolution_note:
                notice["resolution_note"] = resolution_note
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


def check_booking_conflicts(card_data: dict, sandbox_id: str) -> list[dict]:
    """Detect scheduling conflicts between a load being booked and existing engine loads.

    Checks:
    - Overlapping pickup/delivery windows with active engine loads
    - Turnaround time too tight (< 2 hours between delivery and next pickup)
    """
    from dispatch import services as dispatch_svc

    generated: list[dict] = []
    active_loads = dispatch_svc.list_loads()
    active_loads = [
        l for l in active_loads
        if l["status"] not in ("archived", "cancelled", "completed")
    ]

    if not active_loads:
        return generated

    new_pickup = _parse_window_start(card_data.get("pickup_window", ""))
    new_delivery = _parse_window_end(card_data.get("delivery_window", ""))

    if not new_pickup:
        return generated

    for load in active_loads:
        existing_pickup = _parse_datetime(load.get("pickup_datetime", ""))
        existing_delivery = _parse_datetime(load.get("delivery_datetime", ""))

        if not existing_pickup:
            continue

        if _windows_overlap(new_pickup, new_delivery, existing_pickup, existing_delivery):
            generated.append(
                create_notice(
                    "scheduling_overlap",
                    "warning",
                    sandbox_id,
                    f"Pickup/delivery window overlaps with active load {load['load_id'][:12]}... "
                    f"({load.get('pickup_location', '?')} -> {load.get('delivery_location', '?')}).",
                    "Verify scheduling before booking — single-truck operation cannot run overlapping loads.",
                )
            )

        if existing_delivery and new_pickup:
            gap_hours = (new_pickup - existing_delivery).total_seconds() / 3600
            if 0 < gap_hours < 2:
                generated.append(
                    create_notice(
                        "turnaround_too_tight",
                        "warning",
                        sandbox_id,
                        f"Only {gap_hours:.1f}h turnaround between delivery of load "
                        f"{load['load_id'][:12]}... and this pickup.",
                        "Allow at least 2 hours between delivery and next pickup for fueling/rest.",
                    )
                )

    return generated


def _parse_window_start(window: str):
    """Parse start datetime from a window like '2026-07-30 06:00 - 10:00'."""
    if not window:
        return None
    parts = window.split(" - ")
    return _parse_datetime(parts[0].strip())


def _parse_window_end(window: str):
    """Parse end datetime from a window like '2026-07-30 06:00 - 10:00'."""
    if not window:
        return None
    parts = window.split(" - ")
    if len(parts) < 2:
        return _parse_datetime(parts[0].strip())
    end = parts[1].strip()
    start = parts[0].strip()
    if len(end) <= 5 and len(start) >= 10:
        end = start[:11] + end
    return _parse_datetime(end)


def _parse_datetime(dt_str: str):
    """Best-effort parse of a datetime string."""
    if not dt_str:
        return None
    from datetime import datetime as dt_cls
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt_cls.strptime(dt_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _windows_overlap(start_a, end_a, start_b, end_b) -> bool:
    """Check if two time windows overlap. None ends are treated as open-ended."""
    if start_a is None or start_b is None:
        return False
    eff_end_a = end_a or start_a
    eff_end_b = end_b or start_b
    return start_a < eff_end_b and start_b < eff_end_a


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
