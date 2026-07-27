"""Capacity-match rule module.

Deterministic check of the load's required equipment type against the
fleet's available equipment types. The fleet list is an explicit, auditable
constant — same pattern as cin_lite/rules/pricing_anomaly.py's bands.
"""

from __future__ import annotations

from .base import IntelligenceScore

NAME = "capacity_match"
VERSION = "1.0.0"

# Equipment types this fleet can service today.
_FLEET_EQUIPMENT = {"Dry Van", "Reefer", "Flatbed"}

_MATCH_SCORE = 100
_MISMATCH_SCORE = 0
_UNSPECIFIED_SCORE = 0


def run(load: dict, *, facility_pickup=None, facility_delivery=None, broker=None) -> IntelligenceScore:
    equipment = load.get("equipment_type")
    findings = {"equipment_type": equipment, "fleet_equipment": sorted(_FLEET_EQUIPMENT)}

    if not equipment:
        return IntelligenceScore(
            module=NAME, version=VERSION, score=_UNSPECIFIED_SCORE,
            flags=["equipment_unspecified"], findings=findings,
        )

    if equipment in _FLEET_EQUIPMENT:
        return IntelligenceScore(
            module=NAME, version=VERSION, score=_MATCH_SCORE,
            flags=["equipment_match"], findings=findings,
        )

    return IntelligenceScore(
        module=NAME, version=VERSION, score=_MISMATCH_SCORE,
        flags=["equipment_mismatch"], findings=findings,
    )
