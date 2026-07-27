"""Processing Layer — L2-COS Dispatch.

Runs every registered rule module (l2_cos/rules/) over a load record plus
its looked-up facility/broker intelligence, aggregates their IntelligenceScore
output, and rolls the per-module scores up into a single overall score — the
value checked against the publisher trigger (System Rule 4).
"""

from __future__ import annotations

from typing import Any

from .rules import ALL_RULES


def process(
    load: dict,
    *,
    facility_pickup=None,
    facility_delivery=None,
    broker=None,
) -> dict[str, Any]:
    """Apply all rule modules; return {module_name: IntelligenceScore-json}."""
    intelligence: dict[str, Any] = {}
    for rule in ALL_RULES:
        result = rule.run(
            load,
            facility_pickup=facility_pickup,
            facility_delivery=facility_delivery,
            broker=broker,
        )
        intelligence[result.module] = result.model_dump()
    return intelligence


def all_flags(intelligence: dict[str, Any]) -> list[str]:
    """Flatten every flag raised across all modules (for quick triage)."""
    flags: list[str] = []
    for result in intelligence.values():
        flags.extend(result.get("flags", []))
    return flags


def overall_score(intelligence: dict[str, Any]) -> int:
    """Mean of every module's score, rounded — compared against
    l2_cos.models.intelligence.PUBLISH_THRESHOLD by the publisher workflow."""
    scores = [r["score"] for r in intelligence.values() if r.get("score") is not None]
    return round(sum(scores) / len(scores)) if scores else 0
