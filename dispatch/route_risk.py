"""Dispatch Route Risk Extraction Staging Adapter.

This module acts as an extraction staging adapter between Dispatch and the
independently owned top-level `route_risk` domain package.

It injects Dispatch's COMI evaluator into Route Risk events recorded from
Dispatch, while re-exporting the underlying Route Risk queries cleanly.
"""

from __future__ import annotations

import route_risk as rr

_ROUTE_RISK_EVENTS = rr._ROUTE_RISK_EVENTS


def record_route_risk_event(*args, **kwargs) -> dict:
    from dispatch import comi_routing
    if "comi_eval_fn" not in kwargs:
        kwargs["comi_eval_fn"] = comi_routing.evaluate_comi_routing
    return rr.record_route_risk_event(*args, **kwargs)


def get_route_risk(load_id: str) -> dict:
    return rr.get_route_risk(load_id)


def list_route_risk_events(load_id: str | None = None) -> list[dict]:
    return rr.list_route_risk_events(load_id)
