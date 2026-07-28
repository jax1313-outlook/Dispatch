"""Dispatch router — deterministic load routing based on calculator scores.

Consumes a raw load dict, runs it through the load calculator, and produces a
structured routing decision: accept, reject, or flag for dispatcher review.
Thresholds are explicit constants so routing logic stays auditable.

A load that fails viability (rate below minimum, distance too far, overweight,
or invalid data) is always rejected. Viable loads are routed by score:

    score >= 70  →  accept (high priority)
    score >= 50  →  accept (medium priority)
    score <  50  →  flag_review (dispatcher should evaluate)
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from .load_calculator import LoadResult, calculate_load

logger = logging.getLogger(__name__)

DISPATCH_ACTIONS = ("accept", "reject", "flag_review")
DISPATCH_PRIORITIES = ("low", "medium", "high")

_ACCEPT_HIGH_THRESHOLD = 70
_ACCEPT_THRESHOLD = 50

_REJECTION_REASONS: dict[str, str] = {
    "rate_below_minimum": "rate per mile below minimum threshold",
    "distance_too_far": "distance exceeds maximum practical range",
    "overweight": "cargo weight exceeds legal limit",
    "invalid_miles": "invalid or missing mileage data",
    "invalid_rate": "invalid or missing rate data",
}


@dataclass
class DispatchDecision:
    """Structured output of the dispatch router."""

    action: str
    priority: str
    reason: str
    score: int
    flags: list[str] = field(default_factory=list)
    load_result: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def dispatch_load(load: dict) -> DispatchDecision:
    """Route a load opportunity based on its calculated score and viability."""
    result = calculate_load(load)

    logger.debug("dispatch_load scored %d (viable=%s, flags=%s)",
                 result.score, result.viable, result.flags)

    if not result.viable:
        reasons = [_REJECTION_REASONS[f] for f in result.flags if f in _REJECTION_REASONS]
        reason = "; ".join(reasons) or "load failed viability checks"
        logger.info("dispatch_load rejecting: %s", reason)
        return DispatchDecision(
            action="reject",
            priority="low",
            reason=reason,
            score=result.score,
            flags=result.flags,
            load_result=result.to_json(),
        )

    if result.score >= _ACCEPT_HIGH_THRESHOLD:
        logger.info("dispatch_load accepting (high priority, score=%d)", result.score)
        return DispatchDecision(
            action="accept",
            priority="high",
            reason="strong load: favorable rate, distance, and utilization",
            score=result.score,
            flags=result.flags,
            load_result=result.to_json(),
        )

    if result.score >= _ACCEPT_THRESHOLD:
        logger.info("dispatch_load accepting (medium priority, score=%d)", result.score)
        return DispatchDecision(
            action="accept",
            priority="medium",
            reason="acceptable load meeting minimum dispatch criteria",
            score=result.score,
            flags=result.flags,
            load_result=result.to_json(),
        )

    logger.info("dispatch_load flagging for review (score=%d)", result.score)
    return DispatchDecision(
        action="flag_review",
        priority="low",
        reason="viable but marginal; recommend dispatcher review before commitment",
        score=result.score,
        flags=result.flags,
        load_result=result.to_json(),
    )
