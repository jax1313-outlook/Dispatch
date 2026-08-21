"""Route Risk Foundation -- Operational Intelligence function for route-related condition evaluation.

Route Risk evaluates route-related conditions, determines mission impact,
assigns consequence levels (0-5), identifies communication requirements,
and drives Mission Visibility updates through COMI.

Live external APIs (NOAA, DOT, Police, Weather, Traffic) are NOT connected in this pass.
All data is internal, manual, stubbed, or stored locally.

This module is Dispatch's *binding* of the standalone `route_risk` engine: it
injects Dispatch's COMI evaluation and Dispatch's SQLite persistence into an
engine that imports neither. The engine stays independently importable.

M3 (DISPATCH_BUILD_MATRIX_v1) -- events are persisted to the `route_risk_events`
table, which has existed in the schema since it was written and was never
written to. Before M3 they lived only in a module-level dict, so restarting the
process silently destroyed every recorded condition while the Driver Portal
went on displaying "no active Route Risk events" as though that were a fact.
"""

from __future__ import annotations

import route_risk as rr

# Retained for backwards compatibility: `dispatch.route_risk._ROUTE_RISK_EVENTS`
# is the engine's in-memory store. Dispatch no longer writes to it -- every
# Dispatch-side call now goes to SQLite -- but the name stays bound so any
# existing reader keeps resolving. It will be empty in normal Dispatch use, and
# that is correct: a second copy of an operational record would be a second
# source of truth.
_ROUTE_RISK_EVENTS = rr._ROUTE_RISK_EVENTS


def _store_event(event: dict) -> dict:
    from dispatch import store
    return store.create_route_risk_event(event)


def _load_events(load_id: str | None) -> list[dict]:
    from dispatch import store
    return store.list_route_risk_events(load_id)


def record_route_risk_event(*args, **kwargs) -> dict:
    from dispatch import comi_routing
    if "comi_eval_fn" not in kwargs:
        kwargs["comi_eval_fn"] = comi_routing.evaluate_comi_routing
    if "store_fn" not in kwargs:
        kwargs["store_fn"] = _store_event
    return rr.record_route_risk_event(*args, **kwargs)


def get_route_risk(load_id: str) -> dict:
    return rr.get_route_risk(load_id, load_events_fn=_load_events)


def list_route_risk_events(load_id: str | None = None) -> list[dict]:
    return rr.list_route_risk_events(load_id, load_events_fn=_load_events)
