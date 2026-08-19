"""Route Risk Domain Engine — standalone engine for route-related condition evaluation.

Route Risk evaluates route-related conditions, determines mission impact,
assigns consequence levels (0-5), identifies communication requirements,
and drives Mission Visibility updates through COMI.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable, Any

# In-memory store for fallback/test stub only
_ROUTE_RISK_EVENTS: dict[str, list[dict]] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_route_risk_event(
    load_id: str,
    condition_summary: str,
    consequence_level: int = 1,
    estimated_delay_minutes: int = 0,
    source_type: str = "manual_entry",
    source_label: str = "Internal Dispatcher Entry",
    affected_area: str = "",
    affected_corridor: str = "",
    delivery_commitment_status: str = "achievable",
    has_map_visual: bool = True,
    comi_eval_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict:
    """Records a Route Risk event independently without inventing alternative COMI rules."""
    consequence_level = max(0, min(5, int(consequence_level)))
    event_id = f"rr-{uuid.uuid4().hex[:10]}"

    if comi_eval_fn is not None:
        comi_eval = comi_eval_fn(
            load_id=load_id,
            trigger_type="route_risk_event",
            consequence_level=consequence_level,
            source_refs={"route_risk_event_id": event_id},
        )
    else:
        # Return neutral raw data - do not invent alternative COMI rules
        comi_eval = {
            "driver_alert_required": False,
            "stakeholder_update_required": False,
            "mission_visibility_update_required": False,
            "publisher_required": False,
        }

    event = {
        "route_risk_event_id": event_id,
        "load_id": load_id,
        "source_type": source_type,
        "source_label": f"{source_label} (Internal/Stubbed - No live external API)",
        "affected_area": affected_area,
        "affected_corridor": affected_corridor,
        "condition_summary": condition_summary,
        "estimated_delay_minutes": estimated_delay_minutes,
        "delivery_commitment_status": delivery_commitment_status,
        "route_risk_level": f"Level {consequence_level}",
        "consequence_level": consequence_level,
        "driver_notification_required": comi_eval.get("driver_alert_required", False),
        "stakeholder_notification_required": comi_eval.get("stakeholder_update_required", False),
        "mission_visibility_update_required": comi_eval.get("mission_visibility_update_required", False),
        "comi_required": comi_eval.get("publisher_required", False) or comi_eval.get("stakeholder_update_required", False),
        "map_visual_placeholder": {
            "available": has_map_visual,
            "placeholder_type": "embedded_corridor_map_placeholder",
            "label": f"Corridor Map Placeholder: {affected_corridor or affected_area or 'Route Segment'}",
        },
        "created_at": _utc_now(),
        "status": "active",
        "is_live_data": False,
    }

    try:
        from dispatch import store
        store.create_route_risk_event(event)
    except Exception:
        if load_id not in _ROUTE_RISK_EVENTS:
            _ROUTE_RISK_EVENTS[load_id] = []
        _ROUTE_RISK_EVENTS[load_id].append(event)

    return event


def get_route_risk(load_id: str) -> dict:
    """Route Risk lookup for a single load."""
    events = []
    try:
        from dispatch import store
        events = store.list_route_risk_events(load_id)
    except Exception:
        events = _ROUTE_RISK_EVENTS.get(load_id, [])

    if events:
        latest = max(events, key=lambda x: x["created_at"])
        map_placeholder = latest.get("map_visual_placeholder")
        if not map_placeholder:
            corridor = latest.get("affected_corridor") or latest.get("affected_area") or "Route Segment"
            map_placeholder = {
                "available": True,
                "placeholder_type": "embedded_corridor_map_placeholder",
                "label": f"Corridor Map Placeholder: {corridor}",
            }
        return {
            "load_id": load_id,
            "available": True,
            "risk_level": latest["route_risk_level"],
            "consequence_level": latest["consequence_level"],
            "summary": latest["condition_summary"],
            "estimated_delay_minutes": latest["estimated_delay_minutes"],
            "delivery_commitment_status": latest["delivery_commitment_status"],
            "source_label": latest["source_label"],
            "map_visual_placeholder": map_placeholder,
            "checked_at": _utc_now(),
            "is_live_data": False,
            "latest_event": latest,
        }

    return {
        "load_id": load_id,
        "available": False,
        "risk_level": "Level 0",
        "consequence_level": 0,
        "summary": (
            "Route Risk is not yet available. No active Route Risk events recorded. "
            "Live weather/traffic API integrations are not connected; any risk events "
            "are internal/manual entries."
        ),
        "estimated_delay_minutes": 0,
        "delivery_commitment_status": "achievable",
        "source_label": "Internal Route Risk Engine (Stubbed / No Live Feeds)",
        "map_visual_placeholder": {"available": False},
        "checked_at": _utc_now(),
        "is_live_data": False,
        "latest_event": None,
    }


def list_route_risk_events(load_id: str | None = None) -> list[dict]:
    try:
        from dispatch import store
        return store.list_route_risk_events(load_id)
    except Exception:
        if load_id:
            return list(_ROUTE_RISK_EVENTS.get(load_id, []))
        all_events = []
        for events in _ROUTE_RISK_EVENTS.values():
            all_events.extend(events)
        return sorted(all_events, key=lambda x: x["created_at"], reverse=True)
