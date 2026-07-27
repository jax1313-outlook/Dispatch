"""Lane-fit rule module.

Deterministic check of whether a load's origin/destination lane is one the
broker has moved before. Reads the Broker Intelligence Library's
`preferred_lanes` (System Rule 14 — captured once at ingestion, never
re-derived here).
"""

from __future__ import annotations

from .base import IntelligenceScore

NAME = "lane_fit"
VERSION = "1.0.0"

_MATCH_SCORE = 100
_ADJACENT_SCORE = 60  # shares an origin or destination state with a preferred lane
_NEW_LANE_SCORE = 30
_UNKNOWN_LANE_SCORE = 30


def _lane_key(load: dict) -> str | None:
    origin, destination = load.get("origin_state"), load.get("destination_state")
    return f"{origin}-{destination}" if origin and destination else None


def _parts(lane: str) -> tuple[str, str] | None:
    bits = lane.split("-")
    return (bits[0], bits[1]) if len(bits) == 2 else None


def run(load: dict, *, facility_pickup=None, facility_delivery=None, broker=None) -> IntelligenceScore:
    lane = _lane_key(load)
    preferred = list(broker.preferred_lanes) if broker else []
    findings = {"lane": lane, "broker_preferred_lanes": preferred}

    if lane is None:
        return IntelligenceScore(
            module=NAME, version=VERSION, score=_UNKNOWN_LANE_SCORE,
            flags=["lane_unknown"], findings=findings,
        )

    if lane in preferred:
        return IntelligenceScore(
            module=NAME, version=VERSION, score=_MATCH_SCORE,
            flags=["preferred_lane_match"], findings=findings,
        )

    lane_parts = _parts(lane)
    adjacent = False
    if lane_parts:
        for p in preferred:
            p_parts = _parts(p)
            if p_parts and (p_parts[0] == lane_parts[0] or p_parts[1] == lane_parts[1]):
                adjacent = True
                break

    if adjacent:
        return IntelligenceScore(
            module=NAME, version=VERSION, score=_ADJACENT_SCORE,
            flags=["adjacent_lane"], findings=findings,
        )

    return IntelligenceScore(
        module=NAME, version=VERSION, score=_NEW_LANE_SCORE,
        flags=["new_lane"], findings=findings,
    )
