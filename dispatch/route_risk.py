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

#: Truth word for whether the standalone engine is installed. `CONFIGURED` means
#: the package imported; `ABSENT` means it is not on this machine. Those are two
#: of the eight permitted words (CLAUDE.md section 6) and no third reading exists
#: -- in particular this never reports `LIVE`, because the engine has no live
#: weather or traffic feed connected in either case.
ENGINE_STATUS: str

try:
    import route_risk as rr
except ImportError:  # pragma: no cover - exercised by the doctrine drift test
    # Route Risk is a plug-in. The Plug-In Separation Doctrine says Dispatch
    # must not require its presence for core operation, and the standing rule
    # is "degradation is permitted, incapacity is not" -- so an absent engine
    # has to leave Dispatch startable, with the absence visible, rather than
    # taking the whole portal down at import time.
    #
    # Before this was handled, `portal/routes/driver_portal.py` imported this
    # module at module scope, so a missing `route_risk` package raised during
    # blueprint registration and `create_app()` never returned. Every driver
    # surface, every load, every milestone -- gone, because an optional risk
    # advisor was not installed. That is precisely the incapacity the doctrine
    # forbids, and it is why the failure is absorbed here at the binding rather
    # than at each of the four call sites.
    rr = None
    ENGINE_STATUS = "ABSENT"
else:
    ENGINE_STATUS = "CONFIGURED"


class RouteRiskUnavailable(RuntimeError):
    """Raised when a write is attempted and the engine is not installed.

    Reads degrade to "no risk information available". Writes do not degrade:
    silently discarding a recorded hazard would be worse than refusing it,
    because the operator would believe a condition had been logged when nothing
    had. This is the same rule as the milestone gate -- a refusal the operator
    can see beats a success they cannot trust.
    """


# Retained for backwards compatibility: `dispatch.route_risk._ROUTE_RISK_EVENTS`
# is the engine's in-memory store. Dispatch no longer writes to it -- every
# Dispatch-side call now goes to SQLite -- but the name stays bound so any
# existing reader keeps resolving. It will be empty in normal Dispatch use, and
# that is correct: a second copy of an operational record would be a second
# source of truth. With the engine absent there is nothing to bind to, so it is
# an empty dict of the same shape.
_ROUTE_RISK_EVENTS = rr._ROUTE_RISK_EVENTS if rr is not None else {}


def engine_status() -> str:
    """`CONFIGURED` or `ABSENT`. For any surface that reports plug-in state."""
    return ENGINE_STATUS


def _unavailable(load_id: str) -> dict:
    """The engine-absent reading, in the shape every caller already handles.

    Deliberately the same keys the engine returns for "no events", so no caller
    needs to learn a second shape -- with `available` false and a summary that
    names the absence instead of implying the road is clear. `risk_level` is
    "Level 0" for the same reason the engine uses it there: it is the schema's
    floor, not a claim that the route was assessed and found safe. The summary
    is what a person reads, and it says plainly that nothing was assessed.
    """
    return {
        "load_id": load_id,
        "available": False,
        "engine_status": "ABSENT",
        "risk_level": "Level 0",
        "consequence_level": 0,
        "summary": (
            "Route Risk is ABSENT -- the Route Risk engine is not installed on "
            "this machine, so no route condition has been assessed. This is not "
            "a statement that the route is clear."
        ),
        "estimated_delay_minutes": 0,
        "delivery_commitment_status": "achievable",
        "source_label": "Route Risk engine ABSENT",
        "map_visual_placeholder": {"available": False},
        "checked_at": _utc_now_iso(),
        "is_live_data": False,
        "latest_event": None,
    }


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _store_event(event: dict) -> dict:
    from dispatch import store
    return store.create_route_risk_event(event)


def _load_events(load_id: str | None) -> list[dict]:
    from dispatch import store
    return store.list_route_risk_events(load_id)


def record_route_risk_event(*args, **kwargs) -> dict:
    if rr is None:
        raise RouteRiskUnavailable(
            "The Route Risk engine is not installed, so this condition was NOT "
            "recorded. Nothing has been saved. Install the route_risk package, "
            "then record it again."
        )
    from dispatch import comi_routing
    if "comi_eval_fn" not in kwargs:
        kwargs["comi_eval_fn"] = comi_routing.evaluate_comi_routing
    if "store_fn" not in kwargs:
        kwargs["store_fn"] = _store_event
    return rr.record_route_risk_event(*args, **kwargs)


def get_route_risk(load_id: str) -> dict:
    if rr is None:
        return _unavailable(load_id)
    return rr.get_route_risk(load_id, load_events_fn=_load_events)


def list_route_risk_events(load_id: str | None = None) -> list[dict]:
    # Reads Dispatch's own `route_risk_events` table. The engine contributes no
    # logic to this call -- it forwards to the injected reader -- so events
    # already recorded stay retrievable with the engine uninstalled. Losing
    # sight of a hazard someone logged is not an acceptable degradation.
    if rr is None:
        return _load_events(load_id)
    return rr.list_route_risk_events(load_id, load_events_fn=_load_events)
