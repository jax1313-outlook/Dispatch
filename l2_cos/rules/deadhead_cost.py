"""Deadhead-cost rule module.

Deterministic ratio of deadhead (unpaid, empty) miles to loaded miles.
Higher ratios lower the score since they erode the load's effective margin.
Thresholds are explicit constants so the logic stays auditable.
"""

from __future__ import annotations

from .base import IntelligenceScore

NAME = "deadhead_cost"
VERSION = "1.0.0"

_LOW_RATIO = 0.10   # <=10% deadhead: negligible
_HIGH_RATIO = 0.30  # >=30% deadhead: material margin erosion

_MISSING_DATA_SCORE = 50
_LOW_SCORE = 100
_MODERATE_SCORE = 65
_HIGH_SCORE = 20


def run(load: dict, *, facility_pickup=None, facility_delivery=None, broker=None) -> IntelligenceScore:
    miles = load.get("miles")
    deadhead = load.get("deadhead_miles")
    findings: dict = {"miles": miles, "deadhead_miles": deadhead}

    if not isinstance(miles, (int, float)) or miles <= 0 or not isinstance(deadhead, (int, float)) or deadhead < 0:
        return IntelligenceScore(
            module=NAME, version=VERSION, score=_MISSING_DATA_SCORE,
            flags=["deadhead_data_missing"], findings=findings,
        )

    ratio = deadhead / miles
    findings["deadhead_ratio"] = round(ratio, 3)

    if ratio <= _LOW_RATIO:
        return IntelligenceScore(
            module=NAME, version=VERSION, score=_LOW_SCORE,
            flags=["low_deadhead"], findings=findings,
        )
    if ratio >= _HIGH_RATIO:
        return IntelligenceScore(
            module=NAME, version=VERSION, score=_HIGH_SCORE,
            flags=["high_deadhead"], findings=findings,
        )
    return IntelligenceScore(
        module=NAME, version=VERSION, score=_MODERATE_SCORE,
        flags=["moderate_deadhead"], findings=findings,
    )
