"""Facility-risk rule module.

Deterministic read of the Location Intelligence Library (System Rule 14) for
the load's pickup and delivery facilities: historical problems and posted
security requirements lower the score. Nothing here is re-derived from the
load itself — it is purely a lookup against the captured-once facility
record.
"""

from __future__ import annotations

from .base import IntelligenceScore

NAME = "facility_risk"
VERSION = "1.0.0"

_BASE_SCORE = 100
_PER_PROBLEM_PENALTY = 15
_MAX_PROBLEM_PENALTIES = 4
_SECURITY_PENALTY = 10


def _facility_penalty(facility) -> tuple[int, list[str]]:
    if facility is None:
        return 0, []
    penalty = min(len(facility.historical_problems), _MAX_PROBLEM_PENALTIES) * _PER_PROBLEM_PENALTY
    flags: list[str] = []
    if facility.historical_problems:
        flags.append("history_flagged")
    if facility.security_requirements:
        penalty += _SECURITY_PENALTY
        flags.append("security_requirements")
    return penalty, flags


def run(load: dict, *, facility_pickup=None, facility_delivery=None, broker=None) -> IntelligenceScore:
    pickup_penalty, pickup_flags = _facility_penalty(facility_pickup)
    delivery_penalty, delivery_flags = _facility_penalty(facility_delivery)

    flags = [f"pickup_{f}" for f in pickup_flags] + [f"delivery_{f}" for f in delivery_flags]
    if facility_pickup is None or facility_delivery is None:
        flags.append("facility_profile_missing")

    score = max(_BASE_SCORE - pickup_penalty - delivery_penalty, 0)
    findings = {
        "pickup_historical_problems": facility_pickup.historical_problems if facility_pickup else [],
        "delivery_historical_problems": facility_delivery.historical_problems if facility_delivery else [],
    }
    return IntelligenceScore(module=NAME, version=VERSION, score=score, flags=flags, findings=findings)
