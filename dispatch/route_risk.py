"""Route Risk lookup -- the third and last of the three not-yet-built items
identified as valuable in the Jules sandbox discovery report (deployment
blueprint §18), and referenced by the Vision docs (03v2 "Day in the Life",
§10): "Route Risk should act as a predictive operational capability that
reviews construction, weather, traffic, and route-impacting events. Route
Risk should produce predicted delay information..."

None of those data sources -- traffic, weather, construction feeds -- exist
in Dispatch's current tech stack (CLAUDE.md's Tech stack section: local
filesystem, Claude API, Email API; no maps/traffic/weather API, no external
DB). Fabricating a risk level from nothing would violate the same
do-not-invent-facts principle already enforced elsewhere in this codebase
(Publisher "must not invent facts"; rule modules are deterministic, no
nondeterministic LLM calls in the deterministic rule path). So this module
does the honest thing: it defines the target lookup shape and wiring point
-- callers (Driver Portal, a future stakeholder-portal card, etc.) can call
get_route_risk(load_id) today and get a clearly-labeled "not yet available"
result, not a fake number. Wiring a real predictive engine here (a data
source, a rule module, or both) is future work, not decided in this pass --
flagged explicitly rather than silently deferred.
"""

from __future__ import annotations

from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_route_risk(load_id: str) -> dict:
    """Route Risk lookup for a single load. Always returns a dict (never
    raises for an unknown load_id -- an honest "not available" is still
    the correct answer for a load that doesn't exist)."""
    return {
        "load_id": load_id,
        "available": False,
        "risk_level": None,
        "summary": (
            "Route Risk is not yet available. No traffic, weather, or construction "
            "data source is wired up yet -- this is a planned capability "
            "(Vision doc #3v2, section 10), not a live prediction."
        ),
        "checked_at": _utc_now(),
    }
