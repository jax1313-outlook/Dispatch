"""Dispatch Route Risk Extraction Staging Adapter.

This module acts as an extraction staging adapter between Dispatch and the
independently owned top-level `route_risk` domain package.

It safely imports the top-level `route_risk` package if available, or falls back
gracefully to Dispatch local persistence/stubbing so Dispatch never fails at
import time if `route_risk` is absent.
"""

from __future__ import annotations

import sys

try:
    import route_risk as rr
    _ROUTE_RISK_EVENTS = rr._ROUTE_RISK_EVENTS
except ImportError:
    rr = None
    _ROUTE_RISK_EVENTS = {}


def _get_rr():
    if rr is not None:
        return rr
    # Graceful fallback if top-level route_risk package is absent
    class _StubRouteRisk:
        _ROUTE_RISK_EVENTS = _ROUTE_RISK_EVENTS
        @staticmethod
        def record_route_risk_event(load_id, condition_summary, consequence_level=1, **kwargs):
            from dispatch import store
            event = {
                "route_risk_event_id": f"rr-stub-{load_id}",
                "load_id": load_id,
                "condition_summary": condition_summary,
                "consequence_level": consequence_level,
                "route_risk_level": f"Level {consequence_level}",
                "estimated_delay_minutes": kwargs.get("estimated_delay_minutes", 0),
                "delivery_commitment_status": kwargs.get("delivery_commitment_status", "achievable"),
                "source_type": kwargs.get("source_type", "manual_entry"),
                "source_label": kwargs.get("source_label", "Dispatch Fallback Adapter"),
                "driver_notification_required": False,
                "stakeholder_notification_required": False,
                "mission_visibility_update_required": False,
                "comi_required": False,
                "created_at": "",
                "status": "active",
                "is_live_data": False,
            }
            try:
                store.create_route_risk_event(event)
            except Exception:
                pass
            return event

        @staticmethod
        def get_route_risk(load_id):
            from dispatch import store
            events = []
            try:
                events = store.list_route_risk_events(load_id)
            except Exception:
                pass
            if events:
                latest = max(events, key=lambda x: x.get("created_at", ""))
                return {
                    "load_id": load_id,
                    "available": True,
                    "risk_level": latest.get("route_risk_level", "Level 1"),
                    "consequence_level": latest.get("consequence_level", 1),
                    "summary": latest.get("condition_summary", ""),
                    "estimated_delay_minutes": latest.get("estimated_delay_minutes", 0),
                    "delivery_commitment_status": latest.get("delivery_commitment_status", "achievable"),
                    "source_label": latest.get("source_label", "Dispatch Fallback Adapter"),
                    "map_visual_placeholder": {"available": False},
                    "checked_at": "",
                    "is_live_data": False,
                    "latest_event": latest,
                }
            return {
                "load_id": load_id,
                "available": False,
                "risk_level": "Level 0",
                "consequence_level": 0,
                "summary": "Route Risk not recorded.",
                "estimated_delay_minutes": 0,
                "delivery_commitment_status": "achievable",
                "source_label": "Dispatch Fallback Adapter",
                "map_visual_placeholder": {"available": False},
                "checked_at": "",
                "is_live_data": False,
                "latest_event": None,
            }

        @staticmethod
        def list_route_risk_events(load_id=None):
            from dispatch import store
            try:
                return store.list_route_risk_events(load_id)
            except Exception:
                return []

    return _StubRouteRisk


def record_route_risk_event(*args, **kwargs) -> dict:
    from dispatch import comi_routing
    if "comi_eval_fn" not in kwargs:
        kwargs["comi_eval_fn"] = comi_routing.evaluate_comi_routing
    return _get_rr().record_route_risk_event(*args, **kwargs)


def get_route_risk(load_id: str) -> dict:
    return _get_rr().get_route_risk(load_id)


def list_route_risk_events(load_id: str | None = None) -> list[dict]:
    return _get_rr().list_route_risk_events(load_id)
