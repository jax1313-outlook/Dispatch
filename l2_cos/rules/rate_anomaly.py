"""Rate-anomaly rule module.

Deterministic comparison of a load's rate-per-mile against the broker's own
historical rate for the same lane (Broker Intelligence Library,
`historical_rates` — System Rule 14). Mirrors the band-check shape of
cin_lite/rules/pricing_anomaly.py, but the band is the broker's captured
history rather than a fixed constant.
"""

from __future__ import annotations

from .base import IntelligenceScore

NAME = "rate_anomaly"
VERSION = "1.0.0"

# How far below/above the broker's historical rate still counts as "in band".
_TOLERANCE = 0.15  # +/- 15%

_MISSING_RATE_SCORE = 50
_NO_HISTORY_SCORE = 70
_BELOW_BAND_SCORE = 20
_ABOVE_BAND_SCORE = 85
_IN_BAND_SCORE = 100


def run(load: dict, *, facility_pickup=None, facility_delivery=None, broker=None) -> IntelligenceScore:
    rate = load.get("rate_per_mile")
    findings: dict = {"rate_per_mile": rate}

    if rate is None or not isinstance(rate, (int, float)):
        return IntelligenceScore(
            module=NAME, version=VERSION, score=_MISSING_RATE_SCORE,
            flags=["rate_missing"], findings=findings,
        )

    origin, destination = load.get("origin_state"), load.get("destination_state")
    lane = f"{origin}-{destination}" if origin and destination else None
    historical = broker.historical_rates.get(lane) if (broker and lane) else None
    findings["lane"] = lane
    findings["historical_rate"] = historical

    if historical is None:
        return IntelligenceScore(
            module=NAME, version=VERSION, score=_NO_HISTORY_SCORE,
            flags=["no_rate_history"], findings=findings,
        )

    low, high = historical * (1 - _TOLERANCE), historical * (1 + _TOLERANCE)
    findings["band"] = [round(low, 2), round(high, 2)]

    if rate < low:
        return IntelligenceScore(
            module=NAME, version=VERSION, score=_BELOW_BAND_SCORE,
            flags=["rate_below_band"], findings=findings,
        )
    if rate > high:
        return IntelligenceScore(
            module=NAME, version=VERSION, score=_ABOVE_BAND_SCORE,
            flags=["rate_above_band"], findings=findings,
        )
    return IntelligenceScore(
        module=NAME, version=VERSION, score=_IN_BAND_SCORE,
        flags=["rate_in_band"], findings=findings,
    )
