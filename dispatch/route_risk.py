"""Route Risk Foundation -- Operational Intelligence function for route-related condition evaluation.

Route Risk evaluates route-related conditions, determines mission impact,
assigns consequence levels (0-5), identifies communication requirements,
and drives Mission Visibility updates through COMI.

Live external APIs (NOAA, DOT, Police, Weather, Traffic) are NOT connected in this pass.
All data is internal, manual, stubbed, or stored locally.
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
