"""Load calculator — deterministic scoring for dispatch opportunities.

Evaluates a load record against carrier dispatch criteria and produces a
structured result: rate-per-mile, weight utilization, distance fit, and an
overall viability score. Thresholds are explicit constants so the logic
stays auditable and deterministic.

A load record is a dict with these fields:
    origin            str   origin city/region
    destination       str   destination city/region
    miles             float distance in miles (must be > 0)
    rate              float total pay in dollars
    weight            float cargo weight in lbs
    equipment_type    str   e.g. "dry_van", "flatbed", "reefer", "box_truck"
    pickup_date       str   ISO date
    delivery_date     str   ISO date (optional)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

_MIN_RATE_PER_MILE = 2.00
_TARGET_RATE_PER_MILE = 3.00
_MAX_PRACTICAL_MILES = 500
_PREFERRED_MAX_MILES = 250
_MAX_WEIGHT_LBS = 44_000
_EQUIPMENT_TYPES = frozenset({
    "dry_van", "flatbed", "reefer", "box_truck", "sprinter", "straight_truck",
})


@dataclass
class LoadResult:
    """Structured output of the load calculator."""

    viable: bool
    score: int
    rate_per_mile: float | None
    weight_utilization: float | None
    flags: list[str] = field(default_factory=list)
    breakdown: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def calculate_load(load: dict) -> LoadResult:
    """Score a load opportunity and return a structured LoadResult."""
    flags: list[str] = []
    breakdown: dict[str, Any] = {}
    score = 0

    miles = load.get("miles")
    rate = load.get("rate")
    weight = load.get("weight")
    equipment = load.get("equipment_type", "")

    if not isinstance(miles, (int, float)) or miles <= 0:
        flags.append("invalid_miles")
        return LoadResult(viable=False, score=0, rate_per_mile=None,
                          weight_utilization=None, flags=flags, breakdown=breakdown)

    if not isinstance(rate, (int, float)) or rate <= 0:
        flags.append("invalid_rate")
        return LoadResult(viable=False, score=0, rate_per_mile=None,
                          weight_utilization=None, flags=flags, breakdown=breakdown)

    rpm = round(rate / miles, 2)
    breakdown["rate_per_mile"] = rpm

    if rpm >= _TARGET_RATE_PER_MILE:
        score += 40
        flags.append("rate_excellent")
    elif rpm >= _MIN_RATE_PER_MILE:
        score += 25
        flags.append("rate_acceptable")
    else:
        flags.append("rate_below_minimum")

    if miles <= _PREFERRED_MAX_MILES:
        score += 30
        flags.append("distance_preferred")
    elif miles <= _MAX_PRACTICAL_MILES:
        score += 15
        flags.append("distance_acceptable")
    else:
        flags.append("distance_too_far")

    breakdown["miles"] = miles
    breakdown["max_practical"] = _MAX_PRACTICAL_MILES

    weight_util: float | None = None
    if isinstance(weight, (int, float)) and weight > 0:
        weight_util = round(weight / _MAX_WEIGHT_LBS, 2)
        breakdown["weight_utilization"] = weight_util
        if weight > _MAX_WEIGHT_LBS:
            flags.append("overweight")
        elif weight_util >= 0.5:
            score += 20
            flags.append("good_weight_utilization")
        else:
            score += 10
            flags.append("light_load")
    else:
        flags.append("weight_missing")
        breakdown["weight_utilization"] = None

    if equipment:
        if equipment in _EQUIPMENT_TYPES:
            score += 10
            flags.append("equipment_supported")
        else:
            flags.append("equipment_unknown")
        breakdown["equipment_type"] = equipment

    viable = "rate_below_minimum" not in flags and "distance_too_far" not in flags and "overweight" not in flags

    return LoadResult(
        viable=viable,
        score=score,
        rate_per_mile=rpm,
        weight_utilization=weight_util,
        flags=flags,
        breakdown=breakdown,
    )
